"""Audit de sécurité de la phase 10 (§12) : contrôles transverses de l'API.

- toutes les routes sauf /health et /sessions/join exigent une authentification ;
- l'administration n'est accessible qu'au PC (loopback + jeton) ;
- en-tête Host limité aux IP (DNS rebinding) ;
- ressources bornées : envois actifs par téléphone, espace disque réservé.
"""

import re
from collections import namedtuple
from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from starlette.websockets import WebSocketDisconnect

from localdrop.api.deps import ADMIN_HEADER
from localdrop.core.config import Settings
from localdrop.infrastructure.storage import files
from localdrop.services.container import AppServices

pytestmark = pytest.mark.integration

PUBLIC_ROUTES = {("GET", "/api/v1/health"), ("POST", "/api/v1/sessions/join")}
DiskUsage = namedtuple("DiskUsage", "total used free")


def _api_routes(app: FastAPI) -> list[tuple[str, str]]:
    """Inventaire depuis le schéma OpenAPI (les routeurs inclus ne sont plus aplatis)."""
    paths: dict[str, dict[str, object]] = app.openapi()["paths"]
    return [(method.upper(), path) for path, ops in paths.items() for method in ops]


def _concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "1", path)


def _join(client: TestClient, services: AppServices, *, approve: bool = True) -> str:
    info = services.pairing.current_pairing()
    joined = client.post(
        "/api/v1/sessions/join",
        json={
            "session_id": info.session_id,
            "secret": info.secret,
            "display_name": "Pixel",
            "platform": "android",
        },
    ).json()
    if approve:
        services.pairing.approve(joined["device_id"])
    token: str = joined["device_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return token


# ----------------------------------------------------------------- authentification
def test_every_route_except_health_and_join_requires_authentication(
    app: FastAPI, client: TestClient
) -> None:
    routes = _api_routes(app)
    assert len(routes) > 15, "inventaire des routes incomplet"
    exposed = []
    for method, path in routes:
        if (method, path) in PUBLIC_ROUTES:
            continue
        url = _concrete(path)
        if path.endswith("/download"):
            url += "?ticket=faux"
        response = client.request(method, url, json={})
        if response.status_code not in (401, 403):
            exposed.append((method, path, response.status_code))
    assert exposed == []


def test_pending_device_cannot_use_transfer_routes(
    client: TestClient, services: AppServices
) -> None:
    _join(client, services, approve=False)
    response = client.post("/api/v1/transfers", json={"filename": "a.txt", "size": 1})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "DEVICE_PENDING"


def test_admin_routes_need_both_loopback_and_token(
    make_client: Callable[..., TestClient], services: AppServices
) -> None:
    phone_with_token = make_client("192.168.1.50", {ADMIN_HEADER: services.admin_token})
    loopback_without_token = make_client("127.0.0.1")
    loopback_wrong_token = make_client("127.0.0.1", {ADMIN_HEADER: "devine"})
    for client in (phone_with_token, loopback_without_token, loopback_wrong_token):
        response = client.get("/api/v1/devices")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "ADMIN_FORBIDDEN"


def test_device_token_of_revoked_phone_is_refused(
    client: TestClient, services: AppServices
) -> None:
    _join(client, services)
    assert client.get("/api/v1/transfers").status_code == 200
    services.pairing.revoke(services.pairing.list_devices()[0].id)
    response = client.get("/api/v1/transfers")
    assert response.status_code == 401


def test_errors_never_echo_secrets(client: TestClient, services: AppServices) -> None:
    info = services.pairing.current_pairing()
    response = client.post(
        "/api/v1/sessions/join",
        json={
            "session_id": info.session_id,
            "secret": "secret-errone-a-ne-pas-renvoyer",
            "display_name": "Pixel",
            "platform": "android",
        },
    )
    assert response.status_code == 401
    assert "secret-errone" not in response.text
    assert info.secret not in response.text


# ----------------------------------------------------------------- DNS rebinding
def test_dns_rebinding_host_is_refused(app: FastAPI) -> None:
    with TestClient(
        app, base_url="http://site-malveillant.example:8765", client=("192.168.1.50", 50000)
    ) as attacker:
        response = attacker.get("/api/v1/health")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "HOST_NOT_ALLOWED"
        assert response.headers["x-content-type-options"] == "nosniff"
        # Même origine « apparente » pour le navigateur : le contrôle Origin ne suffit pas.
        with (
            pytest.raises(WebSocketDisconnect),
            attacker.websocket_connect(
                "ws://site-malveillant.example:8765/ws",
                headers={"Origin": "http://site-malveillant.example:8765"},
            ) as ws,
        ):
            ws.receive_json()


def test_ip_and_localhost_hosts_are_served(app: FastAPI) -> None:
    for base in ("http://192.168.1.14:8765", "http://127.0.0.1:8765", "http://localhost:8765"):
        with TestClient(app, base_url=base, client=("127.0.0.1", 50000)) as client:
            assert client.get("/api/v1/health").status_code == 200


# ----------------------------------------------------------------- ressources bornées
def _create(client: TestClient, name: str, size: int) -> Response:
    return client.post("/api/v1/transfers", json={"filename": name, "size": size})


@pytest.fixture
def settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"max_active_uploads_per_device": 2})


def test_active_uploads_per_phone_are_capped(client: TestClient, services: AppServices) -> None:
    _join(client, services)
    for name in ("a.bin", "b.bin"):
        assert _create(client, name, 10).status_code == 201
    third = client.post("/api/v1/transfers", json={"filename": "c.bin", "size": 10})
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "TOO_MANY_ACTIVE_TRANSFERS"

    # Une place se libère dès qu'un envoi est annulé.
    first = client.get("/api/v1/transfers").json()[0]["id"]
    client.post(f"/api/v1/transfers/{first}/cancel")
    assert _create(client, "c.bin", 10).status_code == 201


def test_free_space_accounts_for_other_unfinished_uploads(
    client: TestClient, services: AppServices, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deux envois de 60 octets ne peuvent pas tenir ensemble dans 100 octets libres."""
    monkeypatch.setattr(files.shutil, "disk_usage", lambda _: DiskUsage(1000, 900, 100))
    _join(client, services)
    first = client.post("/api/v1/transfers", json={"filename": "a.bin", "size": 60})
    assert first.status_code == 201
    second = client.post("/api/v1/transfers", json={"filename": "b.bin", "size": 60})
    assert second.status_code == 507
    assert second.json()["error"]["code"] == "INSUFFICIENT_DISK_SPACE"

    client.post(f"/api/v1/transfers/{first.json()['id']}/cancel")
    assert _create(client, "b.bin", 60).status_code == 201
