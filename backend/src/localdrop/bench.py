"""Banc de mesure du débit et client HTTP « téléphone » sur vrais sockets (phase 10, §5.1).

``python -m localdrop.bench`` démarre, pour chaque taille de bloc, un vrai serveur
(sockets, SQLite, disque) sur 127.0.0.1, l'appaire, puis envoie et télécharge un
fichier en mesurant le débit. Sur loopback, le réseau n'est pas le goulot : la mesure
reflète le coût côté PC (hash, fsync, commits SQLite) de chaque taille de bloc. Le
débit Wi-Fi réel se mesure avec un téléphone (docs/testing/e2e-matrix.md).

``PhoneClient`` n'utilise que la bibliothèque standard : les tests e2e s'en servent
pour jouer le téléphone (appairage, envoi par blocs, reprise, téléchargement Range).
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import http.client
import json
import logging
import os
import socket
import tempfile
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from localdrop.core.config import MIB, Settings
from localdrop.server import LocalServer
from localdrop.services.container import AppServices, build_services

API = "/api/v1"


class ApiError(RuntimeError):
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        try:
            self.code = str(json.loads(body)["error"]["code"])
        except (ValueError, KeyError, TypeError):
            self.code = ""
        super().__init__(f"HTTP {status} {self.code}")


@dataclass(frozen=True, slots=True)
class Response:
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body)


class PhoneClient:
    """Client HTTP minimal se comportant comme la page mobile."""

    def __init__(self, host: str, port: int, *, timeout: float = 30) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.token: str | None = None
        self.device_id: str | None = None
        # Connexion persistante, comme un navigateur (keep-alive) : sous Windows, ouvrir
        # une connexion TCP par requête ajoutait ~10 ms et faussait les mesures.
        self._conn: http.client.HTTPConnection | None = None

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------ HTTP
    def request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        payload: object | None = None,
        headers: dict[str, str] | None = None,
        check: bool = True,
    ) -> Response:
        all_headers = dict(headers or {})
        if payload is not None:
            body = json.dumps(payload).encode()
            all_headers["Content-Type"] = "application/json"
        if self.token and "Authorization" not in all_headers:
            all_headers["Authorization"] = f"Bearer {self.token}"
        reused = self._conn is not None
        try:
            response = self._send(method, path, body, all_headers)
        except (ConnectionError, http.client.RemoteDisconnected):
            self.close()
            if not reused:
                raise
            # Connexion gardée ouverte puis fermée par le serveur (redémarrage) :
            # un navigateur réessaie de même sur une nouvelle connexion.
            response = self._send(method, path, body, all_headers)
        if check and response.status >= 400:
            raise ApiError(response.status, response.body)
        return response

    def _send(
        self, method: str, path: str, body: bytes | None, headers: dict[str, str]
    ) -> Response:
        if self._conn is None:
            self._conn = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        try:
            self._conn.request(method, path, body=body, headers=headers)
            raw = self._conn.getresponse()
            data = raw.read()
        except BaseException:
            self.close()
            raise
        if raw.will_close:
            self.close()
        return Response(raw.status, {k.lower(): v for k, v in raw.getheaders()}, data)

    # ------------------------------------------------------------------ appairage
    def join(self, session_id: str, secret: str, name: str = "Banc de test") -> str:
        data = self.request(
            "POST",
            f"{API}/sessions/join",
            payload={
                "session_id": session_id,
                "secret": secret,
                "display_name": name,
                "platform": "android",
            },
        ).json()
        self.token = str(data["device_token"])
        self.device_id = str(data["device_id"])
        return self.device_id

    # ------------------------------------------------------------------ envoi
    def create_upload(self, filename: str, size: int) -> dict[str, Any]:
        transfer: dict[str, Any] = self.request(
            "POST", f"{API}/transfers", payload={"filename": filename, "size": size}
        ).json()
        return transfer

    def put_chunk(self, transfer_id: str, index: int, data: bytes) -> dict[str, Any]:
        ack: dict[str, Any] = self.request(
            "PUT",
            f"{API}/transfers/{transfer_id}/chunks/{index}",
            body=data,
            headers={
                "X-Chunk-SHA256": hashlib.sha256(data).hexdigest(),
                "Content-Type": "application/octet-stream",
            },
        ).json()
        return ack

    def received_chunks(self, transfer_id: str) -> list[int]:
        return list(self.request("GET", f"{API}/transfers/{transfer_id}/chunks").json()["received"])

    def complete(self, transfer_id: str, sha256: str) -> dict[str, Any]:
        result: dict[str, Any] = self.request(
            "POST", f"{API}/transfers/{transfer_id}/complete", payload={"sha256": sha256}
        ).json()
        return result

    def send_chunks(
        self, transfer: dict[str, Any], source: Path, indexes: list[int] | None = None
    ) -> list[int]:
        """Envoie les blocs demandés (tous par défaut) en lisant le fichier bloc par bloc."""
        chunk_size = int(transfer["chunk_size"])
        wanted = range(int(transfer["total_chunks"])) if indexes is None else indexes
        sent = []
        with source.open("rb") as fh:
            for index in wanted:
                fh.seek(index * chunk_size)
                self.put_chunk(str(transfer["id"]), index, fh.read(chunk_size))
                sent.append(index)
        return sent

    def upload(self, source: Path, filename: str | None = None) -> dict[str, Any]:
        transfer = self.create_upload(filename or source.name, source.stat().st_size)
        self.send_chunks(transfer, source)
        return self.complete(str(transfer["id"]), file_sha256(source))

    # ------------------------------------------------------------------ téléchargement
    def download(self, transfer_id: str, target: Path, *, byte_range: str | None = None) -> int:
        """Télécharge via ticket (comme un lien <a>) en flux ; renvoie le statut HTTP."""
        ticket = self.request("POST", f"{API}/transfers/{transfer_id}/download-ticket").json()
        conn = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        try:
            conn.request("GET", ticket["url"], headers={"Range": byte_range} if byte_range else {})
            raw = conn.getresponse()
            if raw.status >= 400:
                raise ApiError(raw.status, raw.read())
            with target.open("ab" if byte_range else "wb") as out:
                while block := raw.read(1024 * 1024):
                    out.write(block)
            return raw.status
        finally:
            conn.close()

    def confirm(self, transfer_id: str) -> dict[str, Any]:
        result: dict[str, Any] = self.request(
            "POST", f"{API}/transfers/{transfer_id}/confirm"
        ).json()
        return result


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def write_random_file(path: Path, size: int) -> Path:
    """Fichier aléatoire écrit par morceaux (jamais entièrement en mémoire)."""
    with path.open("wb") as fh:
        remaining = size
        while remaining:
            block = os.urandom(min(remaining, 4 * MIB))
            fh.write(block)
            remaining -= len(block)
    return path


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class RunningServer:
    """Vrai serveur LocalDrop dans un thread, comme dans l'application desktop."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.services: AppServices = build_services(settings)
        self.server = LocalServer(settings, self.services, output=lambda _: None)
        self._thread = threading.Thread(target=self.server.run, name="localdrop-e2e", daemon=True)

    def start(self) -> RunningServer:
        self._thread.start()
        if not self.server.started.wait(15):
            raise RuntimeError("le serveur n'a pas démarré")
        return self

    def stop(self) -> None:
        self.server.stop()
        self._thread.join(15)
        self.services.close()

    def paired_phone(self, name: str = "Banc de test") -> PhoneClient:
        phone = PhoneClient("127.0.0.1", self.settings.port)
        info = self.services.pairing.current_pairing()
        device_id = phone.join(info.session_id, info.secret, name)
        self.services.pairing.approve(device_id)
        return phone


