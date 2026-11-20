"""Outil d'administration en ligne de commande (développement, avant le desktop).

    python -m localdrop.devtools qr            # QR Code courant (à usage unique)
    python -m localdrop.devtools devices       # appareils de la session
    python -m localdrop.devtools transfers     # transferts (état, progression, chemin final)
    python -m localdrop.devtools send <fichier> [--device <id>]   # PC -> téléphone
    python -m localdrop.devtools cancel <transfer_id>              # annule un envoi du PC
    python -m localdrop.devtools watch                             # événements en direct
    python -m localdrop.devtools approve <id>
    python -m localdrop.devtools reject <id>
    python -m localdrop.devtools revoke <id>   # sans id : ferme toute la session

Le jeton admin est lu dans %LOCALAPPDATA%\\LocalDrop\\state\\admin.token et les appels
passent uniquement par 127.0.0.1.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from localdrop.api.deps import ADMIN_HEADER
from localdrop.core.config import Settings


def _call(settings: Settings, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    try:
        token = settings.admin_token_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        sys.exit("Serveur LocalDrop non démarré (jeton admin introuvable).")
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"http://127.0.0.1:{settings.port}/api/v1{path}",
        data=data,
        method=method,
        headers={ADMIN_HEADER: token, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
            return json.loads(response.read() or b"null")
    except urllib.error.HTTPError as exc:
        sys.exit(f"Erreur {exc.code} : {exc.read().decode(errors='replace')}")
    except urllib.error.URLError as exc:
        sys.exit(f"Serveur injoignable : {exc.reason}")


def _print_qr(settings: Settings) -> None:
    import qrcode

    info = _call(settings, "GET", "/admin/pairing")
    if not info["addresses"]:
        sys.exit("Aucune adresse réseau privée joignable.")
    with contextlib.suppress(AttributeError, ValueError):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    best = info["addresses"][0]
    qr = qrcode.QRCode(border=1)
    qr.add_data(best["pairing_url"])
    qr.make(fit=True)
    print(f"QR Code ({best['interface']}, {best['ip']}), valable jusqu'à {info['expires_at']} :")
    qr.print_ascii(out=sys.stdout, invert=True)


def _watch(settings: Settings) -> None:
    """Affiche les événements temps réel (WebSocket admin, loopback uniquement)."""
    from websockets.exceptions import ConnectionClosed
    from websockets.sync.client import connect

    try:
        token = settings.admin_token_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        sys.exit("Serveur LocalDrop non démarré (jeton admin introuvable).")
    with contextlib.suppress(AttributeError, ValueError):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    try:
        with connect(f"ws://127.0.0.1:{settings.port}/ws") as ws:
            ws.send(json.dumps({"type": "auth", "admin_token": token}))
            print("Événements LocalDrop (Ctrl+C pour quitter) :", flush=True)
            for raw in ws:
                event = json.loads(raw)
                data = event.get("data", {})
                details = " ".join(
                    f"{k}={v}" for k, v in data.items() if k not in ("device_id",) and v is not None
                )
                print(f"{event.get('ts', '')[11:19]} {event['type']:<24} {details}", flush=True)
    except KeyboardInterrupt:
        pass
    except (ConnectionClosed, OSError) as exc:
        sys.exit(f"Connexion temps réel interrompue : {exc}")


def _pick_device(settings: Settings, args: argparse.Namespace) -> str:
    if args.device_id:
        return str(args.device_id)
    connected = [d for d in _call(settings, "GET", "/devices") if d["status"] == "connected"]
    if len(connected) != 1:
        sys.exit(f"{len(connected)} appareil(s) connecté(s) : précisez --device <id>.")
    return str(connected[0]["id"])


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m localdrop.devtools")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("qr")
    sub.add_parser("devices")
    sub.add_parser("transfers")
    send = sub.add_parser("send")
    send.add_argument("path")
    send.add_argument("--device", dest="device_id")
    sub.add_parser("cancel").add_argument("transfer_id")
    sub.add_parser("watch")
    for name in ("approve", "reject"):
        sub.add_parser(name).add_argument("device_id")
    sub.add_parser("revoke").add_argument("device_id", nargs="?")
    args = parser.parse_args(argv)
    settings = Settings()

    if args.command == "qr":
        _print_qr(settings)
        return
    if args.command == "watch":
        _watch(settings)
        return
    if args.command == "devices":
        result = _call(settings, "GET", "/devices")
    elif args.command == "transfers":
        result = _call(settings, "GET", "/admin/transfers")
    elif args.command == "send":
        body = {"path": str(Path(args.path).resolve()), "device_id": _pick_device(settings, args)}
        result = _call(settings, "POST", "/admin/transfers/outgoing", body)
    elif args.command == "cancel":
        result = _call(settings, "POST", f"/admin/transfers/{args.transfer_id}/cancel")
    elif args.command in ("approve", "reject"):
        body = {"device_id": args.device_id, "approve": args.command == "approve"}
        result = _call(settings, "POST", "/sessions/approve", body)
    else:
        result = _call(settings, "POST", "/sessions/revoke", {"device_id": args.device_id})
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
