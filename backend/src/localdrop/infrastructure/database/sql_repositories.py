"""Dépôts SQLite implémentant les ports du domaine (sessions, appareils, transferts).

Transactions courtes : une par opération. Les changements d'état concurrents passent
par un UPDATE conditionnel sur le statut attendu (§9.3).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import sessionmaker

from localdrop.domain.devices.models import Device, DeviceStatus, Platform
from localdrop.domain.sessions.models import Session, SessionStatus
from localdrop.domain.transfers.models import ChunkRecord, Direction, Transfer, TransferStatus
from localdrop.domain.transfers.query import TransferPage, TransferQuery
from localdrop.infrastructure.database.models import ChunkRow, DeviceRow, SessionRow, TransferRow

SessionFactory = sessionmaker[OrmSession]

_LIKE_ESCAPE = "!"


def _escape_like(text: str) -> str:
    """Recherche littérale : les jokers LIKE saisis par l'utilisateur sont neutralisés."""
    return text.replace("!", "!!").replace("%", "!%").replace("_", "!_")


# ----------------------------------------------------------------------------- conversions
def _session_to_domain(row: SessionRow) -> Session:
    return Session(
        id=row.id,
        created_at=row.created_at,
        expires_at=row.expires_at,
        status=SessionStatus(row.status),
        pairing_secret_hash=row.pairing_secret_hash,
        pairing_expires_at=row.pairing_expires_at,
    )


def _session_values(session: Session) -> dict[str, Any]:
    return {
        "id": session.id,
        "created_at": session.created_at,
        "expires_at": session.expires_at,
        "status": session.status.value,
        "pairing_secret_hash": session.pairing_secret_hash,
        "pairing_expires_at": session.pairing_expires_at,
    }


def _device_to_domain(row: DeviceRow) -> Device:
    return Device(
        id=row.id,
        session_id=row.session_id,
        display_name=row.display_name,
        platform=Platform(row.platform),
        status=DeviceStatus(row.status),
        token_hash=row.token_hash,
        client_ip=row.client_ip,
        created_at=row.created_at,
        last_seen_at=row.last_seen_at,
        connected_at=row.connected_at,
    )


def _device_values(device: Device) -> dict[str, Any]:
    return {
        "id": device.id,
        "session_id": device.session_id,
        "display_name": device.display_name,
        "platform": device.platform.value,
        "status": device.status.value,
        "token_hash": device.token_hash,
        "client_ip": device.client_ip,
        "created_at": device.created_at,
        "last_seen_at": device.last_seen_at,
        "connected_at": device.connected_at,
    }


def _transfer_to_domain(row: TransferRow) -> Transfer:
    return Transfer(
        id=row.id,
        device_id=row.device_id,
        direction=Direction(row.direction),
        filename=row.filename,
        safe_filename=row.safe_filename,
        total_size=row.total_size,
        chunk_size=row.chunk_size,
        total_chunks=row.total_chunks,
        status=TransferStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
        expires_at=row.expires_at,
        received_bytes=row.received_bytes,
        sha256=row.sha256,
        expected_sha256=row.expected_sha256,
        final_path=row.final_path,
        error_code=row.error_code,
        source_path=row.source_path,
        source_mtime_ns=row.source_mtime_ns,
        fully_served=row.fully_served,
    )


def _transfer_values(transfer: Transfer) -> dict[str, Any]:
    return {
        "id": transfer.id,
        "device_id": transfer.device_id,
        "direction": transfer.direction.value,
        "filename": transfer.filename,
        "safe_filename": transfer.safe_filename,
        "total_size": transfer.total_size,
        "chunk_size": transfer.chunk_size,
        "total_chunks": transfer.total_chunks,
        "status": transfer.status.value,
        "created_at": transfer.created_at,
        "updated_at": transfer.updated_at,
        "expires_at": transfer.expires_at,
        "received_bytes": transfer.received_bytes,
        "sha256": transfer.sha256,
        "expected_sha256": transfer.expected_sha256,
        "final_path": transfer.final_path,
        "error_code": transfer.error_code,
        "source_path": transfer.source_path,
        "source_mtime_ns": transfer.source_mtime_ns,
        "fully_served": transfer.fully_served,
    }


def _chunk_to_domain(row: ChunkRow) -> ChunkRecord:
    return ChunkRecord(row.chunk_index, row.size, row.sha256, row.received_at)


# ----------------------------------------------------------------------------- sessions
class SqlSessionRepository:
    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    def save_session(self, session: Session) -> None:
        with self._sessions.begin() as db:
            db.merge(SessionRow(**_session_values(session)))

    def get_session(self, session_id: str) -> Session | None:
        with self._sessions() as db:
            row = db.get(SessionRow, session_id)
            return _session_to_domain(row) if row else None

    def find_active_session(self, now: datetime) -> Session | None:
        with self._sessions() as db:
            row = db.scalars(
                select(SessionRow)
                .where(SessionRow.status == SessionStatus.ACTIVE.value)
                .where(SessionRow.expires_at > now)
                .order_by(SessionRow.created_at.desc())
                .limit(1)
            ).first()
            return _session_to_domain(row) if row else None

    def expire_sessions(self, now: datetime) -> int:
        with self._sessions.begin() as db:
            result = db.execute(
                update(SessionRow)
                .where(SessionRow.status == SessionStatus.ACTIVE.value)
                .where(SessionRow.expires_at <= now)
                .values(status=SessionStatus.EXPIRED.value)
            )
            return int(getattr(result, "rowcount", 0) or 0)

    def save_device(self, device: Device) -> None:
        with self._sessions.begin() as db:
            db.merge(DeviceRow(**_device_values(device)))

    def get_device(self, device_id: str) -> Device | None:
        with self._sessions() as db:
            row = db.get(DeviceRow, device_id)
            return _device_to_domain(row) if row else None

    def get_device_by_token_hash(self, token_hash: str) -> Device | None:
        with self._sessions() as db:
            row = db.scalars(select(DeviceRow).where(DeviceRow.token_hash == token_hash)).first()
            return _device_to_domain(row) if row else None

    def list_devices(self, session_id: str) -> list[Device]:
        with self._sessions() as db:
            rows = db.scalars(
                select(DeviceRow)
                .where(DeviceRow.session_id == session_id)
                .order_by(DeviceRow.created_at)
            )
            return [_device_to_domain(r) for r in rows]


