from datetime import UTC, datetime

import pytest

from localdrop.domain.devices.models import (
    Device,
    DeviceStatus,
    InvalidDeviceTransitionError,
    Platform,
    clean_display_name,
)
from localdrop.domain.sessions.rate_limit import SlidingWindowRateLimiter
from localdrop.domain.sessions.tokens import generate_secret, hash_secret, secret_matches

pytestmark = pytest.mark.unit
NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


def test_FR_010_secrets_are_random_and_only_hash_is_comparable() -> None:
    a, b = generate_secret(), generate_secret()
    assert a != b
    assert len(a) >= 43  # 32 octets en base64url
    assert hash_secret(a) != a
    assert secret_matches(a, hash_secret(a))
    assert not secret_matches(b, hash_secret(a))


def test_rate_limiter_blocks_then_recovers_after_window() -> None:
    limiter = SlidingWindowRateLimiter(max_attempts=3, window_seconds=60)
    assert [limiter.hit("ip", t) for t in (0, 1, 2)] == [True, True, True]
    assert limiter.hit("ip", 3) is False
    assert limiter.hit("other-ip", 3) is True
    assert limiter.hit("ip", 61) is True


def _device(status: DeviceStatus = DeviceStatus.PENDING) -> Device:
    return Device(
        id="d1",
        session_id="s1",
        display_name="iPhone",
        platform=Platform.IOS,
        status=status,
        token_hash="h",
        client_ip="192.168.1.50",
        created_at=NOW,
        last_seen_at=NOW,
    )


def test_FR_011_pending_device_can_be_approved_once() -> None:
    device = _device()
    device.transition(DeviceStatus.CONNECTED, NOW)
    assert device.status is DeviceStatus.CONNECTED
    assert device.connected_at == NOW
    with pytest.raises(InvalidDeviceTransitionError):
        device.transition(DeviceStatus.REJECTED, NOW)


@pytest.mark.parametrize("terminal", [DeviceStatus.REJECTED, DeviceStatus.REVOKED])
def test_FR_013_terminal_states_are_final(terminal: DeviceStatus) -> None:
    device = _device(terminal)
    assert device.is_terminal
    for target in DeviceStatus:
        with pytest.raises(InvalidDeviceTransitionError):
            device.transition(target, NOW)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("  Pixel 8  ", "Pixel 8"), ("a\x00b\nc", "abc"), ("\x07", "Appareil"), ("x" * 100, "x" * 64)],
)
def test_display_name_is_cleaned(raw: str, expected: str) -> None:
    assert clean_display_name(raw) == expected
