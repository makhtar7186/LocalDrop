"""Assemblage des services de l'application (partagé par l'API et le desktop)."""

from __future__ import annotations

import socket
from dataclasses import dataclass
from datetime import timedelta

from localdrop.core.config import Settings
from localdrop.domain.sessions.rate_limit import SlidingWindowRateLimiter
from localdrop.domain.sessions.tokens import generate_secret
from localdrop.infrastructure.database.memory import InMemorySessionRepository
from localdrop.infrastructure.network.interfaces import (
    DEFAULT_EXCLUDED_PATTERNS,
    detect_candidates,
)
from localdrop.services.events import EventBus
from localdrop.services.network_monitor import AddressProvider, NetworkMonitor
from localdrop.services.pairing import PairingService


@dataclass
class AppServices:
    settings: Settings
    events: EventBus
    pairing: PairingService
    network: NetworkMonitor
    # Jeton des routes d'administration HTTP (outil dev / desktop hors processus).
    admin_token: str
    server_name: str


def build_services(
    settings: Settings,
    *,
    address_provider: AddressProvider | None = None,
    bound_ips: frozenset[str] | None = None,
) -> AppServices:
    events = EventBus()
    excluded = settings.excluded_interface_patterns or DEFAULT_EXCLUDED_PATTERNS
    provider = address_provider or (lambda: detect_candidates(excluded))

    pairing = PairingService(
        InMemorySessionRepository(),
        events,
        session_ttl=timedelta(hours=settings.session_ttl_hours),
        pairing_ttl=timedelta(seconds=settings.pairing_secret_ttl_seconds),
        join_limiter=SlidingWindowRateLimiter(
            settings.join_max_attempts, settings.join_window_seconds
        ),
    )
    pairing.start_session()

    network = NetworkMonitor(provider, events, bound_ips)
    network.refresh()

    return AppServices(
        settings=settings,
        events=events,
        pairing=pairing,
        network=network,
        admin_token=generate_secret(),
        server_name=socket.gethostname(),
    )
