"""Dépôt de transferts en mémoire (phase 3). SQLite le remplacera (phase 6/7)."""

from __future__ import annotations

import copy
import threading
from datetime import datetime

from localdrop.domain.transfers.models import ChunkRecord, Transfer
from localdrop.domain.transfers.query import TransferPage, TransferQuery


class InMemoryTransferRepository:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._transfers: dict[str, Transfer] = {}
        self._chunks: dict[str, dict[int, ChunkRecord]] = {}

    def add(self, transfer: Transfer) -> None:
        with self._lock:
            if transfer.id in self._transfers:
                raise ValueError("Transfert déjà présent")
            self._transfers[transfer.id] = copy.copy(transfer)
            self._chunks[transfer.id] = {}

    def get(self, transfer_id: str) -> Transfer | None:
        with self._lock:
            transfer = self._transfers.get(transfer_id)
            return copy.copy(transfer) if transfer else None

    def save(self, transfer: Transfer, *, expected_status: str | None = None) -> bool:
        with self._lock:
            stored = self._transfers.get(transfer.id)
            if stored is None:
                return False
            if expected_status is not None and stored.status != expected_status:
                return False
            self._transfers[transfer.id] = copy.copy(transfer)
            return True

    def list_for_device(self, device_id: str) -> list[Transfer]:
        with self._lock:
            items = [copy.copy(t) for t in self._transfers.values() if t.device_id == device_id]
        return sorted(items, key=lambda t: t.created_at)

    def list_all(self) -> list[Transfer]:
        with self._lock:
            items = [copy.copy(t) for t in self._transfers.values()]
        return sorted(items, key=lambda t: t.created_at)

    def add_chunk(self, transfer_id: str, chunk: ChunkRecord) -> bool:
        with self._lock:
            chunks = self._chunks.setdefault(transfer_id, {})
            if chunk.index in chunks:
                return False
            chunks[chunk.index] = copy.copy(chunk)
            return True

    def get_chunk(self, transfer_id: str, index: int) -> ChunkRecord | None:
        with self._lock:
            chunk = self._chunks.get(transfer_id, {}).get(index)
            return copy.copy(chunk) if chunk else None

    def received_bytes(self, transfer_id: str) -> int:
        with self._lock:
            return sum(c.size for c in self._chunks.get(transfer_id, {}).values())

    def search(self, query: TransferQuery) -> TransferPage:
        with self._lock:
            found = [copy.copy(t) for t in self._transfers.values() if query.matches(t)]
        found.sort(key=lambda t: (t.created_at, t.id), reverse=True)
        return TransferPage(found[query.offset : query.offset + query.limit], len(found))

    def delete_terminal_before(self, cutoff: datetime) -> int:
        with self._lock:
            doomed = [
                t.id for t in self._transfers.values() if t.is_terminal and t.updated_at < cutoff
            ]
            for transfer_id in doomed:
                del self._transfers[transfer_id]
                self._chunks.pop(transfer_id, None)
            return len(doomed)

    def get_chunks(self, transfer_id: str) -> dict[int, ChunkRecord]:
        with self._lock:
            return {i: copy.copy(c) for i, c in self._chunks.get(transfer_id, {}).items()}
