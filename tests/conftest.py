"""Fixtures partagées des tests d'intégration."""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from localdrop.api.deps import ADMIN_HEADER
from localdrop.core.config import Settings
from localdrop.infrastructure.network.interfaces import AddressCandidate
from localdrop.main import create_app
from localdrop.services.container import AppServices, build_services

PHONE_IP = "192.168.1.50"
PC_LAN_IP = "192.168.1.14"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Configuration isolée : chemins dans tmp_path, petits blocs, pas d'UI ni de sondage réseau."""
    return Settings(
        data_dir=tmp_path / "data",
        receive_dir=tmp_path / "received",
        web_dist_dir=None,
        chunk_size=64 * 1024,
        network_poll_seconds=0,
        free_space_margin=0,
    )


@pytest.fixture
def services(settings: Settings) -> AppServices:
    return build_services(
        settings,
        address_provider=lambda: [AddressCandidate(1, PC_LAN_IP, "Wi-Fi")],
    )


@pytest.fixture
def app(settings: Settings, services: AppServices) -> FastAPI:
    return create_app(settings, services)


@pytest.fixture
def make_client(app: FastAPI) -> Iterator[Callable[..., TestClient]]:
    """Fabrique de clients HTTP simulant une adresse source donnée."""
    clients: list[TestClient] = []

    def _make(ip: str = PHONE_IP, headers: dict[str, str] | None = None) -> TestClient:
        client = TestClient(app, client=(ip, 50000), headers=headers, raise_server_exceptions=False)
        client.__enter__()
        clients.append(client)
        return client

    yield _make
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    """Téléphone sur le réseau local."""
    return make_client(PHONE_IP)


@pytest.fixture
def admin(make_client: Callable[..., TestClient], services: AppServices) -> TestClient:
    """PC hôte : loopback + jeton admin."""
    return make_client("127.0.0.1", {ADMIN_HEADER: services.admin_token})
