from datetime import UTC, datetime, timedelta

import pytest

from localdrop.core.errors import (
    ForbiddenError,
    NotFoundError,
    TooManyRequestsError,
    UnauthorizedError,
)
from localdrop.domain.devices.models import DeviceStatus, InvalidDeviceTransitionError, Platform
from localdrop.domain.sessions.rate_limit import SlidingWindowRateLimiter
from localdrop.infrastructure.database.memory import InMemorySessionRepository
from localdrop.services.events import Event, EventBus
from localdrop.services.pairing import JoinResult, PairingService

pytestmark = pytest.mark.unit


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
        self.mono = 0.0

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        step = timedelta(**delta)
        self.now += step
        self.mono += step.total_seconds()


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def events() -> list[Event]:
    return []


@pytest.fixture
def service(clock: Clock, events: list[Event]) -> PairingService:
    bus = EventBus()
    bus.subscribe(events.append)
    svc = PairingService(
        InMemorySessionRepository(),
        bus,
        session_ttl=timedelta(hours=12),
        pairing_ttl=timedelta(minutes=5),
        join_limiter=SlidingWindowRateLimiter(3, 60),
        clock=clock,
        monotonic=lambda: clock.mono,
    )
    svc.start_session()
    return svc


def _join(
    service: PairingService, secret: str | None = None, ip: str = "192.168.1.50"
) -> JoinResult:
    info = service.current_pairing()
    return service.join(
        session_id=info.session_id,
        secret=secret if secret is not None else info.secret,
        display_name="Pixel",
        platform=Platform.ANDROID,
        client_ip=ip,
    )


def test_FR_011_join_creates_pending_device_and_publishes_event(
    service: PairingService, events: list[Event]
) -> None:
    result = _join(service)
    assert result.device.status is DeviceStatus.PENDING
    assert result.device.token_hash != result.device_token
    assert "device.pending" in [e.type for e in events]


def test_FR_014_qr_secret_is_single_use(service: PairingService) -> None:
    first = service.current_pairing()
    _join(service)
    assert service.current_pairing().secret != first.secret
    with pytest.raises(UnauthorizedError) as exc:
        _join(service, secret=first.secret)
    assert exc.value.code == "PAIRING_SECRET_INVALID"


def test_FR_014_qr_secret_expires_and_is_renewed(service: PairingService, clock: Clock) -> None:
    old = service.current_pairing()
    clock.advance(minutes=6)
    with pytest.raises(UnauthorizedError):
        _join(service, secret=old.secret)
    renewed = service.current_pairing()
    assert renewed.secret != old.secret
    assert renewed.session_id == old.session_id


def test_FR_014_expired_session_is_reported_then_replaced(
    service: PairingService, clock: Clock
) -> None:
    old = service.current_pairing()
    clock.advance(hours=13)
    with pytest.raises(UnauthorizedError) as exc:
        service.join(
            session_id=old.session_id,
            secret=old.secret,
            display_name="x",
            platform=Platform.OTHER,
            client_ip="192.168.1.50",
        )
    assert exc.value.code == "SESSION_EXPIRED"  # §3.3 : le mobile demande un nouveau scan
    assert service.current_pairing().session_id != old.session_id


def test_join_attempts_are_rate_limited_per_ip(service: PairingService, clock: Clock) -> None:
    for _ in range(3):
        with pytest.raises(UnauthorizedError):
            _join(service, secret="mauvais")
    with pytest.raises(TooManyRequestsError):
        _join(service)  # même le bon secret est refusé pendant la fenêtre
    _join(service, ip="192.168.1.51")  # une autre IP n'est pas pénalisée
    clock.advance(seconds=61)
    _join(service)


def test_FR_010_pending_device_cannot_use_transfer_routes(service: PairingService) -> None:
    result = _join(service)
    assert service.device_for_token(result.device_token).status is DeviceStatus.PENDING
    with pytest.raises(ForbiddenError) as exc:
        service.authenticate(result.device_token)
    assert exc.value.code == "DEVICE_PENDING"


def test_FR_011_approved_device_authenticates(service: PairingService, clock: Clock) -> None:
    result = _join(service)
    service.approve(result.device.id)
    clock.advance(seconds=30)
    device = service.authenticate(result.device_token)
    assert device.status is DeviceStatus.CONNECTED
    assert device.last_seen_at == clock.now


def test_FR_011_rejected_device_is_refused(service: PairingService) -> None:
    result = _join(service)
    service.reject(result.device.id)
    with pytest.raises(ForbiddenError) as exc:
        service.device_for_token(result.device_token)
    assert exc.value.code == "DEVICE_REJECTED"
    with pytest.raises(InvalidDeviceTransitionError):
        service.approve(result.device.id)


def test_FR_013_revoked_device_loses_access(service: PairingService) -> None:
    result = _join(service)
    service.approve(result.device.id)
    service.revoke(result.device.id)
    with pytest.raises(UnauthorizedError):
        service.authenticate(result.device_token)


def test_close_session_revokes_every_device(service: PairingService) -> None:
    a = _join(service)
    b = _join(service, ip="192.168.1.51")
    service.approve(a.device.id)
    old_session = service.current_session().id
    service.close_session()
    assert service.current_session().id != old_session
    for result in (a, b):
        with pytest.raises(UnauthorizedError):
            service.device_for_token(result.device_token)
    assert service.list_devices() == []


def test_unknown_device_and_token(service: PairingService) -> None:
    with pytest.raises(NotFoundError):
        service.approve("inconnu")
    with pytest.raises(UnauthorizedError):
        service.device_for_token("jeton-inconnu")
