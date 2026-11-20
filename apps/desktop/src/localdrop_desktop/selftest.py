"""Autotest de l'application installée : ``LocalDrop.exe --self-test [rapport.json]``.

Vérifie, dans un dossier temporaire (jamais les données de l'utilisateur) et en
loopback seul (aucune boîte de dialogue du pare-feu), tout ce qu'un oubli de
packaging casserait : ressources embarquées, migrations Alembic, serveur Uvicorn,
page web, WebSocket, envoi et téléchargement réels, rendu Qt et icône.

L'exécutable est fenêtré (pas de console) : le résultat est écrit dans un fichier
JSON et donné par le code de sortie (0 = tout est bon).
"""

from __future__ import annotations

import json
import os
import platform
import sys
import tempfile
import time
import traceback
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from localdrop import __version__
from localdrop.bench import (
    RunningServer,
    bench_settings,
    file_sha256,
    write_random_file,
)
from localdrop.core.paths import (
    app_icon_path,
    default_web_dist_dir,
    is_frozen,
    migrations_dir,
)

SELF_TEST_FLAG = "--self-test"
CHUNK = 64 * 1024


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""
    seconds: float = 0.0


@dataclass
class Report:
    version: str
    frozen: bool
    python: str
    checks: list[Check]

    @property
    def ok(self) -> bool:
        return bool(self.checks) and all(c.ok for c in self.checks)

    def to_json(self) -> str:
        data: dict[str, Any] = asdict(self)
        data["ok"] = self.ok
        return json.dumps(data, ensure_ascii=False, indent=2)


def default_report_path() -> Path:
    return Path(tempfile.gettempdir()) / "localdrop-selftest.json"


def report_path_from_argv(argv: list[str]) -> Path:
    """``--self-test`` seul, ``--self-test chemin`` ou ``--self-test=chemin``."""
    for index, arg in enumerate(argv):
        if arg.startswith(SELF_TEST_FLAG + "="):
            return Path(arg.split("=", 1)[1])
        if arg == SELF_TEST_FLAG and index + 1 < len(argv):
            candidate = argv[index + 1]
            if not candidate.startswith("-"):
                return Path(candidate)
    return default_report_path()


def _run(checks: list[Check], name: str, step: Callable[[], str]) -> bool:
    started = time.perf_counter()
    try:
        detail = step()
        ok = True
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=4)}"
        ok = False
    checks.append(Check(name, ok, detail, round(time.perf_counter() - started, 3)))
    return ok


def _resources() -> str:
    web = default_web_dist_dir() / "index.html"
    env = migrations_dir() / "env.py"
    versions = sorted((migrations_dir() / "versions").glob("*.py"))
    icon = app_icon_path()
    missing = [str(p) for p in (web, env, icon) if not p.is_file()]
    if missing or not versions:
        raise FileNotFoundError(f"ressources absentes : {missing or 'migrations/versions'}")
    return f"web, {len(versions)} migration(s), icône"


def _server_round_trip(workdir: Path) -> Callable[[], str]:
    def step() -> str:
        settings = bench_settings(workdir, CHUNK).model_copy(
            update={"web_dist_dir": default_web_dist_dir()}
        )
        server = RunningServer(settings).start()
        try:
            return _exercise(server, workdir)
        finally:
            server.stop()

    return step


def _exercise(server: RunningServer, workdir: Path) -> str:
    from websockets.sync.client import connect

    from localdrop.infrastructure.database.engine import database_url, make_engine
    from localdrop.infrastructure.database.migrate import (
        alembic_config,
        current_revision,
        head_revision,
    )

    services = server.services
    head = head_revision(alembic_config())
    engine = make_engine(database_url(server.settings.database_dir))
    try:
        if head is None or current_revision(engine) != head:
            raise RuntimeError("base non migrée au dernier schéma")
    finally:
        engine.dispose()

    phone = server.paired_phone("Autotest")
    port = server.settings.port
    try:
        page = phone.request("GET", "/")
        if b"LocalDrop" not in page.body or "content-security-policy" not in page.headers:
            raise RuntimeError("page mobile absente ou sans CSP")

        url = f"ws://127.0.0.1:{port}/ws"
        with connect(url, open_timeout=10) as ws:
            ws.send(json.dumps({"type": "auth", "token": phone.token}))
            if json.loads(ws.recv(timeout=10)).get("type") != "auth.ok":
                raise RuntimeError("WebSocket : authentification refusée")

        source = write_random_file(workdir / "autotest é.bin", CHUNK * 3 + 17)
        uploaded = phone.upload(source)
        received = server.settings.receive_dir / "autotest é.bin"
        if uploaded["status"] != "completed" or file_sha256(received) != file_sha256(source):
            raise RuntimeError("envoi téléphone -> PC incorrect")

        offered = services.downloads.offer(source, str(phone.device_id))
        target = workdir / "telecharge.bin"
        phone.download(offered.id, target)
        if (
            file_sha256(target) != file_sha256(source)
            or phone.confirm(offered.id)["status"] != "completed"
        ):
            raise RuntimeError("téléchargement PC -> téléphone incorrect")
    finally:
        phone.close()
    return f"migration {head}, page, WebSocket, envoi et téléchargement OK (port {port})"


def _qt() -> str:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from localdrop_desktop.widgets.qr import QrWidget

    app = QApplication.instance() or QApplication([sys.argv[0]])
    icon = QIcon(str(app_icon_path()))
    if icon.isNull():
        raise RuntimeError("icône illisible")
    widget = QrWidget()
    widget.set_data("http://192.168.1.14:8765/#/join?s=x&k=y")
    widget.resize(240, 240)
    if widget.grab().isNull():
        raise RuntimeError("rendu du QR Code impossible")
    widget.deleteLater()
    del app
    return f"Qt {platform.system()} : QR Code et icône rendus"


def run_self_test() -> Report:
    checks: list[Check] = []
    with tempfile.TemporaryDirectory(prefix="localdrop-selftest-") as tmp:
        _run(checks, "ressources embarquées", _resources)
        _run(checks, "serveur, base, page, WebSocket, transferts", _server_round_trip(Path(tmp)))
        _run(checks, "interface Qt", _qt)
    return Report(__version__, is_frozen(), platform.python_version(), checks)


def main(argv: list[str]) -> int:
    import logging

    logging.disable(logging.WARNING)  # pas de bruit : le rapport JSON fait foi
    try:
        report = run_self_test()
    finally:
        logging.disable(logging.NOTSET)
    target = report_path_from_argv(argv)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report.to_json(), encoding="utf-8")
    if sys.stdout is not None:
        status = "OK" if report.ok else "ÉCHEC"
        print(f"Autotest LocalDrop {__version__} : {status} ({target})")
    return 0 if report.ok else 1
