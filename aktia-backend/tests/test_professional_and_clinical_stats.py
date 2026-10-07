import pytest

from app.services import quality_stats
from tests.conftest import TODAY


pytestmark = pytest.mark.usefixtures("rpc_on_database")


def last_7_days(**filters) -> quality_stats.StatsFilters:
    return quality_stats.resolve_filters(
        "7", None, None, filters.get("professional_id"), filters.get("status"), today=TODAY
    )


def yolo(*class_codes: str, available: bool = True) -> dict:
    return {
        "yolo": {
            "available": available,
            "findings": [{"class_code": code, "confidence": 0.8} for code in class_codes]
        }
    }


# --- por profissional -----------------------------------------------------------

def test_stats_by_professional(seed):
    clinic = seed.clinic()
    ana = seed.profile(clinic, "Ana")
    bruno = seed.profile(clinic, "Bruno")
    carla = seed.profile(clinic, "Carla")
    for score, status in [(90, "approved"), (80, "approved"), (70, "approved"),
                          (60, "rejected"), (50, "rejected")]:
        seed.analysis(clinic, score, status, professional_id=ana)
    for _ in range(5):
        seed.analysis(clinic, 95, professional_id=bruno)
    seed.analysis(clinic, 10, "rejected", professional_id=carla)
    seed.analysis(clinic, 30, "rejected", professional_id=None)

    rows = quality_stats.get_by_professional(clinic, last_7_days()).professionals

    assert [(r.full_name, r.total, r.avg_score, r.approved_rate, r.insufficient_data) for r in rows] == [
        ("Bruno", 5, 95.0, 100.0, False),
        ("Ana", 5, 70.0, 60.0, False),
        ("Carla", 1, None, None, True),
        (None, 1, None, None, True),
    ]
    assert rows[1].status_counts.rejected == 2
    assert rows[3].professional_id is None


def test_professional_without_analyses_is_listed_with_nulls(seed):
    clinic = seed.clinic()
    seed.profile(clinic, "Sem exames")

    rows = quality_stats.get_by_professional(clinic, last_7_days()).professionals

    assert [(r.full_name, r.total, r.avg_score, r.insufficient_data) for r in rows] == [
        ("Sem exames", 0, None, True)
    ]


def test_stats_by_professional_never_include_another_clinic(seed):
    clinic_a = seed.clinic("A")
    clinic_b = seed.clinic("B")
    seed.profile(clinic_a, "Da clínica A")
    outsider = seed.profile(clinic_b, "Da clínica B")
    for _ in range(5):
        seed.analysis(clinic_b, 20, "rejected", professional_id=outsider)

    rows = quality_stats.get_by_professional(clinic_a, last_7_days()).professionals

    assert [(r.full_name, r.total) for r in rows] == [("Da clínica A", 0)]


# --- achados clínicos -------------------------------------------------------------

def test_clinical_findings_counts(seed):
    clinic = seed.clinic()
    seed.analysis(clinic, 80, result=yolo("OBT", "OBT", "CAR"))
    seed.analysis(clinic, 80, result=yolo("OBT"))
    seed.analysis(clinic, 80, result=yolo("END", "CAR"))
    seed.analysis(clinic, 80, result=yolo())
    seed.analysis(clinic, 80, result=yolo())
    # Não avaliadas pelo detector: não contam nem no denominador.
    seed.analysis(clinic, 80, result=yolo("IMP", available=False))
    seed.analysis(clinic, 80, result={"yolo": {"findings": [{"class_code": "IMP"}]}})
    seed.analysis(clinic, 80)

    findings = quality_stats.get_clinical_findings(clinic, last_7_days())

    assert findings.analyses_evaluated == 5
    assert findings.insufficient_data is False
    assert [
        (i.class_code, i.label, i.low_reliability, i.count, i.analyses_with_finding, i.percentage_of_analyses)
        for i in findings.items
    ] == [
        ("OBT", "Obturação", False, 3, 2, 40.0),
        ("CAR", "Cárie", True, 2, 2, 40.0),
        ("END", "Tratamento Endodôntico", False, 1, 1, 20.0),
    ]


def test_clinical_findings_empty_list_when_detector_found_nothing(seed):
    clinic = seed.clinic()
    for _ in range(5):
        seed.analysis(clinic, 80, result=yolo())

    findings = quality_stats.get_clinical_findings(clinic, last_7_days())

    assert findings.analyses_evaluated == 5
    assert findings.items == []
    assert findings.insufficient_data is False


def test_clinical_findings_null_when_detector_did_not_run_enough(seed):
    clinic = seed.clinic()
    seed.analysis(clinic, 80, result=yolo("OBT"))
    for _ in range(6):
        seed.analysis(clinic, 80, result=yolo("IMP", available=False))

    findings = quality_stats.get_clinical_findings(clinic, last_7_days())

    assert findings.analyses_evaluated == 1
    assert findings.items is None
    assert findings.insufficient_data is True


def test_clinical_findings_isolated_by_clinic_and_professional(seed):
    clinic_a = seed.clinic("A")
    clinic_b = seed.clinic("B")
    ana = seed.profile(clinic_a, "Ana")
    for _ in range(5):
        seed.analysis(clinic_a, 80, professional_id=ana, result=yolo("OBT"))
    for _ in range(5):
        seed.analysis(clinic_a, 80, result=yolo("END"))
    for _ in range(5):
        seed.analysis(clinic_b, 80, result=yolo("IMP"))

    everyone = quality_stats.get_clinical_findings(clinic_a, last_7_days())
    only_ana = quality_stats.get_clinical_findings(clinic_a, last_7_days(professional_id=ana))

    assert {i.class_code for i in everyone.items} == {"OBT", "END"}
    assert [i.class_code for i in only_ana.items] == ["OBT"]


# --- bucket de radiografias -------------------------------------------------------

def as_user(db, role: str, user_id: str | None = None):
    db.execute("select set_config('request.jwt.claim.sub', %s, false)", (user_id or "",))
    db.execute(f"set role {role}")


def test_bucket_is_no_longer_open_to_anonymous_users(seed, db):
    clinic_a = seed.clinic("A")
    clinic_b = seed.clinic("B")
    user_a = seed.profile(clinic_a)
    db.execute(
        "insert into storage.objects (bucket_id, name) values "
        "('radiographs', %s), ('radiographs', %s), ('radiographs', 'solto.jpg')",
        (f"{clinic_a}/rx.jpg", f"{clinic_b}/rx.jpg")
    )

    open_policies = db.execute(
        "select policyname from pg_policies where schemaname = 'storage' and policyname like 'AktIA - %'"
    ).fetchall()
    assert open_policies == []

    try:
        as_user(db, "anon")
        assert db.execute("select name from storage.objects").fetchall() == []
        assert db.execute("delete from storage.objects").rowcount == 0
        with pytest.raises(Exception):
            db.execute("insert into storage.objects (bucket_id, name) values ('radiographs', 'x.jpg')")

        db.execute("reset role")
        as_user(db, "authenticated", user_a)
        visible = db.execute("select name from storage.objects").fetchall()
        assert [row["name"] for row in visible] == [f"{clinic_a}/rx.jpg"]
    finally:
        db.execute("reset role")

    assert db.execute("select count(*) as n from storage.objects").fetchone()["n"] == 3