@contextlib.contextmanager
def running_server(settings: Settings) -> Iterator[RunningServer]:
    server = RunningServer(settings).start()
    try:
        yield server
    finally:
        server.stop()


def bench_settings(root: Path, chunk_size: int) -> Settings:
    return Settings(
        data_dir=root / "data",
        receive_dir=root / "recus",
        web_dist_dir=None,
        port=free_port(),
        chunk_size=chunk_size,
        lan_enabled=False,
        network_poll_seconds=0,
        maintenance_interval_minutes=0,
        join_help_delay_seconds=0,
        free_space_margin=0,
    )


@dataclass(frozen=True, slots=True)
class BenchResult:
    chunk_size: int
    file_size: int
    upload_seconds: float
    download_seconds: float

    @property
    def upload_mib_s(self) -> float:
        return self.file_size / MIB / self.upload_seconds

    @property
    def download_mib_s(self) -> float:
        return self.file_size / MIB / self.download_seconds


def bench_once(source: Path, chunk_size: int, workdir: Path) -> BenchResult:
    workdir.mkdir(parents=True, exist_ok=True)
    with running_server(bench_settings(workdir, chunk_size)) as server:
        phone = server.paired_phone()
        started = time.perf_counter()
        uploaded = phone.upload(source)
        upload_seconds = time.perf_counter() - started
        if uploaded["status"] != "completed":
            raise RuntimeError(f"envoi non terminé : {uploaded['status']}")

        offered = server.services.downloads.offer(source, str(phone.device_id))
        target = workdir / "telecharge.bin"
        started = time.perf_counter()
        phone.download(offered.id, target)
        download_seconds = time.perf_counter() - started
        phone.confirm(offered.id)
        phone.close()
        if file_sha256(target) != uploaded["sha256"]:
            raise RuntimeError("fichier téléchargé différent de l'original")
    return BenchResult(chunk_size, source.stat().st_size, upload_seconds, download_seconds)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m localdrop.bench",
        description="Débit d'envoi et de téléchargement par taille de bloc (loopback).",
    )
    parser.add_argument("--size-mib", type=int, default=256, help="taille du fichier de test")
    parser.add_argument(
        "--chunks-mib",
        type=float,
        nargs="+",
        default=[1, 2, 4, 8, 16],
        help="tailles de bloc à comparer, en Mio",
    )
    parser.add_argument("--repeat", type=int, default=2, help="mesures par taille (meilleure)")
    args = parser.parse_args(argv)
    logging.disable(logging.WARNING)  # pas d'interface web à servir : avertissement inutile

    with tempfile.TemporaryDirectory(prefix="localdrop-bench-") as tmp:
        root = Path(tmp)
        source = write_random_file(root / "source.bin", args.size_mib * MIB)
        # Préchauffage : l'antivirus analyse le fichier neuf à sa première lecture, ce
        # qui ralentissait la première mesure de chaque série.
        file_sha256(source)
        bench_once(source, int(args.chunks_mib[0] * MIB), root / "warmup")
        print(f"Fichier de {args.size_mib} Mio, {args.repeat} mesure(s) par taille de bloc\n")
        print(f"{'bloc':>8} | {'envoi':>12} | {'téléchargement':>15}")
        print(f"{'-' * 8}-+-{'-' * 12}-+-{'-' * 15}")
        for chunk_mib in args.chunks_mib:
            runs = []
            for attempt in range(args.repeat):
                workdir = root / f"run-{chunk_mib}-{attempt}"
                runs.append(bench_once(source, int(chunk_mib * MIB), workdir))
            best_up = max(r.upload_mib_s for r in runs)
            best_down = max(r.download_mib_s for r in runs)
            print(f"{chunk_mib:>4g} Mio | {best_up:>6.1f} Mio/s | {best_down:>9.1f} Mio/s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
