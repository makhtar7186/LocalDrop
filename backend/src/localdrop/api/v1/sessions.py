"""Routes sessions et appareils (§10.1)."""

from __future__ import annotations

from fastapi import APIRouter, Request, status

from localdrop.api.deps import AdminDep, ServicesDep, client_ip, device_token
from localdrop.infrastructure.network.interfaces import base_url, pairing_url
from localdrop.schemas.sessions import (
    ApproveRequest,
    DeviceOut,
    JoinRequest,
    JoinResponse,
    PairingAddress,
    PairingInfoResponse,
    RevokeRequest,
    RevokeResponse,
    SessionStatusResponse,
)

router = APIRouter(tags=["sessions"])


# ----------------------------------------------------------------- appareil mobile
@router.post("/sessions/join", status_code=status.HTTP_201_CREATED, response_model=JoinResponse)
async def join(payload: JoinRequest, request: Request, services: ServicesDep) -> JoinResponse:
    """Demande d'appairage (route publique, limitée en fréquence)."""
    result = services.pairing.join(
        session_id=payload.session_id,
        secret=payload.secret,
        display_name=payload.display_name,
        platform=payload.platform,
        client_ip=client_ip(request),
    )
    return JoinResponse(
        device_id=result.device.id,
        device_token=result.device_token,
        status=result.device.status,
    )


@router.get("/sessions/status", response_model=SessionStatusResponse)
async def session_status(request: Request, services: ServicesDep) -> SessionStatusResponse:
    """État de l'appareil courant (attente, connecté). 401/403 si révoqué ou refusé."""
    device = services.pairing.device_for_token(device_token(request))
    session = services.pairing.current_session()
    return SessionStatusResponse(
        device_id=device.id,
        display_name=device.display_name,
        status=device.status,
        server_name=services.server_name,
        session_expires_at=session.expires_at,
    )


# ----------------------------------------------------------------- administration (PC)
@router.post("/sessions/approve", response_model=DeviceOut)
async def approve(payload: ApproveRequest, _: AdminDep, services: ServicesDep) -> DeviceOut:
    pairing = services.pairing
    device = (
        pairing.approve(payload.device_id) if payload.approve else pairing.reject(payload.device_id)
    )
    return DeviceOut.from_domain(device)


@router.post("/sessions/revoke", response_model=RevokeResponse)
async def revoke(payload: RevokeRequest, _: AdminDep, services: ServicesDep) -> RevokeResponse:
    if payload.device_id is None:
        session = services.pairing.close_session()
        return RevokeResponse(revoked="session", session_id=session.id)
    device = services.pairing.revoke(payload.device_id)
    return RevokeResponse(revoked="device", session_id=device.session_id)


@router.get("/devices", response_model=list[DeviceOut])
async def list_devices(_: AdminDep, services: ServicesDep) -> list[DeviceOut]:
    return [DeviceOut.from_domain(d) for d in services.pairing.list_devices()]


@router.get("/admin/pairing", response_model=PairingInfoResponse)
async def pairing_info(_: AdminDep, services: ServicesDep) -> PairingInfoResponse:
    """URL(s) du QR Code courant, une par adresse joignable (§8.1)."""
    info = services.pairing.current_pairing()
    port = services.settings.port
    addresses = [
        PairingAddress(
            interface=c.interface,
            ip=c.ip,
            url=base_url(c.ip, port),
            pairing_url=pairing_url(base_url(c.ip, port), info.session_id, info.secret),
        )
        for c in services.network.reachable_candidates()
    ]
    return PairingInfoResponse(
        session_id=info.session_id, expires_at=info.expires_at, addresses=addresses
    )
