"""Appairage de bout en bout via l'API (§16.2 : appairage, révocation)."""

from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from localdrop.api.deps import ADMIN_HEADER
from localdrop.services.container import AppServices

pytestmark = pytest.mark.integration


def _pairing_params(admin: TestClient) -> dict[str, str]:
    response = admin.get("/api/v1/admin/pairing")
    assert response.status_code == 200
    address = response.json()["addresses"][0]
    assert address["url"] == "http://192.168.1.14:8765"
    local = response.json()["loopback_pairing_url"]
    assert local.startswith("http://127.0.0.1:8765/#/join?")
    assert urlsplit(local).fragment == urlsplit(address["pairing_url"]).fragment
    fragment = urlsplit(address["pairing_url"]).fragment
    query = parse_qs(fragment.split("?", 1)[1])
    return {"session_id": query["s"][0], "secret": query["k"][0]}


def _join(client: TestClient, params: dict[str, str], **extra: Any) -> Any:
    body = {**params, "display_name": "Pixel 8", "platform": "android", **extra}
    return client.post("/api/v1/sessions/join", json=body)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_FR_010_to_013_full_pairing_flow(client: TestClient, admin: TestClient) -> None:
    params = _pairing_params(admin)

    joined = _join(client, params)
    assert joined.status_code == 201
    token = joined.json()["device_token"]
    device_id = joined.json()["device_id"]
    assert joined.json()["status"] == "pending"

    status = client.get("/api/v1/sessions/status", headers=_auth(token))
    assert status.status_code == 200
    assert status.json()["status"] == "pending"
    assert status.json()["server_name"]

    devices = admin.get("/api/v1/devices").json()
    assert [(d["id"], d["status"], d["client_ip"]) for d in devices] == [
        (device_id, "pending", "192.168.1.50")
    ]

    approved = admin.post("/api/v1/sessions/approve", json={"device_id": device_id})
    assert approved.status_code == 200
    assert approved.json()["status"] == "connected"
    assert client.get("/api/v1/sessions/status", headers=_auth(token)).json()["status"] == (
        "connected"
    )

    # Le QR Code utilisé ne peut pas servir une seconde fois.
    replay = _join(client, params)
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "PAIRING_SECRET_INVALID"

    revoked = admin.post("/api/v1/sessions/revoke", json={"device_id": device_id})
    assert revoked.json()["revoked"] == "device"
    after = client.get("/api/v1/sessions/status", headers=_auth(token))
    assert after.status_code == 401


def test_FR_011_rejected_device_gets_403(client: TestClient, admin: TestClient) -> None:
    joined = _join(client, _pairing_params(admin)).json()
    admin.post(
        "/api/v1/sessions/approve", json={"device_id": joined["device_id"], "approve": False}
    )
    response = client.get("/api/v1/sessions/status", headers=_auth(joined["device_token"]))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "DEVICE_REJECTED"


def test_closing_session_invalidates_everything(client: TestClient, admin: TestClient) -> None:
    params = _pairing_params(admin)
    joined = _join(client, params).json()
    closed = admin.post("/api/v1/sessions/revoke", json={})
    assert closed.json()["revoked"] == "session"
    assert (
        client.get("/api/v1/sessions/status", headers=_auth(joined["device_token"])).status_code
        == 401
    )
    assert _pairing_params(admin)["session_id"] != params["session_id"]


def test_status_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/api/v1/sessions/status")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_join_rejects_unknown_fields_and_bad_secret(client: TestClient, admin: TestClient) -> None:
    params = _pairing_params(admin)
    assert _join(client, params, is_admin=True).status_code == 422
    bad = _join(client, {**params, "secret": "faux"})
    assert bad.status_code == 401
    assert "faux" not in bad.text


@pytest.mark.parametrize(
    ("ip", "with_token"),
    [("192.168.1.50", True), ("127.0.0.1", False)],
    ids=["lan-avec-jeton", "loopback-sans-jeton"],
)
def test_admin_routes_require_loopback_and_token(
    make_client: Callable[..., TestClient], services: AppServices, ip: str, with_token: bool
) -> None:
    headers = {ADMIN_HEADER: services.admin_token} if with_token else {}
    caller = make_client(ip, headers)
    for method, path in [
        ("GET", "/api/v1/devices"),
        ("GET", "/api/v1/admin/pairing"),
        ("POST", "/api/v1/sessions/approve"),
        ("POST", "/api/v1/sessions/revoke"),
    ]:
        response = caller.request(method, path, json={"device_id": "x"})
        assert response.status_code == 403, path
        assert response.json()["error"]["code"] == "ADMIN_FORBIDDEN"


@pytest.mark.parametrize("ip", ["8.8.8.8", "100.65.90.44", "testclient"])
def test_clients_outside_private_networks_are_refused(
    make_client: Callable[..., TestClient], ip: str
) -> None:
    response = make_client(ip).get("/api/v1/health")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CLIENT_NOT_ALLOWED"
    assert response.headers["x-content-type-options"] == "nosniff"
