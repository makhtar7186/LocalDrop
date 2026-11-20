"""Cas d'usage sessions, appairage et appareils (FR-010 à FR-014, §8.2, §12)."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from localdrop.core.errors import (
    ForbiddenError,
    NotFoundError,
    TooManyRequestsError,
    UnauthorizedError,
)
from localdrop.domain.devices.models import Device, DeviceStatus, Platform, clean_display_name
from localdrop.domain.sessions.models import Session, SessionStatus
from localdrop.domain.sessions.rate_limit import SlidingWindowRateLimiter
from localdrop.domain.sessions.repository import SessionRepository
from localdrop.domain.sessions.tokens import generate_id, generate_secret, hash_secret
from localdrop.services.events import EventBus

logger = logging.getLogger(__name__)

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class PairingInfo:
    session_id: str
    secret: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class JoinResult:
    device: Device
    device_token: str


class PairingService:
    def __init__(
        self,
        repository: SessionRepository,
        events: EventBus,
        *,
        session_ttl: timedelta,
        pairing_ttl: timedelta,
        join_limiter: SlidingWindowRateLimiter,
        clock: Clock = utc_now,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._repo = repository
        self._events = events
        self._session_ttl = session_ttl
        self._pairing_ttl = pairing_ttl
        self._limiter = join_limiter
        self._clock = clock
        self._monotonic = monotonic
        self._lock = threading.RLock()
        self._session_id: str | None = None
        # Secret d'appairage en clair : en mémoire uniquement, pour afficher le QR Code.
        self._pairing_secret: str | None = None

    # ------------------------------------------------------------------ session
    def start_session(self) -> Session:
        """Crée une nouvelle session (et révoque la précédente s'il y en a une)."""
        with self._lock:
            if self._session_id is not None:
                self._revoke_session_locked(self._session_id)
            now = self._clock()
            secret = generate_secret()
            session = Session(
                id=generate_id(),
                created_at=now,
                expires_at=now + self._session_ttl,
                status=SessionStatus.ACTIVE,
                pairing_secret_hash=hash_secret(secret),
                pairing_expires_at=now + self._pairing_ttl,
            )
            self._repo.save_session(session)
            self._session_id = session.id
            self._pairing_secret = secret
        logger.info("Session %s démarrée", session.id)
        self._events.publish("session.started", {"session_id": session.id})
        return session

    def resume_or_start_session(self) -> Session:
        """Au démarrage : reprend la session active (appareils approuvés conservés) ou en
        crée une. Le secret d'appairage en clair n'est jamais persisté : nouveau QR Code."""
        with self._lock:
            session = self._repo.find_active_session(self._clock())
            if session is None:
                return self.start_session()
            self._session_id = session.id
            session = self._rotate_pairing_secret_locked(session)
        logger.info("Session %s reprise", session.id)
        return session

    def current_session(self) -> Session:
        with self._lock:
            session = self._repo.get_session(self._session_id) if self._session_id else None
            if session is None or not session.is_active(self._clock()):
                return self.start_session()
            return session

    def current_pairing(self) -> PairingInfo:
        """Secret valide pour le QR Code (renouvelé s'il a expiré)."""
        with self._lock:
            session = self.current_session()
            if self._pairing_secret is None or self._clock() >= session.pairing_expires_at:
                session = self._rotate_pairing_secret_locked(session)
            assert self._pairing_secret is not None  # noqa: S101 - invariant interne
            return PairingInfo(session.id, self._pairing_secret, session.pairing_expires_at)

    def close_session(self) -> Session:
        """Ferme la session courante (tous les appareils révoqués) et en ouvre une neuve."""
        return self.start_session()

    # ------------------------------------------------------------------ appairage
    def join(
        self,
        *,
        session_id: str,
        secret: str,
        display_name: str,
        platform: Platform,
        client_ip: str,
    ) -> JoinResult:
        if not self._limiter.hit(f"join:{client_ip}", self._monotonic()):
            logger.warning("Trop de tentatives d'appairage depuis %s", client_ip)
            raise TooManyRequestsError(
                "Trop de tentatives, réessayez dans un instant", code="PAIRING_RATE_LIMITED"
            )

        with self._lock:
            now = self._clock()
            session = self._repo.get_session(session_id)
            if session is None or session.id != self._session_id:
                raise UnauthorizedError("Session inconnue", code="SESSION_INVALID")
            if not session.is_active(now):
                raise UnauthorizedError("Session expirée", code="SESSION_EXPIRED")
            if not session.accepts_pairing_secret(secret, now):
                logger.warning("Secret d'appairage invalide depuis %s", client_ip)
                raise UnauthorizedError("QR Code invalide ou expiré", code="PAIRING_SECRET_INVALID")

            token = generate_secret()
            device = Device(
                id=generate_id(),
                session_id=session.id,
                display_name=clean_display_name(display_name),
                platform=platform,
                status=DeviceStatus.PENDING,
                token_hash=hash_secret(token),
                client_ip=client_ip,
                created_at=now,
                last_seen_at=now,
            )
            self._repo.save_device(device)
            # QR Code à usage unique : l'ancien est invalidé (§12.2-2).
            self._rotate_pairing_secret_locked(session)

        logger.info("Appareil %s (%s) en attente d'approbation", device.id, device.platform)
        self._events.publish("device.pending", _device_event(device))
        return JoinResult(device=device, device_token=token)

    # ------------------------------------------------------------------ authentification
    def device_for_token(self, token: str) -> Device:
        """Appareil associé au jeton, quel que soit son état (pour /sessions/status)."""
        device = self._repo.get_device_by_token_hash(hash_secret(token))
        if device is None or device.status is DeviceStatus.REVOKED:
            raise UnauthorizedError("Session terminée", code="DEVICE_UNAUTHORIZED")
        session = self._repo.get_session(device.session_id)
        if session is None or not session.is_active(self._clock()):
            raise UnauthorizedError("Session expirée", code="SESSION_EXPIRED")
        if device.status is DeviceStatus.REJECTED:
            raise ForbiddenError("Appareil refusé", code="DEVICE_REJECTED")
        return device

    def authenticate(self, token: str) -> Device:
        """Appareil approuvé uniquement (routes de transfert)."""
        with self._lock:
            device = self.device_for_token(token)
            if device.status is DeviceStatus.PENDING:
                raise ForbiddenError("En attente d'approbation", code="DEVICE_PENDING")
            now = self._clock()
            if device.status is DeviceStatus.DISCONNECTED:
                device.transition(DeviceStatus.CONNECTED, now)
            device.last_seen_at = now
            self._repo.save_device(device)
            return device

    def active_device(self, device_id: str) -> Device:
        """Appareil approuvé et toujours autorisé (ticket de téléchargement, envoi PC)."""
        device = self._repo.get_device(device_id)
        if device is None or device.status not in (
            DeviceStatus.CONNECTED,
            DeviceStatus.DISCONNECTED,
        ):
            raise UnauthorizedError("Appareil non autorisé", code="DEVICE_UNAUTHORIZED")
        session = self._repo.get_session(device.session_id)
        if session is None or not session.is_active(self._clock()):
            raise UnauthorizedError("Session expirée", code="SESSION_EXPIRED")
        return device

    def set_presence(self, device_id: str, *, online: bool) -> None:
        """Présence temps réel (FR-012) : connected <-> disconnected selon les WebSocket."""
        with self._lock:
            device = self._repo.get_device(device_id)
            if device is None or device.status not in (
                DeviceStatus.CONNECTED,
                DeviceStatus.DISCONNECTED,
            ):
                return
            target = DeviceStatus.CONNECTED if online else DeviceStatus.DISCONNECTED
            if device.status is target:
                return
            now = self._clock()
            device.transition(target, now)
            device.last_seen_at = now
            self._repo.save_device(device)
        self._events.publish(
            "device.connected" if online else "device.disconnected", _device_event(device)
        )

    # ------------------------------------------------------------------ administration
    def approve(self, device_id: str) -> Device:
        device = self._change_status(device_id, DeviceStatus.CONNECTED)
        logger.info("Appareil %s approuvé", device.id)
        self._events.publish("device.connected", _device_event(device))
        return device

    def reject(self, device_id: str) -> Device:
        device = self._change_status(device_id, DeviceStatus.REJECTED)
        logger.info("Appareil %s refusé", device.id)
        self._events.publish("device.rejected", _device_event(device))
        return device

    def revoke(self, device_id: str) -> Device:
        device = self._change_status(device_id, DeviceStatus.REVOKED)
        logger.info("Appareil %s révoqué", device.id)
        self._events.publish("device.revoked", _device_event(device))
        return device

    def list_devices(self) -> list[Device]:
        return self._repo.list_devices(self.current_session().id)

    # ------------------------------------------------------------------ interne
    def _change_status(self, device_id: str, status: DeviceStatus) -> Device:
        with self._lock:
            device = self._repo.get_device(device_id)
            if device is None or device.session_id != self._session_id:
                raise NotFoundError("Appareil introuvable", code="DEVICE_NOT_FOUND")
            device.transition(status, self._clock())
            self._repo.save_device(device)
            return device

    def _rotate_pairing_secret_locked(self, session: Session) -> Session:
        now = self._clock()
        secret = generate_secret()
        session.pairing_secret_hash = hash_secret(secret)
        session.pairing_expires_at = now + self._pairing_ttl
        self._repo.save_session(session)
        self._pairing_secret = secret
        self._events.publish(
            "session.pairing_rotated",
            {"session_id": session.id, "expires_at": session.pairing_expires_at.isoformat()},
        )
        return session

    def _revoke_session_locked(self, session_id: str) -> None:
        session = self._repo.get_session(session_id)
        if session is None:
            return
        now = self._clock()
        for device in self._repo.list_devices(session_id):
            if not device.is_terminal:
                device.transition(DeviceStatus.REVOKED, now)
                self._repo.save_device(device)
                self._events.publish("device.revoked", _device_event(device))
        session.status = SessionStatus.REVOKED
        self._repo.save_session(session)
        self._pairing_secret = None


def _device_event(device: Device) -> dict[str, str]:
    return {
        "device_id": device.id,
        "display_name": device.display_name,
        "platform": device.platform.value,
        "status": device.status.value,
        "client_ip": device.client_ip,
    }
