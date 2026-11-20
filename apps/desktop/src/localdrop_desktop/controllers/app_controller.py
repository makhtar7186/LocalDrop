"""Façade en processus entre l'interface et les services (§8.6).

Les administrations (approuver, refuser, révoquer, proposer un fichier, annuler) passent
par les services en processus, jamais par HTTP. Tout accès base ou disque s'exécute via
``TaskRunner`` ; les résultats reviennent dans le thread GUI.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

from localdrop.core.config import Settings, save_user_settings
from localdrop.domain.devices.models import Device, DeviceStatus
from localdrop.domain.transfers.models import ACTIVE_STATUSES, Direction, Transfer
from localdrop.domain.transfers.query import TransferPage, TransferQuery
from localdrop.infrastructure.network.interfaces import base_url, pairing_url
from localdrop.services.container import AppServices
from localdrop_desktop.bridge import EventBridge
from localdrop_desktop.workers.server_worker import ServerWorker
from localdrop_desktop.workers.tasks import TaskRunner

logger = logging.getLogger(__name__)

_REFRESH_DELAY_MS = 250  # regroupe les rafraîchissements de progression


@dataclass(frozen=True)
class PairingView:
    """Ce que le tableau de bord affiche. ``qr_url`` contient le secret : jamais affiché
    en texte, seulement encodé dans le QR Code."""

    qr_url: str | None
    addresses: list[tuple[str, str]]  # (url de base, interface)


class AppController(QObject):
    server_state_changed = Signal(str)  # "starting" | "running" | "stopped" | "error"
    server_error = Signal(str)
    help_available = Signal(str)
    pairing_changed = Signal()
    devices_changed = Signal(list)
    transfers_changed = Signal(list)
    approval_requested = Signal(dict)
    approval_resolved = Signal(str)  # device_id décidé (ici ou ailleurs)
    notification = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        settings: Settings,
        services: AppServices,
        parent: QObject | None = None,
        open_folder: Callable[[Path], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.services = services
        self.runner = TaskRunner(self)
        self.bridge = EventBridge(services.events, self)
        self.worker = ServerWorker(settings, services, self)
        self._open_folder = open_folder or reveal_in_explorer
        self.server_state = "stopped"
        self._shut_down = False

        self._transfers_timer = QTimer(self)
        self._transfers_timer.setSingleShot(True)
        self._transfers_timer.setInterval(_REFRESH_DELAY_MS)
        self._transfers_timer.timeout.connect(self.refresh_transfers)

        self.bridge.event_received.connect(self._on_event)
        self.worker.started.connect(self._on_server_started)
        self.worker.stopped.connect(lambda: self._set_state("stopped"))
        self.worker.failed.connect(self._on_server_failed)
        self.worker.help_available.connect(self.help_available)

    # ------------------------------------------------------------------ serveur (FR-001)
    def start_server(self) -> None:
        if self.worker.running:
            return
        self._set_state("starting")
        self.worker.start()

    def stop_server(self) -> bool:
        stopped = self.worker.stop()
        if stopped:
            self._set_state("stopped")
        return stopped

    def _on_server_started(self) -> None:
        self._set_state("running")
        self.pairing_changed.emit()

    def _on_server_failed(self, message: str) -> None:
        self._set_state("error")
        self.server_error.emit(message)

    def _set_state(self, state: str) -> None:
        if state != self.server_state:
            self.server_state = state
            self.server_state_changed.emit(state)

    # ------------------------------------------------------------------ appairage
    def pairing_view(self) -> PairingView:
        """Lecture rapide (mémoire + une requête courte) : appelée depuis le thread GUI."""
        candidates = self.services.network.reachable_candidates()
        port = self.settings.port
        addresses = [(base_url(c.ip, port), c.interface) for c in candidates]
        if not self.settings.lan_enabled or not candidates or self.server_state != "running":
            return PairingView(None, addresses)
        info = self.services.pairing.current_pairing()
        return PairingView(pairing_url(addresses[0][0], info.session_id, info.secret), addresses)

    # ------------------------------------------------------------------ appareils (FR-011 à 013)
    def refresh_devices(self, *_: object) -> None:
        # *_ : utilisable comme rappel après une action (reçoit son résultat).
        self.runner.run(self.services.pairing.list_devices, on_done=self.devices_changed.emit)

    def approve(self, device_id: str) -> None:
        self._mutate(self.services.pairing.approve, device_id, then=self.refresh_devices)

    def reject(self, device_id: str) -> None:
        self._mutate(self.services.pairing.reject, device_id, then=self.refresh_devices)

    def revoke(self, device_id: str) -> None:
        self._mutate(self.services.pairing.revoke, device_id, then=self.refresh_devices)

    def close_session(self) -> None:
        def done(_: Any) -> None:
            self.refresh_devices()
            self.pairing_changed.emit()
            self.notification.emit("Session fermée : tous les appareils ont été déconnectés.")

        self._mutate(lambda: self.services.pairing.close_session(), then=done)

    # ------------------------------------------------------------------ transferts
    def refresh_transfers(self) -> None:
        self.runner.run(self.services.transfers.list_all, on_done=self._emit_active_transfers)

    def _emit_active_transfers(self, transfers: list[Transfer]) -> None:
        active = [t for t in transfers if t.status in ACTIVE_STATUSES]
        self.transfers_changed.emit(sorted(active, key=lambda t: t.created_at, reverse=True))

    def offer_files(self, paths: Iterable[Path], device_id: str) -> None:
        """Glisser-déposer ou sélection : met les fichiers à disposition du téléphone."""
        files = [p for p in paths if p.is_file()]
        skipped = [p.name for p in paths if not p.is_file()]
        if skipped:
            self.error.emit(
                "Seuls les fichiers peuvent être envoyés (dossiers ignorés) : " + ", ".join(skipped)
            )
        for path in files:
            self._mutate(
                self.services.downloads.offer,
                path,
                device_id,
                then=lambda t: self.notification.emit(
                    f"« {t.safe_filename} » proposé au téléphone."
                ),
            )

    def cancel_transfer(self, transfer: Transfer) -> None:
        if transfer.direction is Direction.UPLOAD:
            self._mutate(
                self.services.transfers.cancel, None, transfer.id, then=self._refresh_later
            )
        else:
            self._mutate(self.services.downloads.cancel, transfer.id, then=self._refresh_later)

    def has_active_transfers(self) -> bool:
        return self.services.transfers.has_active_transfers()

    # ------------------------------------------------------------------ historique (FR-034)
    def search_history(self, query: TransferQuery, on_done: Callable[[TransferPage], None]) -> None:
        self.runner.run(
            self.services.transfers.history, query, on_done=on_done, on_error=self._fail
        )

    def reveal(self, transfer: Transfer) -> None:
        """« Ouvrir le dossier » : sélectionne le fichier dans l'Explorateur, sans l'ouvrir."""
        target = transfer.final_path or transfer.source_path
        if not target or not Path(target).exists():
            self.error.emit("Le fichier n'est plus à cet emplacement.")
            return
        self._open_folder(Path(target))

    # ------------------------------------------------------------------ paramètres
    def save_settings(self, values: dict[str, Any]) -> None:
        save_user_settings(self.settings, values)  # lève ValueError si invalide

    # ------------------------------------------------------------------ arrêt
    def shutdown(self) -> None:
        """Arrêt propre : serveur (WebSocket fermés, Uvicorn), tâches, base, jeton admin.
        Idempotent (fermeture de fenêtre et fin de l'application)."""
        if self._shut_down:
            return
        self._shut_down = True
        self.bridge.close()
        self.worker.stop()
        self.runner.shutdown()
        self.services.close()
        self.settings.admin_token_file.unlink(missing_ok=True)

    # ------------------------------------------------------------------ interne
    def _on_event(self, event_type: str, data: dict[str, Any]) -> None:
        if event_type.startswith("device."):
            self.refresh_devices()
            if event_type == "device.pending":
                self.approval_requested.emit(data)
            elif event_type in ("device.connected", "device.rejected", "device.revoked"):
                self.approval_resolved.emit(str(data.get("device_id", "")))
        elif event_type.startswith("transfer."):
            self._refresh_later()
            if event_type == "transfer.completed" and data.get("direction") == "upload":
                self.notification.emit(f"Fichier reçu : {data.get('filename')}")
        elif event_type in ("session.pairing_rotated", "session.started", "server.network_changed"):
            self.pairing_changed.emit()

    def _refresh_later(self, *_: Any) -> None:
        if not self._transfers_timer.isActive():
            self._transfers_timer.start()

    def _mutate(self, function: Callable[..., Any], *args: Any, then: Callable[[Any], Any]) -> None:
        self.runner.run(function, *args, on_done=then, on_error=self._fail)

    def _fail(self, error: BaseException) -> None:
        message = getattr(error, "message", None) or str(error) or error.__class__.__name__
        self.error.emit(message)


def connected_devices(devices: list[Device]) -> list[Device]:
    return [d for d in devices if d.status in (DeviceStatus.CONNECTED, DeviceStatus.DISCONNECTED)]


def reveal_in_explorer(path: Path) -> None:
    """Ouvre le dossier et sélectionne le fichier. N'exécute JAMAIS le fichier (§12.2-9)."""
    if sys.platform == "win32":
        subprocess.Popen(["explorer", f"/select,{path}"])  # noqa: S603, S607
    else:  # pragma: no cover - plateformes de développement
        subprocess.Popen(["xdg-open", str(path.parent)])  # noqa: S603, S607
