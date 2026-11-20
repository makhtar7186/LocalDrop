"""Configuration centralisée de LocalDrop.

Toutes les valeurs sont surchargeables par variables d'environnement préfixées
``LOCALDROP_`` (ex. ``LOCALDROP_PORT=9000``).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from localdrop.core.paths import default_data_dir, default_receive_dir, default_web_dist_dir

MIB = 1024 * 1024

logger = logging.getLogger(__name__)

SETTINGS_FILENAME = "settings.json"
ENV_PREFIX = "LOCALDROP_"

# Paramètres modifiables depuis l'écran Paramètres (§14.2) et persistés.
USER_EDITABLE: tuple[str, ...] = (
    "receive_dir",
    "port",
    "chunk_size",
    "max_concurrent_transfers",
    "temp_retention_hours",
    "session_ttl_hours",
    "history_retention_days",
    "lan_enabled",
)

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LOCALDROP_", extra="ignore")

    # Serveur
    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1024, le=65535)
    debug: bool = False

    # Emplacements
    data_dir: Path = Field(default_factory=default_data_dir)
    receive_dir: Path = Field(default_factory=default_receive_dir)
    web_dist_dir: Path | None = Field(default_factory=default_web_dist_dir)

    # Transferts (§5.1, §9.1) : valeurs initiales à valider par benchmark
    chunk_size: int = Field(default=4 * MIB, ge=64 * 1024, le=64 * MIB)
    max_concurrent_transfers: int = Field(default=2, ge=1, le=8)
    temp_retention_hours: int = Field(default=24, ge=1)
    max_file_size: int | None = Field(default=None, ge=0)  # None = limité par le disque
    download_ticket_ttl_seconds: int = Field(default=900, ge=30)  # liens de téléchargement
    free_space_margin: int = Field(default=64 * MIB, ge=0)  # réserve laissée libre sur le disque
    # Plafond d'envois non terminés par téléphone (audit phase 10 : épuisement de ressources)
    max_active_uploads_per_device: int = Field(default=32, ge=1)

    # Maintenance (FR-035, §13.3)
    maintenance_interval_minutes: float = Field(default=15, ge=0)  # 0 = au démarrage seulement
    history_retention_days: float | None = Field(default=30, gt=0)  # None = conservé sans limite
    orphan_grace_minutes: float = Field(default=60, ge=0)

    # Réseau (§8.1, §12.2-11)
    lan_enabled: bool = True  # lier aussi les IPv4 privées détectées (sinon loopback seul)
    allow_public_clients: bool = False  # refuser les clients hors réseaux privés
    network_poll_seconds: float = Field(default=5.0, ge=0)  # 0 = surveillance désactivée
    join_help_delay_seconds: float = Field(default=60, ge=0)  # aide si aucun téléphone (§3.3)
    excluded_interface_patterns: tuple[str, ...] | None = None  # None = liste par défaut

    # Sessions et appairage (§8.2, §12.2)
    session_ttl_hours: float = Field(default=12, gt=0)
    pairing_secret_ttl_seconds: int = Field(default=300, ge=30)
    join_max_attempts: int = Field(default=10, ge=1)
    join_window_seconds: int = Field(default=60, ge=1)
    ws_auth_timeout_seconds: float = Field(default=5.0, gt=0)  # premier message WebSocket

    # Persistance (ADR-004) : "memory" réservé aux tests rapides
    persistence: Literal["sqlite", "memory"] = "sqlite"

    # Journalisation
    log_level: LogLevel = "INFO"
    log_max_bytes: int = Field(default=5 * MIB, ge=64 * 1024)
    log_backup_count: int = Field(default=5, ge=1)

    @property
    def settings_file(self) -> Path:
        return self.data_dir / SETTINGS_FILENAME

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def database_dir(self) -> Path:
        return self.data_dir / "database"

    @property
    def state_dir(self) -> Path:
        return self.data_dir / "state"

    @property
    def admin_token_file(self) -> Path:
        return self.state_dir / "admin.token"


def load_settings(**overrides: Any) -> Settings:
    """Paramètres effectifs : variables d'environnement > settings.json > défauts.

    Un fichier illisible ou une valeur invalide est ignoré (journalisé) : l'application
    doit toujours pouvoir démarrer.
    """
    base = Settings(**overrides)
    try:
        stored = json.loads(base.settings_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return base
    except (OSError, ValueError):
        logger.warning("Paramètres illisibles (%s) : valeurs par défaut", base.settings_file)
        return base
    if not isinstance(stored, dict):
        return base
    from_file = {
        key: value
        for key, value in stored.items()
        if key in USER_EDITABLE
        and key not in overrides
        and f"{ENV_PREFIX}{key.upper()}" not in os.environ
    }
    try:
        return Settings(**{**from_file, **overrides})
    except ValueError:
        logger.warning("Paramètres invalides dans %s : valeurs par défaut", base.settings_file)
        return base


def save_user_settings(settings: Settings, values: dict[str, Any]) -> Settings:
    """Valide puis enregistre les paramètres modifiables. Appliqués au prochain démarrage."""
    unknown = set(values) - set(USER_EDITABLE)
    if unknown:
        raise ValueError(f"Paramètres non modifiables : {sorted(unknown)}")
    validated = Settings(**{**settings.model_dump(), **values})  # lève si invalide
    stored: dict[str, Any] = {}
    if settings.settings_file.exists():
        try:
            loaded = json.loads(settings.settings_file.read_text(encoding="utf-8"))
            stored = loaded if isinstance(loaded, dict) else {}
        except (OSError, ValueError):
            stored = {}
    for key in values:
        value = getattr(validated, key)
        stored[key] = str(value) if isinstance(value, Path) else value
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    temporary = settings.settings_file.with_suffix(".tmp")
    temporary.write_text(json.dumps(stored, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(settings.settings_file)  # écriture atomique (fichier de config, pas un reçu)
    return validated
