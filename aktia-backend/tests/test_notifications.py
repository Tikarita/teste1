from uuid import uuid4

import psycopg
import pytest

from app.services import notification_service


URL = "/api/v1/notifications/"


@pytest.fixture
def notifications_on_database(db, monkeypatch):
    """Faz o serviço de avisos gravar e ler no Postgres de teste."""

    def insert(rows: list[dict]) -> None:
        for row in rows:
            db.execute(
                """
                insert into notifications (clinic_id, recipient_id, radiograph_id, kind, title, message)
                values (%(clinic_id)s, %(recipient_id)s, %(radiograph_id)s, %(kind)s, %(title)s, %(message)s)
                on conflict (radiograph_id, recipient_id, kind) do nothing
                """,
                row
            )

    def select(recipient_id: str, clinic_id: str) -> list[dict]:
        return db.execute(
            "select * from notifications where recipient_id = %s and clinic_id = %s "
            "order by created_at desc limit 30",
            (recipient_id, clinic_id)
        ).fetchall()

    def mark(notification_id: str, recipient_id: str) -> list[dict]:
        return db.execute(
            "update notifications set read_at = now() "
            "where id = %s and recipient_id = %s and read_at is null returning *",
            (notification_id, recipient_id)
        ).fetchall()

    monkeypatch.setattr(notification_service, "_insert_notifications", insert)
    monkeypatch.setattr(notification_service, "_select_notifications", select)
    monkeypatch.setattr(notification_service, "_mark_read", mark)


@pytest.fixture
def clinic(seed):
    clinic_id = seed.clinic("Clínica A")
    return {
        "id": clinic_id,
        "uploader": seed.profile(clinic_id, "Recepção"),
        "dentist": seed.profile(clinic_id, "Dra. Ana"),
    }


def notify(clinic, radiograph_id, professional, requester, score=18.4, file_name="rx-01.jpg"):
    notification_service.notify_inadequate_exam(
        {"id": radiograph_id, "professional_id": professional, "file_name": file_name},
        {"score": score},
        {"profile": {"id": requester}, "clinic": {"id": clinic["id"]}}
    )


pytestmark = pytest.mark.usefixtures("notifications_on_database")


def test_inadequate_exam_notifies_the_professional_and_the_requester(client, login, clinic, seed):
    radiograph = seed.radiograph(clinic["id"], clinic["dentist"])
    notify(clinic, radiograph, clinic["dentist"], clinic["uploader"])

    login(clinic["id"], clinic["dentist"])
    dentist_view = client.get(URL).json()
    login(clinic["id"], clinic["uploader"])
    uploader_view = client.get(URL).json()

    assert dentist_view["unread_count"] == 1 and uploader_view["unread_count"] == 1
    item = dentist_view["items"][0]
    assert item["kind"] == "inadequate_exam"
    assert item["title"] == "Exame inadequado: refaça o exame"
    assert "rx-01.jpg" in item["message"] and "18.4/100" in item["message"]
    assert "Confira a imagem e refaça o exame" in item["message"]
    assert item["radiograph_id"] == radiograph
    assert item["read_at"] is None


def test_same_person_as_professional_and_requester_gets_one_notification(client, login, clinic, seed):
    radiograph = seed.radiograph(clinic["id"], clinic["dentist"])
    notify(clinic, radiograph, clinic["dentist"], clinic["dentist"])

    login(clinic["id"], clinic["dentist"])

    assert client.get(URL).json()["unread_count"] == 1


def test_reanalysis_does_not_repeat_the_notification(client, login, clinic, seed):
    radiograph = seed.radiograph(clinic["id"], clinic["dentist"])
    notify(clinic, radiograph, clinic["dentist"], clinic["uploader"])
    notify(clinic, radiograph, clinic["dentist"], clinic["uploader"], score=12.0)

    login(clinic["id"], clinic["dentist"])
    body = client.get(URL).json()

    assert len(body["items"]) == 1
    assert "18.4/100" in body["items"][0]["message"]


def test_mark_as_read(client, login, clinic, seed):
    first = seed.radiograph(clinic["id"], clinic["dentist"])
    second = seed.radiograph(clinic["id"], clinic["dentist"])
    notify(clinic, first, clinic["dentist"], clinic["dentist"])
    notify(clinic, second, clinic["dentist"], clinic["dentist"])
    login(clinic["id"], clinic["dentist"])
    target = client.get(URL).json()["items"][0]["id"]

    after = client.post(f"{URL}{target}/read").json()
    again = client.post(f"{URL}{target}/read")

    assert after["unread_count"] == 1
    assert next(i for i in after["items"] if i["id"] == target)["read_at"] is not None
    assert again.status_code == 200 and again.json()["unread_count"] == 1


def test_nobody_reads_or_acknowledges_another_persons_notification(client, login, clinic, seed):
    radiograph = seed.radiograph(clinic["id"], clinic["dentist"])
    notify(clinic, radiograph, clinic["dentist"], clinic["dentist"])
    login(clinic["id"], clinic["dentist"])
    target = client.get(URL).json()["items"][0]["id"]

    login(clinic["id"], clinic["uploader"])
    listing = client.get(URL).json()
    attempt = client.post(f"{URL}{target}/read")

    assert listing == {"unread_count": 0, "items": []}
    assert attempt.status_code == 404

    login(clinic["id"], clinic["dentist"])
    assert client.get(URL).json()["unread_count"] == 1


def test_notification_routes_require_authentication(client):
    assert client.get(URL).status_code == 401
    assert client.post(f"{URL}{uuid4()}/read").status_code == 401


def test_rls_shows_only_the_users_own_notifications(clinic, seed, db):
    radiograph = seed.radiograph(clinic["id"], clinic["dentist"])
    notify(clinic, radiograph, clinic["dentist"], clinic["uploader"])

    db.execute("select set_config('request.jwt.claim.sub', %s, false)", (clinic["dentist"],))
    db.execute("set role authenticated")
    try:
        visible = db.execute("select recipient_id from notifications").fetchall()
        assert [str(row["recipient_id"]) for row in visible] == [clinic["dentist"]]
        assert db.execute("update notifications set read_at = now()").rowcount == 0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute(
                "insert into notifications (clinic_id, recipient_id, kind, title, message) "
                "values (%s, %s, 'inadequate_exam', 't', 'm')",
                (clinic["id"], clinic["dentist"])
            )
    finally:
        db.execute("reset role")
