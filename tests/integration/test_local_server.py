"""LocalServer sur vrais sockets : redémarrage sur nouvelle adresse (FR-003), aide (§3.3)."""

import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from localdrop.core.config import Settings
from localdrop.domain.devices.models import Platform
from localdrop.infrastructure.network.interfaces import AddressCandidate
from localdrop.server import LocalServer, connection_help
from localdrop.services.container import AppServices, build_services

pytestmark = pytest.mark.integration

SECOND_LOOPBACK = "127.0.0.2"  # simule l'adresse d'un point d'accès activé après le lancement


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _can_bind(ip: str) -> bool:
    try:
        with socket.socket() as sock:
            sock.bind((ip, 0))
    except OSError:
        return False
    return True


class Harness:
    def __init__(self, tmp_path: Path, help_delay: float = 0) -> None:
        self.addresses: list[AddressCandidate] = []
        self.output: list[str] = []
        self.settings = Settings(
            data_dir=tmp_path / "data",
            receive_dir=tmp_path / "recus",
            web_dist_dir=None,
            port=_free_port(),
            network_poll_seconds=0,  # le test déclenche lui-même la détection
            maintenance_interval_minutes=0,
            persistence="memory",
            join_help_delay_seconds=help_delay,
        )
        self.services: AppServices = build_services(
            self.settings, address_provider=lambda: list(self.addresses)
        )
        self.server = LocalServer(self.settings, self.services, output=self.output.append)
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def start(self) -> None:
        self.thread.start()
        assert self.server.started.wait(10), "le serveur n'a pas démarré"

    def stop(self) -> None:
        self.server.stop()
        self.thread.join(10)
        self.services.close()

    def health(self, ip: str) -> int:
        return httpx.get(f"http://{ip}:{self.settings.port}/api/v1/health", timeout=2).status_code


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[Harness]:
    h = Harness(tmp_path)
    yield h
    h.stop()


@pytest.mark.skipif(not _can_bind(SECOND_LOOPBACK), reason="127.0.0.2 indisponible")
def test_FR_003_new_address_is_served_after_automatic_restart(harness: Harness) -> None:
    harness.start()
    assert harness.health("127.0.0.1") == 200
    # Non écoutée : refus ou expiration selon l'OS (Windows laisse expirer sur 127.0.0.2).
    with pytest.raises(httpx.TransportError):
        harness.health(SECOND_LOOPBACK)

    # Le point d'accès apparaît : la surveillance réseau le détecte.
    harness.addresses = [AddressCandidate(0, SECOND_LOOPBACK, "Point d'accès")]
    harness.server.started.clear()
    harness.services.network.refresh()

    deadline = time.monotonic() + 15
    while not (harness.server.restarts == 1 and harness.server.started.is_set()):
        assert time.monotonic() < deadline, "pas de redémarrage"
        time.sleep(0.05)

    assert harness.health(SECOND_LOOPBACK) == 200
    assert harness.health("127.0.0.1") == 200
    assert any("Réseau modifié" in line for line in harness.output)
    assert sum("=== LocalDrop ===" in line for line in harness.output) == 2  # QR réaffiché
    assert SECOND_LOOPBACK in harness.output[-1]


def test_join_help_shown_when_no_phone_shows_up(tmp_path: Path) -> None:
    h = Harness(tmp_path, help_delay=0.3)
    h.addresses = [AddressCandidate(1, "127.0.0.1", "Wi-Fi")]
    try:
        h.start()
        deadline = time.monotonic() + 5
        while not any("Aucun téléphone" in line for line in h.output):
            assert time.monotonic() < deadline, "aide non affichée"
            time.sleep(0.05)
    finally:
        h.stop()


def test_join_help_not_shown_once_a_phone_scanned(tmp_path: Path) -> None:
    h = Harness(tmp_path, help_delay=0.5)
    h.addresses = [AddressCandidate(1, "127.0.0.1", "Wi-Fi")]
    try:
        h.start()
        info = h.services.pairing.current_pairing()
        h.services.pairing.join(
            session_id=info.session_id,
            secret=info.secret,
            display_name="Pixel",
            platform=Platform.ANDROID,
            client_ip="192.168.1.50",
        )
        time.sleep(1)
        assert not any("Aucun téléphone" in line for line in h.output)
    finally:
        h.stop()


def test_help_text_mentions_hotspot_test_url_and_public_profile(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    h.addresses = [AddressCandidate(1, "192.168.1.7", "Wi-Fi")]
    h.services.network.refresh_quietly()
    text = connection_help(h.settings, h.services, {"Wi-Fi": "Public"})
    h.services.close()
    assert f"http://192.168.1.7:{h.settings.port}/api/v1/health" in text
    assert "point d'accès mobile" in text
    assert "« Public »" in text
    assert "« Public »" not in connection_help(h.settings, h.services, {"Wi-Fi": "Private"})
