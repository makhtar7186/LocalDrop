"""Bout en bout sur vrais sockets (phase 10, §16.3 automatisable).

Un vrai serveur LocalDrop (Uvicorn, SQLite, disque) tourne dans un thread comme dans
l'application desktop ; ``PhoneClient`` joue le téléphone en HTTP brut. Seul le lien
radio (Wi-Fi, point d'accès) et les navigateurs mobiles restent à valider à la main
(docs/testing/e2e-matrix.md).
"""

import socket
from collections.abc import Iterator
from pathlib import Path

import pytest

from localdrop.bench import (
    ApiError,
    PhoneClient,
    RunningServer,
    bench_settings,
    file_sha256,
    running_server,
    write_random_file,
)
from localdrop.core.config import Settings

pytestmark = pytest.mark.e2e

CHUNK = 64 * 1024


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return bench_settings(tmp_path, CHUNK)


@pytest.fixture
def server(settings: Settings) -> Iterator[RunningServer]:
    with running_server(settings) as running:
        yield running


@pytest.fixture
def phone(server: RunningServer) -> Iterator[PhoneClient]:
    client = server.paired_phone("Pixel e2e")
    yield client
    client.close()


def test_round_trip_with_unicode_names_collision_and_range_resume(
    server: RunningServer, phone: PhoneClient, tmp_path: Path
) -> None:
    """Téléphone -> PC (2 fois le même nom), puis PC -> téléphone en deux morceaux."""
    source = write_random_file(tmp_path / "source.bin", CHUNK * 3 + 777)
    name = "Vidéo d'été 🎉 Ünïcødé.mp4"

    first = phone.upload(source, name)
    second = phone.upload(source, name)
    assert first["status"] == second["status"] == "completed"
    received = sorted(p.name for p in server.settings.receive_dir.iterdir() if p.is_file())
    assert received == ["Vidéo d'été 🎉 Ünïcødé (1).mp4", "Vidéo d'été 🎉 Ünïcødé.mp4"]
    for published in received:
        assert file_sha256(server.settings.receive_dir / published) == file_sha256(source)

    offered = server.services.downloads.offer(source, str(phone.device_id))
    target = tmp_path / "telecharge.bin"
    split = CHUNK + 5
    assert phone.download(offered.id, target, byte_range=f"bytes=0-{split - 1}") == 206
    assert phone.download(offered.id, target, byte_range=f"bytes={split}-") == 206
    assert file_sha256(target) == file_sha256(source)
    assert phone.confirm(offered.id)["status"] == "completed"


def test_server_restart_mid_upload_only_missing_chunks_are_sent(
    settings: Settings, tmp_path: Path
) -> None:
    """FR-026, §16.4 : redémarrage du PC en plein envoi, reprise sans renvoyer l'acquis."""
    source = write_random_file(tmp_path / "gros.bin", CHUNK * 5)
    first = RunningServer(settings).start()
    try:
        phone = first.paired_phone()
        transfer = phone.create_upload("gros.bin", CHUNK * 5)
        phone.send_chunks(transfer, source, [0, 1, 3])
    finally:
        first.stop()  # arrêt du PC (port libéré)

    with running_server(settings) as second:  # même port, même base
        status = phone.request("GET", f"/api/v1/transfers/{transfer['id']}").json()
        assert status["status"] == "paused"
        phone.request("POST", f"/api/v1/transfers/{transfer['id']}/resume")
        received = phone.received_chunks(transfer["id"])
        assert received == [0, 1, 3]

        missing = [i for i in range(transfer["total_chunks"]) if i not in received]
        assert phone.send_chunks(transfer, source, missing) == [2, 4]
        done = phone.complete(transfer["id"], file_sha256(source))
        assert done["status"] == "completed"
        assert file_sha256(second.settings.receive_dir / "gros.bin") == file_sha256(source)
        phone.close()


def test_connection_cut_in_the_middle_of_a_chunk_is_not_recorded(
    server: RunningServer, phone: PhoneClient, tmp_path: Path
) -> None:
    """Perte du réseau pendant un bloc : rien n'est confirmé, le bloc se renvoie ensuite."""
    source = write_random_file(tmp_path / "coupe.bin", CHUNK * 2)
    transfer = phone.create_upload("coupe.bin", CHUNK * 2)
    chunk = source.read_bytes()[:CHUNK]

    with socket.create_connection(("127.0.0.1", server.settings.port), timeout=5) as raw:
        raw.sendall(
            (
                f"PUT /api/v1/transfers/{transfer['id']}/chunks/0 HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{server.settings.port}\r\n"
                f"Authorization: Bearer {phone.token}\r\n"
                f"X-Chunk-SHA256: {'0' * 64}\r\n"
                f"Content-Length: {CHUNK}\r\n\r\n"
            ).encode()
            + chunk[: CHUNK // 3]
        )
    # Coupure franche : le serveur ne doit rien avoir enregistré.
    assert phone.received_chunks(transfer["id"]) == []

    phone.send_chunks(transfer, source)
    assert phone.complete(transfer["id"], file_sha256(source))["status"] == "completed"


def test_revoked_phone_is_cut_off_immediately(server: RunningServer, phone: PhoneClient) -> None:
    assert phone.request("GET", "/api/v1/transfers").status == 200
    server.services.pairing.revoke(str(phone.device_id))
    with pytest.raises(ApiError) as exc:
        phone.request("GET", "/api/v1/transfers")
    assert exc.value.status == 401


def test_disk_full_is_reported_clearly(tmp_path: Path) -> None:
    """§16.3 « espace disque insuffisant » : refus explicite dès la création."""
    huge_margin = bench_settings(tmp_path, CHUNK).model_copy(update={"free_space_margin": 1 << 60})
    with running_server(huge_margin) as server:
        phone = server.paired_phone()
        with pytest.raises(ApiError) as exc:
            phone.create_upload("film.mkv", 10)
        assert exc.value.status == 507
        assert exc.value.code == "INSUFFICIENT_DISK_SPACE"
        phone.close()


def test_dns_rebinding_is_refused_on_the_real_server(server: RunningServer) -> None:
    with socket.create_connection(("127.0.0.1", server.settings.port), timeout=5) as raw:
        raw.sendall(
            b"GET /api/v1/health HTTP/1.1\r\nHost: site-malveillant.example\r\n"
            b"Connection: close\r\n\r\n"
        )
        answer = b""
        while block := raw.recv(4096):  # en-têtes et corps peuvent arriver séparément
            answer += block
    assert answer.startswith(b"HTTP/1.1 400")
    assert b"HOST_NOT_ALLOWED" in answer
