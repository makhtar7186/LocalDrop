"""Transferts sortants PC -> téléphone (FR-020, FR-029, §6.3, §9.4).

- Le fichier source n'est pas copié : taille et date de modification sont mémorisées
  et revérifiées à chaque téléchargement.
- Un lien de téléchargement ne peut pas porter d'en-tête Authorization : le téléphone
  obtient un ticket court (lié au transfert et à l'appareil) qu'il passe en query.
- Servir les octets ne prouve pas la réception : seul l'accusé du téléphone fait passer
  le transfert à ``completed`` (§6.3).
"""

from __future__ import annotations

import hmac
import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from localdrop.core.errors import ConflictError, LocalDropError, NotFoundError, UnauthorizedError
from localdrop.domain.devices.models import Device
from localdrop.domain.sessions.tokens import generate_id, generate_secret, hash_secret
from localdrop.domain.transfers.filenames import sanitize_filename
from localdrop.domain.transfers.models import (
    Direction,
    Transfer,
    TransferStatus,
    total_chunks_for,
)
from localdrop.domain.transfers.repository import TransferRepository
from localdrop.services.events import EventBus
from localdrop.services.pairing import Clock, PairingService, utc_now
from localdrop.services.transfers import transfer_event

logger = logging.getLogger(__name__)


class SourceUnavailableError(LocalDropError):
    code = "SOURCE_UNAVAILABLE"
    status_code = 410


class InvalidSourceError(LocalDropError):
    code = "INVALID_SOURCE"
    status_code = 400


@dataclass(frozen=True, slots=True)
class DownloadTicket:
    token: str
    expires_at: datetime


@dataclass(slots=True)
class _TicketRecord:
    transfer_id: str
    device_id: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class DownloadGrant:
    transfer: Transfer
    path: Path


