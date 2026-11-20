"""Chemins en mode exécutable PyInstaller (phase 11) : tout vient de sys._MEIPASS."""

import sys
from pathlib import Path

import pytest

from localdrop.core import paths

pytestmark = pytest.mark.unit


@pytest.fixture
def frozen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    bundle = tmp_path / "_internal"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    return bundle


def test_bundled_resources_are_resolved_from_meipass(frozen: Path) -> None:
    assert paths.is_frozen()
    assert paths.resource_root() == frozen
    assert paths.default_web_dist_dir() == frozen / "web"
    assert paths.migrations_dir() == frozen / "migrations"
    assert paths.app_icon_path() == frozen / "localdrop.ico"


def test_user_data_never_lives_in_the_bundle(
    frozen: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))
    assert paths.default_data_dir() == tmp_path / "AppData" / "Local" / "LocalDrop"
    assert not paths.default_data_dir().is_relative_to(frozen)
    assert not paths.default_receive_dir().is_relative_to(frozen)


def test_source_mode_resources_exist() -> None:
    """En développement, les mêmes fonctions désignent les fichiers du dépôt."""
    assert not paths.is_frozen()
    assert (paths.migrations_dir() / "env.py").is_file()
    assert paths.app_icon_path().is_file()
