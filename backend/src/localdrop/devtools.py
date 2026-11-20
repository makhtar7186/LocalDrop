"""Outil d'administration en ligne de commande (développement, avant le desktop).

    python -m localdrop.devtools qr            # QR Code courant (à usage unique)
    python -m localdrop.devtools devices       # appareils de la session
    python -m localdrop.devtools transfers     # transferts (état, progression, chemin final)
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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m localdrop.devtools")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("qr")
    sub.add_parser("devices")
    sub.add_parser("transfers")
    for name in ("approve", "reject"):
        sub.add_parser(name).add_argument("device_id")
    sub.add_parser("revoke").add_argument("device_id", nargs="?")
    args = parser.parse_args(argv)
    settings = Settings()

    if args.command == "qr":
        _print_qr(settings)
        return
    if args.command == "devices":
        result = _call(settings, "GET", "/devices")
    elif args.command == "transfers":
        result = _call(settings, "GET", "/admin/transfers")
    elif args.command in ("approve", "reject"):
        body = {"device_id": args.device_id, "approve": args.command == "approve"}
        result = _call(settings, "POST", "/sessions/approve", body)
    else:
        result = _call(settings, "POST", "/sessions/revoke", {"device_id": args.device_id})
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
