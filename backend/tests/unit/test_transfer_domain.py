from datetime import UTC, datetime

import pytest

from localdrop.domain.transfers.models import (
    Direction,
    InvalidChunkError,
    InvalidTransitionError,
    Transfer,
    TransferStatus,
    can_transition,
    missing_chunks,
    total_chunks_for,
)

pytestmark = pytest.mark.unit
S = TransferStatus
NOW = datetime(2026, 11, 20, tzinfo=UTC)

ALLOWED = {
    (S.CREATED, S.WAITING),
    (S.WAITING, S.TRANSFERRING),
    (S.TRANSFERRING, S.VERIFYING),
    (S.TRANSFERRING, S.PAUSED),
    (S.PAUSED, S.TRANSFERRING),
    (S.VERIFYING, S.COMPLETED),
    (S.VERIFYING, S.FAILED),
    (S.CREATED, S.CANCELLED),
    (S.WAITING, S.CANCELLED),
    (S.TRANSFERRING, S.CANCELLED),
    (S.PAUSED, S.CANCELLED),
}


@pytest.mark.parametrize("source", list(S))
@pytest.mark.parametrize("target", list(S))
def test_state_machine_matches_specification(source: S, target: S) -> None:
    assert can_transition(source, target) == ((source, target) in ALLOWED)


def _transfer(size: int, chunk: int = 10, status: S = S.TRANSFERRING) -> Transfer:
    return Transfer(
        id="t",
        device_id="d",
        direction=Direction.UPLOAD,
        filename="f",
        safe_filename="f",
        total_size=size,
        chunk_size=chunk,
        total_chunks=total_chunks_for(size, chunk),
        status=status,
        created_at=NOW,
        updated_at=NOW,
        expires_at=NOW,
    )


def test_completed_transfer_is_immutable() -> None:
    transfer = _transfer(5, status=S.COMPLETED)
    for target in S:
        with pytest.raises(InvalidTransitionError):
            transfer.transition(target, NOW)


@pytest.mark.parametrize(
    ("size", "chunk", "expected"), [(0, 10, 0), (1, 10, 1), (10, 10, 1), (11, 10, 2), (25, 10, 3)]
)
def test_total_chunks(size: int, chunk: int, expected: int) -> None:
    assert total_chunks_for(size, chunk) == expected


def test_expected_chunk_sizes_and_bounds() -> None:
    transfer = _transfer(25)
    assert [transfer.expected_chunk_size(i) for i in range(3)] == [10, 10, 5]
    assert transfer.chunk_offset(2) == 20
    for index in (-1, 3):
        with pytest.raises(InvalidChunkError):
            transfer.expected_chunk_size(index)


def test_missing_chunks() -> None:
    assert missing_chunks(5, {0, 2, 4}) == [1, 3]
