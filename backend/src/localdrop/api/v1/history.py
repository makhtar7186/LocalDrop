"""Historique des transferts (FR-034, §14.2 History, §14.3 Historique)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from localdrop.api.deps import AdminDep, DeviceDep, ServicesDep
from localdrop.domain.transfers.models import Direction, TransferStatus
from localdrop.domain.transfers.query import MAX_PAGE_SIZE, TransferQuery
from localdrop.schemas.transfers import (
    AdminHistoryPage,
    AdminTransferOut,
    HistoryPage,
    TransferOut,
)

router = APIRouter(tags=["historique"])

DirectionParam = Annotated[Direction | None, Query()]
StatusParam = Annotated[list[TransferStatus] | None, Query()]
TextParam = Annotated[str | None, Query(max_length=200)]
LimitParam = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
OffsetParam = Annotated[int, Query(ge=0)]


@router.get("/history", response_model=HistoryPage)
def device_history(
    device: DeviceDep,
    services: ServicesDep,
    direction: DirectionParam = None,
    status: StatusParam = None,
    q: TextParam = None,
    limit: LimitParam = 50,
    offset: OffsetParam = 0,
) -> HistoryPage:
    """Transferts de l'appareil courant uniquement, du plus récent au plus ancien."""
    query = TransferQuery(
        device_id=device.id,
        direction=direction,
        statuses=frozenset(status or ()),
        text=q or None,
        limit=limit,
        offset=offset,
    )
    page = services.transfers.history(query)
    return HistoryPage(
        items=[TransferOut.from_domain(t) for t in page.items],
        total=page.total,
        limit=limit,
        offset=offset,
    )


@router.get("/admin/history", response_model=AdminHistoryPage)
def admin_history(
    _: AdminDep,
    services: ServicesDep,
    device_id: Annotated[str | None, Query(max_length=64)] = None,
    direction: DirectionParam = None,
    status: StatusParam = None,
    q: TextParam = None,
    limit: LimitParam = 50,
    offset: OffsetParam = 0,
) -> AdminHistoryPage:
    query = TransferQuery(
        device_id=device_id,
        direction=direction,
        statuses=frozenset(status or ()),
        text=q or None,
        limit=limit,
        offset=offset,
    )
    page = services.transfers.history(query)
    return AdminHistoryPage(
        items=[AdminTransferOut.from_domain(t) for t in page.items],
        total=page.total,
        limit=limit,
        offset=offset,
    )
