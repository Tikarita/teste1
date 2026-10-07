from datetime import datetime
from uuid import uuid4

import psycopg
import pytest

from app.services import quality_stats, review_service
from tests.conftest import TIMEZONE, TODAY, local_noon


pytestmark = pytest.mark.usefixtures("rpc_on_database")


def last_7_days(**filters) -> quality_stats.StatsFilters:
    return quality_stats.resolve_filters("7", None, None, filters.get("professional_id"), None, today=TODAY)


def record_review(db, radiograph, clinic, reviewer, verdict, reasons=(), repeated=False, notes=None):
    return db.execute(
        "select * from record_review(%s, %s, %s, %s, %s, %s::text[], %s)",
        (radiograph, clinic, reviewer, verdict, repeated, list(reasons), notes)
    ).fetchone()


@pytest.fixture
def exam(seed, db):
    """Cria uma radiografia (com análise da IA, se informada) e, opcionalmente, a revisa."""

    def _exam(clinic, reviewer=None, ai=None, verdict=None, reasons=(), repeated=False, professional=None):
        if ai is None:
            radiograph = seed.radiograph(clinic, professional, created_at=local_noon(TODAY))
        else:
            analysis = seed.analysis(clinic, 80 if ai == "adequate" else 20,
                                     "approved" if ai == "adequate" else "rejected",
                                     professional_id=professional)
            radiograph = str(db.execute(
                "select radiograph_id from analyses where id = %s", (analysis,)
            ).fetchone()["radiograph_id"])
            db.execute("update radiographs set created_at = %s where id = %s", (local_noon(TODAY), radiograph))

        if verdict:
            record_review(db, radiograph, clinic, reviewer, verdict, reasons, repeated)
        return radiograph

    return _exam


# --- gravação -----------------------------------------------------------------

def test_record_review_links_the_current_analysis_and_reviewer_name(seed, db, exam):
    clinic = seed.clinic()
    reviewer = seed.profile(clinic, "Dra. Revisora")
    radiograph = exam(clinic, ai="adequate")

    review = record_review(db, radiograph, clinic, reviewer, "inadequate",
                           ["positioning", "motion"][:1], repeated=True, notes="Paciente se moveu.")

    analysis = db.execute("select id from analyses where radiograph_id = %s", (radiograph,)).fetchone()
    assert review["analysis_id"] == analysis["id"]
    assert review["reviewed_by_name"] == "Dra. Revisora"
    assert (review["verdict"], review["repeated"], review["reasons"]) == ("inadequate", True, ["positioning"])
    assert review["notes"] == "Paciente se moveu."
    assert review["is_current"] is True


def test_reviewing_again_keeps_history_and_only_latest_is_current(seed, db, exam):
    clinic = seed.clinic()
    reviewer = seed.profile(clinic)
    radiograph = exam(clinic)

    first = record_review(db, radiograph, clinic, reviewer, "inadequate", ["contrast"])
    second = record_review(db, radiograph, clinic, reviewer, "adequate")

    rows = {str(r["id"]): r for r in db.execute("select id, is_current from radiograph_reviews").fetchall()}
    assert len(rows) == 2
    assert rows[str(first["id"])]["is_current"] is False
    assert rows[str(second["id"])]["is_current"] is True


def test_record_review_refuses_other_clinics(seed, db, exam):
    clinic_a = seed.clinic("A")
    clinic_b = seed.clinic("B")
    reviewer_a = seed.profile(clinic_a)
    reviewer_b = seed.profile(clinic_b)
    radiograph_b = exam(clinic_b)

    with pytest.raises(psycopg.errors.NoDataFound):
        record_review(db, radiograph_b, clinic_a, reviewer_a, "adequate")

    with pytest.raises(psycopg.errors.CheckViolation):
        record_review(db, radiograph_b, clinic_b, reviewer_a, "adequate")

    assert record_review(db, radiograph_b, clinic_b, reviewer_b, "adequate")["verdict"] == "adequate"


@pytest.mark.parametrize("verdict, reasons, repeated", [
    ("inadequate", [], False),
    ("adequate", ["contrast"], False),
    ("adequate", [], True),
    ("inadequate", ["motivo-inventado"], False),
    ("talvez", [], False),
])
def test_database_rejects_inconsistent_reviews(seed, db, exam, verdict, reasons, repeated):
    clinic = seed.clinic()
    reviewer = seed.profile(clinic)
    radiograph = exam(clinic)

    with pytest.raises(psycopg.errors.CheckViolation):
        record_review(db, radiograph, clinic, reviewer, verdict, reasons, repeated)


# --- indicadores ----------------------------------------------------------------

