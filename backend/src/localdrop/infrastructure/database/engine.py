"""Moteur SQLite (ADR-004) : métadonnées uniquement, durabilité forte."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

DATABASE_FILENAME = "localdrop.db"


def database_path(database_dir: Path) -> Path:
    return database_dir / DATABASE_FILENAME


def database_url(database_dir: Path) -> str:
    return f"sqlite:///{database_path(database_dir).as_posix()}"


def _casefold(value: str | None) -> str | None:
    return value.casefold() if value is not None else None


def _apply_pragmas(dbapi_connection: Any, _: Any) -> None:
    # lower() de SQLite ne connaît que l'ASCII : « Été » doit trouver « été ».
    dbapi_connection.create_function("casefold", 1, _casefold, deterministic=True)
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        # Un bloc confirmé au client doit survivre à une coupure de courant (§9.2-5).
        cursor.execute("PRAGMA synchronous=FULL")
    finally:
        cursor.close()


def make_engine(url: str) -> Engine:
    engine = create_engine(
        url,
        # Le serveur (threads de travail) et le desktop partagent le moteur.
        connect_args={"check_same_thread": False},
    )
    event.listen(engine, "connect", _apply_pragmas)
    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