# ----------------------------------------------------------------------------- transferts
class SqlTransferRepository:
    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    def add(self, transfer: Transfer) -> None:
        with self._sessions.begin() as db:
            db.add(TransferRow(**_transfer_values(transfer)))

    def get(self, transfer_id: str) -> Transfer | None:
        with self._sessions() as db:
            row = db.get(TransferRow, transfer_id)
            return _transfer_to_domain(row) if row else None

    def save(self, transfer: Transfer, *, expected_status: str | None = None) -> bool:
        statement = update(TransferRow).where(TransferRow.id == transfer.id)
        if expected_status is not None:
            # Update conditionnel : seul l'appel qui voit encore l'état attendu gagne.
            statement = statement.where(TransferRow.status == str(expected_status))
        values = _transfer_values(transfer)
        del values["id"]
        with self._sessions.begin() as db:
            result = db.execute(statement.values(**values))
            return bool(getattr(result, "rowcount", 0) == 1)

    def list_for_device(self, device_id: str) -> list[Transfer]:
        with self._sessions() as db:
            rows = db.scalars(
                select(TransferRow)
                .where(TransferRow.device_id == device_id)
                .order_by(TransferRow.created_at)
            )
            return [_transfer_to_domain(r) for r in rows]

    def list_all(self) -> list[Transfer]:
        with self._sessions() as db:
            rows = db.scalars(select(TransferRow).order_by(TransferRow.created_at))
            return [_transfer_to_domain(r) for r in rows]

    def add_chunk(self, transfer_id: str, chunk: ChunkRecord) -> bool:
        try:
            with self._sessions.begin() as db:
                db.add(
                    ChunkRow(
                        transfer_id=transfer_id,
                        chunk_index=chunk.index,
                        size=chunk.size,
                        sha256=chunk.sha256,
                        received_at=chunk.received_at,
                    )
                )
        except IntegrityError:
            return False  # contrainte unique (transfer_id, chunk_index)
        return True

    def search(self, query: TransferQuery) -> TransferPage:
        conditions: list[Any] = []
        if query.device_id is not None:
            conditions.append(TransferRow.device_id == query.device_id)
        if query.direction is not None:
            conditions.append(TransferRow.direction == query.direction.value)
        if query.statuses:
            conditions.append(TransferRow.status.in_(sorted(s.value for s in query.statuses)))
        if query.text:
            pattern = f"%{_escape_like(query.text.casefold())}%"
            conditions.append(
                or_(
                    func.casefold(TransferRow.safe_filename).like(pattern, escape=_LIKE_ESCAPE),
                    func.casefold(TransferRow.filename).like(pattern, escape=_LIKE_ESCAPE),
                )
            )
        with self._sessions() as db:
            total = db.scalar(select(func.count()).select_from(TransferRow).where(*conditions))
            rows = db.scalars(
                select(TransferRow)
                .where(*conditions)
                .order_by(TransferRow.created_at.desc(), TransferRow.id.desc())
                .limit(query.limit)
                .offset(query.offset)
            )
            return TransferPage([_transfer_to_domain(r) for r in rows], int(total or 0))

    def delete_terminal_before(self, cutoff: datetime) -> int:
        terminal = ("completed", "failed", "cancelled")
        old_terminal = (TransferRow.status.in_(terminal), TransferRow.updated_at < cutoff)
        with self._sessions.begin() as db:
            doomed = select(TransferRow.id).where(*old_terminal)
            db.execute(delete(ChunkRow).where(ChunkRow.transfer_id.in_(doomed)))
            result = db.execute(delete(TransferRow).where(*old_terminal))
            return int(getattr(result, "rowcount", 0) or 0)

    def get_chunks(self, transfer_id: str) -> dict[int, ChunkRecord]:
        with self._sessions() as db:
            rows = db.scalars(select(ChunkRow).where(ChunkRow.transfer_id == transfer_id))
            return {r.chunk_index: _chunk_to_domain(r) for r in rows}

    def get_chunk(self, transfer_id: str, index: int) -> ChunkRecord | None:
        with self._sessions() as db:
            row = db.get(ChunkRow, (transfer_id, index))
            return _chunk_to_domain(row) if row else None

    def received_bytes(self, transfer_id: str) -> int:
        with self._sessions() as db:
            total = db.scalar(
                select(func.coalesce(func.sum(ChunkRow.size), 0)).where(
                    ChunkRow.transfer_id == transfer_id
                )
            )
            return int(total or 0)
