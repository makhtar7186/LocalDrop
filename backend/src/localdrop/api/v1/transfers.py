"""Routes de transfert (§10.2). Toutes exigent un appareil approuvé."""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Header, Path, Request, status
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from localdrop.api.deps import AdminDep, DeviceDep, ServicesDep
from localdrop.core.errors import LocalDropError
from localdrop.schemas.transfers import (
    AdminTransferOut,
    ChunkAck,
    ChunkListResponse,
    CompleteTransferRequest,
    CreateTransferRequest,
    TransferOut,
)

router = APIRouter(tags=["transferts"])

_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
TransferId = Annotated[str, Path(min_length=1, max_length=64)]


class ChunkTooLargeError(LocalDropError):
    code = "CHUNK_TOO_LARGE"
    status_code = 413


class ClientDisconnectedError(LocalDropError):
    code = "CLIENT_DISCONNECTED"
    status_code = 400


@router.post("/transfers", status_code=status.HTTP_201_CREATED, response_model=TransferOut)
async def create_transfer(
    payload: CreateTransferRequest, device: DeviceDep, services: ServicesDep
) -> TransferOut:
    transfer = await run_in_threadpool(
        services.transfers.create_upload, device, payload.filename, payload.size
    )
    return TransferOut.from_domain(transfer)


@router.get("/transfers", response_model=list[TransferOut])
async def list_transfers(device: DeviceDep, services: ServicesDep) -> list[TransferOut]:
    return [TransferOut.from_domain(t) for t in services.transfers.list_for(device)]


@router.get("/transfers/{transfer_id}", response_model=TransferOut)
async def get_transfer(
    transfer_id: TransferId, device: DeviceDep, services: ServicesDep
) -> TransferOut:
    return TransferOut.from_domain(services.transfers.get(device, transfer_id))


@router.get("/transfers/{transfer_id}/chunks", response_model=ChunkListResponse)
async def list_chunks(
    transfer_id: TransferId, device: DeviceDep, services: ServicesDep
) -> ChunkListResponse:
    transfer = services.transfers.get(device, transfer_id)
    return ChunkListResponse(
        transfer_id=transfer.id,
        total_chunks=transfer.total_chunks,
        received=services.transfers.received_chunks(device, transfer_id),
    )


@router.put("/transfers/{transfer_id}/chunks/{index}", response_model=ChunkAck)
async def put_chunk(
    transfer_id: TransferId,
    index: Annotated[int, Path(ge=0)],
    request: Request,
    device: DeviceDep,
    services: ServicesDep,
    chunk_sha256: Annotated[str, Header(alias="X-Chunk-SHA256")],
) -> ChunkAck:
    if not _SHA256.fullmatch(chunk_sha256):
        raise LocalDropError(
            "En-tête X-Chunk-SHA256 invalide", code="CHUNK_HASH_HEADER_INVALID", status_code=422
        )
    # Valide transfert et index avant de lire le corps ; la lecture est bornée.
    expected = services.transfers.expected_chunk_size(device, transfer_id, index)
    declared_length = request.headers.get("content-length")
    if (
        declared_length is not None
        and declared_length.isdigit()
        and int(declared_length) > expected
    ):
        raise ChunkTooLargeError("Bloc trop volumineux", details={"expected": expected})

    body = bytearray()
    try:
        async for part in request.stream():
            body += part
            if len(body) > expected:
                raise ChunkTooLargeError("Bloc trop volumineux", details={"expected": expected})
    except ClientDisconnect as exc:
        raise ClientDisconnectedError("Connexion interrompue pendant l'envoi du bloc") from exc

    transfer, already = await run_in_threadpool(
        services.transfers.put_chunk, device, transfer_id, index, bytes(body), chunk_sha256
    )
    return ChunkAck(
        index=index,
        already_received=already,
        received_bytes=transfer.received_bytes,
        status=transfer.status,
    )


@router.post("/transfers/{transfer_id}/complete", response_model=TransferOut)
async def complete_transfer(
    transfer_id: TransferId,
    payload: CompleteTransferRequest,
    device: DeviceDep,
    services: ServicesDep,
) -> TransferOut:
    transfer = await run_in_threadpool(
        services.transfers.complete, device, transfer_id, payload.sha256
    )
    return TransferOut.from_domain(transfer)


@router.post("/transfers/{transfer_id}/cancel", response_model=TransferOut)
async def cancel_transfer(
    transfer_id: TransferId, device: DeviceDep, services: ServicesDep
) -> TransferOut:
    transfer = await run_in_threadpool(services.transfers.cancel, device, transfer_id)
    return TransferOut.from_domain(transfer)


@router.get("/admin/transfers", response_model=list[AdminTransferOut])
async def admin_list_transfers(_: AdminDep, services: ServicesDep) -> list[AdminTransferOut]:
    return [AdminTransferOut.from_domain(t) for t in services.transfers.list_all()]
