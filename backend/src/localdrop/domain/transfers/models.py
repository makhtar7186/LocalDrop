"""Transferts : machine à états (§8.3) et calcul des blocs (§9)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from localdrop.core.errors import ConflictError, LocalDropError


class TransferStatus(StrEnum):
    CREATED = "created"
    WAITING = "waiting"
    TRANSFERRING = "transferring"
    PAUSED = "paused"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Direction(StrEnum):
    UPLOAD = "upload"  # téléphone -> PC
    DOWNLOAD = "download"  # PC -> téléphone


_S = TransferStatus
_TRANSITIONS: dict[TransferStatus, frozenset[TransferStatus]] = {
    _S.CREATED: frozenset({_S.WAITING, _S.CANCELLED}),
    _S.WAITING: frozenset({_S.TRANSFERRING, _S.CANCELLED}),
    _S.TRANSFERRING: frozenset({_S.VERIFYING, _S.PAUSED, _S.CANCELLED}),
    _S.PAUSED: frozenset({_S.TRANSFERRING, _S.CANCELLED}),
    _S.VERIFYING: frozenset({_S.COMPLETED, _S.FAILED}),
    _S.COMPLETED: frozenset(),
    _S.FAILED: frozenset(),
    _S.CANCELLED: frozenset(),
}

ACTIVE_STATUSES = frozenset({_S.CREATED, _S.WAITING, _S.TRANSFERRING, _S.PAUSED, _S.VERIFYING})


class InvalidTransitionError(ConflictError):
    code = "INVALID_TRANSITION"


class InvalidChunkError(LocalDropError):
    code = "INVALID_CHUNK"
    status_code = 422


def can_transition(current: TransferStatus, target: TransferStatus) -> bool:
    return target in _TRANSITIONS[current]


def total_chunks_for(total_size: int, chunk_size: int) -> int:
    if total_size < 0 or chunk_size <= 0:
        raise ValueError("Taille invalide")
    return -(-total_size // chunk_size)  # division entière par excès


@dataclass(slots=True)
class ChunkRecord:
    index: int
    size: int
    sha256: str
    received_at: datetime


@dataclass(slots=True)
class Transfer:
    id: str
    device_id: str
    direction: Direction
    filename: str  # nom d'origine (affichage uniquement)
    safe_filename: str  # nom assaini proposé pour la publication
    total_size: int
    chunk_size: int
    total_chunks: int
    status: TransferStatus
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    received_bytes: int = 0
    sha256: str | None = None  # hash global vérifié
    final_path: str | None = None
    error_code: str | None = None
    # Sortants (PC -> téléphone) : fichier source non copié, contrôlé à chaque service.
    source_path: str | None = None
    source_mtime_ns: int | None = None
    fully_served: bool = False  # servi en entier au moins une fois (≠ reçu : §6.3)

    @property
    def is_terminal(self) -> bool:
        return not _TRANSITIONS[self.status]

    def transition(self, target: TransferStatus, now: datetime) -> None:
        if not can_transition(self.status, target):
            raise InvalidTransitionError(
                f"Transition impossible : {self.status} -> {target}",
                details={"from": self.status.value, "to": target.value},
            )
        self.status = target
        self.updated_at = now

    def chunk_offset(self, index: int) -> int:
        return index * self.chunk_size

    def expected_chunk_size(self, index: int) -> int:
        if not 0 <= index < self.total_chunks:
            raise InvalidChunkError(
                "Index de bloc hors limites",
                code="CHUNK_INDEX_OUT_OF_RANGE",
                details={"index": index, "total_chunks": self.total_chunks},
            )
        if index == self.total_chunks - 1:
            return self.total_size - self.chunk_size * (self.total_chunks - 1)
        return self.chunk_size


def missing_chunks(total_chunks: int, received: set[int]) -> list[int]:
    return [i for i in range(total_chunks) if i not in received]
