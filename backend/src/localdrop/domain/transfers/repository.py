"""Port de persistance des transferts (implémenté dans infrastructure/)."""

from __future__ import annotations

from typing import Protocol

from localdrop.domain.transfers.models import ChunkRecord, Transfer


class TransferRepository(Protocol):
    def add(self, transfer: Transfer) -> None: ...

    def get(self, transfer_id: str) -> Transfer | None: ...

    def save(self, transfer: Transfer, *, expected_status: str | None = None) -> bool:
        """Enregistre le transfert. Avec ``expected_status``, n'écrit que si l'état stocké
        vaut encore cette valeur (update conditionnel) et renvoie False sinon."""
        ...

    def list_for_device(self, device_id: str) -> list[Transfer]: ...

    def list_all(self) -> list[Transfer]: ...

    def add_chunk(self, transfer_id: str, chunk: ChunkRecord) -> bool:
        """Ajoute un bloc validé. False si l'index existe déjà (contrainte unique)."""
        ...

    def get_chunks(self, transfer_id: str) -> dict[int, ChunkRecord]: ...

    def get_chunk(self, transfer_id: str, index: int) -> ChunkRecord | None: ...

    def received_bytes(self, transfer_id: str) -> int:
        """Somme des tailles des blocs validés (source de vérité de la progression)."""
        ...
