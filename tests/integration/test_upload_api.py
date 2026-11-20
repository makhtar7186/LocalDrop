"""Envoi téléphone -> PC par l'API (§9.2, §16.2 : envoi d'un bloc, finalisation)."""

import hashlib
import os
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from localdrop.core.config import Settings
from localdrop.services.container import AppServices

pytestmark = pytest.mark.integration


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def phone(client: TestClient, services: AppServices) -> TestClient:
    """Téléphone appairé et approuvé."""
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
    services.pairing.approve(joined["device_id"])
    client.headers["Authorization"] = f"Bearer {joined['device_token']}"
    return client


def _put(phone: TestClient, transfer_id: str, index: int, data: bytes, digest: str | None = None):  # type: ignore[no-untyped-def]
    return phone.put(
        f"/api/v1/transfers/{transfer_id}/chunks/{index}",
        content=data,
        headers={"X-Chunk-SHA256": digest or sha(data), "Content-Type": "application/octet-stream"},
    )


def test_FR_021_upload_in_chunks_with_interruption(phone: TestClient, settings: Settings) -> None:
    chunk = settings.chunk_size
    data = os.urandom(chunk * 2 + 1234)

    created = phone.post(
        "/api/v1/transfers", json={"filename": "vacances/été.mp4", "size": len(data)}
    )
    assert created.status_code == 201
    transfer = created.json()
    assert transfer["status"] == "waiting"
    assert transfer["total_chunks"] == 3
    assert transfer["chunk_size"] == chunk
    assert transfer["safe_filename"] == "été.mp4"
    tid = transfer["id"]

    # Envoi partiel puis « coupure » : le serveur indique les blocs manquants.
    assert _put(phone, tid, 2, data[2 * chunk :]).json()["status"] == "transferring"
    assert phone.get(f"/api/v1/transfers/{tid}/chunks").json()["received"] == [2]

    for index in (0, 1):
        ack = _put(phone, tid, index, data[index * chunk : (index + 1) * chunk])
        assert ack.status_code == 200
    resent = _put(phone, tid, 0, data[:chunk])
    assert resent.json()["already_received"] is True
    assert phone.get(f"/api/v1/transfers/{tid}").json()["received_bytes"] == len(data)

    done = phone.post(f"/api/v1/transfers/{tid}/complete", json={"sha256": sha(data)})
    assert done.status_code == 200
    assert done.json()["status"] == "completed"
    assert done.json()["sha256"] == sha(data)
    assert (settings.receive_dir / "été.mp4").read_bytes() == data

    again = phone.post(f"/api/v1/transfers/{tid}/complete", json={"sha256": sha(data)})
    assert again.status_code == 409


def test_pending_or_anonymous_devices_cannot_upload(
    client: TestClient, services: AppServices
) -> None:
    assert client.post("/api/v1/transfers", json={"filename": "a", "size": 1}).status_code == 401
    info = services.pairing.current_pairing()
    token = client.post(
        "/api/v1/sessions/join",
        json={"session_id": info.session_id, "secret": info.secret, "display_name": "x"},
    ).json()["device_token"]
    pending = client.post(
        "/api/v1/transfers",
        json={"filename": "a", "size": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert pending.status_code == 403
    assert pending.json()["error"]["code"] == "DEVICE_PENDING"


def test_chunk_validation_errors(phone: TestClient) -> None:
    tid = phone.post("/api/v1/transfers", json={"filename": "a.bin", "size": 10}).json()["id"]

    too_big = _put(phone, tid, 0, b"x" * 11)
    assert too_big.status_code == 413
    assert too_big.json()["error"]["code"] == "CHUNK_TOO_LARGE"

    wrong_hash = _put(phone, tid, 0, b"x" * 10, sha(b"y"))
    assert wrong_hash.status_code == 422
    assert wrong_hash.json()["error"]["code"] == "CHUNK_HASH_MISMATCH"

    bad_header = _put(phone, tid, 0, b"x" * 10, "pas-un-hash")
    assert bad_header.json()["error"]["code"] == "CHUNK_HASH_HEADER_INVALID"

    missing_header = phone.put(f"/api/v1/transfers/{tid}/chunks/0", content=b"x" * 10)
    assert missing_header.status_code == 422

    out_of_range = _put(phone, tid, 1, b"x")
    assert out_of_range.json()["error"]["code"] == "CHUNK_INDEX_OUT_OF_RANGE"

    assert phone.get(f"/api/v1/transfers/{tid}/chunks").json()["received"] == []


def test_FR_027_corrupted_file_is_not_published(phone: TestClient, settings: Settings) -> None:
    data = b"contenu"
    tid = phone.post("/api/v1/transfers", json={"filename": "doc.txt", "size": len(data)}).json()[
        "id"
    ]
    _put(phone, tid, 0, data)
    failed = phone.post(f"/api/v1/transfers/{tid}/complete", json={"sha256": sha(b"autre")})
    assert failed.json()["status"] == "failed"
    assert failed.json()["error_code"] == "FILE_HASH_MISMATCH"
    assert not (settings.receive_dir / "doc.txt").exists()


def test_FR_025_cancel(phone: TestClient) -> None:
    tid = phone.post("/api/v1/transfers", json={"filename": "a.bin", "size": 3}).json()["id"]
    assert phone.post(f"/api/v1/transfers/{tid}/cancel").json()["status"] == "cancelled"
    assert _put(phone, tid, 0, b"abc").status_code == 409


def test_transfer_of_another_device_is_invisible(
    phone: TestClient, make_client: Callable[..., TestClient], services: AppServices
) -> None:
    tid = phone.post("/api/v1/transfers", json={"filename": "a.bin", "size": 3}).json()["id"]
    info = services.pairing.current_pairing()
    other = make_client("192.168.1.77")
    joined = other.post(
        "/api/v1/sessions/join",
        json={"session_id": info.session_id, "secret": info.secret, "display_name": "Autre"},
    ).json()
    services.pairing.approve(joined["device_id"])
    other.headers["Authorization"] = f"Bearer {joined['device_token']}"

    assert other.get(f"/api/v1/transfers/{tid}").status_code == 404
    assert other.get("/api/v1/transfers").json() == []
    assert len(phone.get("/api/v1/transfers").json()) == 1


def test_admin_sees_all_transfers_with_final_path(
    phone: TestClient, admin: TestClient, settings: Settings
) -> None:
    tid = phone.post("/api/v1/transfers", json={"filename": "a.txt", "size": 2}).json()["id"]
    _put(phone, tid, 0, b"ok")
    phone.post(f"/api/v1/transfers/{tid}/complete", json={"sha256": sha(b"ok")})
    listed = admin.get("/api/v1/admin/transfers").json()
    assert listed[0]["status"] == "completed"
    assert Path(listed[0]["final_path"]) == (settings.receive_dir / "a.txt").resolve()
    assert phone.get("/api/v1/admin/transfers").status_code == 403
