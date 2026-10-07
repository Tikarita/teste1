import types
from uuid import uuid4

import pytest

from app.api import staff as staff_api
from tests.conftest import session_for


class FakeSupabase:
    """Só o que as rotas de equipe usam: criar usuário no Auth e gravar/ler profiles."""

    def __init__(self):
        self.profiles: list[dict] = []
        self.created_users: list[dict] = []
        self.deleted_users: list[str] = []
        self.fail_profile_write = False
        self.auth = types.SimpleNamespace(admin=types.SimpleNamespace(
            create_user=self._create_user,
            delete_user=self.deleted_users.append
        ))

    def _create_user(self, payload):
        self.created_users.append(payload)
        return types.SimpleNamespace(user=types.SimpleNamespace(id=str(uuid4())))

    def table(self, name):
        assert name == "profiles"
        fake = self

        class Query:
            filters: dict = {}

            def select(self, *_):
                return self

            def eq(self, column, value):
                self.filters = {**self.filters, column: str(value)}
                return self

            def upsert(self, row):
                if fake.fail_profile_write:
                    raise RuntimeError("violates check constraint")
                fake.profiles.append(row)
                return self

            def execute(self):
                rows = [
                    row for row in fake.profiles
                    if all(str(row.get(k)) == v for k, v in self.filters.items())
                ]
                return types.SimpleNamespace(data=rows)

        return Query()


@pytest.fixture
def fake_supabase(monkeypatch):
    fake = FakeSupabase()
    monkeypatch.setattr(staff_api, "supabase", fake)
    return fake


@pytest.fixture
def login_as(login):
    """Como o `login` do conftest, mas escolhendo o papel do usuário."""
    from app.api.auth import get_current_user
    from app.main import app

    def _login(clinic_id: str, role: str = "admin") -> str:
        profile_id = str(uuid4())
        session = session_for(clinic_id, profile_id)
        session["profile"]["role"] = role
        app.dependency_overrides[get_current_user] = lambda: session
        return profile_id

    return _login


NEW_MEMBER = {"full_name": "Dra. Maria", "email": "maria@clinica.com", "role": "user"}


@pytest.mark.parametrize("method, path", [
    ("post", "/api/v1/staff/"),
    ("get", "/api/v1/staff/clinic/{id}"),
    ("get", "/api/v1/clinics/"),
    ("post", "/api/v1/clinics/"),
])
def test_routes_require_authentication(client, fake_supabase, method, path):
    response = getattr(client, method)(path.format(id=uuid4()))

    assert response.status_code == 401
    assert fake_supabase.created_users == []


def test_admin_creates_staff_in_their_own_clinic(client, login_as, fake_supabase):
    clinic_a, clinic_b = str(uuid4()), str(uuid4())
    login_as(clinic_a, "admin")

    response = client.post("/api/v1/staff/", json={**NEW_MEMBER, "clinic_id": clinic_b})

    assert response.status_code == 200
    assert response.json()["data"]["clinic_id"] == clinic_a
    assert response.json()["temporary_password"]
    assert [p["clinic_id"] for p in fake_supabase.profiles] == [clinic_a]
    assert fake_supabase.created_users[0]["user_metadata"]["clinic_id"] == clinic_a


@pytest.mark.parametrize("role", ["manager", "user"])
def test_only_admins_can_create_staff(client, login_as, fake_supabase, role):
    login_as(str(uuid4()), role)

    response = client.post("/api/v1/staff/", json=NEW_MEMBER)

    assert response.status_code == 403
    assert fake_supabase.created_users == []


@pytest.mark.parametrize("role", ["dentist", "technician", ""])
def test_roles_outside_the_database_constraint_are_rejected(client, login_as, fake_supabase, role):
    login_as(str(uuid4()), "admin")

    response = client.post("/api/v1/staff/", json={**NEW_MEMBER, "role": role})

    assert response.status_code == 422
    assert fake_supabase.created_users == []


def test_auth_user_is_removed_when_the_profile_cannot_be_saved(client, login_as, fake_supabase):
    login_as(str(uuid4()), "admin")
    fake_supabase.fail_profile_write = True

    response = client.post("/api/v1/staff/", json=NEW_MEMBER)

    assert response.status_code == 500
    assert len(fake_supabase.deleted_users) == 1


def test_staff_list_is_limited_to_the_users_clinic(client, login_as, fake_supabase):
    clinic_a, clinic_b = str(uuid4()), str(uuid4())
    fake_supabase.profiles += [
        {"id": "1", "clinic_id": clinic_a, "full_name": "Da A"},
        {"id": "2", "clinic_id": clinic_b, "full_name": "Da B"},
    ]
    login_as(clinic_a, "user")

    own = client.get(f"/api/v1/staff/clinic/{clinic_a}")
    other = client.get(f"/api/v1/staff/clinic/{clinic_b}")

    assert [p["full_name"] for p in own.json()["data"]] == ["Da A"]
    assert other.status_code == 403


def test_clinic_list_returns_only_the_users_clinic(client, login_as):
    clinic_a = str(uuid4())
    login_as(clinic_a, "user")

    response = client.get("/api/v1/clinics/")

    assert [clinic["id"] for clinic in response.json()["data"]] == [clinic_a]
