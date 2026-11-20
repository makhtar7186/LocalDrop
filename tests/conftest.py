"""Fixtures partagées des tests d'intégration."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from localdrop.core.config import Settings
from localdrop.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Configuration isolée : tous les chemins dans tmp_path, petits blocs, pas d'UI web."""
    return Settings(
        data_dir=tmp_path / "data",
        receive_dir=tmp_path / "received",
        web_dist_dir=None,
        chunk_size=64 * 1024,
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