def test_review_stats(seed, exam):
    clinic = seed.clinic()
    reviewer = seed.profile(clinic)
    # IA adequada: 3 confirmadas, 1 que a IA deixou passar (repetida).
    for _ in range(3):
        exam(clinic, reviewer, ai="adequate", verdict="adequate")
    exam(clinic, reviewer, ai="adequate", verdict="inadequate", reasons=["positioning", "sharpness"], repeated=True)
    # IA inadequada: 1 confirmada, 1 alarme falso.
    exam(clinic, reviewer, ai="inadequate", verdict="inadequate", reasons=["positioning"])
    exam(clinic, reviewer, ai="inadequate", verdict="adequate")
    # Sem análise da IA, mas revisada: entra na rejeição, não na concordância.
    exam(clinic, reviewer, verdict="inadequate", reasons=["other"], repeated=True)
    # Enviadas e ainda não revisadas.
    exam(clinic, ai="adequate")
    exam(clinic)
    exam(clinic)

    stats = review_service.get_review_stats(clinic, last_7_days())

    assert (stats.uploaded, stats.reviewed, stats.coverage_rate) == (10, 7, 70.0)
    assert (stats.human_adequate, stats.human_inadequate, stats.repeated) == (4, 3, 2)
    assert stats.rejection_rate == 42.9
    assert stats.repeat_rate == 28.6
    assert (stats.compared_with_ai, stats.agreed_with_ai, stats.ai_agreement_rate) == (6, 4, 66.7)
    assert (stats.ai_missed, stats.ai_false_alarm) == (1, 1)
    assert [(r.reason, r.label, r.count, r.percentage) for r in stats.reasons] == [
        ("positioning", "Posicionamento", 2, 50.0),
        ("other", "Outro motivo", 1, 25.0),
        ("sharpness", "Nitidez", 1, 25.0),
    ]
    assert stats.insufficient_data is False


def test_review_stats_use_only_the_latest_review(seed, db, exam):
    clinic = seed.clinic()
    reviewer = seed.profile(clinic)
    for _ in range(5):
        radiograph = exam(clinic, reviewer, verdict="inadequate", reasons=["contrast"], repeated=True)
        record_review(db, radiograph, clinic, reviewer, "adequate")

    stats = review_service.get_review_stats(clinic, last_7_days())

    assert (stats.reviewed, stats.human_adequate, stats.human_inadequate, stats.repeated) == (5, 5, 0, 0)
    assert stats.rejection_rate == 0.0
    assert stats.reasons == []


def test_review_stats_without_enough_reviews_use_null(seed, exam):
    clinic = seed.clinic()
    reviewer = seed.profile(clinic)
    exam(clinic, reviewer, ai="adequate", verdict="inadequate", reasons=["contrast"])
    for _ in range(9):
        exam(clinic)

    stats = review_service.get_review_stats(clinic, last_7_days())

    assert (stats.uploaded, stats.reviewed, stats.human_inadequate) == (10, 1, 1)
    assert stats.coverage_rate == 10.0
    assert stats.rejection_rate is None
    assert stats.repeat_rate is None
    assert stats.ai_agreement_rate is None
    assert stats.reasons is None
    assert stats.insufficient_data is True


def test_review_stats_with_nothing_uploaded(seed):
    stats = review_service.get_review_stats(seed.clinic(), last_7_days())

    assert (stats.uploaded, stats.reviewed) == (0, 0)
    assert stats.coverage_rate is None
    assert stats.insufficient_data is True


def test_review_stats_are_isolated_by_clinic_and_professional(seed, exam):
    clinic_a = seed.clinic("A")
    clinic_b = seed.clinic("B")
    reviewer_a = seed.profile(clinic_a)
    ana = seed.profile(clinic_a, "Ana")
    reviewer_b = seed.profile(clinic_b)
    for _ in range(5):
        exam(clinic_a, reviewer_a, verdict="adequate", professional=ana)
    for _ in range(5):
        exam(clinic_a, reviewer_a, verdict="inadequate", reasons=["noise"])
    for _ in range(6):
        exam(clinic_b, reviewer_b, verdict="inadequate", reasons=["framing"], repeated=True)

    everyone = review_service.get_review_stats(clinic_a, last_7_days())
    only_ana = review_service.get_review_stats(clinic_a, last_7_days(professional_id=ana))

    assert (everyone.reviewed, everyone.rejection_rate, everyone.repeated) == (10, 50.0, 0)
    assert [r.reason for r in everyone.reasons] == ["noise"]
    assert (only_ana.reviewed, only_ana.rejection_rate) == (5, 0.0)


def test_rls_on_reviews(seed, db, exam):
    clinic_a = seed.clinic("A")
    clinic_b = seed.clinic("B")
    user_a = seed.profile(clinic_a)
    user_b = seed.profile(clinic_b)
    exam(clinic_a, user_a, verdict="adequate")
    exam(clinic_b, user_b, verdict="adequate")

    db.execute("select set_config('request.jwt.claim.sub', %s, false)", (user_a,))
    db.execute("set role authenticated")
    try:
        visible = db.execute("select clinic_id from radiograph_reviews").fetchall()
        assert [str(r["clinic_id"]) for r in visible] == [clinic_a]
        assert db.execute("update radiograph_reviews set verdict = 'inadequate', reasons = '{other}'").rowcount == 0
        assert db.execute("delete from radiograph_reviews").rowcount == 0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("select * from review_summary(%s, now() - interval '1 day', now())", (clinic_b,))
    finally:
        db.execute("reset role")