class DownloadService:
    def __init__(
        self,
        repository: TransferRepository,
        pairing: PairingService,
        events: EventBus,
        *,
        chunk_size: int,
        retention: timedelta,
        ticket_ttl: timedelta,
        clock: Clock = utc_now,
    ) -> None:
        self._repo = repository
        self._pairing = pairing
        self._events = events
        self._chunk_size = chunk_size
        self._retention = retention
        self._ticket_ttl = ticket_ttl
        self._clock = clock
        self._lock = threading.Lock()
        self._tickets: dict[str, _TicketRecord] = {}

    # ------------------------------------------------------------------ PC : mise à disposition
    def offer(self, source: Path, device_id: str) -> Transfer:
        """Met un fichier local à disposition d'un appareil approuvé."""
        device = self._pairing.active_device(device_id)
        try:
            path = source.resolve(strict=True)
            stat = path.stat()
        except OSError as exc:
            raise InvalidSourceError("Fichier introuvable ou illisible") from exc
        if not path.is_file():
            raise InvalidSourceError("Seuls les fichiers peuvent être envoyés")
        if not os.access(path, os.R_OK):
            raise InvalidSourceError("Fichier illisible")

        now = self._clock()
        name = sanitize_filename(path.name)
        transfer = Transfer(
            id=generate_id(),
            device_id=device.id,
            direction=Direction.DOWNLOAD,
            filename=name,
            safe_filename=name,
            total_size=stat.st_size,
            chunk_size=self._chunk_size,
            total_chunks=total_chunks_for(stat.st_size, self._chunk_size),
            status=TransferStatus.CREATED,
            created_at=now,
            updated_at=now,
            expires_at=now + self._retention,
            source_path=str(path),
            source_mtime_ns=stat.st_mtime_ns,
        )
        transfer.transition(TransferStatus.WAITING, now)
        self._repo.add(transfer)
        logger.info("Fichier proposé à %s : %s (%d octets)", device.id, name, stat.st_size)
        self._events.publish("transfer.created", transfer_event(transfer))
        return transfer

    # ------------------------------------------------------------------ téléphone : ticket
    def issue_ticket(self, device: Device, transfer_id: str) -> DownloadTicket:
        transfer = self._own_download(device, transfer_id)
        if transfer.status not in (TransferStatus.WAITING, TransferStatus.TRANSFERRING):
            raise _not_downloadable(transfer)
        token = generate_secret()
        expires_at = self._clock() + self._ticket_ttl
        with self._lock:
            self._purge_expired_locked()
            self._tickets[hash_secret(token)] = _TicketRecord(transfer.id, device.id, expires_at)
        return DownloadTicket(token, expires_at)

    # ------------------------------------------------------------------ téléchargement
    def open_download(self, transfer_id: str, ticket: str) -> DownloadGrant:
        """Valide le ticket, l'appareil et la source ; passe le transfert en cours."""
        with self._lock:
            record = self._tickets.get(hash_secret(ticket))
        now = self._clock()
        if (
            record is None
            or now >= record.expires_at
            or not hmac.compare_digest(record.transfer_id, transfer_id)
        ):
            raise UnauthorizedError(
                "Lien de téléchargement invalide ou expiré", code="TICKET_INVALID"
            )
        # L'appareil a pu être révoqué depuis l'émission du ticket.
        device = self._pairing.active_device(record.device_id)

        transfer = self._own_download(device, transfer_id)
        if transfer.status not in (TransferStatus.WAITING, TransferStatus.TRANSFERRING):
            raise _not_downloadable(transfer)
        path = self._checked_source(transfer)

        if transfer.status is TransferStatus.WAITING:
            transfer.transition(TransferStatus.TRANSFERRING, now)
            if self._repo.save(transfer, expected_status=TransferStatus.WAITING):
                self._events.publish("transfer.progress", transfer_event(transfer))
            else:
                transfer = self._own_download(device, transfer_id)
        return DownloadGrant(transfer, path)

    def mark_served(self, transfer_id: str) -> None:
        """Le fichier a été envoyé jusqu'au bout (indicatif : ce n'est pas une preuve)."""
        transfer = self._repo.get(transfer_id)
        if transfer is None or transfer.fully_served:
            return
        transfer.fully_served = True
        transfer.received_bytes = transfer.total_size
        transfer.updated_at = self._clock()
        if self._repo.save(transfer, expected_status=transfer.status):
            self._events.publish("transfer.progress", transfer_event(transfer))

    # ------------------------------------------------------------------ accusé / annulation
    def confirm(self, device: Device, transfer_id: str) -> Transfer:
        """Accusé de réception du téléphone : seul signal fiable de livraison (§6.3)."""
        transfer = self._own_download(device, transfer_id)
        if transfer.status is not TransferStatus.TRANSFERRING:
            raise ConflictError(
                "Le fichier n'a pas encore été téléchargé",
                code="DOWNLOAD_NOT_STARTED"
                if transfer.status is TransferStatus.WAITING
                else "TRANSFER_NOT_COMPLETABLE",
                details={"status": transfer.status.value},
            )
        now = self._clock()
        transfer.transition(TransferStatus.VERIFYING, now)
        if not self._repo.save(transfer, expected_status=TransferStatus.TRANSFERRING):
            raise ConflictError("Transfert déjà confirmé", code="TRANSFER_NOT_COMPLETABLE")
        transfer.transition(TransferStatus.COMPLETED, now)
        transfer.received_bytes = transfer.total_size
        self._repo.save(transfer)
        self._revoke_tickets(transfer_id)
        logger.info("Réception confirmée par %s : %s", device.id, transfer.safe_filename)
        self._events.publish("transfer.completed", transfer_event(transfer))
        return transfer

    def cancel(self, transfer_id: str, device: Device | None = None) -> Transfer:
        """Annulation par le téléphone (device) ou par le PC (device=None)."""
        transfer = (
            self._own_download(device, transfer_id) if device else self._repo.get(transfer_id)
        )
        if transfer is None or transfer.direction is not Direction.DOWNLOAD:
            raise NotFoundError("Transfert introuvable", code="TRANSFER_NOT_FOUND")
        previous = transfer.status
        transfer.transition(TransferStatus.CANCELLED, self._clock())
        if not self._repo.save(transfer, expected_status=previous):
            raise ConflictError("Transfert modifié entre-temps", code="TRANSFER_NOT_COMPLETABLE")
        self._revoke_tickets(transfer_id)
        self._events.publish("transfer.cancelled", transfer_event(transfer))
        return transfer

    # ------------------------------------------------------------------ interne
    def _own_download(self, device: Device, transfer_id: str) -> Transfer:
        transfer = self._repo.get(transfer_id)
        if (
            transfer is None
            or transfer.device_id != device.id
            or transfer.direction is not Direction.DOWNLOAD
        ):
            raise NotFoundError("Transfert introuvable", code="TRANSFER_NOT_FOUND")
        return transfer

    def _checked_source(self, transfer: Transfer) -> Path:
        path = Path(transfer.source_path or "")
        try:
            stat = path.stat()
        except OSError as exc:
            raise SourceUnavailableError("Le fichier n'est plus disponible sur le PC") from exc
        if stat.st_size != transfer.total_size or stat.st_mtime_ns != transfer.source_mtime_ns:
            raise SourceUnavailableError(
                "Le fichier a été modifié sur le PC depuis son envoi", code="SOURCE_CHANGED"
            )
        return path

    def _revoke_tickets(self, transfer_id: str) -> None:
        with self._lock:
            for key in [k for k, r in self._tickets.items() if r.transfer_id == transfer_id]:
                del self._tickets[key]

    def _purge_expired_locked(self) -> None:
        now = self._clock()
        for key in [k for k, r in self._tickets.items() if now >= r.expires_at]:
            del self._tickets[key]


def _not_downloadable(transfer: Transfer) -> ConflictError:
    return ConflictError(
        "Ce fichier n'est plus disponible au téléchargement",
        code="TRANSFER_NOT_DOWNLOADABLE",
        details={"status": transfer.status.value},
    )
