"""Dépendances FastAPI partagées : configuration, services, authentification."""

from __future__ import annotations

import hmac
import ipaddress
from typing import Annotated

from fastapi import Depends, Request

from localdrop.core.config import Settings
from localdrop.core.errors import ForbiddenError, UnauthorizedError
from localdrop.domain.devices.models import Device
from localdrop.services.container import AppServices

ADMIN_HEADER = "X-LocalDrop-Admin"


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_services(request: Request) -> AppServices:
    services: AppServices = request.app.state.services
    return services


SettingsDep = Annotated[Settings, Depends(get_settings)]
ServicesDep = Annotated[AppServices, Depends(get_services)]


def client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


def _bearer_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise UnauthorizedError("Authentification requise", code="AUTH_REQUIRED")
    return token.strip()


def device_token(request: Request) -> str:
    return _bearer_token(request)


def require_device(request: Request, services: ServicesDep) -> Device:
    """Appareil approuvé et non révoqué (toutes les routes de transfert)."""
    return services.pairing.authenticate(_bearer_token(request))


def require_admin(request: Request, services: ServicesDep) -> None:
    """Administration : client loopback ET jeton admin (protection DNS rebinding incluse,
    car un navigateur ne peut pas ajouter d'en-tête personnalisé cross-origin sans CORS)."""
    try:
        is_loopback = ipaddress.ip_address(client_ip(request)).is_loopback
    except ValueError:
        is_loopback = False
    provided = request.headers.get(ADMIN_HEADER, "")
    if not is_loopback or not hmac.compare_digest(provided, services.admin_token):
        raise ForbiddenError("Accès réservé au PC hôte", code="ADMIN_FORBIDDEN")


DeviceDep = Annotated[Device, Depends(require_device)]
AdminDep = Annotated[None, Depends(require_admin)]
