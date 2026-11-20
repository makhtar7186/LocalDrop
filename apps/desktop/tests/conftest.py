"""Fixtures de l'application desktop (pytest-qt, rendu hors écran)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # aucune fenêtre réelle pendant les tests

import socket
from collections.abc import Iterator
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from localdrop.core.config import Settings
from localdrop.domain.devices.models import Device, Platform
from localdrop.infrastructure.network.interfaces import AddressCandidate
from localdrop.services.container import AppServices, build_services
from localdrop_desktop.controllers.app_controller import AppController


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        receive_dir=tmp_path / "recus",
        web_dist_dir=None,
        port=free_port(),
        network_poll_seconds=0,
        maintenance_interval_minutes=0,
        join_help_delay_seconds=0,
        persistence="memory",
    )


@pytest.fixture
def services(settings: Settings) -> Iterator[AppServices]:
    built = build_services(
        settings, address_provider=lambda: [AddressCandidate(1, "127.0.0.1", "Wi-Fi")]
    )
    yield built
    built.close()


class FolderSpy:
    def __init__(self) -> None:
        self.revealed: list[Path] = []

    def __call__(self, path: Path) -> None:
        self.revealed.append(path)


@pytest.fixture
def folders() -> FolderSpy:
    return FolderSpy()


@pytest.fixture
def controller(
    qtbot: QtBot, settings: Settings, services: AppServices, folders: FolderSpy
) -> Iterator[AppController]:
    ctrl = AppController(settings, services, open_folder=folders)
    yield ctrl
    ctrl.shutdown()


def join_phone(services: AppServices, name: str = "Pixel 8") -> Device:
    """Simule un téléphone qui vient de scanner le QR Code."""
    info = services.pairing.current_pairing()
    return services.pairing.join(
        session_id=info.session_id,
        secret=info.secret,
        display_name=name,
        platform=Platform.ANDROID,
        client_ip="192.168.1.50",
    ).device
