"""Pause, reprise et redémarrage du serveur vus par l'API, sur SQLite (FR-026, §9.2-7)."""

import hashlib
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from localdrop.core.config import Settings
from localdrop.infrastructure.network.interfaces import AddressCandidate
from localdrop.main import create_app
from localdrop.services.container import build_services

pytestmark = pytest.mark.integration
PHONE = ("192.168.1.50", 50000)
SERVER = "http://192.168.1.14:8765"
CHUNK = 64 * 1024
DATA = os.urandom(CHUNK * 2 + 321)
PARTS = [DATA[i : i + CHUNK] for i in range(0, len(DATA), CHUNK)]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        receive_dir=tmp_path / "recus",
        web_dist_dir=None,
        chunk_size=CHUNK,
        network_poll_seconds=0,
        free_space_margin=0,
        persistence="sqlite",
    )


@contextmanager
def running_server(settings: Settings) -> Iterator[tuple[TestClient, object]]:
    """Un « processus » LocalDrop : services + application, fermés à la sortie."""
    services = build_services(
        settings, address_provider=lambda: [AddressCandidate(1, "192.168.1.14", "Wi-Fi")]
    )
    try:
        with TestClient(create_app(settings, services), client=PHONE, base_url=SERVER) as client:
            yield client, services
    finally:
        services.close()


def _pair(client: TestClient, services: object) -> str:
    pairing = services.pairing  # type: ignore[attr-defined]
    info = pairing.current_pairing()
    joined = client.post(
        "/api/v1/sessions/join",
        json={"session_id": info.session_id, "secret": info.secret, "display_name": "Pixel"},
    ).json()
    pairing.approve(joined["device_id"])
    return str(joined["device_token"])


def _put(client: TestClient, tid: str, index: int):  # type: ignore[no-untyped-def]
    return client.put(
        f"/api/v1/transfers/{tid}/chunks/{index}",
        content=PARTS[index],
        headers={"X-Chunk-SHA256": sha(PARTS[index])},
    )


def test_FR_026_pause_then_resume(settings: Settings) -> None:
    with running_server(settings) as (client, services):
        client.headers["Authorization"] = f"Bearer {_pair(client, services)}"
        tid = client.post(
            "/api/v1/transfers", json={"filename": "a.bin", "size": len(DATA)}
        ).json()["id"]
        _put(client, tid, 0)

        assert client.post(f"/api/v1/transfers/{tid}/pause").json()["status"] == "paused"
        refused = _put(client, tid, 1)
        assert refused.status_code == 409
        assert refused.json()["error"]["code"] == "TRANSFER_PAUSED"

        resumed = client.post(f"/api/v1/transfers/{tid}/resume")
        assert resumed.json()["status"] == "transferring"
        assert client.post(f"/api/v1/transfers/{tid}/resume").status_code == 200  # idempotent

        for index in (1, 2):
            assert _put(client, tid, index).status_code == 200
        done = client.post(f"/api/v1/transfers/{tid}/complete", json={"sha256": sha(DATA)})
        assert done.json()["status"] == "completed"
        assert client.post(f"/api/v1/transfers/{tid}/resume").status_code == 409


def test_FR_026_phone_resumes_after_pc_restart(settings: Settings) -> None:
    with running_server(settings) as (client, services):
        token = _pair(client, services)
        client.headers["Authorization"] = f"Bearer {token}"
        tid = client.post(
            "/api/v1/transfers", json={"filename": "film.mp4", "size": len(DATA)}
        ).json()["id"]
        _put(client, tid, 0)
        _put(client, tid, 2)

    # --- le PC redémarre : même base, nouveau processus
    with running_server(settings) as (client, _):
        client.headers["Authorization"] = f"Bearer {token}"  # le jeton du téléphone reste valable
        assert client.get("/api/v1/sessions/status").json()["status"] == "connected"

        state = client.get(f"/api/v1/transfers/{tid}").json()
        assert state["status"] == "paused"
        assert state["received_bytes"] == len(PARTS[0]) + len(PARTS[2])
        assert client.get(f"/api/v1/transfers/{tid}/chunks").json()["received"] == [0, 2]

        client.post(f"/api/v1/transfers/{tid}/resume")
        assert _put(client, tid, 1).status_code == 200  # seul le bloc manquant
        done = client.post(f"/api/v1/transfers/{tid}/complete", json={"sha256": sha(DATA)})
        assert done.json()["status"] == "completed"

    assert (settings.receive_dir / "film.mp4").read_bytes() == DATA
