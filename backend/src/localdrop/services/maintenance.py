"""Tâche de maintenance (FR-035, §13.3), au démarrage puis périodiquement.

- transfert actif expiré -> annulé (EXPIRED), fichier temporaire supprimé ;
- temporaire d'un transfert en échec : conservé pour diagnostic jusqu'à expiration ;
- fichier temporaire orphelin -> supprimé, après un délai de grâce (un upload en cours
  de création crée son temporaire juste avant de s'enregistrer) ;
- historique des transferts terminés -> purgé après la durée de conservation ;
- sessions échues -> « expired ».
Ne supprime JAMAIS un fichier final : seul le dossier temporaire est concerné.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import timedelta

from localdrop.domain.sessions.repository import SessionRepository
from localdrop.domain.transfers.models import Direction, TransferStatus
from localdrop.domain.transfers.repository import TransferRepository
from localdrop.infrastructure.storage.files import FileStorage
from localdrop.services.downloads import DownloadService
from localdrop.services.events import EventBus
from localdrop.services.pairing import Clock, utc_now
from localdrop.services.transfers import transfer_event

logger = logging.getLogger(__name__)

_CANCELLABLE = frozenset(
    {
        TransferStatus.CREATED,
        TransferStatus.WAITING,
        TransferStatus.TRANSFERRING,
        TransferStatus.PAUSED,
    }
)


@dataclass
class MaintenanceReport:
    expired: list[str] = field(default_factory=list)
    temp_deleted: list[str] = field(default_factory=list)
    orphans_deleted: list[str] = field(default_factory=list)
    history_purged: int = 0
    sessions_expired: int = 0

    @property
    def has_changes(self) -> bool:
        return bool(
            self.expired
            or self.temp_deleted
            or self.orphans_deleted
            or self.history_purged
            or self.sessions_expired
        )


class MaintenanceService:
    def __init__(
        self,
        transfers: TransferRepository,
        sessions: SessionRepository,
        storage: FileStorage,
        downloads: DownloadService,
        events: EventBus,
        *,
        history_retention: timedelta | None,
        orphan_grace: timedelta,
        clock: Clock = utc_now,
    ) -> None:
        self._transfers = transfers
        self._sessions = sessions
        self._storage = storage
        self._downloads = downloads
        self._events = events
        self._history_retention = history_retention
        self._orphan_grace = orphan_grace
        self._clock = clock
        self._lock = threading.Lock()  # une seule passe à la fois

    def run_once(self) -> MaintenanceReport:
        with self._lock:
            report = MaintenanceReport()
            now = self._clock()
            self._expire_transfers(report)
            self._clean_orphans(report)
            if self._history_retention is not None:
                report.history_purged = self._transfers.delete_terminal_before(
                    now - self._history_retention
                )
            report.sessions_expired = self._sessions.expire_sessions(now)
            if report.has_changes:
                logger.info(
                    "Maintenance : %d expirés, %d temporaires et %d orphelins supprimés, "
                    "%d entrées d'historique purgées, %d sessions expirées",
                    len(report.expired),
                    len(report.temp_deleted),
                    len(report.orphans_deleted),
                    report.history_purged,
                    report.sessions_expired,
                )
            return report

    async def run_periodically(self, interval_seconds: float) -> None:
        while True:
            await asyncio.sleep(interval_seconds)
            try:
                await asyncio.to_thread(self.run_once)
            except Exception:
                logger.exception("Échec de la maintenance périodique")

    # ------------------------------------------------------------------ interne
    def _expire_transfers(self, report: MaintenanceReport) -> None:
        now = self._clock()
        for transfer in self._transfers.list_all():
            expired = now >= transfer.expires_at
            if transfer.direction is Direction.DOWNLOAD:
                if expired and transfer.status in _CANCELLABLE:
                    self._downloads.cancel(transfer.id)  # révoque aussi les tickets
                    report.expired.append(transfer.id)
                continue

            if expired and transfer.status in _CANCELLABLE:
                previous = transfer.status
                transfer.transition(TransferStatus.CANCELLED, now)
                transfer.error_code = "EXPIRED"
                if self._transfers.save(transfer, expected_status=previous):
                    report.expired.append(transfer.id)
                    self._events.publish("transfer.cancelled", transfer_event(transfer))
                    self._delete_temp(transfer.id, report)
                continue

            # Temporaire d'un transfert terminé : supprimé, sauf échec encore en diagnostic.
            keep_for_diagnosis = transfer.status is TransferStatus.FAILED and not expired
            if transfer.is_terminal and not keep_for_diagnosis:
                self._delete_temp(transfer.id, report)

    def _delete_temp(self, transfer_id: str, report: MaintenanceReport) -> None:
        if self._storage.temp_exists(transfer_id):
            self._storage.delete_temp(transfer_id)
            report.temp_deleted.append(transfer_id)

    def _clean_orphans(self, report: MaintenanceReport) -> None:
        known = {t.id for t in self._transfers.list_all()}
        cutoff = self._clock() - self._orphan_grace
        for transfer_id in self._storage.list_temp_ids():
            if transfer_id in known:
                continue
            modified = self._storage.temp_modified_at(transfer_id)
            if modified is not None and modified < cutoff:
                self._storage.delete_temp(transfer_id)
                report.orphans_deleted.append(transfer_id)
