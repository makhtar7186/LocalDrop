"""Test de fumée de l'exécutable construit (§17.2, skill localdrop-packaging-windows).

Lance le vrai LocalDrop.exe (avec sa fenêtre) en isolement :
- données et réception dans un dossier temporaire (jamais ceux de l'utilisateur) ;
- loopback seul (LOCALDROP_LAN_ENABLED=false) : pas de boîte de dialogue du pare-feu.

Scénario :
1. démarrage : santé, page mobile servie ;
2. appairage comme un téléphone, approbation par l'API d'administration ;
3. envoi d'un fichier au nom Unicode, vérifié par hash ; fichier proposé par le PC
   et téléchargé ;
4. fermeture **normale** (WM_CLOSE, comme la croix de la fenêtre) : sortie en moins
   de 20 s, code 0, port libéré, jeton admin supprimé ;
5. relance : base retrouvée, historique conservé, puis fermeture.

Usage : ``.venv/Scripts/python scripts/smoke_test_exe.py [dist/LocalDrop/LocalDrop.exe]``
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from localdrop.bench import PhoneClient, file_sha256, free_port, write_random_file

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "dist" / "LocalDrop" / "LocalDrop.exe"
ADMIN_HEADER = "X-LocalDrop-Admin"


class SmokeError(AssertionError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeError(message)
    print(f"  ✓ {message}")


class App:
    def __init__(self, exe: Path, root: Path, port: int) -> None:
        self.exe = exe
        self.data_dir = root / "donnees"
        self.receive_dir = root / "recus"
        self.port = port
        self.process: subprocess.Popen[bytes] | None = None

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        env = {
            **os.environ,
            "LOCALDROP_DATA_DIR": str(self.data_dir),
            "LOCALDROP_RECEIVE_DIR": str(self.receive_dir),
            "LOCALDROP_PORT": str(self.port),
            "LOCALDROP_LAN_ENABLED": "false",
        }
        self.process = subprocess.Popen([str(self.exe)], env=env)  # noqa: S603
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise SmokeError(f"l'application s'est arrêtée (code {self.process.returncode})")
            try:
                with urllib.request.urlopen(f"{self.base}/api/v1/health", timeout=2) as r:  # noqa: S310
                    if r.status == 200:
                        return
            except (urllib.error.URLError, OSError):
                time.sleep(0.3)
        raise SmokeError("le serveur n'a pas répondu en 40 s")

    def admin(self, method: str, path: str, payload: object | None = None) -> dict[str, Any]:
        token = (self.data_dir / "state" / "admin.token").read_text(encoding="utf-8").strip()
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(  # noqa: S310
            f"{self.base}/api/v1{path}",
            data=body,
            method=method,
            headers={ADMIN_HEADER: token, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            data: dict[str, Any] = json.load(response)
            return data

    def close(self) -> int:
        """Fermeture comme la croix de la fenêtre (WM_CLOSE), sans forcer."""
        if self.process is None:
            raise SmokeError("application non démarrée")
        subprocess.run(  # noqa: S603
            ["taskkill", "/PID", str(self.process.pid)],  # noqa: S607
            check=False,
            capture_output=True,
        )
        try:
            return self.process.wait(20)
        except subprocess.TimeoutExpired as exc:
            self.process.kill()
            raise SmokeError("l'application ne s'est pas fermée en 20 s") from exc

    def kill(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.kill()
            self.process.wait(10)


def port_is_free(port: int) -> bool:
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def first_run(app: App, work: Path) -> str:
    print("1. Démarrage")
    app.start()
    page = PhoneClient("127.0.0.1", app.port).request("GET", "/")
    check(b"LocalDrop" in page.body, "page mobile servie par l'exécutable")

    print("2. Appairage et approbation")
    info = app.admin("GET", "/admin/pairing")
    fragment = parse_qs(urlsplit(info["loopback_pairing_url"]).fragment.split("?", 1)[1])
    phone = PhoneClient("127.0.0.1", app.port)
    device_id = phone.join(fragment["s"][0], fragment["k"][0], "Test de fumée")
    app.admin("POST", "/sessions/approve", {"device_id": device_id, "approve": True})
    check(phone.request("GET", "/api/v1/transfers").status == 200, "téléphone approuvé")

    print("3. Transferts")
    name = "Fumée été 🎉.bin"
    source = write_random_file(work / "source.bin", 5 * 1024 * 1024 + 123)
    done = phone.upload(source, name)
    check(done["status"] == "completed", "envoi téléphone -> PC terminé")
    check(
        file_sha256(app.receive_dir / name) == file_sha256(source),
        "fichier reçu identique (SHA-256)",
    )
    offered = app.admin(
        "POST", "/admin/transfers/outgoing", {"path": str(source), "device_id": device_id}
    )
    target = work / "telecharge.bin"
    phone.download(offered["id"], target)
    phone.confirm(offered["id"])
    check(file_sha256(target) == file_sha256(source), "téléchargement PC -> téléphone identique")
    phone.close()

    print("4. Fermeture normale")
    code = app.close()
    check(code == 0, f"sortie propre (code {code})")
    check(port_is_free(app.port), "port libéré")
    check(not (app.data_dir / "state" / "admin.token").exists(), "jeton admin supprimé")
    return name


def second_run(app: App, name: str) -> None:
    print("5. Relance")
    app.start()
    history = app.admin("GET", "/admin/history?limit=10")
    names = [item["safe_filename"] for item in history["items"]]
    check(name in names, "historique retrouvé après redémarrage")
    check(any((app.data_dir / "database").glob("*.db")), "base SQLite dans le dossier de données")
    code = app.close()
    check(code == 0, f"seconde fermeture propre (code {code})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("exe", nargs="?", type=Path, default=DEFAULT_EXE)
    args = parser.parse_args(argv)
    # Sortie redirigée (cp1252) : jamais d'erreur d'encodage sur ✓ ou un emoji.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    exe = args.exe.resolve()
    if not exe.is_file():
        print(f"Exécutable introuvable : {exe}", file=sys.stderr)
        return 2

    print(f"Test de fumée : {exe}")
    temporary = tempfile.TemporaryDirectory(prefix="localdrop-fumee-", ignore_cleanup_errors=True)
    with temporary as tmp:
        root = Path(tmp)
        app = App(exe, root, free_port())
        try:
            name = first_run(app, root)
            second_run(app, name)
        except SmokeError as exc:
            print(f"ÉCHEC : {exc}", file=sys.stderr)
            log = app.data_dir / "logs" / "localdrop.log"
            if log.is_file():
                print("--- fin du journal ---", file=sys.stderr)
                print(
                    "\n".join(log.read_text(encoding="utf-8").splitlines()[-25:]), file=sys.stderr
                )
            return 1
        finally:
            app.kill()
    print("Test de fumée réussi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
