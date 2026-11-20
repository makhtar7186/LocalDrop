from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from localdrop.domain.transfers.models import Direction, Transfer, TransferStatus

SHA256_PATTERN = r"^[0-9a-fA-F]{64}$"


class CreateTransferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=1024)
    size: int = Field(ge=0)


class CompleteTransferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sha256: str = Field(pattern=SHA256_PATTERN)


class TransferOut(BaseModel):
    id: str
    direction: Direction
    filename: str
    safe_filename: str
    size: int
    chunk_size: int
    total_chunks: int
    status: TransferStatus
    received_bytes: int
    sha256: str | None
    error_code: str | None
    fully_served: bool
    created_at: datetime
    updated_at: datetime
    expires_at: datetime

    @classmethod
    def from_domain(cls, transfer: Transfer) -> TransferOut:
        return cls(
            id=transfer.id,
            direction=transfer.direction,
            filename=transfer.filename,
            safe_filename=transfer.safe_filename,
            size=transfer.total_size,
            chunk_size=transfer.chunk_size,
            total_chunks=transfer.total_chunks,
            status=transfer.status,
            received_bytes=transfer.received_bytes,
            sha256=transfer.sha256,
            error_code=transfer.error_code,
            fully_served=transfer.fully_served,
            created_at=transfer.created_at,
            updated_at=transfer.updated_at,
            expires_at=transfer.expires_at,
        )


class AdminTransferOut(TransferOut):
    device_id: str
    final_path: str | None

    @classmethod
    def from_domain(cls, transfer: Transfer) -> AdminTransferOut:
        base = TransferOut.from_domain(transfer).model_dump()
        return cls(**base, device_id=transfer.device_id, final_path=transfer.final_path)


class ChunkListResponse(BaseModel):
    transfer_id: str
    total_chunks: int
    received: list[int]


class ChunkAck(BaseModel):
    index: int
    already_received: bool
    received_bytes: int
    status: TransferStatus


class DownloadTicketResponse(BaseModel):
    url: str  # chemin relatif à l'origine, ticket inclus
    expires_at: datetime


class OfferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=4096)
    device_id: str = Field(min_length=1, max_length=64)


class HistoryPage(BaseModel):
    items: list[TransferOut]
    total: int
    limit: int
    offset: int


class AdminHistoryPage(BaseModel):
    items: list[AdminTransferOut]
    total: int
    limit: int
    offset: int
