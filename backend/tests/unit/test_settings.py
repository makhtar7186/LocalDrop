from pathlib import Path

import pytest
from pydantic import ValidationError

from localdrop.core.config import MIB, Settings


@pytest.mark.unit
def test_defaults_match_specification(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    settings = Settings()
    assert settings.host == "127.0.0.1"
    assert settings.port == 8765
    assert settings.chunk_size == 4 * MIB
    assert settings.max_concurrent_transfers == 2
    assert settings.temp_retention_hours == 24
    assert settings.data_dir == tmp_path / "LocalDrop"
    assert settings.logs_dir == tmp_path / "LocalDrop" / "logs"
    assert settings.receive_dir.parts[-2:] == ("Downloads", "LocalDrop")


@pytest.mark.unit
def test_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCALDROP_PORT", "9100")
    monkeypatch.setenv("LOCALDROP_CHUNK_SIZE", str(8 * MIB))
    settings = Settings()
    assert settings.port == 9100
    assert settings.chunk_size == 8 * MIB


@pytest.mark.unit
@pytest.mark.parametrize(
    ("field", "value"),
    [("port", 80), ("chunk_size", 1024), ("max_concurrent_transfers", 0)],
)
def test_out_of_range_values_are_rejected(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(**{field: value})
