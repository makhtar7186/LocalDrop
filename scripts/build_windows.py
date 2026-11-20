"""Construction de la version distribuable de LocalDrop (phase 11, ADR-008).

Étapes, chacune arrêtant tout en cas d'échec :
1. interface web : ``npm ci`` (avec --clean-web) puis ``npm run build`` ;
2. qualité : ruff, mypy, pytest, lint/typecheck/tests web (sauf --skip-checks) ;
3. exécutable : ``pyinstaller localdrop.spec --noconfirm --clean`` ;
4. autotest dans l'exécutable gelé (``LocalDrop.exe --self-test``) ;
5. test de fumée de l'application réelle (scripts/smoke_test_exe.py) ;
6. archive ``dist/LocalDrop-<version>-windows-x64.zip`` et son SHA-256.

Usage : ``.venv/Scripts/python scripts/build_windows.py [--skip-checks] [--clean-web]``
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv" / "Scripts"
DIST = ROOT / "dist"
APP_DIR = DIST / "LocalDrop"
EXE = APP_DIR / "LocalDrop.exe"
NPM = shutil.which("npm") or "npm"

# Fichiers ajoutés à côté de l'exécutable dans l'archive.
EXTRA_FILES = {
    ROOT / "docs" / "guide-utilisateur.md": "LISEZ-MOI.md",
}


def step(title: str) -> None:
    print(f"\n=== {title}", flush=True)


def run(*command: str | Path) -> None:
    printable = " ".join(str(c) for c in command)
    print(f"$ {printable}", flush=True)
    started = time.perf_counter()
    result = subprocess.run([str(c) for c in command], cwd=ROOT, check=False)  # noqa: S603
    if result.returncode != 0:
        sys.exit(f"Échec ({result.returncode}) : {printable}")
    print(f"  ({time.perf_counter() - started:.1f} s)", flush=True)


def version() -> str:
    sys.path.insert(0, str(ROOT / "backend" / "src"))
    from localdrop import __version__

    return __version__


def self_test() -> None:
    report = Path(tempfile.gettempdir()) / "localdrop-build-selftest.json"
    report.unlink(missing_ok=True)
    result = subprocess.run([str(EXE), f"--self-test={report}"], check=False)  # noqa: S603
    data = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
    for check in data.get("checks", []):
        mark = "✓" if check["ok"] else "✗"
        print(f"  {mark} {check['name']} ({check['seconds']} s)")
        if not check["ok"]:
            print(check["detail"])
    if result.returncode != 0 or not data.get("ok") or not data.get("frozen"):
        sys.exit(f"Autotest de l'exécutable en échec (rapport : {report})")


def make_archive(name: str) -> Path:
    archive = DIST / f"{name}.zip"
    archive.unlink(missing_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(APP_DIR.rglob("*")):
            if path.is_file():
                zf.write(path, Path("LocalDrop") / path.relative_to(APP_DIR))
        for source, target in EXTRA_FILES.items():
            zf.write(source, Path("LocalDrop") / target)
    return archive


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Construit la version distribuable.")
    parser.add_argument("--skip-checks", action="store_true", help="sans tests ni linters")
    parser.add_argument("--clean-web", action="store_true", help="npm ci avant le build web")
    args = parser.parse_args(argv)
    # Sortie redirigée (cp1252) : jamais d'erreur d'encodage sur ✓ ou un emoji.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    ver = version()
    print(f"LocalDrop {ver}")

    step("1. Interface web")
    if args.clean_web:
        run(NPM, "--prefix", "apps/web", "ci")
    run(NPM, "--prefix", "apps/web", "run", "build")

    if not args.skip_checks:
        step("2. Qualité et tests")
        run(VENV / "ruff", "check", ".")
        run(VENV / "ruff", "format", "--check", ".")
        run(VENV / "mypy")
        run(VENV / "pytest", "-q", "--tb=native")
        run(NPM, "--prefix", "apps/web", "run", "lint")
        run(NPM, "--prefix", "apps/web", "run", "typecheck")
        run(NPM, "--prefix", "apps/web", "test")

    step("3. Exécutable (PyInstaller)")
    run(VENV / "pyinstaller", "localdrop.spec", "--noconfirm", "--clean")

    step("4. Autotest dans l'exécutable")
    self_test()

    step("5. Test de fumée de l'application")
    run(VENV / "python", "scripts/smoke_test_exe.py", EXE)

    step("6. Archive")
    archive = make_archive(f"LocalDrop-{ver}-windows-x64")
    digest = sha256(archive)
    (archive.parent / f"{archive.name}.sha256").write_text(
        f"{digest}  {archive.name}\n", encoding="utf-8"
    )
    size = archive.stat().st_size / 1024 / 1024
    print(f"  {archive.relative_to(ROOT)} ({size:.1f} Mo)\n  SHA-256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
