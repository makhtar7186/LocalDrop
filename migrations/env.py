"""Environnement Alembic de LocalDrop.

- À l'exécution : l'application fournit sa connexion (``config.attributes["connection"]``).
- En ligne de commande : l'URL vient de ``sqlalchemy.url`` ou, à défaut, de Settings.
SQLite gère mal ALTER TABLE : ``render_as_batch=True``.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, engine_from_config, pool

from localdrop.infrastructure.database.models import Base

config = context.config
target_metadata = Base.metadata

if config.config_file_name is not None and config.attributes.get("connection") is None:
    fileConfig(config.config_file_name)


def _url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    from localdrop.core.config import Settings
    from localdrop.infrastructure.database.engine import database_url

    settings = Settings()
    settings.database_dir.mkdir(parents=True, exist_ok=True)
    return database_url(settings.database_dir)


def _run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    engine = engine_from_config(
        {"sqlalchemy.url": _url()}, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with engine.connect() as connection:
        _run(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
