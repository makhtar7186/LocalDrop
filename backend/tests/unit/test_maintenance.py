import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from localdrop.domain.devices.models import Device, Platform
from localdrop.domain.sessions.rate_limit import SlidingWindowRateLimiter
from localdrop.domain.transfers.models import TransferStatus
from localdrop.infrastructure.database.memory import InMemorySessionRepository
from localdrop.infrastructure.database.memory_transfers import InMemoryTransferRepository
from localdrop.infrastructure.storage.files import FileStorage
from localdrop.services.downloads import DownloadService
from localdrop.services.events import Event, EventBus
from localdrop.services.maintenance import MaintenanceService
from localdrop.services.pairing import PairingService
from localdrop.services.transfers import TransferService

pytestmark = pytest.mark.unit


class Clock:
    def __init__(self) -> None:
        self.now = datetime.now(UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        self.now += timedelta(**delta)


class World:
    """Services réels en mémoire, partageant une horloge contrôlée."""

    def __init__(self, tmp_path: Path) -> None:
        self.clock = Clock()
        self.events: list[Event] = []
        bus = EventBus()
        bus.subscribe(self.events.append)
        self.sessions = InMemorySessionRepository()
        self.repo = InMemoryTransferRepository()
        self.storage = FileStorage(tmp_path / "recus", free_space_margin=0)
        self.pairing = PairingService(
            self.sessions,
            bus,
            session_ttl=timedelta(hours=12),
            pairing_ttl=timedelta(minutes=5),
            join_limiter=SlidingWindowRateLimiter(100, 60),
            clock=self.clock,
        )
        self.pairing.start_session()
        retention = timedelta(hours=24)
        self.transfers = TransferService(
            self.repo, self.storage, bus, chunk_size=4, retention=retention, clock=self.clock
        )
        self.downloads = DownloadService(
            self.repo,
            self.pairing,
            bus,
            chunk_size=4,
            retention=retention,
            ticket_ttl=timedelta(minutes=15),
            clock=self.clock,
        )
        self.maintenance = MaintenanceService(
            self.repo,
            self.sessions,
            self.storage,
            self.downloads,
            bus,
            history_retention=timedelta(days=30),
            orphan_grace=timedelta(hours=1),
            clock=self.clock,
        )

    def phone(self) -> Device:
        info = self.pairing.current_pairing()
        joined = self.pairing.join(
            session_id=info.session_id,
            secret=info.secret,
            display_name="Pixel",
            platform=Platform.ANDROID,
            client_ip="192.168.1.50",
        )
        return self.pairing.approve(joined.device.id)


@pytest.fixture
def world(tmp_path: Path) -> Iterator[World]:
    built = World(tmp_path)
    yield built
    built.storage.close_all()  # fichiers temporaires gardés ouverts entre deux blocs


def test_FR_035_expired_active_upload_is_cancelled_and_its_temp_deleted(world: World) -> None:
    phone = world.phone()
    stale = world.transfers.create_upload(phone, "vieux.bin", 8)
    world.clock.advance(hours=1)
    fresh = world.transfers.create_upload(phone, "recent.bin", 8)

    world.clock.advance(hours=23, minutes=30)  # « vieux » a 24 h 30, « récent » 23 h 30
    report = world.maintenance.run_once()

    assert report.expired == [stale.id]
    expired = world.transfers.get(phone, stale.id)
    assert (expired.status, expired.error_code) == (TransferStatus.CANCELLED, "EXPIRED")
    assert not world.storage.temp_exists(stale.id)
    assert world.storage.temp_exists(fresh.id)
    assert "transfer.cancelled" in [e.type for e in world.events]


def test_failed_temp_kept_for_diagnosis_until_expiry(world: World) -> None:
    phone = world.phone()
    transfer = world.transfers.create_upload(phone, "a.bin", 4)
    world.transfers.put_chunk(phone, transfer.id, 0, b"abcd", _sha(b"abcd"))
    world.transfers.complete(phone, transfer.id, "0" * 64)  # hash faux -> failed

    assert world.maintenance.run_once().temp_deleted == []
    assert world.storage.temp_exists(transfer.id)

    world.clock.advance(hours=25)
    assert world.maintenance.run_once().temp_deleted == [transfer.id]


def test_orphan_temp_files_respect_a_grace_period(world: World) -> None:
    world.storage.ensure_directories()
    orphan = world.storage.temp_dir / ("a" * 32 + ".part")
    orphan.write_bytes(b"reste")

    assert world.maintenance.run_once().orphans_deleted == []  # peut-être un upload qui démarre
    old = (world.clock.now - timedelta(hours=2)).timestamp()
    os.utime(orphan, (old, old))
    assert world.maintenance.run_once().orphans_deleted == ["a" * 32]
    assert not orphan.exists()


def test_history_is_purged_but_final_files_are_never_touched(world: World) -> None:
    phone = world.phone()
    transfer = world.transfers.create_upload(phone, "photo.jpg", 4)
    world.transfers.put_chunk(phone, transfer.id, 0, b"abcd", _sha(b"abcd"))
    done = world.transfers.complete(phone, transfer.id, _sha(b"abcd"))
    active = world.transfers.create_upload(phone, "en-cours.bin", 4)

    world.clock.advance(days=31)
    report = world.maintenance.run_once()

    assert report.history_purged == 1
    assert world.repo.get(transfer.id) is None
    assert Path(done.final_path or "").read_bytes() == b"abcd"  # fichier reçu conservé
    still_there = world.repo.get(active.id)
    assert still_there is not None  # un transfert actif n'est jamais purgé (il expire d'abord)
    assert still_there.status is TransferStatus.CANCELLED


def test_expired_download_offer_is_cancelled(world: World, tmp_path: Path) -> None:
    phone = world.phone()
    source = tmp_path / "doc.pdf"
    source.write_bytes(b"pdf")
    offer = world.downloads.offer(source, phone.id)
    world.clock.advance(hours=25)
    report = world.maintenance.run_once()
    assert offer.id in report.expired
    assert source.exists()  # le fichier source du PC n'est jamais supprimé


def test_expired_sessions_are_marked(world: World) -> None:
    world.clock.advance(hours=13)
    assert world.maintenance.run_once().sessions_expired == 1
    assert world.maintenance.run_once().sessions_expired == 0


def _sha(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
