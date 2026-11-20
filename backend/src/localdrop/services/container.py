"""Assemblage des services de l'application (partagé par l'API et le desktop)."""

from __future__ import annotations

import socket
from dataclasses import dataclass
from datetime import timedelta

from localdrop.core.config import Settings
from localdrop.domain.sessions.rate_limit import SlidingWindowRateLimiter
from localdrop.domain.sessions.tokens import generate_secret
from localdrop.infrastructure.database.memory import InMemorySessionRepository
from localdrop.infrastructure.database.memory_transfers import InMemoryTransferRepository
from localdrop.infrastructure.network.interfaces import (
    DEFAULT_EXCLUDED_PATTERNS,
    detect_candidates,
)
from localdrop.infrastructure.storage.files import FileStorage
from localdrop.services.downloads import DownloadService
from localdrop.services.events import EventBus
from localdrop.services.network_monitor import AddressProvider, NetworkMonitor
from localdrop.services.pairing import PairingService
from localdrop.services.transfers import TransferService


@dataclass
class AppServices:
    settings: Settings
    events: EventBus
    pairing: PairingService
    network: NetworkMonitor
    storage: FileStorage
    transfers: TransferService
    downloads: DownloadService
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

    storage = FileStorage(settings.receive_dir, free_space_margin=settings.free_space_margin)
    transfer_repository = InMemoryTransferRepository()
    transfers = TransferService(
        transfer_repository,
        storage,
        events,
        chunk_size=settings.chunk_size,
        retention=timedelta(hours=settings.temp_retention_hours),
        max_file_size=settings.max_file_size,
    )
    downloads = DownloadService(
        transfer_repository,
        pairing,
        events,
        chunk_size=settings.chunk_size,
        retention=timedelta(hours=settings.temp_retention_hours),
        ticket_ttl=timedelta(seconds=settings.download_ticket_ttl_seconds),
    )

    return AppServices(
        settings=settings,
        events=events,
        pairing=pairing,
        network=network,
        storage=storage,
        transfers=transfers,
        downloads=downloads,
        admin_token=generate_secret(),
        server_name=socket.gethostname(),
    )
