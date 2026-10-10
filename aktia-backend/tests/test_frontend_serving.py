from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import mount_frontend


def make_client(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>AktIA</html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('aktia')", encoding="utf-8")
    (dist / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path / "segredo.txt").write_text("fora da pasta do site", encoding="utf-8")

    application = FastAPI()

    @application.get("/health")
    def health():
        return {"status": "healthy"}

    mount_frontend(application, dist)
    return TestClient(application)


def test_site_and_its_files_are_served(tmp_path):
    client = make_client(tmp_path)

    assert client.get("/").text == "<html>AktIA</html>"
    assert "aktia" in client.get("/assets/app.js").text
    assert client.get("/favicon.svg").text == "<svg/>"


def test_screen_routes_fall_back_to_the_index(tmp_path):
    client = make_client(tmp_path)

    for path in ("/radiografias", "/radiografias/123?analisar=1", "/pre-laudos/abc"):
        assert client.get(path).text == "<html>AktIA</html>"


def test_api_routes_are_not_swallowed_and_nothing_outside_the_site_leaks(tmp_path):
    client = make_client(tmp_path)

    assert client.get("/health").json() == {"status": "healthy"}
    assert client.get("/api/v1/rota-que-nao-existe").status_code == 404
    assert "fora da pasta" not in client.get("/%2e%2e/segredo.txt").text
    assert "fora da pasta" not in client.get("/..%2fsegredo.txt").text
