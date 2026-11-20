"""Lancement du serveur seul : ``python -m localdrop``.

Le desktop (phase 8) embarquera le serveur dans un thread ; ce point d'entrée sert au
développement et au premier jalon (§18.1). Le QR Code est affiché dans le terminal
(stdout, jamais dans les logs) ; l'approbation se fait avec ``python -m localdrop.devtools``.
"""

from __future__ import annotations

import contextlib
import logging
import socket
import sys

import uvicorn

from localdrop.core.config import Settings
from localdrop.core.logging import setup_logging
from localdrop.infrastructure.network.interfaces import base_url, pairing_url
from localdrop.main import create_app
from localdrop.services.container import AppServices, build_services

logger = logging.getLogger("localdrop")


def _bind(ip: str, port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):  # Windows : empêche le détournement du port
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        sock.bind((ip, port))
    except OSError:
        sock.close()
        raise
    sock.set_inheritable(True)
    return sock


def _bind_all(settings: Settings, services: AppServices) -> list[socket.socket]:
    try:
        sockets = [_bind(settings.host, settings.port)]
    except OSError as exc:
        print(
            f"\nImpossible d'utiliser le port {settings.port} ({exc.strerror}).\n"
            f"Choisissez-en un autre, par exemple : set LOCALDROP_PORT={settings.port + 1}\n",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    bound = {settings.host}
    if settings.lan_enabled:
        for candidate in services.network.candidates:
            if candidate.ip in bound:
                continue
            try:
                sockets.append(_bind(candidate.ip, settings.port))
                bound.add(candidate.ip)
            except OSError as exc:
                logger.warning("Liaison impossible sur %s : %s", candidate.ip, exc.strerror)
    services.network.bound_ips = frozenset(bound)
    return sockets


def _print_pairing(settings: Settings, services: AppServices) -> None:
    with contextlib.suppress(AttributeError, ValueError):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    info = services.pairing.current_pairing()
    candidates = services.network.reachable_candidates()
    print("\n=== LocalDrop ===")
    print("Utilisez un réseau de confiance et évitez les Wi-Fi publics (connexion non chiffrée).")
    if not settings.lan_enabled:
        print("\nMode local uniquement (LOCALDROP_LAN_ENABLED=false) : le téléphone ne peut pas")
        print("se connecter. Retirez cette variable pour exposer LocalDrop sur le réseau local.")
        return
    if not candidates:
        print("\nAucune adresse réseau privée détectée : connectez le PC au Wi-Fi ou au hotspot.")
        return

    import qrcode

    best = candidates[0]
    url = pairing_url(base_url(best.ip, settings.port), info.session_id, info.secret)
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    print(f"\nScannez ce QR Code avec le téléphone ({best.interface}, {best.ip}) :\n")
    qr.print_ascii(out=sys.stdout, invert=True)
    print("Adresses disponibles :")
    for c in candidates:
        print(f"  - {base_url(c.ip, settings.port)}  ({c.interface})")
    print(
        "\nWindows peut demander l'autorisation du pare-feu : choisissez « Réseaux privés ».\n"
        "Le QR Code est à usage unique. Pour le régénérer et approuver les appareils :\n"
        "  python -m localdrop.devtools qr | devices | approve <id> | reject <id> | revoke <id>\n"
    )


def main() -> None:
    settings = Settings()
    setup_logging(settings)
    services = build_services(settings)
    sockets = _bind_all(settings, services)

    settings.state_dir.mkdir(parents=True, exist_ok=True)
    settings.admin_token_file.write_text(services.admin_token, encoding="utf-8")

    _print_pairing(settings, services)
    sys.stdout.flush()  # visible immédiatement même si stdout est redirigé
    logger.info("Écoute sur : %s", ", ".join(sorted(services.network.bound_ips or ())))

    config = uvicorn.Config(
        create_app(settings, services),
        access_log=False,
        log_config=None,
        server_header=False,
    )
    try:
        uvicorn.Server(config).run(sockets=sockets)
    finally:
        services.close()
        settings.admin_token_file.unlink(missing_ok=True)
        for sock in sockets:
            sock.close()


if __name__ == "__main__":
    main()
