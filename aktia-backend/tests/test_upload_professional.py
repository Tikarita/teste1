import sys
import types
from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image

from app.api import analysis
from app.core.config import settings


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.filters: list[tuple[str, str]] = []
        self.operation = "select"
        self.payload = None

    def select(self, *_):
        return self

    def eq(self, column, value):
        self.filters.append((column, str(value)))
        return self

    def limit(self, _):
        return self

    def order(self, *_, **__):
        return self

    def insert(self, payload):
        self.operation, self.payload = "insert", payload
        return self

    def delete(self):
        self.operation = "delete"
        return self

    def execute(self):
        if self.operation == "insert":
            row = {"id": str(uuid4()), **self.payload}
            self.rows.append(row)
            return FakeResponse([row])

        matches = [
            row for row in self.rows
            if all(str(row.get(column)) == value for column, value in self.filters)
        ]

        if self.operation == "delete":
            for row in matches:
                self.rows.remove(row)

        return FakeResponse(matches)


class FakeBucket:
    def __init__(self, files: dict):
        self.files = files

    def upload(self, path, file, file_options=None):
        self.files[path] = file

    def download(self, path):
        return self.files[path]

    def remove(self, paths):
        for path in paths:
            self.files.pop(path, None)

    def create_signed_url(self, path, _expires_in):
        return {"signedUrl": f"http://storage.test/{path}"}


class FakeSupabase:
    """Cliente do Supabase em memória: só o que as rotas de radiografia usam."""

    def __init__(self):
        self.tables: dict[str, list[dict]] = {"profiles": [], "radiographs": []}
        self.files: dict[str, bytes] = {}
        self.rpc_calls: list[tuple[str, dict]] = []
        self.storage = types.SimpleNamespace(from_=lambda _bucket: FakeBucket(self.files))

    def table(self, name):
        return FakeQuery(self.tables[name])

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))
        return types.SimpleNamespace(execute=lambda: FakeResponse(str(uuid4())))


@pytest.fixture
def fake_supabase(monkeypatch):
    fake = FakeSupabase()
    monkeypatch.setattr(analysis, "supabase", fake)
    # A revisão humana tem testes próprios (test_reviews.py); aqui não há nenhuma.
    monkeypatch.setattr(analysis.review_service, "_current_review_row", lambda *_: None)
    return fake


@pytest.fixture
def clinics(fake_supabase):
    """Duas clínicas, cada uma com dois profissionais."""
    people = {
        "a": (str(uuid4()), [str(uuid4()), str(uuid4())]),
        "b": (str(uuid4()), [str(uuid4()), str(uuid4())]),
    }
    for clinic_id, profile_ids in people.values():
        for profile_id in profile_ids:
            fake_supabase.tables["profiles"].append({"id": profile_id, "clinic_id": clinic_id})
    return people


def png() -> bytes:
    buffer = BytesIO()
    Image.new("L", (8, 8), 128).save(buffer, format="PNG")
    return buffer.getvalue()


def upload(client, **form):
    return client.post(
        "/api/v1/analysis/upload",
        data=form,
        files={"file": ("rx.png", png(), "image/png")}
    )


def test_upload_requires_authentication(client, fake_supabase):
    response = upload(client)

    assert response.status_code == 401
    assert fake_supabase.tables["radiographs"] == []


def test_upload_defaults_professional_to_the_logged_user(client, login, clinics, fake_supabase):
    clinic_a, (user, _) = clinics["a"]
    login(clinic_a, user)

    response = upload(client)

    assert response.status_code == 200
    stored = fake_supabase.tables["radiographs"][0]
    assert stored["clinic_id"] == clinic_a
    assert stored["uploaded_by"] == user
    assert stored["professional_id"] == user


def test_upload_accepts_a_professional_from_the_same_clinic(client, login, clinics, fake_supabase):
    clinic_a, (user, colleague) = clinics["a"]
    login(clinic_a, user)

    response = upload(client, professional_id=colleague)

    assert response.status_code == 200
    stored = fake_supabase.tables["radiographs"][0]
    assert stored["uploaded_by"] == user
    assert stored["professional_id"] == colleague


def test_upload_rejects_a_professional_from_another_clinic(client, login, clinics, fake_supabase):
    clinic_a, (user, _) = clinics["a"]
    _, (outsider, _) = clinics["b"]
    login(clinic_a, user)

    response = upload(client, professional_id=outsider)

    assert response.status_code == 400
    assert fake_supabase.tables["radiographs"] == []
    assert fake_supabase.files == {}


