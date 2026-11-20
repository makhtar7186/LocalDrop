"""Résolution centralisée des chemins (mode source et mode PyInstaller).

Aucun autre module ne doit calculer de chemin à partir de ``__file__`` ou du
répertoire courant.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "LocalDrop"


def is_frozen() -> bool:
    """Vrai lorsque l'application s'exécute depuis un exécutable PyInstaller."""
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def resource_root() -> Path:
    """Racine des ressources embarquées (lecture seule)."""
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    # backend/src/localdrop/core/paths.py -> racine du dépôt
    return Path(__file__).resolve().parents[4]


def default_web_dist_dir() -> Path:
    """Emplacement du build de l'interface mobile."""
    if is_frozen():
        return resource_root() / "web"
    return resource_root() / "apps" / "web" / "dist"


def app_icon_path() -> Path:
    """Icône de l'application (fenêtre, barre des tâches, exécutable)."""
    if is_frozen():
        return resource_root() / "localdrop.ico"
    return resource_root() / "packaging" / "localdrop.ico"


def migrations_dir() -> Path:
    """Scripts Alembic, embarqués tels quels dans l'exécutable."""
    return resource_root() / "migrations"


def default_data_dir() -> Path:
    """Données d'exécution : base, logs, état (``%LOCALAPPDATA%\\LocalDrop``)."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / APP_DIR_NAME


def default_receive_dir() -> Path:
    """Dossier de réception par défaut (``%USERPROFILE%\\Downloads\\LocalDrop``)."""
    return Path.home() / "Downloads" / APP_DIR_NAME
