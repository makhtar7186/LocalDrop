"""Historique par l'API (FR-034)."""

import hashlib
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from localdrop.services.container import AppServices

pytestmark = pytest.mark.integration


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _approved(client: TestClient, services: AppServices) -> str:
    info = services.pairing.current_pairing()
    joined = client.post(
        "/api/v1/sessions/join",
        json={"session_id": info.session_id, "secret": info.secret, "display_name": "Tél"},
    ).json()
    services.pairing.approve(joined["device_id"])
    client.headers["Authorization"] = f"Bearer {joined['device_token']}"
    return str(joined["device_id"])


def _upload(client: TestClient, name: str, data: bytes, finish: bool = True) -> str:
    tid = str(
        client.post("/api/v1/transfers", json={"filename": name, "size": len(data)}).json()["id"]
    )
    client.put(
        f"/api/v1/transfers/{tid}/chunks/0", content=data, headers={"X-Chunk-SHA256": sha(data)}
    )
    if finish:
        client.post(f"/api/v1/transfers/{tid}/complete", json={"sha256": sha(data)})
    return tid


def test_FR_034_device_history_is_filtered_and_private(
    client: TestClient,
    admin: TestClient,
    make_client: Callable[..., TestClient],
    services: AppServices,
    tmp_path: Path,
) -> None:
    device_id = _approved(client, services)
    first = _upload(client, "Été.jpg", b"a")
    second = _upload(client, "notes.txt", b"b", finish=False)
    source = tmp_path / "Plan été.pdf"
    source.write_bytes(b"pdf")
    offered = admin.post(
        "/api/v1/admin/transfers/outgoing", json={"path": str(source), "device_id": device_id}
    ).json()["id"]

    other = make_client("192.168.1.77")
    _approved(other, services)
    _upload(other, "secret.txt", b"c")

    page = client.get("/api/v1/history").json()
    assert page["total"] == 3
    assert [t["id"] for t in page["items"]] == [offered, second, first]  # plus récent d'abord

    def ids(params: str) -> list[str]:
        return [t["id"] for t in client.get(f"/api/v1/history?{params}").json()["items"]]

    assert ids("direction=download") == [offered]
    assert ids("status=completed") == [first]
    assert ids("status=completed&status=transferring") == [second, first]
    assert ids("q=%C3%A9t%C3%A9") == [offered, first]  # « été »
    assert ids("limit=1&offset=1") == [second]

    assert client.get("/api/v1/history?limit=0").status_code == 422
    assert client.get("/api/v1/history?status=inconnu").status_code == 422
    assert client.get("/api/v1/admin/history").status_code == 403


def test_admin_history_spans_devices(
    client: TestClient,
    admin: TestClient,
    make_client: Callable[..., TestClient],
    services: AppServices,
) -> None:
    mine = _approved(client, services)
    _upload(client, "a.txt", b"a")
    other = make_client("192.168.1.77")
    _approved(other, services)
    _upload(other, "b.txt", b"b")

    page = admin.get("/api/v1/admin/history").json()
    assert page["total"] == 2
    assert {t["device_id"] for t in page["items"]} == {mine, page["items"][0]["device_id"]}
    only_mine = admin.get(f"/api/v1/admin/history?device_id={mine}").json()
    assert [t["safe_filename"] for t in only_mine["items"]] == ["a.txt"]
    assert only_mine["items"][0]["final_path"].endswith("a.txt")
