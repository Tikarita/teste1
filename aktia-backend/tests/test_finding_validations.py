from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

from app.services import finding_validation_service, quality_stats
from tests.conftest import TODAY


pytestmark = pytest.mark.usefixtures("rpc_on_database")


def yolo(*class_codes: str) -> dict:
    return {"yolo": {"available": True, "findings": [{"class_code": code, "confidence": 0.8} for code in class_codes]}}


def record(db, radiograph, clinic, validator, decisions: dict[int, str]):
    return db.execute(
        "select * from record_finding_validations(%s, %s, %s, %s)",
        (radiograph, clinic, validator, Jsonb([{"finding_index": i, "decision": d} for i, d in decisions.items()]))
    ).fetchall()


@pytest.fixture
def exam(seed, db):
    """Radiografia analisada com os achados informados; devolve o id da radiografia."""

    def _exam(clinic, *class_codes):
        analysis = seed.analysis(clinic, 80, result=yolo(*class_codes))
        return str(db.execute("select radiograph_id from analyses where id = %s", (analysis,)).fetchone()["radiograph_id"])

    return _exam


# --- gravação -----------------------------------------------------------------

def test_decisions_are_recorded_with_class_and_validator(seed, db, exam):
    clinic = seed.clinic()
    dentist = seed.profile(clinic, "Dra. Ana")
    radiograph = exam(clinic, "OBT", "CAR", "END")

    rows = record(db, radiograph, clinic, dentist, {0: "confirmed", 1: "discarded"})

    assert [(r["finding_index"], r["class_code"], r["decision"], r["validated_by_name"]) for r in rows] == [
        (0, "OBT", "confirmed", "Dra. Ana"),
        (1, "CAR", "discarded", "Dra. Ana"),
    ]


def test_changing_and_undoing_a_decision_keeps_history(seed, db, exam):
    clinic = seed.clinic()
    dentist = seed.profile(clinic)
    radiograph = exam(clinic, "OBT", "CAR")
    record(db, radiograph, clinic, dentist, {0: "confirmed", 1: "confirmed"})

    record(db, radiograph, clinic, dentist, {0: "discarded"})
    current = record(db, radiograph, clinic, dentist, {1: "pending"})

    assert [(r["finding_index"], r["decision"]) for r in current] == [(0, "discarded")]
    history = db.execute(
        "select finding_index, decision, is_current from finding_validations order by created_at, finding_index"
    ).fetchall()
    assert len(history) == 3
    assert sum(1 for row in history if row["is_current"]) == 1


@pytest.mark.parametrize("decisions", [{3: "confirmed"}, {-1: "confirmed"}, {0: "talvez"}])
def test_invalid_decisions_are_rejected_and_nothing_is_saved(seed, db, exam, decisions):
    clinic = seed.clinic()
    dentist = seed.profile(clinic)
    radiograph = exam(clinic, "OBT", "CAR")

    with pytest.raises(psycopg.errors.CheckViolation):
        record(db, radiograph, clinic, dentist, {0: "confirmed", **decisions})

    assert db.execute("select count(*) as n from finding_validations").fetchone()["n"] == 0


def test_other_clinics_cannot_validate(seed, db, exam):
    clinic_a = seed.clinic("A")
    clinic_b = seed.clinic("B")
    dentist_a = seed.profile(clinic_a)
    radiograph_b = exam(clinic_b, "OBT")

    with pytest.raises(psycopg.errors.NoDataFound):
        record(db, radiograph_b, clinic_a, dentist_a, {0: "confirmed"})

    with pytest.raises(psycopg.errors.CheckViolation):
        record(db, radiograph_b, clinic_b, dentist_a, {0: "confirmed"})


def test_reanalysis_starts_the_validation_over(seed, db, exam):
    clinic = seed.clinic()
    dentist = seed.profile(clinic)
    radiograph = exam(clinic, "OBT", "CAR")
    record(db, radiograph, clinic, dentist, {0: "confirmed", 1: "discarded"})

    db.execute(
        "select record_analysis(%s, %s, 'approved', 80::numeric, true, 'modelo', 'ok', %s, '[]'::jsonb)",
        (radiograph, clinic, Jsonb(yolo("END")))
    )

    current = db.execute("select * from current_finding_validations(%s, %s)", (radiograph, clinic)).fetchall()
    assert current == []
    assert db.execute("select count(*) as n from finding_validations").fetchone()["n"] == 2

    assert [r["class_code"] for r in record(db, radiograph, clinic, dentist, {0: "confirmed"})] == ["END"]


# --- acerto do detector ---------------------------------------------------------

def last_7_days() -> quality_stats.StatsFilters:
    return quality_stats.resolve_filters("7", None, None, None, None, today=TODAY)


def test_detector_stats_by_class(seed, db, exam):
    clinic = seed.clinic()
    dentist = seed.profile(clinic)
    first = exam(clinic, "OBT", "OBT", "OBT", "CAR", "CAR")
    second = exam(clinic, "OBT", "OBT", "CAR", "END")
    record(db, first, clinic, dentist, {0: "confirmed", 1: "confirmed", 2: "confirmed", 3: "discarded", 4: "discarded"})
    record(db, second, clinic, dentist, {0: "confirmed", 1: "discarded", 2: "confirmed"})

    stats = finding_validation_service.get_detector_stats(clinic, last_7_days())

    assert (stats.validated, stats.confirmation_rate, stats.insufficient_data) == (8, 62.5, False)
    assert [
        (c.class_code, c.label, c.low_reliability, c.confirmed, c.discarded, c.confirmation_rate)
        for c in stats.classes
    ] == [
        ("OBT", "Obturação", False, 4, 1, 80.0),
        ("CAR", "Cárie", True, 1, 2, None),
    ]