# --- API ------------------------------------------------------------------------

@pytest.fixture
def reviews_on_database(db, monkeypatch):
    """Faz o serviço de revisão gravar e ler no Postgres de teste."""

    def record(params: dict) -> dict:
        return db.execute(
            "select * from record_review(%(p_radiograph_id)s, %(p_clinic_id)s, %(p_reviewed_by)s, "
            "%(p_verdict)s, %(p_repeated)s, %(p_reasons)s::text[], %(p_notes)s)",
            params
        ).fetchone()

    def current(radiograph_id: str, clinic_id: str):
        return db.execute(
            "select * from radiograph_reviews where radiograph_id = %s and clinic_id = %s and is_current",
            (radiograph_id, clinic_id)
        ).fetchone()

    def clinic_radiograph(radiograph_id: str, clinic_id: str) -> dict:
        from fastapi import HTTPException

        row = db.execute(
            "select * from radiographs where id::text = %s and clinic_id = %s", (radiograph_id, clinic_id)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Radiografia não encontrada")
        return row

    from app.api import analysis

    monkeypatch.setattr(review_service, "_record_review", record)
    monkeypatch.setattr(review_service, "_current_review_row", current)
    monkeypatch.setattr(analysis, "_get_clinic_radiograph", clinic_radiograph)


def test_review_endpoint_records_the_logged_user(client, login, seed, exam, reviews_on_database):
    clinic = seed.clinic()
    reviewer = seed.profile(clinic, "Dr. Revisor")
    radiograph = exam(clinic, ai="adequate")
    login(clinic, reviewer)

    response = client.post(f"/api/v1/analysis/{radiograph}/review", json={
        "verdict": "inadequate", "reasons": ["positioning", "positioning", "coverage"],
        "repeated": True, "notes": "  Mento fora do apoio.  "
    })

    assert response.status_code == 201
    body = response.json()
    assert body["reviewed_by"] == reviewer
    assert body["reviewed_by_name"] == "Dr. Revisor"
    assert body["reasons"] == ["positioning", "coverage"]
    assert body["notes"] == "Mento fora do apoio."
    assert body["repeated"] is True


@pytest.mark.parametrize("payload", [
    {"verdict": "inadequate"},
    {"verdict": "inadequate", "reasons": []},
    {"verdict": "adequate", "reasons": ["contrast"]},
    {"verdict": "adequate", "repeated": True},
    {"verdict": "inadequate", "reasons": ["motivo-inventado"]},
    {"verdict": "talvez"},
    {},
])
def test_review_endpoint_rejects_inconsistent_payloads(client, login, seed, exam, reviews_on_database, db, payload):
    clinic = seed.clinic()
    reviewer = seed.profile(clinic)
    radiograph = exam(clinic)
    login(clinic, reviewer)

    response = client.post(f"/api/v1/analysis/{radiograph}/review", json=payload)

    assert response.status_code == 422
    assert db.execute("select count(*) as n from radiograph_reviews").fetchone()["n"] == 0


def test_review_endpoint_hides_other_clinics(client, login, seed, exam, reviews_on_database, db):
    clinic_a = seed.clinic("A")
    clinic_b = seed.clinic("B")
    user_a = seed.profile(clinic_a)
    radiograph_b = exam(clinic_b)
    login(clinic_a, user_a)

    response = client.post(f"/api/v1/analysis/{radiograph_b}/review", json={"verdict": "adequate"})

    assert response.status_code == 404
    assert db.execute("select count(*) as n from radiograph_reviews").fetchone()["n"] == 0


def test_review_routes_require_authentication(client):
    assert client.post(f"/api/v1/analysis/{uuid4()}/review", json={"verdict": "adequate"}).status_code == 401
    assert client.get("/api/v1/stats/reviews").status_code == 401


def test_review_stats_endpoint(client, login, seed, db, reviews_on_database):
    clinic = seed.clinic()
    reviewer = seed.profile(clinic)
    today = datetime.now(TIMEZONE).date()
    for index in range(5):
        radiograph = seed.radiograph(clinic, created_at=local_noon(today))
        record_review(db, radiograph, clinic, reviewer,
                      "inadequate" if index < 2 else "adequate",
                      ["contrast"] if index < 2 else [])
    login(clinic, reviewer)

    body = client.get("/api/v1/stats/reviews", params={"period": "7"}).json()

    assert (body["uploaded"], body["reviewed"], body["rejection_rate"]) == (5, 5, 40.0)
    assert body["reasons"] == [{"reason": "contrast", "label": "Contraste", "count": 2, "percentage": 100.0}]
    assert body["min_sample_size"] == 5
    assert body["insufficient_data"] is False