def test_upload_ignores_clinic_and_uploader_sent_by_the_client(client, login, clinics, fake_supabase):
    clinic_a, (user, _) = clinics["a"]
    clinic_b, (other_user, _) = clinics["b"]
    login(clinic_a, user)

    response = upload(client, clinic_id=clinic_b, uploaded_by=other_user)

    assert response.status_code == 200
    stored = fake_supabase.tables["radiographs"][0]
    assert stored["clinic_id"] == clinic_a
    assert stored["uploaded_by"] == user


def test_radiograph_routes_hide_other_clinics(client, login, clinics, fake_supabase):
    clinic_a, (user_a, _) = clinics["a"]
    clinic_b, (user_b, _) = clinics["b"]
    login(clinic_a, user_a)
    radiograph_id = upload(client).json()["data"][0]["id"]

    login(clinic_b, user_b)

    assert client.get(f"/api/v1/analysis/{radiograph_id}").status_code == 404
    assert client.delete(f"/api/v1/analysis/{radiograph_id}").status_code == 404
    assert client.get(f"/api/v1/analysis/clinic/{clinic_a}").status_code == 403
    assert client.get(f"/api/v1/analysis/clinic/{clinic_b}").json() == {"data": []}
    assert len(fake_supabase.tables["radiographs"]) == 1

    login(clinic_a, user_a)

    assert client.get(f"/api/v1/analysis/{radiograph_id}").status_code == 200
    assert len(client.get(f"/api/v1/analysis/clinic/{clinic_a}").json()["data"]) == 1


@pytest.mark.parametrize("method, path", [
    ("get", "/api/v1/analysis/clinic/{id}"),
    ("get", "/api/v1/analysis/{id}"),
    ("post", "/api/v1/analysis/{id}/analyze"),
    ("delete", "/api/v1/analysis/{id}"),
])
def test_radiograph_routes_require_authentication(client, fake_supabase, method, path):
    response = getattr(client, method)(path.format(id=uuid4()))

    assert response.status_code == 401


@pytest.fixture
def stub_model(monkeypatch):
    """
    Troca o serviço de IA (que exige torch) por um resultado fixo. O teste
    cobre só o que a rota faz com o resultado, não o modelo.
    """
    result = {
        "yolo": {"model": None, "available": False, "findings": []},
        "efficientnet": {
            "model": "modelo-de-teste",
            "is_adequate": False,
            "score": 41.5,
            "criteria": [
                {"category": "sharpness", "label": "Nitidez", "score": 30, "status": "rejected", "raw_value": 250.0},
                {"category": "coverage", "label": "Cobertura anatômica", "score": None, "status": "pending", "raw_value": None}
            ],
            "recommendation": "Repita a captura."
        }
    }
    module = types.ModuleType("app.services.analysis_service")
    module.analyze_radiograph = lambda _image_bytes: result
    monkeypatch.setitem(sys.modules, "app.services.analysis_service", module)
    monkeypatch.setattr(settings, "ENABLE_AI", True)
    return result


def test_analyze_records_the_analysis_for_the_users_clinic(client, login, clinics, fake_supabase, stub_model):
    clinic_a, (user, _) = clinics["a"]
    login(clinic_a, user)
    radiograph_id = upload(client).json()["data"][0]["id"]

    response = client.post(f"/api/v1/analysis/{radiograph_id}/analyze")

    assert response.status_code == 200
    assert response.json() == {"data": stub_model}
    assert fake_supabase.rpc_calls == [("record_analysis", {
        "p_radiograph_id": radiograph_id,
        "p_clinic_id": clinic_a,
        "p_status": "rejected",
        "p_quality_score": 41.5,
        "p_is_adequate": False,
        "p_model_version": "modelo-de-teste",
        "p_recommendation": "Repita a captura.",
        "p_result": stub_model,
        "p_findings": [{"category": "sharpness", "status": "rejected", "score": 30}]
    })]


def test_analyze_fails_loudly_when_the_result_cannot_be_saved(client, login, clinics, fake_supabase, stub_model):
    clinic_a, (user, _) = clinics["a"]
    login(clinic_a, user)
    radiograph_id = upload(client).json()["data"][0]["id"]

    def broken_rpc(_name, _params):
        raise RuntimeError("function record_analysis does not exist")

    fake_supabase.rpc = broken_rpc

    response = client.post(f"/api/v1/analysis/{radiograph_id}/analyze")

    assert response.status_code == 500
    assert "não pôde ser salva" in response.json()["detail"]


def test_analyze_refuses_a_radiograph_from_another_clinic(client, login, clinics, fake_supabase, stub_model):
    clinic_a, (user_a, _) = clinics["a"]
    clinic_b, (user_b, _) = clinics["b"]
    login(clinic_a, user_a)
    radiograph_id = upload(client).json()["data"][0]["id"]

    login(clinic_b, user_b)
    response = client.post(f"/api/v1/analysis/{radiograph_id}/analyze")

    assert response.status_code == 404
    assert fake_supabase.rpc_calls == []