def test_detector_stats_without_enough_validations(seed, db, exam):
    clinic = seed.clinic()
    dentist = seed.profile(clinic)
    radiograph = exam(clinic, "OBT", "CAR")
    record(db, radiograph, clinic, dentist, {0: "confirmed"})

    stats = finding_validation_service.get_detector_stats(clinic, last_7_days())

    assert (stats.validated, stats.confirmation_rate, stats.insufficient_data) == (1, None, True)
    assert stats.classes[0].confirmation_rate is None


def test_detector_stats_are_isolated_by_clinic(seed, db, exam):
    clinic_a = seed.clinic("A")
    clinic_b = seed.clinic("B")
    dentist_b = seed.profile(clinic_b)
    radiograph_b = exam(clinic_b, "OBT", "OBT", "OBT", "OBT", "OBT")
    record(db, radiograph_b, clinic_b, dentist_b, {i: "confirmed" for i in range(5)})

    stats = finding_validation_service.get_detector_stats(clinic_a, last_7_days())

    assert (stats.validated, stats.classes) == (0, [])


def test_rls_on_finding_validations(seed, db, exam):
    clinic_a = seed.clinic("A")
    clinic_b = seed.clinic("B")
    user_a = seed.profile(clinic_a)
    user_b = seed.profile(clinic_b)
    record(db, exam(clinic_a, "OBT"), clinic_a, user_a, {0: "confirmed"})
    record(db, exam(clinic_b, "OBT"), clinic_b, user_b, {0: "confirmed"})

    db.execute("select set_config('request.jwt.claim.sub', %s, false)", (user_a,))
    db.execute("set role authenticated")
    try:
        visible = db.execute("select clinic_id from finding_validations").fetchall()
        assert [str(row["clinic_id"]) for row in visible] == [clinic_a]
        assert db.execute("update finding_validations set decision = 'discarded'").rowcount == 0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("select * from current_finding_validations(%s, %s)", (uuid4(), clinic_b))
    finally:
        db.execute("reset role")


# --- API ------------------------------------------------------------------------

@pytest.fixture
def validations_on_database(db, monkeypatch):
    from fastapi import HTTPException

    from app.api import analysis

    def current_rows(radiograph_id: str, clinic_id: str) -> list[dict]:
        return db.execute(
            "select * from current_finding_validations(%s, %s)", (radiograph_id, clinic_id)
        ).fetchall()

    def record_rows(params: dict) -> list[dict]:
        return db.execute(
            "select * from record_finding_validations(%(p_radiograph_id)s, %(p_clinic_id)s, %(p_validated_by)s, %(d)s)",
            {**params, "d": Jsonb(params["p_decisions"])}
        ).fetchall()

    def clinic_radiograph(radiograph_id: str, clinic_id: str) -> dict:
        row = db.execute(
            "select * from radiographs where id::text = %s and clinic_id = %s", (radiograph_id, clinic_id)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Radiografia não encontrada")
        return row

    monkeypatch.setattr(finding_validation_service, "_current_rows", current_rows)
    monkeypatch.setattr(finding_validation_service, "_record", record_rows)
    monkeypatch.setattr(analysis, "_get_clinic_radiograph", clinic_radiograph)


def url(radiograph: str) -> str:
    return f"/api/v1/analysis/{radiograph}/findings/validate"


def test_validate_endpoint_records_the_logged_user(client, login, seed, exam, validations_on_database):
    clinic = seed.clinic()
    dentist = seed.profile(clinic, "Dr. Bruno")
    radiograph = exam(clinic, "OBT", "CAR", "END")
    login(clinic, dentist)

    response = client.post(url(radiograph), json={"decisions": [
        {"finding_index": 0, "decision": "confirmed"},
        {"finding_index": 2, "decision": "discarded"},
    ]})

    assert response.status_code == 200
    assert [(v["finding_index"], v["class_code"], v["decision"], v["validated_by"], v["validated_by_name"])
            for v in response.json()] == [
        (0, "OBT", "confirmed", dentist, "Dr. Bruno"),
        (2, "END", "discarded", dentist, "Dr. Bruno"),
    ]


def test_validate_endpoint_rejects_findings_that_do_not_exist(client, login, seed, exam, validations_on_database, db):
    clinic = seed.clinic()
    dentist = seed.profile(clinic)
    radiograph = exam(clinic, "OBT")
    login(clinic, dentist)

    out_of_range = client.post(url(radiograph), json={"decisions": [{"finding_index": 7, "decision": "confirmed"}]})
    malformed = client.post(url(radiograph), json={"decisions": [{"finding_index": 0, "decision": "talvez"}]})
    empty = client.post(url(radiograph), json={"decisions": []})

    assert out_of_range.status_code == 400
    assert malformed.status_code == 422 and empty.status_code == 422
    assert db.execute("select count(*) as n from finding_validations").fetchone()["n"] == 0


def test_validate_endpoint_hides_other_clinics_and_requires_login(client, login, seed, exam, validations_on_database, db):
    clinic_a = seed.clinic("A")
    clinic_b = seed.clinic("B")
    user_a = seed.profile(clinic_a)
    radiograph_b = exam(clinic_b, "OBT")
    body = {"decisions": [{"finding_index": 0, "decision": "confirmed"}]}

    assert client.post(url(radiograph_b), json=body).status_code == 401

    login(clinic_a, user_a)
    assert client.post(url(radiograph_b), json=body).status_code == 404
    assert db.execute("select count(*) as n from finding_validations").fetchone()["n"] == 0
    assert client.get("/api/v1/stats/detector").status_code == 200
