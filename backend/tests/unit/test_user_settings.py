import json
from pathlib import Path

import pytest

from localdrop.core.config import Settings, load_settings, save_user_settings

pytestmark = pytest.mark.unit


@pytest.fixture
def base(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data")


def _write(settings: Settings, content: str) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.settings_file.write_text(content, encoding="utf-8")


def test_saved_values_are_loaded(base: Settings, tmp_path: Path) -> None:
    save_user_settings(base, {"port": 9100, "receive_dir": tmp_path / "Réception"})
    loaded = load_settings(data_dir=base.data_dir)
    assert loaded.port == 9100
    assert loaded.receive_dir == tmp_path / "Réception"
    stored = json.loads(base.settings_file.read_text(encoding="utf-8"))
    assert stored == {"port": 9100, "receive_dir": str(tmp_path / "Réception")}


def test_saving_merges_with_previous_values(base: Settings) -> None:
    save_user_settings(base, {"port": 9100})
    save_user_settings(base, {"lan_enabled": False})
    loaded = load_settings(data_dir=base.data_dir)
    assert (loaded.port, loaded.lan_enabled) == (9100, False)


def test_environment_wins_over_file(base: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    save_user_settings(base, {"port": 9100})
    monkeypatch.setenv("LOCALDROP_PORT", "9300")
    assert load_settings(data_dir=base.data_dir).port == 9300


@pytest.mark.parametrize(
    "content",
    ["{pas du json", "[1, 2]", '{"port": 80}', '{"chunk_size": "beaucoup"}'],
    ids=["json-invalide", "pas-un-objet", "port-hors-limites", "type-invalide"],
)
def test_broken_file_never_prevents_startup(base: Settings, content: str) -> None:
    _write(base, content)
    assert load_settings(data_dir=base.data_dir).port == 8765  # valeurs par défaut


def test_only_user_editable_keys_are_applied(base: Settings) -> None:
    _write(base, json.dumps({"port": 9100, "allow_public_clients": True, "host": "0.0.0.0"}))  # noqa: S104
    loaded = load_settings(data_dir=base.data_dir)
    assert loaded.port == 9100
    assert loaded.allow_public_clients is False  # jamais modifiable par fichier
    assert loaded.host == "127.0.0.1"


def test_save_validates_and_rejects_unknown_keys(base: Settings) -> None:
    with pytest.raises(ValueError, match="non modifiables"):
        save_user_settings(base, {"allow_public_clients": True})
    with pytest.raises(ValueError):
        save_user_settings(base, {"port": 80})
    assert not base.settings_file.exists()
