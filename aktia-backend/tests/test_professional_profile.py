from datetime import datetime

import pytest

from tests.conftest import TIMEZONE, local_noon


pytestmark = pytest.mark.usefixtures("rpc_on_database")


def today():
    return datetime.now(TIMEZONE).date()


def url(professional_id: str) -> str:
    return f"/api/v1/stats/professionals/{professional_id}"


@pytest.fixture
def clinic(seed, db):
    """Ana: 5 análises (média 90, todas adequadas). Bruno: 5 análises (média 50, 1 adequada)."""
    clinic_id = seed.clinic("Clínica A")
    admin = seed.profile(clinic_id, "Admin")
    ana = seed.profile(clinic_id, "Ana")
    bruno = seed.profile(clinic_id, "Bruno")

    for _ in range(5):
        seed.analysis(clinic_id, 90, day=today(), professional_id=ana)
    for score, status in [(70, "approved"), (50, "rejected"), (50, "rejected"), (40, "rejected"), (40, "rejected")]:
        seed.analysis(clinic_id, score, status, day=today(), professional_id=bruno,
                      findings={"sharpness": "rejected"} if status == "rejected" else None)

    # Revisão humana das 5 radiografias do Bruno: 2 rejeitadas, 1 repetida.
    radiographs = db.execute(
        "select id from radiographs where professional_id = %s order by created_at, id", (bruno,)
    ).fetchall()
    for index, row in enumerate(radiographs):
        db.execute("update radiographs set created_at = %s where id = %s", (local_noon(today()), row["id"]))
        db.execute(
            "select record_review(%s, %s, %s, %s, %s, %s::text[], null)",
            (row["id"], clinic_id, admin, "inadequate" if index < 2 else "adequate",
             index == 0, ["positioning"] if index < 2 else [])
        )

    return {"id": clinic_id, "admin": admin, "ana": ana, "bruno": bruno}


def test_profile_numbers_and_comparison_with_the_clinic(client, login, clinic):
    login(clinic["id"], clinic["admin"], "admin")

    response = client.get(url(clinic["bruno"]), params={"period": "7"})

    assert response.status_code == 200
    body = response.json()
    assert body["professional"] == {"id": clinic["bruno"], "full_name": "Bruno", "role": "user"}

    assert (body["summary"]["total"], body["summary"]["avg_score"]) == (5, 50.0)
    assert body["summary"]["status_rates"]["approved"] == 20.0
    assert (body["clinic_summary"]["total"], body["clinic_summary"]["avg_score"]) == (10, 70.0)
    assert body["versus_clinic"] == {
        "avg_score_delta": -20.0,
        "approved_rate_delta": -40.0,
        "insufficient_data": False
    }

    assert body["history"] == [{"bucket": today().isoformat(), "avg_score": 50.0, "total": 5}]
    assert "quality_findings" not in body

    assert (body["review"]["reviewed"], body["review"]["rejection_rate"], body["review"]["repeated"]) == (5, 40.0, 1)
    assert [r["reason"] for r in body["review"]["reasons"]] == ["positioning"]
    assert body["clinic_rejection_rate"] == 40.0
    assert body["previous"]["insufficient_data"] is True


def test_profile_without_enough_data_uses_null(client, login, clinic, seed):
    newcomer = seed.profile(clinic["id"], "Recém-chegada")
    seed.analysis(clinic["id"], 80, day=today(), professional_id=newcomer)
    login(clinic["id"], clinic["admin"], "admin")

    body = client.get(url(newcomer)).json()

    assert body["summary"]["total"] == 1
    assert body["summary"]["avg_score"] is None
    assert body["versus_clinic"] == {
        "avg_score_delta": None, "approved_rate_delta": None, "insufficient_data": True
    }
    assert body["history"] is None
    assert body["review"]["rejection_rate"] is None


@pytest.mark.parametrize("role, viewer, target, expected", [
    ("admin", "admin", "bruno", 200),
    ("manager", "admin", "bruno", 200),
    ("user", "ana", "ana", 200),
    ("user", "ana", "bruno", 403),
])
def test_only_admins_and_managers_see_other_peoples_profiles(client, login, clinic, role, viewer, target, expected):
    login(clinic["id"], clinic[viewer], role)

    assert client.get(url(clinic[target])).status_code == expected


def test_profile_of_another_clinics_professional_is_not_found(client, login, clinic, seed):
    clinic_b = seed.clinic("Clínica B")
    outsider = seed.profile(clinic_b, "De fora")
    for _ in range(5):
        seed.analysis(clinic_b, 10, "rejected", day=today(), professional_id=outsider)
    login(clinic["id"], clinic["admin"], "admin")

    response = client.get(url(outsider))

    assert response.status_code == 404


def test_profile_requires_authentication(client, clinic):
    assert client.get(url(clinic["ana"])).status_code == 401
