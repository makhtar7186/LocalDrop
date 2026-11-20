import os
import shutil
import sys
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from localdrop.infrastructure.storage.files import (
    FileStorage,
    InsufficientDiskSpaceError,
    UnsafePathError,
)

pytestmark = pytest.mark.unit
TID = "0" * 31 + "1"


@pytest.fixture
def storage(tmp_path: Path) -> FileStorage:
    return FileStorage(tmp_path / "recus", free_space_margin=0)


def test_temp_file_lives_next_to_destination(storage: FileStorage) -> None:
    path = storage.create_temp(TID)
    assert path.parent == storage.temp_dir.resolve()
    assert storage.temp_dir.parent == storage.receive_dir
    assert path.name == f"{TID}.part"


@pytest.mark.parametrize("bad_id", ["../x", "abc", "0" * 31 + "/", "A" * 32])
def test_temp_path_rejects_unexpected_ids(storage: FileStorage, bad_id: str) -> None:
    with pytest.raises(UnsafePathError):
        storage.temp_path(bad_id)


def test_chunks_written_out_of_order(storage: FileStorage) -> None:
    storage.create_temp(TID)
    storage.write_chunk(TID, 4, b"5678")
    storage.write_chunk(TID, 0, b"1234")
    storage.write_chunk(TID, 0, b"1234")  # réécriture idempotente
    assert storage.temp_size(TID) == 8
    final = storage.publish(TID, "data.bin")
    assert final.read_bytes() == b"12345678"
    assert not storage.temp_path(TID).exists()


def test_FR_028_publish_never_overwrites(storage: FileStorage) -> None:
    storage.ensure_directories()
    existing = storage.receive_dir / "photo.jpg"
    existing.write_bytes(b"original")
    (storage.receive_dir / "photo (1).jpg").write_bytes(b"autre")

    storage.create_temp(TID)
    storage.write_chunk(TID, 0, b"nouveau")
    final = storage.publish(TID, "photo.jpg")

    assert final.name == "photo (2).jpg"
    assert existing.read_bytes() == b"original"
    assert final.read_bytes() == b"nouveau"


@pytest.mark.skipif(sys.platform != "win32", reason="Mark-of-the-Web propre à Windows")
def test_published_file_is_marked_as_from_network(storage: FileStorage) -> None:
    storage.create_temp(TID)
    final = storage.publish(TID, "setup.exe")
    with open(f"{final}:Zone.Identifier", encoding="ascii") as stream:  # noqa: PTH123
        assert "ZoneId=3" in stream.read()


def test_insufficient_disk_space_is_refused_before_writing(
    storage: FileStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Usage(NamedTuple):
        total: int
        used: int
        free: int

    def fake_usage(_: Any) -> Usage:
        return Usage(100, 90, 10)

    monkeypatch.setattr(shutil, "disk_usage", fake_usage)
    with pytest.raises(InsufficientDiskSpaceError) as exc:
        storage.check_free_space(11)
    assert exc.value.status_code == 507
    storage.check_free_space(10)


def test_delete_temp_is_idempotent(storage: FileStorage) -> None:
    storage.create_temp(TID)
    storage.delete_temp(TID)
    storage.delete_temp(TID)
    assert not os.path.exists(storage.temp_path(TID))  # noqa: PTH110
