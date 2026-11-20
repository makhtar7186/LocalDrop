"""Serveur local LocalDrop : liaison des sockets, redémarrage sur changement réseau, aide.

Réutilisé par ``python -m localdrop`` et par le desktop (phase 8, dans un thread).

- Liaison explicite : 127.0.0.1 + chaque IPv4 privée détectée, jamais 0.0.0.0 (§12.2-11).
- Nouvelle adresse (point d'accès activé après le lancement, changement de Wi-Fi) :
  le serveur se relance proprement sur les nouvelles adresses et réaffiche le QR Code
  (FR-003). Sessions et transferts sont en base : les téléphones se reconnectent seuls.
- Aucun téléphone ne s'est présenté après ``join_help_delay_seconds`` : aide affichée (§3.3).

Uniquement l'API publique d'Uvicorn (``Server.run(sockets=...)``, ``should_exit``).
"""

from __future__ import annotations

import json
import logging
import socket
import subprocess
import sys
import threading
from collections.abc import Callable

import uvicorn
from fastapi import FastAPI

from localdrop.core.config import Settings
from localdrop.infrastructure.network.interfaces import base_url, pairing_url
from localdrop.main import create_app
from localdrop.services.container import AppServices
from localdrop.services.events import Event

logger = logging.getLogger(__name__)

Output = Callable[[str], None]


class PortUnavailableError(RuntimeError):
    pass


def bind_socket(ip: str, port: int) -> socket.socket:
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


class LocalServer:
    def __init__(
        self,
        settings: Settings,
        services: AppServices,
        *,
        app: FastAPI | None = None,
        output: Output = print,
        graceful_timeout: int = 3,
    ) -> None:
        self._settings = settings
        self._services = services
        self._app = app or create_app(settings, services)
        self._output = output
        self._graceful_timeout = graceful_timeout
        self._server: uvicorn.Server | None = None
        self._lock = threading.Lock()
        self._restart_requested = False
        self._stop_requested = False
        self._joined = threading.Event()
        self._help_timer: threading.Timer | None = None
        self.started = threading.Event()  # le serveur accepte des connexions
        self.restarts = 0

    # ------------------------------------------------------------------ cycle de vie
    def run(self) -> None:
        """Bloquant : sert jusqu'à l'arrêt, en se relançant sur changement réseau."""
        unsubscribe = self._services.events.subscribe(self._on_event)
        try:
            while True:
                sockets = self._bind_all()
                try:
                    self._announce()
                    config = uvicorn.Config(
                        self._app,
                        access_log=False,
                        log_config=None,
                        server_header=False,
                        timeout_graceful_shutdown=self._graceful_timeout,
                    )
                    server = uvicorn.Server(config)
                    with self._lock:
                        self._server = server
                        self._restart_requested = False
                    threading.Thread(
                        target=self._signal_started, args=(server,), daemon=True
                    ).start()
                    server.run(sockets=sockets)
                finally:
                    self.started.clear()
                    self._cancel_help()
                    for sock in sockets:
                        sock.close()
                with self._lock:
                    restart = self._restart_requested and not self._stop_requested
                if not restart:
                    return
                self.restarts += 1
                logger.info("Redémarrage de l'écoute sur les nouvelles adresses réseau")
        finally:
            unsubscribe()

    def stop(self) -> None:
        with self._lock:
            self._stop_requested = True
            if self._server is not None:
                self._server.should_exit = True

    def _signal_started(self, server: uvicorn.Server) -> None:
        while not server.started and not server.should_exit:
            threading.Event().wait(0.02)
        if server.started:
            self.started.set()

    # ------------------------------------------------------------------ événements
    def _on_event(self, event: Event) -> None:
        if event.type == "device.pending":
            self._joined.set()
            self._cancel_help()
        elif event.type == "server.network_changed" and event.data.get("restart_required"):
            with self._lock:
                if self._server is not None and not self._stop_requested:
                    self._restart_requested = True
                    self._server.should_exit = True

    # ------------------------------------------------------------------ sockets
    def _bind_all(self) -> list[socket.socket]:
        settings = self._settings
        try:
            sockets = [bind_socket(settings.host, settings.port)]
        except OSError as exc:
            raise PortUnavailableError(
                f"Impossible d'utiliser le port {settings.port} ({exc.strerror}). "
                f"Choisissez-en un autre, par exemple : set LOCALDROP_PORT={settings.port + 1}"
            ) from exc

        self._services.network.refresh_quietly()
        bound = {settings.host}
        if settings.lan_enabled:
            for candidate in self._services.network.candidates:
                if candidate.ip in bound:
                    continue
                try:
                    sockets.append(bind_socket(candidate.ip, settings.port))
                    bound.add(candidate.ip)
                except OSError as exc:
                    logger.warning("Liaison impossible sur %s : %s", candidate.ip, exc.strerror)
        self._services.network.bound_ips = frozenset(bound)
        logger.info("Écoute sur : %s", ", ".join(sorted(bound)))
        return sockets

    # ------------------------------------------------------------------ affichage
    def _announce(self) -> None:
        if self.restarts:
            self._output("\nRéseau modifié : LocalDrop écoute maintenant les nouvelles adresses.")
        self._output(pairing_banner(self._settings, self._services))
        delay = self._settings.join_help_delay_seconds
        if delay > 0 and self._settings.lan_enabled and not self._joined.is_set():
            self._help_timer = threading.Timer(delay, self._show_help)
            self._help_timer.daemon = True
            self._help_timer.start()

    def _cancel_help(self) -> None:
        timer, self._help_timer = self._help_timer, None
        if timer is not None:
            timer.cancel()

    def _show_help(self) -> None:
        if not self._joined.is_set():
            self._output(connection_help(self._settings, self._services, network_profiles()))


