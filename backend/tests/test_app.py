from pathlib import Path

from starlette.testclient import TestClient

from app.main import create_app


def test_health_check_reports_local_service_is_ready() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_built_frontend_is_served_from_the_application_root(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text(
        "<!doctype html><title>A 股 K 线终端</title>",
        encoding="utf-8",
    )
    client = TestClient(create_app(static_dir=tmp_path))

    response = client.get("/")

    assert response.status_code == 200
    assert "A 股 K 线终端" in response.text


def test_built_frontend_falls_back_to_index_for_client_routes(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text(
        "<!doctype html><title>A 股 K 线终端</title>",
        encoding="utf-8",
    )
    client = TestClient(create_app(static_dir=tmp_path))

    for path in ("/stocks/000001", "/settings"):
        response = client.get(path)

        assert response.status_code == 200
        assert "A 股 K 线终端" in response.text
