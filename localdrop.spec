# -*- mode: python ; coding: utf-8 -*-
"""Exécutable Windows de LocalDrop (PyInstaller, mode onedir, fenêtré). ADR-008.

Construction complète (web, tests, exécutable, autotest, archive) :
    .venv/Scripts/python scripts/build_windows.py
Exécutable seul :
    .venv/Scripts/pyinstaller localdrop.spec --noconfirm --clean

Ressources embarquées (résolues par backend/src/localdrop/core/paths.py) :
    web/            build de l'interface mobile (apps/web/dist)
    migrations/     scripts Alembic, copiés tels quels (chargés depuis le disque)
    localdrop.ico   icône de la fenêtre et de la barre des tâches
"""

import re
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

ROOT = Path(SPECPATH)  # noqa: F821 - fourni par PyInstaller
WEB_DIST = ROOT / "apps" / "web" / "dist"
ICON = ROOT / "packaging" / "localdrop.ico"

if not (WEB_DIST / "index.html").is_file():
    sys.exit("Interface web non compilée : npm --prefix apps/web run build")

VERSION = re.search(
    r'^__version__ = "([^"]+)"',
    (ROOT / "backend" / "src" / "localdrop" / "__init__.py").read_text(encoding="utf-8"),
    re.MULTILINE,
).group(1)
NUMERIC = tuple(int(n) for n in re.findall(r"\d+", VERSION)[:3]) + (0,)


def tree(source: Path, target: str) -> list[tuple[str, str]]:
    """Copie récursive sans caches Python."""
    pairs = []
    for path in sorted(source.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            pairs.append((str(path), str(Path(target) / path.parent.relative_to(source))))
    return pairs


datas = tree(WEB_DIST, "web") + tree(ROOT / "migrations", "migrations") + [(str(ICON), ".")]

hiddenimports = (
    collect_submodules("localdrop")
    + collect_submodules("localdrop_desktop")
    # Uvicorn choisit ses implémentations à l'exécution (« auto ») : tout embarquer.
    + collect_submodules("uvicorn")
    # Alembic charge env.py et les migrations depuis le disque : leurs imports ne sont
    # pas visibles à l'analyse.
    + collect_submodules("alembic")
    + ["sqlalchemy.dialects.sqlite", "logging.config"]
)

# Modules lourds jamais utilisés (outils de développement, modules Qt non importés).
excludes = [
    "tkinter",
    "pytest",
    "_pytest",
    "hypothesis",
    "mypy",
    "IPython",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.Qt3DCore",
    "PySide6.QtMultimedia",
    "PySide6.QtPdf",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtBluetooth",
    "PySide6.QtPositioning",
    "PySide6.QtSql",
    "PySide6.QtTest",
]

version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=NUMERIC, prodvers=NUMERIC),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040C04B0",  # français, Unicode
                    [
                        StringStruct("CompanyName", "LocalDrop"),
                        StringStruct("FileDescription", "LocalDrop - partage PC <-> smartphone"),
                        StringStruct("FileVersion", VERSION),
                        StringStruct("InternalName", "LocalDrop"),
                        StringStruct("OriginalFilename", "LocalDrop.exe"),
                        StringStruct("ProductName", "LocalDrop"),
                        StringStruct("ProductVersion", VERSION),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [0x040C, 1200])]),
    ],
)

a = Analysis(  # noqa: F821
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT / "backend" / "src"), str(ROOT / "apps" / "desktop" / "src")],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LocalDrop",
    icon=str(ICON),
    version=version_info,
    console=False,  # application fenêtrée : sys.stdout/sys.stderr valent None
    upx=False,  # UPX multiplie les faux positifs antivirus
    debug=False,
    strip=False,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    name="LocalDrop",
    upx=False,
    strip=False,
)
