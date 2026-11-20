"""Critères de recherche dans l'historique des transferts (FR-034)."""

from __future__ import annotations

from dataclasses import dataclass, field

from localdrop.domain.transfers.models import Direction, Transfer, TransferStatus

MAX_PAGE_SIZE = 200


@dataclass(frozen=True, slots=True)
class TransferQuery:
    device_id: str | None = None
    direction: Direction | None = None
    statuses: frozenset[TransferStatus] = field(default_factory=frozenset)
    text: str | None = None  # recherche dans le nom (insensible à la casse)
    limit: int = 50
    offset: int = 0

    def __post_init__(self) -> None:
        if not 1 <= self.limit <= MAX_PAGE_SIZE or self.offset < 0:
            raise ValueError("Pagination invalide")

    def matches(self, transfer: Transfer) -> bool:
        """Filtre de référence (implémentation mémoire, et contrat des dépôts)."""
        if self.device_id is not None and transfer.device_id != self.device_id:
            return False
        if self.direction is not None and transfer.direction is not self.direction:
            return False
        if self.statuses and transfer.status not in self.statuses:
            return False
        if self.text:
            needle = self.text.casefold()
            return needle in transfer.safe_filename.casefold() or needle in (
                transfer.filename.casefold()
            )
        return True


@dataclass(frozen=True, slots=True)
class TransferPage:
    items: list[Transfer]
    total: int
