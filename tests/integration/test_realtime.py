"""WebSocket /ws (§8.5, §10.4, FR-012, FR-042)."""

import hashlib
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from localdrop.services.container import AppServices

pytestmark = pytest.mark.integration

# Starlette force « ws://testserver » pour un chemin relatif : Host doit être une IP.
WS_URL = "ws://192.168.1.14:8765/ws"


def _join(client: TestClient, services: AppServices, approve: bool = True) -> dict[str, str]:
    info = services.pairing.current_pairing()
    joined: dict[str, str] = client.post(
        "/api/v1/sessions/join",
        json={"session_id": info.session_id, "secret": info.secret, "display_name": "Pixel"},
    ).json()
    if approve:
        services.pairing.approve(joined["device_id"])
    return joined


@contextmanager
def _ws(client: TestClient, token: str) -> Iterator[WebSocketTestSession]:
    with client.websocket_connect(WS_URL) as ws:
        ws.send_json({"type": "auth", "token": token})
        ack = ws.receive_json()
        assert ack["type"] == "auth.ok", ack
        yield ws


def _next_event(ws: WebSocketTestSession, event_type: str) -> dict[str, Any]:
    """Prochain message du type demandé (les autres sont ignorés)."""
    while True:
        message: dict[str, Any] = ws.receive_json()
        if message["type"] == event_type:
            return message


def _assert_nothing_pending(ws: WebSocketTestSession) -> None:
    # Tous les messages sortants passent par la même file : le pong arrive après
    # tout événement déjà distribué.
    ws.send_json({"type": "ping"})
    assert ws.receive_json() == {"type": "pong"}


def test_FR_042_device_receives_its_events_in_order(
    client: TestClient, admin: TestClient, services: AppServices, tmp_path: Path
) -> None:
    joined = _join(client, services)
    source = tmp_path / "doc.pdf"
    source.write_bytes(b"x" * 10)

    with _ws(client, joined["device_token"]) as ws:
        admin.post(
            "/api/v1/admin/transfers/outgoing",
            json={"path": str(source), "device_id": joined["device_id"]},
        )
        event = _next_event(ws, "transfer.created")
        assert set(event) == {"id", "type", "ts", "data"}
        assert event["data"]["direction"] == "download"
        assert event["data"]["filename"] == "doc.pdf"
        _assert_nothing_pending(ws)


def test_upload_progress_is_pushed(client: TestClient, services: AppServices) -> None:
    joined = _join(client, services)
    client.headers["Authorization"] = f"Bearer {joined['device_token']}"
    data = b"a" * (64 * 1024 + 10)  # 2 blocs

    with _ws(client, joined["device_token"]) as ws:
        tid = client.post(
            "/api/v1/transfers", json={"filename": "v.mp4", "size": len(data)}
        ).json()["id"]
        for index, part in enumerate([data[: 64 * 1024], data[64 * 1024 :]]):
            client.put(
                f"/api/v1/transfers/{tid}/chunks/{index}",
                content=part,
                headers={"X-Chunk-SHA256": hashlib.sha256(part).hexdigest()},
            )
        client.post(
            f"/api/v1/transfers/{tid}/complete", json={"sha256": hashlib.sha256(data).hexdigest()}
        )

        types: list[str] = []
        while not types or types[-1] != "transfer.completed":
            message = ws.receive_json()
            if message["type"].startswith("transfer."):
                types.append(message["type"])
                assert message["data"]["transfer_id"] == tid
        assert types[0] == "transfer.created"
        assert "transfer.progress" in types
        progress = [t for t in types if t == "transfer.progress"]
        assert (
            1 <= len(progress) <= 2
        )  # limité en fréquence, mais le dernier bloc est toujours publié


def test_devices_only_see_their_own_events(
    client: TestClient,
    admin: TestClient,
    make_client: Callable[..., TestClient],
    services: AppServices,
    tmp_path: Path,
) -> None:
    mine = _join(client, services)
    other_client = make_client("192.168.1.77")
    other = _join(other_client, services)
    source = tmp_path / "secret.txt"
    source.write_text("confidentiel")

    with _ws(client, mine["device_token"]) as ws:
        admin.post(
            "/api/v1/admin/transfers/outgoing",
            json={"path": str(source), "device_id": other["device_id"]},
        )
        _assert_nothing_pending(ws)


