"""Schéma initial : sessions, devices, transfers, transfer_chunks (§11).

Révision : 0001
Précédente : aucune
Écrite à la main : contraintes CHECK et index explicites.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("pairing_secret_hash", sa.String(64), nullable=False),
        sa.Column("pairing_expires_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(_in("status", ("active", "expired", "revoked")), name="ck_sessions_status"),
    )

    op.create_table(
        "devices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("display_name", sa.String(64), nullable=False),
        sa.Column("platform", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("client_ip", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("connected_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            _in("status", ("pending", "connected", "disconnected", "rejected", "revoked")),
            name="ck_devices_status",
        ),
        sa.CheckConstraint(
            _in("platform", ("android", "ios", "windows", "other")), name="ck_devices_platform"
        ),
    )
    op.create_index("ix_devices_session_id", "devices", ["session_id"])

    op.create_table(
        "transfers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("device_id", sa.String(36), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("filename", sa.String(1024), nullable=False),
        sa.Column("safe_filename", sa.String(255), nullable=False),
        sa.Column("total_size", sa.BigInteger(), nullable=False),
        sa.Column("chunk_size", sa.Integer(), nullable=False),
        sa.Column("total_chunks", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("received_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("expected_sha256", sa.String(64), nullable=True),
        sa.Column("final_path", sa.String(4096), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("source_path", sa.String(4096), nullable=True),
        sa.Column("source_mtime_ns", sa.BigInteger(), nullable=True),
        sa.Column("fully_served", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            _in(
                "status",
                (
                    "created",
                    "waiting",
                    "transferring",
                    "paused",
                    "verifying",
                    "completed",
                    "failed",
                    "cancelled",
                ),
            ),
            name="ck_transfers_status",
        ),
        sa.CheckConstraint(_in("direction", ("upload", "download")), name="ck_transfers_direction"),
        sa.CheckConstraint("total_size >= 0", name="ck_transfers_total_size"),
        sa.CheckConstraint("chunk_size > 0", name="ck_transfers_chunk_size"),
    )
    op.create_index("ix_transfers_status", "transfers", ["status"])
    op.create_index("ix_transfers_device_id", "transfers", ["device_id"])
    op.create_index("ix_transfers_expires_at", "transfers", ["expires_at"])

    op.create_table(
        "transfer_chunks",
        sa.Column(
            "transfer_id",
            sa.String(36),
            sa.ForeignKey("transfers.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("chunk_index", sa.Integer(), primary_key=True),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("size >= 0", name="ck_transfer_chunks_size"),
    )


def downgrade() -> None:
    op.drop_table("transfer_chunks")
    op.drop_index("ix_transfers_expires_at", table_name="transfers")
    op.drop_index("ix_transfers_device_id", table_name="transfers")
    op.drop_index("ix_transfers_status", table_name="transfers")
    op.drop_table("transfers")
    op.drop_index("ix_devices_session_id", table_name="devices")
    op.drop_table("devices")
    op.drop_table("sessions")
