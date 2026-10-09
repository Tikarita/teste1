import types

import pytest

from app.services import model_store, supabase_service


class FakeStorage:
    def __init__(self, files: dict[str, bytes]):
        self.files, self.requests = files, []

    def from_(self, bucket):
        fake = self

        class Bucket:
            def download(self, name):
                fake.requests.append((bucket, name))
                return fake.files[name]

        return Bucket()


@pytest.fixture
def storage(monkeypatch):
    fake = FakeStorage({"modelo.pt": b"pesos-do-modelo"})
    monkeypatch.setattr(supabase_service, "supabase", types.SimpleNamespace(storage=fake))
    return fake


def test_existing_file_is_used_without_downloading(tmp_path, storage):
    path = tmp_path / "modelo.pt"
    path.write_bytes(b"local")

    assert model_store.ensure_model_file(path) == path
    assert path.read_bytes() == b"local" and storage.requests == []


def test_missing_file_is_downloaded_from_the_models_bucket(tmp_path, storage):
    path = tmp_path / "ml" / "modelo.pt"

    model_store.ensure_model_file(path)

    assert path.read_bytes() == b"pesos-do-modelo"
    assert storage.requests == [("models", "modelo.pt")]
    assert list(path.parent.iterdir()) == [path]


def test_missing_everywhere_raises_a_clear_error(tmp_path, storage):
    path = tmp_path / "outro.pt"

    with pytest.raises(FileNotFoundError, match="bucket 'models'"):
        model_store.ensure_model_file(path)

    assert not path.exists()
