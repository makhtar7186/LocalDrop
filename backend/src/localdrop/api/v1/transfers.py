"""Routes de transfert (§10.2).

Routes « def » : FastAPI les exécute dans un thread (accès SQLite synchrones, ADR-004).
Routes « async def » : uniquement celles qui lisent un flux ou délèguent explicitement.

Toutes exigent un appareil approuvé (Bearer), sauf ``/download`` qui exige un ticket
court émis à cet appareil, et ``/admin/*`` réservées au PC.
"""

from __future__ import annotations

import re
from pathlib import Path as PathLib
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Header, Path, Query, Request, status
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from localdrop.api.deps import AdminDep, DeviceDep, ServicesDep
from localdrop.core.errors import LocalDropError
from localdrop.domain.transfers.models import Direction
from localdrop.schemas.transfers import (
    AdminTransferOut,
    ChunkAck,
    ChunkListResponse,
    CompleteTransferRequest,
    CreateTransferRequest,
    DownloadTicketResponse,
    OfferRequest,
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
def list_transfers(device: DeviceDep, services: ServicesDep) -> list[TransferOut]:
    return [TransferOut.from_domain(t) for t in services.transfers.list_for(device)]


@router.get("/transfers/{transfer_id}", response_model=TransferOut)
def get_transfer(transfer_id: TransferId, device: DeviceDep, services: ServicesDep) -> TransferOut:
    return TransferOut.from_domain(services.transfers.get(device, transfer_id))


@router.get("/transfers/{transfer_id}/chunks", response_model=ChunkListResponse)
def list_chunks(
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
def cancel_transfer(
    transfer_id: TransferId, device: DeviceDep, services: ServicesDep
) -> TransferOut:
    existing = services.transfers.get(device, transfer_id)
    if existing.direction is Direction.DOWNLOAD:
        transfer = services.downloads.cancel(transfer_id, device)
    else:
        transfer = services.transfers.cancel(device, transfer_id)
    return TransferOut.from_domain(transfer)


@router.post("/transfers/{transfer_id}/pause", response_model=TransferOut)
def pause_transfer(
    transfer_id: TransferId, device: DeviceDep, services: ServicesDep
) -> TransferOut:
    return TransferOut.from_domain(services.transfers.pause(device, transfer_id))


@router.post("/transfers/{transfer_id}/resume", response_model=TransferOut)
def resume_transfer(
    transfer_id: TransferId, device: DeviceDep, services: ServicesDep
) -> TransferOut:
    """Reprise (FR-026) : le client relit ensuite /chunks et n'envoie que les manquants."""
    return TransferOut.from_domain(services.transfers.resume(device, transfer_id))


# ----------------------------------------------------------------- PC -> téléphone
@router.post("/transfers/{transfer_id}/download-ticket", response_model=DownloadTicketResponse)
def download_ticket(
    transfer_id: TransferId, device: DeviceDep, services: ServicesDep
) -> DownloadTicketResponse:
    """Ticket court pour un lien <a> (qui ne peut pas porter d'en-tête Authorization)."""
    ticket = services.downloads.issue_ticket(device, transfer_id)
    return DownloadTicketResponse(
        url=f"/api/v1/transfers/{quote(transfer_id)}/download?ticket={quote(ticket.token)}",
        expires_at=ticket.expires_at,
    )


@router.get("/transfers/{transfer_id}/download", response_class=FileResponse)
async def download(
    transfer_id: TransferId,
    request: Request,
    services: ServicesDep,
    ticket: Annotated[str, Query(min_length=1, max_length=128)],
) -> FileResponse:
    """Téléchargement streaming avec reprise (Range). Toujours en pièce jointe opaque :
    un fichier HTML servi en ligne s'exécuterait dans l'origine LocalDrop."""
    grant = await run_in_threadpool(services.downloads.open_download, transfer_id, ticket)
    size = grant.transfer.total_size
    background = (
        BackgroundTask(services.downloads.mark_served, transfer_id)
        if _reaches_end(request.headers.get("range"), size)
        else None
    )
    return FileResponse(
        grant.path,
        filename=grant.transfer.safe_filename,
        media_type="application/octet-stream",
        content_disposition_type="attachment",
        headers={"Content-Security-Policy": "sandbox", "X-Download-Options": "noopen"},
        background=background,
    )


def _reaches_end(range_header: str | None, size: int) -> bool:
    """Vrai si la réponse enverra le fichier jusqu'au dernier octet."""
    if not range_header:
        return True
    match = re.fullmatch(r"\s*bytes=(\d*)-(\d*)\s*", range_header)
    if not match:
        return True  # en-tête non reconnu : Starlette servira le fichier entier
    end = match.group(2)
    return not end or int(end) >= size - 1


@router.post("/transfers/{transfer_id}/confirm", response_model=TransferOut)
def confirm_download(
    transfer_id: TransferId, device: DeviceDep, services: ServicesDep
) -> TransferOut:
    """Accusé de réception du téléphone : seul signal fiable de livraison (§6.3)."""
    return TransferOut.from_domain(services.downloads.confirm(device, transfer_id))


# ----------------------------------------------------------------- administration (PC)
@router.get("/admin/transfers", response_model=list[AdminTransferOut])
def admin_list_transfers(_: AdminDep, services: ServicesDep) -> list[AdminTransferOut]:
    return [AdminTransferOut.from_domain(t) for t in services.transfers.list_all()]


@router.post(
    "/admin/transfers/outgoing",
    status_code=status.HTTP_201_CREATED,
    response_model=AdminTransferOut,
)
async def admin_offer(
    payload: OfferRequest, _: AdminDep, services: ServicesDep
) -> AdminTransferOut:
    transfer = await run_in_threadpool(
        services.downloads.offer, PathLib(payload.path), payload.device_id
    )
    return AdminTransferOut.from_domain(transfer)


@router.post("/admin/transfers/{transfer_id}/cancel", response_model=AdminTransferOut)
def admin_cancel(transfer_id: TransferId, _: AdminDep, services: ServicesDep) -> AdminTransferOut:
    return AdminTransferOut.from_domain(services.downloads.cancel(transfer_id))