# ----------------------------------------------------------------------------- textes
def pairing_banner(settings: Settings, services: AppServices) -> str:
    lines = [
        "",
        "=== LocalDrop ===",
        "Utilisez un réseau de confiance et évitez les Wi-Fi publics (connexion non chiffrée).",
    ]
    if not settings.lan_enabled:
        lines += [
            "",
            "Mode local uniquement (LOCALDROP_LAN_ENABLED=false) : le téléphone ne peut pas",
            "se connecter. Retirez cette variable pour exposer LocalDrop sur le réseau local.",
        ]
        return "\n".join(lines)
    candidates = services.network.reachable_candidates()
    if not candidates:
        lines += [
            "",
            "Aucune adresse réseau privée détectée : connectez le PC au Wi-Fi ou activez son",
            "point d'accès mobile. LocalDrop l'utilisera automatiquement dès qu'il apparaîtra.",
        ]
        return "\n".join(lines)

    import io

    import qrcode

    info = services.pairing.current_pairing()
    best = candidates[0]
    qr = qrcode.QRCode(border=1)
    qr.add_data(pairing_url(base_url(best.ip, settings.port), info.session_id, info.secret))
    qr.make(fit=True)
    buffer = io.StringIO()
    qr.print_ascii(out=buffer, invert=True)
    lines += [
        "",
        f"Scannez ce QR Code avec le téléphone ({best.interface}, {best.ip}) :",
        "",
        buffer.getvalue().rstrip("\n"),
        "Adresses disponibles :",
        *(f"  - {base_url(c.ip, settings.port)}  ({c.interface})" for c in candidates),
        "",
        "Windows peut demander l'autorisation du pare-feu : choisissez « Réseaux privés ».",
        "Après le scan, autorisez le téléphone :",
        "  python -m localdrop.devtools devices      puis      approve <id>",
        "QR Code à usage unique ; pour en afficher un nouveau : python -m localdrop.devtools qr",
        "",
    ]
    return "\n".join(lines)


def connection_help(
    settings: Settings, services: AppServices, profiles: dict[str, str] | None
) -> str:
    """Aide affichée si aucun téléphone ne s'est présenté (§3.3 « Réseau isolé »)."""
    candidates = services.network.reachable_candidates()
    test_url = f"{base_url(candidates[0].ip, settings.port)}/api/v1/health" if candidates else None
    lines = [
        "",
        "--- Aucun téléphone ne s'est encore connecté ---",
        "1. Le téléphone doit être sur le MÊME réseau que le PC (même Wi-Fi, ou le point",
        "   d'accès mobile du PC). Les données mobiles (4G/5G) ne fonctionnent pas.",
    ]
    if test_url:
        lines += [
            f"2. Test : ouvrez {test_url} dans le navigateur du téléphone.",
            '   - « {"status":"ok"…} » s\'affiche : le réseau fonctionne, rescannez le QR Code.',
            "   - La page ne charge pas : le réseau bloque les échanges entre appareils.",
        ]
    lines += [
        "3. Réseaux professionnels, d'hôtel ou « invité » : l'« isolation des clients » empêche",
        "   souvent le téléphone de joindre le PC. Solution : activez le point d'accès mobile",
        "   du PC (Paramètres > Réseau et Internet > Point d'accès sans fil mobile) et",
        "   connectez-y le téléphone. LocalDrop détectera la nouvelle adresse et affichera",
        "   un nouveau QR Code.",
    ]
    public = sorted(
        {c.interface for c in candidates if (profiles or {}).get(c.interface) == "Public"}
    )
    if public:
        lines += [
            f"4. Le réseau {', '.join(public)} est classé « Public » par Windows : le pare-feu",
            "   peut bloquer les connexions entrantes. Passez-le en « Privé » (Paramètres >",
            "   Réseau et Internet > propriétés du réseau) si c'est un réseau de confiance.",
        ]
    return "\n".join([*lines, ""])


def network_profiles() -> dict[str, str] | None:
    """Catégorie Windows (Public/Private/DomainAuthenticated) par interface, au mieux."""
    if sys.platform != "win32":
        return None
    command = (
        "Get-NetConnectionProfile | Select-Object InterfaceAlias,NetworkCategory "
        "| ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(  # noqa: S603 - commande fixe, sans entrée externe
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        data = json.loads(completed.stdout or "null")
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    entries = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
    categories = {0: "Public", 1: "Private", 2: "DomainAuthenticated"}
    profiles: dict[str, str] = {}
    for entry in entries:
        alias, category = entry.get("InterfaceAlias"), entry.get("NetworkCategory")
        if isinstance(alias, str):
            label = categories.get(category) if isinstance(category, int) else None
            profiles[alias] = label or str(category)
    return profiles
