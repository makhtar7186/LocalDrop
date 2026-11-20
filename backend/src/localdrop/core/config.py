"""Configuration centralisée de LocalDrop.

Toutes les valeurs sont surchargeables par variables d'environnement préfixées
``LOCALDROP_`` (ex. ``LOCALDROP_PORT=9000``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from localdrop.core.paths import default_data_dir, default_receive_dir, default_web_dist_dir

MIB = 1024 * 1024

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

    # Réseau (§8.1, §12.2-11)
    lan_enabled: bool = True  # lier aussi les IPv4 privées détectées (sinon loopback seul)
    allow_public_clients: bool = False  # refuser les clients hors réseaux privés
    network_poll_seconds: float = Field(default=5.0, ge=0)  # 0 = surveillance désactivée
    excluded_interface_patterns: tuple[str, ...] | None = None  # None = liste par défaut

    # Sessions et appairage (§8.2, §12.2)
    session_ttl_hours: float = Field(default=12, gt=0)
    pairing_secret_ttl_seconds: int = Field(default=300, ge=30)
    join_max_attempts: int = Field(default=10, ge=1)
    join_window_seconds: int = Field(default=60, ge=1)

    # Journalisation
    log_level: LogLevel = "INFO"
    log_max_bytes: int = Field(default=5 * MIB, ge=64 * 1024)
    log_backup_count: int = Field(default=5, ge=1)

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
