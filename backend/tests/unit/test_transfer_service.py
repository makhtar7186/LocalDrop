import hashlib
import os
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from localdrop.core.errors import ConflictError, NotFoundError
from localdrop.domain.devices.models import Device, DeviceStatus, Platform
from localdrop.domain.transfers.models import (
    InvalidChunkError,
    InvalidTransitionError,
    TransferStatus,
)
from localdrop.infrastructure.database.memory_transfers import InMemoryTransferRepository
from localdrop.infrastructure.storage.files import FileStorage
from localdrop.services.events import Event, EventBus
from localdrop.services.transfers import FileTooLargeError, TransferService

pytestmark = pytest.mark.unit
CHUNK = 8
NOW = datetime(2026, 11, 20, tzinfo=UTC)


def _device(device_id: str = "phone") -> Device:
    return Device(
        id=device_id,
        session_id="s",
        display_name="Pixel",
        platform=Platform.ANDROID,
        status=DeviceStatus.CONNECTED,
        token_hash="h",
        client_ip="192.168.1.50",
        created_at=NOW,
        last_seen_at=NOW,
    )


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def chunks(data: bytes) -> list[bytes]:
    return [data[i : i + CHUNK] for i in range(0, len(data), CHUNK)]


@pytest.fixture
def events() -> list[Event]:
    return []


@pytest.fixture
def storage(tmp_path: Path) -> Iterator[FileStorage]:
    store = FileStorage(tmp_path / "recus", free_space_margin=0)
    yield store
    store.close_all()  # fichiers temporaires gardés ouverts entre deux blocs


@pytest.fixture
def service(storage: FileStorage, events: list[Event]) -> TransferService:
    bus = EventBus()
    bus.subscribe(events.append)
    return TransferService(
        InMemoryTransferRepository(),
        storage,
        bus,
        chunk_size=CHUNK,
        retention=timedelta(hours=24),
        max_file_size=1000,
        clock=lambda: NOW,
    )


DATA = os.urandom(20)  # 3 blocs : 8 + 8 + 4
PHONE = _device()


def _upload_all(service: TransferService, data: bytes = DATA, name: str = "photo.jpg") -> str:
    transfer = service.create_upload(PHONE, name, len(data))
    for index, part in enumerate(chunks(data)):
        service.put_chunk(PHONE, transfer.id, index, part, sha(part))
    return transfer.id


def test_FR_021_upload_publishes_identical_file(
    service: TransferService, storage: FileStorage, events: list[Event]
) -> None:
    transfer_id = _upload_all(service)
    done = service.complete(PHONE, transfer_id, sha(DATA))

    assert done.status is TransferStatus.COMPLETED
    assert done.received_bytes == len(DATA)
    assert done.final_path is not None
    assert Path(done.final_path).read_bytes() == DATA
    assert Path(done.final_path).parent == storage.receive_dir.resolve()
    assert not storage.temp_path(transfer_id).exists()
    types = [e.type for e in events]
    assert types[0] == "transfer.created"
    assert types[-1] == "transfer.completed"
    assert "transfer.progress" in types


def test_FR_027_global_hash_mismatch_fails_and_keeps_temp(
    service: TransferService, storage: FileStorage
) -> None:
    transfer_id = _upload_all(service)
    failed = service.complete(PHONE, transfer_id, sha(b"autre contenu"))
    assert failed.status is TransferStatus.FAILED
    assert failed.error_code == "FILE_HASH_MISMATCH"
    assert storage.temp_path(transfer_id).exists()
    assert list(storage.receive_dir.glob("*.jpg")) == []


def test_chunk_resend_is_idempotent_but_other_content_conflicts(service: TransferService) -> None:
    transfer = service.create_upload(PHONE, "a.bin", len(DATA))
    first = chunks(DATA)[0]
    _, already = service.put_chunk(PHONE, transfer.id, 0, first, sha(first))
    assert already is False
    _, already = service.put_chunk(PHONE, transfer.id, 0, first, sha(first))
    assert already is True
    other = bytes(CHUNK)
    with pytest.raises(ConflictError) as exc:
        service.put_chunk(PHONE, transfer.id, 0, other, sha(other))
    assert exc.value.code == "CHUNK_CONFLICT"
    assert service.get(PHONE, transfer.id).received_bytes == CHUNK