def test_FR_011_pending_device_learns_approval_instantly(
    client: TestClient, admin: TestClient, services: AppServices
) -> None:
    joined = _join(client, services, approve=False)
    with _ws(client, joined["device_token"]) as ws:
        admin.post("/api/v1/sessions/approve", json={"device_id": joined["device_id"]})
        event = _next_event(ws, "device.connected")
        assert event["data"]["status"] == "connected"


def test_FR_013_revocation_closes_socket_immediately(
    client: TestClient, admin: TestClient, services: AppServices
) -> None:
    joined = _join(client, services)
    with _ws(client, joined["device_token"]) as ws:
        admin.post("/api/v1/sessions/revoke", json={"device_id": joined["device_id"]})
        assert _next_event(ws, "device.revoked")["data"]["device_id"] == joined["device_id"]
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        assert closed.value.code == 4401


@pytest.mark.parametrize(
    ("first_message", "code"),
    [
        ({"type": "auth", "token": "faux"}, 4401),
        ({"type": "hello"}, 4401),
        ({"type": "auth"}, 4401),
        ({"type": "auth", "admin_token": "x"}, 4403),  # admin depuis le LAN : refusé
    ],
)
def test_authentication_failures(
    client: TestClient, first_message: dict[str, str], code: int
) -> None:
    with client.websocket_connect(WS_URL) as ws:
        ws.send_json(first_message)
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == code


def test_authentication_must_be_fast(client: TestClient) -> None:
    with client.websocket_connect(WS_URL) as ws, pytest.raises(WebSocketDisconnect) as closed:
        ws.receive_json()  # aucun message d'authentification envoyé
    assert closed.value.code == 4408


def test_rejected_device_is_refused(
    client: TestClient, admin: TestClient, services: AppServices
) -> None:
    joined = _join(client, services, approve=False)
    admin.post(
        "/api/v1/sessions/approve", json={"device_id": joined["device_id"], "approve": False}
    )
    with client.websocket_connect(WS_URL) as ws:
        ws.send_json({"type": "auth", "token": joined["device_token"]})
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 4403


def test_cross_site_origin_is_refused(client: TestClient) -> None:
    with (
        pytest.raises(WebSocketDisconnect) as closed,
        client.websocket_connect(WS_URL, headers={"Origin": "http://site-malveillant.example"}),
    ):
        pass
    assert closed.value.code == 4403


def test_admin_sees_everything_from_loopback(
    client: TestClient, admin: TestClient, services: AppServices
) -> None:
    with admin.websocket_connect(WS_URL) as ws:
        ws.send_json({"type": "auth", "admin_token": services.admin_token})
        assert ws.receive_json()["data"]["role"] == "admin"
        joined = _join(client, services, approve=False)
        event = _next_event(ws, "device.pending")
        assert event["data"]["device_id"] == joined["device_id"]


def _device_status(admin: TestClient, device_id: str) -> str:
    return next(d["status"] for d in admin.get("/api/v1/devices").json() if d["id"] == device_id)


def _wait_for_status(admin: TestClient, device_id: str, expected: str) -> None:
    deadline = time.monotonic() + 5
    while _device_status(admin, device_id) != expected:
        assert time.monotonic() < deadline, f"statut attendu : {expected}"
        time.sleep(0.02)


def test_FR_012_presence_follows_websocket(
    client: TestClient, admin: TestClient, services: AppServices
) -> None:
    joined = _join(client, services)
    with _ws(client, joined["device_token"]):
        assert _device_status(admin, joined["device_id"]) == "connected"
    _wait_for_status(admin, joined["device_id"], "disconnected")

    # Toute requête authentifiée signale le retour de l'appareil.
    client.get("/api/v1/transfers", headers={"Authorization": f"Bearer {joined['device_token']}"})
    assert _device_status(admin, joined["device_id"]) == "connected"
