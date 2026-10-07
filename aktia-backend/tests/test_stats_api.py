from datetime import datetime

import pytest

from tests.conftest import TIMEZONE


pytestmark = pytest.mark.usefixtures("rpc_on_database")

ROUTES = [
    "/api/v1/stats/summary",
    "/api/v1/stats/history",
    "/api/v1/stats/findings",
    "/api/v1/stats/professionals",
    "/api/v1/stats/clinical-findings",
]


@pytest.fixture
def two_clinics(seed):
    """Clínica A com 5 análises boas hoje; clínica B com 6 ruins."""
    today = datetime.now(TIMEZONE).date()

    clinic_a = seed.clinic("A")
    clinic_b = seed.clinic("B")
    user_a = seed.profile(clinic_a, "Usuária A")
    user_b = seed.profile(clinic_b, "Usuário B")

    for _ in range(5):
        seed.analysis(clinic_a, 90, day=today, professional_id=user_a,
                      findings={"contrast": "attention"})
    for _ in range(6):
        seed.analysis(clinic_b, 20, "rejected", day=today, professional_id=user_b,
                      findings={"sharpness": "rejected"})

    return {"a": (clinic_a, user_a), "b": (clinic_b, user_b)}


@pytest.mark.parametrize("route", ROUTES)
def test_routes_require_authentication(client, route):
    response = client.get(route)

    assert response.status_code == 401


def test_summary_response_shape(client, login, two_clinics):
    login(*two_clinics["a"])

    response = client.get("/api/v1/stats/summary", params={"period": "7"})

    assert response.status_code == 200
    body = response.json()
    assert body["current"] == {
        "total": 5,
        "status_counts": {"approved": 5, "attention": 0, "rejected": 0},
        "avg_score": 90.0,
        "status_rates": {"approved": 100.0, "attention": 0.0, "rejected": 0.0},
        "insufficient_data": False
    }
    assert body["previous"] == {
        "total": 0,
        "status_counts": {"approved": 0, "attention": 0, "rejected": 0},
        "avg_score": None,
        "status_rates": None,
        "insufficient_data": True
    }
    assert body["comparison"] == {
        "avg_score_delta": None,
        "approved_rate_delta": None,
        "insufficient_data": True
    }
    assert body["min_sample_size"] == 5
    assert body["filters"] == {"professional_id": None, "status": None}


def test_each_clinic_gets_only_its_own_numbers(client, login, two_clinics):
    login(*two_clinics["a"])
    summary_a = client.get("/api/v1/stats/summary").json()["current"]
    history_a = client.get("/api/v1/stats/history").json()
    findings_a = client.get("/api/v1/stats/findings").json()

    login(*two_clinics["b"])
    summary_b = client.get("/api/v1/stats/summary").json()["current"]
    findings_b = client.get("/api/v1/stats/findings").json()

    assert (summary_a["total"], summary_a["avg_score"]) == (5, 90.0)
    assert history_a["total"] == 5
    assert [item["category"] for item in findings_a["items"]] == ["contrast"]

    assert (summary_b["total"], summary_b["avg_score"]) == (6, 20.0)
    assert [item["category"] for item in findings_b["items"]] == ["sharpness"]


@pytest.mark.parametrize("route", ROUTES)
def test_clinic_id_in_the_request_is_ignored(client, login, two_clinics, route):
    clinic_b, _ = two_clinics["b"]
    login(*two_clinics["a"])

    own = client.get(route).json()
    forced = client.get(route, params={"clinic_id": clinic_b, "p_clinic_id": clinic_b}).json()

    assert forced == own


def test_clinic_a_cannot_reach_clinic_b_through_the_professional_filter(client, login, two_clinics):
    _, user_b = two_clinics["b"]
    login(*two_clinics["a"])

    body = client.get("/api/v1/stats/summary", params={"professional_id": user_b}).json()

    assert body["current"]["total"] == 0
    assert body["current"]["avg_score"] is None
    assert body["current"]["insufficient_data"] is True


def test_filters_by_professional_and_status(client, login, two_clinics, seed):
    clinic_a, user_a = two_clinics["a"]
    colleague = seed.profile(clinic_a, "Colega")
    today = datetime.now(TIMEZONE).date()
    for _ in range(5):
        seed.analysis(clinic_a, 40, "rejected", day=today, professional_id=colleague)
    login(clinic_a, user_a)

    by_professional = client.get(
        "/api/v1/stats/summary", params={"professional_id": colleague}
    ).json()["current"]
    by_status = client.get(
        "/api/v1/stats/summary", params={"status": "approved"}
    ).json()["current"]

    assert (by_professional["total"], by_professional["avg_score"]) == (5, 40.0)
    assert (by_status["total"], by_status["avg_score"]) == (5, 90.0)


def test_history_and_findings_response_shape(client, login, two_clinics):
    login(*two_clinics["a"])
    today = datetime.now(TIMEZONE).date().isoformat()

    history = client.get("/api/v1/stats/history", params={"period": "7"}).json()
    findings = client.get("/api/v1/stats/findings", params={"period": "7"}).json()

    assert history["granularity"] == "day"
    assert history["points"] == [{"bucket": today, "avg_score": 90.0, "total": 5}]
    assert history["insufficient_data"] is False

    assert findings["total_analyses"] == 5
    assert findings["items"] == [
        {"category": "contrast", "label": "Contraste", "count": 5, "percentage": 100.0}
    ]


def test_custom_period(client, login, two_clinics):
    login(*two_clinics["a"])

    missing_dates = client.get("/api/v1/stats/summary", params={"period": "custom"})
    past = client.get(
        "/api/v1/stats/summary",
        params={"period": "custom", "start": "2020-01-01", "end": "2020-01-31"}
    )

    assert missing_dates.status_code == 400
    assert past.status_code == 200
    assert past.json()["current"]["insufficient_data"] is True


@pytest.mark.parametrize("params", [
    {"period": "15"},
    {"status": "ok"},
    {"professional_id": "nao-e-uuid"},
])
def test_invalid_filters_are_rejected(client, login, two_clinics, params):
    login(*two_clinics["a"])

    response = client.get("/api/v1/stats/summary", params=params)

    assert response.status_code == 422