@pytest.mark.parametrize(
    ("index", "data_fn", "code"),
    [
        (0, lambda: DATA[:CHUNK], "CHUNK_HASH_MISMATCH"),  # hash déclaré faux
        (0, lambda: DATA[:5], "CHUNK_SIZE_MISMATCH"),
        (3, lambda: DATA[:4], "CHUNK_INDEX_OUT_OF_RANGE"),
    ],
)
def test_invalid_chunks_are_rejected_and_not_recorded(
    service: TransferService, index: int, data_fn: object, code: str
) -> None:
    transfer = service.create_upload(PHONE, "a.bin", len(DATA))
    data = data_fn()  # type: ignore[operator]
    declared = sha(b"x") if code == "CHUNK_HASH_MISMATCH" else sha(data)
    with pytest.raises(InvalidChunkError) as exc:
        service.put_chunk(PHONE, transfer.id, index, data, declared)
    assert exc.value.code == code
    assert service.received_chunks(PHONE, transfer.id) == []


def test_complete_refuses_missing_chunks(service: TransferService) -> None:
    transfer = service.create_upload(PHONE, "a.bin", len(DATA))
    part = chunks(DATA)[1]
    service.put_chunk(PHONE, transfer.id, 1, part, sha(part))
    with pytest.raises(ConflictError) as exc:
        service.complete(PHONE, transfer.id, sha(DATA))
    assert exc.value.code == "CHUNKS_MISSING"
    assert exc.value.details["missing"] == [0, 2]
    assert service.received_chunks(PHONE, transfer.id) == [1]


def test_concurrent_complete_calls_publish_exactly_once(
    service: TransferService, storage: FileStorage
) -> None:
    transfer_id = _upload_all(service)
    barrier = threading.Barrier(4)

    def finish() -> str:
        barrier.wait()
        try:
            return service.complete(PHONE, transfer_id, sha(DATA)).status.value
        except ConflictError:
            return "conflict"

    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(lambda _: finish(), range(4)))

    assert sorted(results) == ["completed", "conflict", "conflict", "conflict"]
    assert len(list(storage.receive_dir.glob("photo*.jpg"))) == 1


def test_empty_file_can_be_completed_directly(service: TransferService) -> None:
    transfer = service.create_upload(PHONE, "vide.txt", 0)
    assert transfer.total_chunks == 0
    done = service.complete(PHONE, transfer.id, sha(b""))
    assert done.status is TransferStatus.COMPLETED
    assert Path(done.final_path or "").read_bytes() == b""


def test_FR_025_cancel_removes_temp_and_blocks_further_chunks(
    service: TransferService, storage: FileStorage
) -> None:
    transfer = service.create_upload(PHONE, "a.bin", len(DATA))
    cancelled = service.cancel(PHONE, transfer.id)
    assert cancelled.status is TransferStatus.CANCELLED
    assert not storage.temp_path(transfer.id).exists()
    part = chunks(DATA)[0]
    with pytest.raises(ConflictError):
        service.put_chunk(PHONE, transfer.id, 0, part, sha(part))
    with pytest.raises(InvalidTransitionError):
        service.cancel(PHONE, transfer.id)


def test_transfers_are_private_to_their_device(service: TransferService) -> None:
    transfer = service.create_upload(PHONE, "a.bin", 4)
    intruder = _device("autre")
    with pytest.raises(NotFoundError):
        service.get(intruder, transfer.id)
    with pytest.raises(NotFoundError):
        service.put_chunk(intruder, transfer.id, 0, b"abcd", sha(b"abcd"))
    assert service.list_for(intruder) == []


def test_size_limit(service: TransferService) -> None:
    with pytest.raises(FileTooLargeError):
        service.create_upload(PHONE, "gros.iso", 1001)


def test_FR_028_two_uploads_with_same_name_do_not_overwrite(service: TransferService) -> None:
    first = service.complete(PHONE, _upload_all(service), sha(DATA))
    other = os.urandom(9)
    second = service.complete(PHONE, _upload_all(service, other), sha(other))
    assert Path(first.final_path or "").name == "photo.jpg"
    assert Path(second.final_path or "").name == "photo (1).jpg"
    assert Path(first.final_path or "").read_bytes() == DATA
