import tomllib

import pytest

import localdrop
from localdrop.core.paths import resource_root


@pytest.mark.unit
def test_package_version_matches_pyproject() -> None:
    """Une seule version : celle du paquet, reprise par l'exécutable Windows."""
    pyproject = tomllib.loads((resource_root() / "pyproject.toml").read_text(encoding="utf-8"))
    assert localdrop.__version__ == pyproject["project"]["version"]
