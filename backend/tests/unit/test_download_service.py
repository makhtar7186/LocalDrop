import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from localdrop.core.errors import ConflictError, NotFoundError, UnauthorizedError
from localdrop.domain.devices.models import Device, Platform
from localdrop.domain.sessions.rate_limit import SlidingWindowRateLimiter
from localdrop.domain.transfers.models import Direction, TransferStatus
from localdrop.infrastructure.database.memory import InMemorySessionRepository
from localdrop.infrastructure.database.memory_transfers import InMemoryTransferRepository
from localdrop.services.downloads import (
    DownloadService,
    InvalidSourceError,
    SourceUnavailableError,
)
from localdrop.services.events import Event, EventBus
from localdrop.services.pairing import PairingService

pytestmark = pytest.mark.unit


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 20, 12, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def events() -> list[Event]:
    return []


@pytest.fixture
def pairing(clock: Clock, events: list[Event]) -> PairingService:
    bus = EventBus()
    bus.subscribe(events.append)
    service = PairingService(
        InMemorySessionRepository(),
        bus,
        session_ttl=timedelta(hours=12),
        pairing_ttl=timedelta(minutes=5),
        join_limiter=SlidingWindowRateLimiter(100, 60),
        clock=clock,
    )
    service.start_session()
    return service


def _approved(pairing: PairingService, ip: str = "192.168.1.50") -> Device:
    info = pairing.current_pairing()
    result = pairing.join(
        session_id=info.session_id,
        secret=info.secret,
        display_name="Pixel",
        platform=Platform.ANDROID,
        client_ip=ip,
    )
    return pairing.approve(result.device.id)


@pytest.fixture
def phone(pairing: PairingService) -> Device:
    return _approved(pairing)


@pytest.fixture
def service(pairing: PairingService, clock: Clock, events: list[Event]) -> DownloadService:
    bus = EventBus()
    bus.subscribe(events.append)
    return DownloadService(
        InMemoryTransferRepository(),
        pairing,
        bus,
        chunk_size=1024,
        retention=timedelta(hours=24),
        ticket_ttl=timedelta(minutes=15),
        clock=clock,
    )


@pytest.fixture
def source(tmp_path: Path) -> Path:
    path = tmp_path / "Rapport annuel.pdf"
    path.write_bytes(os.urandom(3000))
    return path


def test_FR_020_offer_registers_file_without_copying(
    service: DownloadService, phone: Device, source: Path, tmp_path: Path, events: list[Event]
) -> None:
    transfer = service.offer(source, phone.id)
    assert transfer.direction is Direction.DOWNLOAD
    assert transfer.status is TransferStatus.WAITING
    assert transfer.total_size == 3000
    assert transfer.safe_filename == "Rapport annuel.pdf"
    assert transfer.source_path == str(source.resolve())
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Rapport annuel.pdf"]
    assert events[-1].type == "transfer.created"


def test_offer_rejects_directories_missing_files_and_unapproved_devices(
    service: DownloadService, pairing: PairingService, phone: Device, tmp_path: Path, source: Path
) -> None:
    with pytest.raises(InvalidSourceError):
        service.offer(tmp_path, phone.id)
    with pytest.raises(InvalidSourceError):
        service.offer(tmp_path / "absent.txt", phone.id)
    pairing.revoke(phone.id)
    with pytest.raises(UnauthorizedError):
        service.offer(source, phone.id)


def test_FR_029_ticket_opens_download_and_marks_transferring(
    service: DownloadService, phone: Device, source: Path
) -> None:
    transfer = service.offer(source, phone.id)
    ticket = service.issue_ticket(phone, transfer.id)
    grant = service.open_download(transfer.id, ticket.token)
    assert grant.path == source.resolve()
    assert grant.transfer.status is TransferStatus.TRANSFERRING
    # Le même ticket reste valable (reprise par Range) jusqu'à expiration.
    assert service.open_download(transfer.id, ticket.token).transfer.status is (
        TransferStatus.TRANSFERRING
    )


def test_ticket_is_bound_to_transfer_and_expires(
    service: DownloadService, phone: Device, source: Path, clock: Clock
) -> None:
    first = service.offer(source, phone.id)
    second = service.offer(source, phone.id)
    ticket = service.issue_ticket(phone, first.id)
    with pytest.raises(UnauthorizedError):
        service.open_download(second.id, ticket.token)
    with pytest.raises(UnauthorizedError):
        service.open_download(first.id, "ticket-inventé")
    clock.now += timedelta(minutes=16)
    with pytest.raises(UnauthorizedError):
        service.open_download(first.id, ticket.token)


def test_FR_013_revoked_device_ticket_stops_working(
    service: DownloadService, pairing: PairingService, phone: Device, source: Path
) -> None:
    transfer = service.offer(source, phone.id)
    ticket = service.issue_ticket(phone, transfer.id)
    pairing.revoke(phone.id)
    with pytest.raises(UnauthorizedError):
        service.open_download(transfer.id, ticket.token)


def test_other_device_cannot_obtain_ticket(
    service: DownloadService, pairing: PairingService, phone: Device, source: Path
) -> None:
    transfer = service.offer(source, phone.id)
    other = _approved(pairing, "192.168.1.77")
    with pytest.raises(NotFoundError):
        service.issue_ticket(other, transfer.id)


@pytest.mark.parametrize("change", ["modify", "delete"])
def test_changed_or_deleted_source_is_refused(
    service: DownloadService, phone: Device, source: Path, change: str
) -> None:
    transfer = service.offer(source, phone.id)
    ticket = service.issue_ticket(phone, transfer.id)
    if change == "modify":
        source.write_bytes(b"autre contenu")
    else:
        source.unlink()
    with pytest.raises(SourceUnavailableError):
        service.open_download(transfer.id, ticket.token)


def test_completion_requires_explicit_confirmation(
    service: DownloadService, phone: Device, source: Path
) -> None:
    transfer = service.offer(source, phone.id)
    with pytest.raises(ConflictError) as exc:
        service.confirm(phone, transfer.id)  # rien n'a été téléchargé
    assert exc.value.code == "DOWNLOAD_NOT_STARTED"

    ticket = service.issue_ticket(phone, transfer.id)
    service.open_download(transfer.id, ticket.token)
    service.mark_served(transfer.id)
    served = service._repo.get(transfer.id)
    assert served is not None
    # Servi en entier ≠ reçu : le statut reste « en cours » (§6.3).
    assert served.fully_served is True
    assert served.status is TransferStatus.TRANSFERRING

    done = service.confirm(phone, transfer.id)
    assert done.status is TransferStatus.COMPLETED
    with pytest.raises(UnauthorizedError):
        service.open_download(transfer.id, ticket.token)  # tickets révoqués
    with pytest.raises(ConflictError):
        service.confirm(phone, transfer.id)


def test_FR_025_cancel_by_pc_or_phone(
    service: DownloadService, phone: Device, source: Path
) -> None:
    by_pc = service.offer(source, phone.id)
    ticket = service.issue_ticket(phone, by_pc.id)
    assert service.cancel(by_pc.id).status is TransferStatus.CANCELLED
    with pytest.raises(UnauthorizedError):  # l'annulation révoque les tickets émis
        service.open_download(by_pc.id, ticket.token)

    by_phone = service.offer(source, phone.id)
    assert service.cancel(by_phone.id, phone).status is TransferStatus.CANCELLED
    with pytest.raises(ConflictError):
        service.issue_ticket(phone, by_phone.id)
