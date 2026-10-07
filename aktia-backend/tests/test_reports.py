from datetime import datetime, timedelta

import psycopg
import pytest

from tests.conftest import TIMEZONE


pytestmark = pytest.mark.usefixtures("reports_on_database")

URL = "/api/v1/reports/quality"


def today():
    return datetime.now(TIMEZONE).date()


def period(days: int = 7) -> dict:
    return {
        "period_start": (today() - timedelta(days=days - 1)).isoformat(),
        "period_end": today().isoformat()
    }


@pytest.fixture
def clinic_a(seed):
    """Clínica com 6 radiografias analisadas hoje (4 adequadas) e 1 sem análise."""
    clinic = seed.clinic("Clínica A")
    admin = seed.profile(clinic, "Admin A")
    ana = seed.profile(clinic, "Ana")

    for score, status in [(90, "approved"), (80, "approved"), (70, "approved"),
                          (60, "approved"), (40, "rejected")]:
        seed.analysis(clinic, score, status, day=today(), professional_id=ana,
                      findings={"sharpness": "rejected" if status == "rejected" else "approved"})
    seed.analysis(clinic, 20, "rejected", day=today(), professional_id=None,
                  findings={"contrast": "attention"})
    seed.radiograph(clinic, ana)

    return {"clinic": clinic, "admin": admin, "ana": ana}


def test_report_numbers_match_the_period(client, login, clinic_a):
    login(clinic_a["clinic"], clinic_a["admin"], "admin")

    response = client.post(URL, json={**period(), "notes": "  Recalibrado o sensor em 02/10.  "})

    assert response.status_code == 201
    report = response.json()
    data = report["data"]

    assert report["report_type"] == "quality"
    assert report["title"].startswith("Relatório de Garantia da Qualidade — ")
    assert report["notes"] == "Recalibrado o sensor em 02/10."
    assert report["generated_by_name"] == "Usuária de Teste"

    assert data["clinic"] == {"name": "Clínica", "cnpj": "00.000.000/0001-91"}
    assert data["volume"] == {"uploaded": 7, "analyzed": 6, "not_analyzed": 1}
    assert data["summary"]["total"] == 6
    assert data["summary"]["avg_score"] == 60.0
    assert data["summary"]["status_counts"] == {"approved": 4, "attention": 0, "rejected": 2}
    assert data["summary"]["status_rates"]["rejected"] == 33.3
    assert data["previous"]["insufficient_data"] is True
    assert data["comparison"]["avg_score_delta"] is None
    assert data["history"] == [{"bucket": today().isoformat(), "avg_score": 60.0, "total": 6}]
    assert data["models"] == [{"model_version": "modelo-de-teste", "total": 6}]

    by_name = {p["full_name"]: p for p in data["professionals"]}
    assert (by_name["Ana"]["total"], by_name["Ana"]["avg_score"], by_name["Ana"]["approved_rate"]) == (5, 68.0, 80.0)
    assert by_name["Admin A"]["total"] == 0
    assert by_name[None]["total"] == 1 and by_name[None]["avg_score"] is None

    assert [(f["category"], f["count"]) for f in data["quality_findings"]] == [("contrast", 1), ("sharpness", 1)]
    assert any("RDC ANVISA nº 611/2022" in line for line in data["methodology"])
    assert any("não substitui" in line for line in data["methodology"])


def test_issued_report_is_frozen(client, login, clinic_a, seed):
    login(clinic_a["clinic"], clinic_a["admin"], "admin")
    issued = client.post(URL, json=period()).json()

    for _ in range(10):
        seed.analysis(clinic_a["clinic"], 100, day=today())

    reopened = client.get(f"{URL}/{issued['id']}").json()
    fresh = client.post(URL, json=period()).json()

    assert reopened["data"] == issued["data"]
    assert reopened["data"]["summary"]["total"] == 6
    assert fresh["data"]["summary"]["total"] == 16


def test_report_without_enough_data_uses_null_not_zero(client, login, seed):
    clinic = seed.clinic()
    admin = seed.profile(clinic, "Admin")
    seed.analysis(clinic, 80, day=today())
    login(clinic, admin, "admin")

    data = client.post(URL, json=period()).json()["data"]

    assert data["summary"]["total"] == 1
    assert data["summary"]["avg_score"] is None
    assert data["summary"]["status_rates"] is None
    assert data["summary"]["insufficient_data"] is True
    assert data["history"] is None
    assert data["quality_findings"] is None


@pytest.mark.parametrize("role, expected", [("admin", 201), ("manager", 201), ("user", 403)])
def test_only_admins_and_managers_issue_reports(client, login, clinic_a, role, expected):
    login(clinic_a["clinic"], clinic_a["admin"], role)

    assert client.post(URL, json=period()).status_code == expected


def test_reports_are_isolated_by_clinic(client, login, clinic_a, seed):
    clinic_b = seed.clinic("Clínica B")
    admin_b = seed.profile(clinic_b, "Admin B")

    login(clinic_a["clinic"], clinic_a["admin"], "admin")
    report_a = client.post(URL, json=period()).json()

    login(clinic_b, admin_b, "admin")
    report_b = client.post(URL, json=period()).json()

    assert report_b["data"]["summary"]["total"] == 0
    assert report_b["data"]["volume"]["uploaded"] == 0
    assert [r["id"] for r in client.get(URL).json()] == [report_b["id"]]
    assert client.get(f"{URL}/{report_a['id']}").status_code == 404

    login(clinic_a["clinic"], clinic_a["admin"], "user")
    assert [r["id"] for r in client.get(URL).json()] == [report_a["id"]]
    assert client.get(f"{URL}/{report_a['id']}").status_code == 200


@pytest.mark.parametrize("body", [
    {"period_start": "2026-03-10", "period_end": "2026-03-01"},
    {"period_start": "2024-01-01", "period_end": "2026-01-01"},
    {"period_start": "2020-01-01", "period_end": "2999-01-01"},
])
def test_invalid_periods_are_rejected(client, login, clinic_a, body):
    login(clinic_a["clinic"], clinic_a["admin"], "admin")

    assert client.post(URL, json=body).status_code == 400


@pytest.mark.parametrize("method, path", [("post", URL), ("get", URL), ("get", f"{URL}/00000000-0000-0000-0000-000000000000")])
def test_report_routes_require_authentication(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_rls_lets_a_clinic_read_only_its_own_reports(client, login, clinic_a, seed, db):
    clinic_b = seed.clinic("Clínica B")
    admin_b = seed.profile(clinic_b, "Admin B")
    login(clinic_a["clinic"], clinic_a["admin"], "admin")
    client.post(URL, json=period())
    login(clinic_b, admin_b, "admin")
    client.post(URL, json=period())

    db.execute("select set_config('request.jwt.claim.sub', %s, false)", (clinic_a["admin"],))
    db.execute("set role authenticated")
    try:
        visible = db.execute("select clinic_id from reports").fetchall()
        assert [str(row["clinic_id"]) for row in visible] == [clinic_a["clinic"]]
        assert db.execute("update reports set notes = 'alterado'").rowcount == 0
        assert db.execute("delete from reports").rowcount == 0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("select * from report_volume(%s, now() - interval '1 day', now())", (clinic_b,))
    finally:
        db.execute("reset role")

    assert db.execute("select count(*) as n from reports").fetchone()["n"] == 2
