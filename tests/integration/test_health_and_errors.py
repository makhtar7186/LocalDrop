from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

import localdrop
from localdrop.core.config import Settings
from localdrop.core.errors import ConflictError
from localdrop.main import create_app

pytestmark = pytest.mark.integration

LAN = ("192.168.1.50", 50000)


def test_FR_006_health_reports_ok_and_version(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": localdrop.__version__}


def test_api_responses_carry_security_headers(client: TestClient) -> None:
    headers = client.get("/api/v1/health").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["x-frame-options"] == "DENY"
    assert headers["cache-control"] == "no-store"


def test_unknown_api_route_uses_error_format(client: TestClient) -> None:
    response = client.get("/api/v1/inexistant")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_wrong_method_uses_error_format(client: TestClient) -> None:
    response = client.post("/api/v1/health")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_docs_are_disabled_outside_debug(client: TestClient) -> None:
    assert client.get("/api/docs").status_code == 404
    assert client.get("/api/openapi.json").status_code == 404


class _Payload(BaseModel):
    secret: str
    size: int


def _app_with_test_routes(settings: Settings) -> FastAPI:
    app = create_app(settings)

    @app.post("/api/v1/_test/validate")
    async def validate(payload: _Payload) -> dict[str, str]:
        return {"ok": "yes"}

    @app.get("/api/v1/_test/conflict")
    async def conflict() -> None:
        raise ConflictError("Déjà finalisé", code="TRANSFER_ALREADY_COMPLETED", details={"id": "x"})

    @app.get("/api/v1/_test/boom")
    async def boom() -> None:
        raise RuntimeError("panne interne sensible")

    return app


def test_domain_error_is_mapped(settings: Settings) -> None:
    with TestClient(_app_with_test_routes(settings), client=LAN) as client:
        response = client.get("/api/v1/_test/conflict")
    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "TRANSFER_ALREADY_COMPLETED",
            "message": "Déjà finalisé",
            "details": {"id": "x"},
        }
    }


def test_validation_error_never_echoes_input(settings: Settings) -> None:
    with TestClient(_app_with_test_routes(settings), client=LAN) as client:
        response = client.post(
            "/api/v1/_test/validate", json={"secret": "ne-pas-renvoyer", "size": "abc"}
        )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "ne-pas-renvoyer" not in response.text
    assert body["error"]["details"]["errors"][0]["loc"] == ["body", "size"]


def test_unexpected_error_hides_internals(settings: Settings) -> None:
    with TestClient(
        _app_with_test_routes(settings), client=LAN, raise_server_exceptions=False
    ) as client:
        response = client.get("/api/v1/_test/boom")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "panne interne" not in response.text


def test_web_ui_is_served_when_built(settings: Settings, tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>LocalDrop</title>", encoding="utf-8")
    app = create_app(settings.model_copy(update={"web_dist_dir": dist}))

    with TestClient(app, client=LAN) as client:
        page = client.get("/")
        api_miss = client.get("/api/v1/inexistant")
        wrong_method = client.post("/api/v1/health")

    assert page.status_code == 200
    assert "LocalDrop" in page.text
    assert page.headers["x-frame-options"] == "DENY"
    # L'UI montée sur "/" ne doit pas masquer les 404/405 JSON de l'API.
    assert api_miss.status_code == 404
    assert api_miss.json()["error"]["code"] == "NOT_FOUND"
    assert wrong_method.status_code == 405
    assert wrong_method.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
