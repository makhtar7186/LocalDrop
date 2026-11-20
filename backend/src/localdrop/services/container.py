"""Assemblage des services de l'application (partagé par l'API et le desktop)."""

from __future__ import annotations

import socket
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta

from localdrop.core.config import Settings
from localdrop.domain.sessions.rate_limit import SlidingWindowRateLimiter
from localdrop.domain.sessions.repository import SessionRepository
from localdrop.domain.sessions.tokens import generate_secret
from localdrop.domain.transfers.repository import TransferRepository
from localdrop.infrastructure.database.memory import InMemorySessionRepository
from localdrop.infrastructure.database.memory_transfers import InMemoryTransferRepository
from localdrop.infrastructure.network.interfaces import (
    DEFAULT_EXCLUDED_PATTERNS,
    detect_candidates,
)
from localdrop.infrastructure.storage.files import FileStorage
from localdrop.services.downloads import DownloadService
from localdrop.services.events import EventBus
from localdrop.services.maintenance import MaintenanceReport, MaintenanceService
from localdrop.services.network_monitor import AddressProvider, NetworkMonitor
from localdrop.services.pairing import PairingService
from localdrop.services.transfers import ReconcileReport, TransferService


@dataclass
class AppServices:
    settings: Settings
    events: EventBus
    pairing: PairingService
    network: NetworkMonitor
    storage: FileStorage
    transfers: TransferService
    downloads: DownloadService
    maintenance: MaintenanceService
    # Jeton des routes d'administration HTTP (outil dev / desktop hors processus).
    admin_token: str
    server_name: str
    reconcile_report: ReconcileReport = field(default_factory=ReconcileReport)
    maintenance_report: MaintenanceReport = field(default_factory=MaintenanceReport)
    _closers: list[Callable[[], None]] = field(default_factory=list, repr=False)

    def close(self) -> None:
        """Libère les ressources (moteur SQLite). À appeler à l'arrêt du processus."""
        while self._closers:
            self._closers.pop()()


def _repositories(
    settings: Settings,
) -> tuple[SessionRepository, TransferRepository, list[Callable[[], None]]]:
    if settings.persistence == "memory":
        return InMemorySessionRepository(), InMemoryTransferRepository(), []

    from localdrop.infrastructure.database.engine import (
        database_url,
        make_engine,
        make_session_factory,
    )
    from localdrop.infrastructure.database.migrate import upgrade_database
    from localdrop.infrastructure.database.sql_repositories import (
        SqlSessionRepository,
        SqlTransferRepository,
    )

    settings.database_dir.mkdir(parents=True, exist_ok=True)
    engine = make_engine(database_url(settings.database_dir))
    upgrade_database(engine, settings.database_dir)
    sessions = make_session_factory(engine)
    return SqlSessionRepository(sessions), SqlTransferRepository(sessions), [engine.dispose]


def build_services(
    settings: Settings,
    *,
    address_provider: AddressProvider | None = None,
    bound_ips: frozenset[str] | None = None,
) -> AppServices:
    events = EventBus()
    excluded = settings.excluded_interface_patterns or DEFAULT_EXCLUDED_PATTERNS
    provider = address_provider or (lambda: detect_candidates(excluded))
    session_repository, transfer_repository, closers = _repositories(settings)

    pairing = PairingService(
        session_repository,
        events,
        session_ttl=timedelta(hours=settings.session_ttl_hours),
        pairing_ttl=timedelta(seconds=settings.pairing_secret_ttl_seconds),
        join_limiter=SlidingWindowRateLimiter(
            settings.join_max_attempts, settings.join_window_seconds
        ),
    )
    # Les appareils approuvés restent valables après un redémarrage du serveur.
    pairing.resume_or_start_session()

    network = NetworkMonitor(provider, events, bound_ips)
    network.refresh()

    storage = FileStorage(settings.receive_dir, free_space_margin=settings.free_space_margin)
    closers.append(storage.close_all)
    transfers = TransferService(
        transfer_repository,
        storage,
        events,
        chunk_size=settings.chunk_size,
        retention=timedelta(hours=settings.temp_retention_hours),
        max_file_size=settings.max_file_size,
        max_active_uploads=settings.max_active_uploads_per_device,
    )
    downloads = DownloadService(
        transfer_repository,
        pairing,
        events,
        chunk_size=settings.chunk_size,
        retention=timedelta(hours=settings.temp_retention_hours),
        ticket_ttl=timedelta(seconds=settings.download_ticket_ttl_seconds),
    )
    report = transfers.reconcile()
    maintenance = MaintenanceService(
        transfer_repository,
        session_repository,
        storage,
        downloads,
        events,
        history_retention=(
            timedelta(days=settings.history_retention_days)
            if settings.history_retention_days is not None
            else None
        ),
        orphan_grace=timedelta(minutes=settings.orphan_grace_minutes),
    )
    maintenance_report = maintenance.run_once()

    return AppServices(
        settings=settings,
        events=events,
        pairing=pairing,
        network=network,
        storage=storage,
        transfers=transfers,
        downloads=downloads,
        maintenance=maintenance,
        admin_token=generate_secret(),
        server_name=socket.gethostname(),
        reconcile_report=report,
        maintenance_report=maintenance_report,
        _closers=closers,
    )
