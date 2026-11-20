"""Migrations Alembic exécutées au démarrage, précédées d'une sauvegarde (§11.5, §17.3).

La configuration Alembic est construite par code : aucun alembic.ini n'est nécessaire
à l'exécution (mode PyInstaller compris).
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine

from localdrop.core.paths import migrations_dir
from localdrop.infrastructure.database.engine import database_path

logger = logging.getLogger(__name__)

BACKUPS_TO_KEEP = 5


def alembic_config(url: str | None = None) -> Config:
    """Configuration Alembic par code. Sans URL, l'appelant fournit sa connexion via
    ``config.attributes["connection"]`` (cas de l'application)."""
    config = Config()
    config.set_main_option("script_location", str(migrations_dir()))
    if url is not None:
        # ConfigParser interprète « % » : les chemins Windows encodés (C%3A) doivent l'échapper.
        config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def head_revision(config: Config) -> str | None:
    return ScriptDirectory.from_config(config).get_current_head()


def current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def backup_database(db_file: Path, backups_dir: Path, keep: int = BACKUPS_TO_KEEP) -> Path:
    """Copie cohérente de la base (API backup de SQLite, compatible WAL)."""
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    target = backups_dir / f"localdrop-{stamp}.db"
    source = sqlite3.connect(db_file)
    try:
        destination = sqlite3.connect(target)
        try:
            source.backup(destination)
        finally:
            destination.close()
    finally:
        source.close()
    for old in sorted(backups_dir.glob("localdrop-*.db"))[:-keep]:
        old.unlink(missing_ok=True)
    return target


def upgrade_database(engine: Engine, database_dir: Path) -> None:
    """Met la base au dernier schéma. Sauvegarde préalable si une base existante change."""
    database_dir.mkdir(parents=True, exist_ok=True)
    config = alembic_config()
    head = head_revision(config)
    current = current_revision(engine)
    if current == head:
        return

    db_file = database_path(database_dir)
    if current is not None and db_file.exists():
        backup = backup_database(db_file, database_dir / "backups")
        logger.info("Base sauvegardée avant migration : %s", backup.name)

    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    logger.info("Schéma de base de données : %s -> %s", current or "vide", head)
