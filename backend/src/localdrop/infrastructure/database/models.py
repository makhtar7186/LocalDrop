"""Modèles ORM (§11). Ils ne sortent jamais de infrastructure/ : les dépôts
convertissent vers les entités de domaine."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    TypeDecorator,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class UTCDateTime(TypeDecorator[datetime]):
    """Stocke en UTC naïf (SQLite n'a pas de fuseau), relit en UTC aware."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Datetime sans fuseau horaire refusée")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        assert isinstance(value, datetime)  # noqa: S101 - garanti par le type DateTime
        return value.replace(tzinfo=UTC)


def _in(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


SESSION_STATUSES = ("active", "expired", "revoked")
DEVICE_STATUSES = ("pending", "connected", "disconnected", "rejected", "revoked")
PLATFORMS = ("android", "ios", "windows", "other")
TRANSFER_STATUSES = (
    "created",
    "waiting",
    "transferring",
    "paused",
    "verifying",
    "completed",
    "failed",
    "cancelled",
)
DIRECTIONS = ("upload", "download")


class Base(DeclarativeBase):
    pass


class SessionRow(Base):
    __tablename__ = "sessions"
    __table_args__ = (CheckConstraint(_in("status", SESSION_STATUSES), name="ck_sessions_status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    status: Mapped[str] = mapped_column(String(16))
    pairing_secret_hash: Mapped[str] = mapped_column(String(64))
    pairing_expires_at: Mapped[datetime] = mapped_column(UTCDateTime())


class DeviceRow(Base):
    __tablename__ = "devices"
    __table_args__ = (
        CheckConstraint(_in("status", DEVICE_STATUSES), name="ck_devices_status"),
        CheckConstraint(_in("platform", PLATFORMS), name="ck_devices_platform"),
        Index("ix_devices_session_id", "session_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id"))
    display_name: Mapped[str] = mapped_column(String(64))
    platform: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    client_ip: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime())
    connected_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class TransferRow(Base):
    __tablename__ = "transfers"
    __table_args__ = (
        CheckConstraint(_in("status", TRANSFER_STATUSES), name="ck_transfers_status"),
        CheckConstraint(_in("direction", DIRECTIONS), name="ck_transfers_direction"),
        CheckConstraint("total_size >= 0", name="ck_transfers_total_size"),
        CheckConstraint("chunk_size > 0", name="ck_transfers_chunk_size"),
        Index("ix_transfers_status", "status"),
        Index("ix_transfers_device_id", "device_id"),
        Index("ix_transfers_expires_at", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(36), ForeignKey("devices.id"))
    direction: Mapped[str] = mapped_column(String(16))
    filename: Mapped[str] = mapped_column(String(1024))
    safe_filename: Mapped[str] = mapped_column(String(255))
    total_size: Mapped[int] = mapped_column(BigInteger)
    chunk_size: Mapped[int] = mapped_column(Integer)
    total_chunks: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    received_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expected_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    final_path: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_path: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    source_mtime_ns: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    fully_served: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())


class ChunkRow(Base):
    __tablename__ = "transfer_chunks"
    __table_args__ = (CheckConstraint("size >= 0", name="ck_transfer_chunks_size"),)

    # Clé primaire composite = contrainte unique (transfer_id, chunk_index) du §11.4.
    transfer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("transfers.id", ondelete="CASCADE"), primary_key=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    received_at: Mapped[datetime] = mapped_column(UTCDateTime())
