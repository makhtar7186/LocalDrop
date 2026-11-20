"""Cas d'usage des transferts entrants téléphone -> PC (FR-020 à FR-028, §9).

Méthodes synchrones (I/O disque) : les routes les appellent via un thread.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta

from localdrop.core.errors import ConflictError, LocalDropError, NotFoundError
from localdrop.domain.devices.models import Device
from localdrop.domain.sessions.tokens import generate_id
from localdrop.domain.transfers.filenames import sanitize_filename
from localdrop.domain.transfers.models import (
    ACTIVE_STATUSES,
    ChunkRecord,
    Direction,
    InvalidChunkError,
    Transfer,
    TransferStatus,
    total_chunks_for,
)
from localdrop.domain.transfers.query import TransferPage, TransferQuery
from localdrop.domain.transfers.repository import TransferRepository
from localdrop.infrastructure.storage.files import FileStorage
from localdrop.services.events import EventBus
from localdrop.services.pairing import Clock, utc_now

logger = logging.getLogger(__name__)

_PROGRESS_MIN_INTERVAL = 0.25  # ~4 événements de progression par seconde et par transfert


@dataclass
class ReconcileReport:
    paused: list[str] = field(default_factory=list)
    reverified: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    orphans_deleted: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.paused or self.reverified or self.failed or self.orphans_deleted)


class FileTooLargeError(LocalDropError):
    code = "FILE_TOO_LARGE"
    status_code = 413


class TransferService:
    def __init__(
        self,
        repository: TransferRepository,
        storage: FileStorage,
        events: EventBus,
        *,
        chunk_size: int,
        retention: timedelta,
        max_file_size: int | None = None,
        clock: Clock = utc_now,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._repo = repository
        self._storage = storage
        self._events = events
        self._chunk_size = chunk_size
        self._retention = retention
        self._max_file_size = max_file_size
        self._clock = clock
        self._monotonic = monotonic
        self._locks_guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}
        self._last_progress: dict[str, float] = {}

    # ------------------------------------------------------------------ création
    def create_upload(self, device: Device, filename: str, size: int) -> Transfer:
        if self._max_file_size is not None and size > self._max_file_size:
            raise FileTooLargeError(
                "Fichier trop volumineux", details={"max_file_size": self._max_file_size}
            )
        self._storage.check_free_space(size)

        now = self._clock()
        transfer = Transfer(
            id=generate_id(),
            device_id=device.id,
            direction=Direction.UPLOAD,
            filename=filename,
            safe_filename=sanitize_filename(filename),
            total_size=size,
            chunk_size=self._chunk_size,
            total_chunks=total_chunks_for(size, self._chunk_size),
            status=TransferStatus.CREATED,
            created_at=now,
            updated_at=now,
            expires_at=now + self._retention,
        )
        self._storage.create_temp(transfer.id)
        transfer.transition(TransferStatus.WAITING, now)
        self._repo.add(transfer)
        logger.info(
            "Transfert %s créé : %s (%d octets, %d blocs)",
            transfer.id,
            transfer.safe_filename,
            size,
            transfer.total_chunks,
        )
        self._events.publish("transfer.created", transfer_event(transfer))
        return transfer

    # ------------------------------------------------------------------ lecture
    def get(self, device: Device, transfer_id: str) -> Transfer:
        transfer = self._repo.get(transfer_id)
        # Un transfert d'un autre appareil est traité comme inexistant.
        if transfer is None or transfer.device_id != device.id:
            raise NotFoundError("Transfert introuvable", code="TRANSFER_NOT_FOUND")
        return transfer

    def _own_upload(self, device: Device, transfer_id: str) -> Transfer:
        transfer = self.get(device, transfer_id)
        if transfer.direction is not Direction.UPLOAD:
            raise NotFoundError("Transfert entrant introuvable", code="TRANSFER_NOT_FOUND")
        return transfer

    def list_for(self, device: Device) -> list[Transfer]:
        return self._repo.list_for_device(device.id)

    def list_all(self) -> list[Transfer]:
        return self._repo.list_all()

    def history(self, query: TransferQuery) -> TransferPage:
        """Historique filtré (FR-034). L'appelant fixe ``device_id`` pour un téléphone."""
        return self._repo.search(query)

    def received_chunks(self, device: Device, transfer_id: str) -> list[int]:
        self._own_upload(device, transfer_id)
        return sorted(self._repo.get_chunks(transfer_id))

    def expected_chunk_size(self, device: Device, transfer_id: str, index: int) -> int:
        return self._own_upload(device, transfer_id).expected_chunk_size(index)

    # ------------------------------------------------------------------ blocs
    def put_chunk(
        self, device: Device, transfer_id: str, index: int, data: bytes, declared_sha256: str
    ) -> tuple[Transfer, bool]:
        """Valide puis écrit un bloc. Renvoie (transfert, déjà_reçu)."""
        declared = declared_sha256.lower()
        with self._lock_for(transfer_id):
            transfer = self._own_upload(device, transfer_id)
            expected_size = transfer.expected_chunk_size(index)

            existing = self._repo.get_chunk(transfer_id, index)
            actual = hashlib.sha256(data).hexdigest()
            if existing is not None:
                # Idempotence (§9.3) : même contenu = déjà validé ; contenu différent = refus.
                if hmac.compare_digest(existing.sha256, actual):
                    return transfer, True
                raise ConflictError(
                    "Un autre contenu a déjà été validé pour ce bloc",
                    code="CHUNK_CONFLICT",
                    details={"index": index},
                )

            if transfer.status is TransferStatus.WAITING:
                transfer.transition(TransferStatus.TRANSFERRING, self._clock())
            elif transfer.status is TransferStatus.PAUSED:
                raise ConflictError(
                    "Transfert en pause : reprenez-le avant d'envoyer des blocs",
                    code="TRANSFER_PAUSED",
                )
            elif transfer.status is not TransferStatus.TRANSFERRING:
                raise ConflictError(
                    "Le transfert n'accepte pas de bloc dans cet état",
                    code="TRANSFER_NOT_ACCEPTING_CHUNKS",
                    details={"status": transfer.status.value},
                )

            if len(data) != expected_size:
                raise InvalidChunkError(
                    "Taille de bloc incorrecte",
                    code="CHUNK_SIZE_MISMATCH",
                    details={"index": index, "expected": expected_size, "received": len(data)},
                )
            if not hmac.compare_digest(actual, declared):
                raise InvalidChunkError(
                    "Empreinte du bloc incorrecte",
                    code="CHUNK_HASH_MISMATCH",
                    details={"index": index},
                )

            # Durable d'abord, enregistré ensuite : un bloc n'est confirmé qu'après les deux.
            self._storage.write_chunk(transfer_id, transfer.chunk_offset(index), data)
            now = self._clock()
            self._repo.add_chunk(transfer_id, ChunkRecord(index, len(data), actual, now))
            transfer.received_bytes = self._repo.received_bytes(transfer_id)
            transfer.updated_at = now
            self._repo.save(transfer)

        self._publish_progress(transfer)
        return transfer, False

    # ------------------------------------------------------------------ finalisation
    def complete(self, device: Device, transfer_id: str, sha256: str) -> Transfer:
        """Vérifie taille et SHA-256 global puis publie le fichier (§9.2-8 à 10).

        Sérialisé avec les écritures de blocs par le verrou du transfert ; l'update
        conditionnel garantit en plus qu'un seul appel passe en vérification.
        """
        with self._lock_for(transfer_id):
            return self._complete_locked(device, transfer_id, sha256.lower())

    def _complete_locked(self, device: Device, transfer_id: str, sha256: str) -> Transfer:
        transfer = self._own_upload(device, transfer_id)
        now = self._clock()

        # Fichier vide : aucun bloc, on passe directement en transfert.
        if transfer.status is TransferStatus.WAITING and transfer.total_chunks == 0:
            transfer.transition(TransferStatus.TRANSFERRING, now)
            if not self._repo.save(transfer, expected_status=TransferStatus.WAITING):
                raise _already_finalizing()

        if transfer.status is not TransferStatus.TRANSFERRING:
            raise _already_finalizing(transfer.status)

        received = self._repo.get_chunks(transfer_id)
        missing = [i for i in range(transfer.total_chunks) if i not in received]
        if missing:
            raise ConflictError(
                "Des blocs sont manquants",
                code="CHUNKS_MISSING",
                details={"missing": missing[:100], "missing_count": len(missing)},
            )

        # Update conditionnel : un seul appel concurrent peut passer en vérification.
        # Le hash annoncé est mémorisé : une vérification interrompue par un arrêt
        # brutal est rejouée au démarrage suivant (reconcile).
        transfer.transition(TransferStatus.VERIFYING, now)
        transfer.expected_sha256 = sha256
        if not self._repo.save(transfer, expected_status=TransferStatus.TRANSFERRING):
            raise _already_finalizing()
        return self._verify_and_publish(transfer, sha256)

    def _verify_and_publish(self, transfer: Transfer, client_sha256: str) -> Transfer:
        error_code: str | None = None
        actual_sha: str | None = None
        try:
            if self._storage.temp_size(transfer.id) != transfer.total_size:
                error_code = "FILE_SIZE_MISMATCH"
            else:
                actual_sha = self._storage.temp_sha256(transfer.id)
                if not hmac.compare_digest(actual_sha, client_sha256):
                    error_code = "FILE_HASH_MISMATCH"
        except OSError:
            logger.exception("Vérification impossible pour %s", transfer.id)
            error_code = "VERIFICATION_ERROR"

        now = self._clock()
        if error_code is not None:
            # Le fichier temporaire est conservé pour diagnostic jusqu'à expiration.
            transfer.transition(TransferStatus.FAILED, now)
            transfer.error_code = error_code
            self._repo.save(transfer)
            logger.warning("Transfert %s en échec : %s", transfer.id, error_code)
            self._events.publish("transfer.failed", transfer_event(transfer))
            return transfer

        final_path = self._storage.publish(transfer.id, transfer.safe_filename)
        transfer.transition(TransferStatus.COMPLETED, self._clock())
        transfer.sha256 = actual_sha
        transfer.final_path = str(final_path)
        transfer.safe_filename = final_path.name
        self._repo.save(transfer)
        self._events.publish("transfer.completed", transfer_event(transfer))
        return transfer

    # ------------------------------------------------------------------ annulation
    def cancel(self, device: Device, transfer_id: str) -> Transfer:
        with self._lock_for(transfer_id):
            transfer = self._own_upload(device, transfer_id)
            previous = transfer.status
            transfer.transition(TransferStatus.CANCELLED, self._clock())
            if not self._repo.save(transfer, expected_status=previous):
                raise _already_finalizing()
            self._storage.delete_temp(transfer_id)
        logger.info("Transfert %s annulé", transfer_id)
        self._events.publish("transfer.cancelled", transfer_event(transfer))
        return transfer

    # ------------------------------------------------------------------ pause / reprise
    def pause(self, device: Device, transfer_id: str) -> Transfer:
        with self._lock_for(transfer_id):
            transfer = self._own_upload(device, transfer_id)
            if transfer.status is TransferStatus.PAUSED:
                return transfer
            transfer.transition(TransferStatus.PAUSED, self._clock())
            if not self._repo.save(transfer, expected_status=TransferStatus.TRANSFERRING):
                raise _already_finalizing()
        self._events.publish("transfer.paused", transfer_event(transfer))
        return transfer

    def resume(self, device: Device, transfer_id: str) -> Transfer:
        """Reprise (FR-026), idempotente : le client envoie ensuite les blocs manquants."""
        with self._lock_for(transfer_id):
            transfer = self._own_upload(device, transfer_id)
            if transfer.status in (TransferStatus.WAITING, TransferStatus.TRANSFERRING):
                return transfer
            transfer.transition(TransferStatus.TRANSFERRING, self._clock())
            if not self._repo.save(transfer, expected_status=TransferStatus.PAUSED):
                raise _already_finalizing()
        self._events.publish("transfer.progress", transfer_event(transfer))
        return transfer

    # ------------------------------------------------------------------ démarrage
    def reconcile(self) -> ReconcileReport:
        """Remet la base et les fichiers temporaires en cohérence après un arrêt (§5.2).

        - upload actif sans fichier temporaire -> failed (TEMP_FILE_MISSING) ;
        - upload qui recevait des blocs -> paused (le client le reprend) ;
        - vérification interrompue -> rejouée avec le hash mémorisé ;
        - fichier temporaire sans upload actif -> supprimé.
        """
        report = ReconcileReport()
        active_uploads: set[str] = set()
        for transfer in self._repo.list_all():
            if transfer.direction is not Direction.UPLOAD or transfer.is_terminal:
                continue
            with self._lock_for(transfer.id):
                if not self._storage.temp_exists(transfer.id):
                    self._fail(transfer, "TEMP_FILE_MISSING")
                    report.failed.append(transfer.id)
                    continue
                active_uploads.add(transfer.id)
                if transfer.status is TransferStatus.TRANSFERRING:
                    transfer.received_bytes = self._repo.received_bytes(transfer.id)
                    transfer.transition(TransferStatus.PAUSED, self._clock())
                    self._repo.save(transfer, expected_status=TransferStatus.TRANSFERRING)
                    report.paused.append(transfer.id)
                elif transfer.status is TransferStatus.VERIFYING:
                    if transfer.expected_sha256:
                        self._verify_and_publish(transfer, transfer.expected_sha256)
                    else:
                        self._fail(transfer, "VERIFICATION_INTERRUPTED")
                    report.reverified.append(transfer.id)

        for orphan in self._storage.list_temp_ids():
            if orphan not in active_uploads:
                self._storage.delete_temp(orphan)
                report.orphans_deleted.append(orphan)

        if report.has_changes:
            logger.info(
                "Réconciliation : %d en pause, %d revérifiés, %d en échec, %d orphelins supprimés",
                len(report.paused),
                len(report.reverified),
                len(report.failed),
                len(report.orphans_deleted),
            )
        return report

    def _fail(self, transfer: Transfer, error_code: str) -> None:
        """Échec explicite et traçable, en respectant la machine à états (§8.3)."""
        previous = transfer.status
        now = self._clock()
        # « failed » n'est atteignable que depuis « verifying » : on suit le chemin légal.
        path = {
            TransferStatus.CREATED: [TransferStatus.WAITING, TransferStatus.TRANSFERRING],
            TransferStatus.WAITING: [TransferStatus.TRANSFERRING],
            TransferStatus.PAUSED: [TransferStatus.TRANSFERRING],
        }.get(previous, [])
        for step in [*path, TransferStatus.VERIFYING]:
            if transfer.status is not TransferStatus.VERIFYING:
                transfer.transition(step, now)
        transfer.transition(TransferStatus.FAILED, now)
        transfer.error_code = error_code
        self._repo.save(transfer, expected_status=previous)
        logger.warning("Transfert %s en échec : %s", transfer.id, error_code)
        self._events.publish("transfer.failed", transfer_event(transfer))

    def has_active_transfers(self) -> bool:
        return any(t.status in ACTIVE_STATUSES for t in self._repo.list_all())

    # ------------------------------------------------------------------ interne
    def _lock_for(self, transfer_id: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(transfer_id, threading.Lock())

    def _publish_progress(self, transfer: Transfer) -> None:
        now = self._monotonic()
        last = self._last_progress.get(transfer.id)
        is_last_chunk = transfer.received_bytes >= transfer.total_size
        if last is not None and now - last < _PROGRESS_MIN_INTERVAL and not is_last_chunk:
            return
        self._last_progress[transfer.id] = now
        self._events.publish("transfer.progress", transfer_event(transfer))


def _already_finalizing(status: TransferStatus | None = None) -> ConflictError:
    return ConflictError(
        "Le transfert est déjà en cours de finalisation ou terminé",
        code="TRANSFER_NOT_COMPLETABLE",
        details={"status": status.value} if status else {},
    )


def transfer_event(transfer: Transfer) -> dict[str, object]:
    """Charge utile des événements transfer.* (bus, WebSocket, desktop)."""
    return {
        "transfer_id": transfer.id,
        "device_id": transfer.device_id,
        "direction": transfer.direction.value,
        "filename": transfer.safe_filename,
        "status": transfer.status.value,
        "total_size": transfer.total_size,
        "received_bytes": transfer.received_bytes,
        "error_code": transfer.error_code,
        "fully_served": transfer.fully_served,
    }
