from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from localdrop.core.errors import ConflictError


class DeviceStatus(StrEnum):
    PENDING = "pending"  # a scanné le QR Code, attend l'approbation sur le PC
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    REJECTED = "rejected"
    REVOKED = "revoked"


class Platform(StrEnum):
    ANDROID = "android"
    IOS = "ios"
    WINDOWS = "windows"
    OTHER = "other"


_TRANSITIONS: dict[DeviceStatus, frozenset[DeviceStatus]] = {
    DeviceStatus.PENDING: frozenset(
        {DeviceStatus.CONNECTED, DeviceStatus.REJECTED, DeviceStatus.REVOKED}
    ),
    DeviceStatus.CONNECTED: frozenset({DeviceStatus.DISCONNECTED, DeviceStatus.REVOKED}),
    DeviceStatus.DISCONNECTED: frozenset({DeviceStatus.CONNECTED, DeviceStatus.REVOKED}),
    DeviceStatus.REJECTED: frozenset(),
    DeviceStatus.REVOKED: frozenset(),
}


class InvalidDeviceTransitionError(ConflictError):
    code = "INVALID_DEVICE_TRANSITION"


@dataclass(slots=True)
class Device:
    id: str
    session_id: str
    display_name: str
    platform: Platform
    status: DeviceStatus
    token_hash: str
    client_ip: str
    created_at: datetime
    last_seen_at: datetime
    connected_at: datetime | None = None

    def transition(self, new_status: DeviceStatus, now: datetime) -> None:
        if new_status not in _TRANSITIONS[self.status]:
            raise InvalidDeviceTransitionError(
                f"Transition impossible : {self.status} -> {new_status}",
                details={"from": self.status.value, "to": new_status.value},
            )
        self.status = new_status
        if new_status is DeviceStatus.CONNECTED and self.connected_at is None:
            self.connected_at = now

    @property
    def is_terminal(self) -> bool:
        return not _TRANSITIONS[self.status]


def clean_display_name(raw: str, max_length: int = 64) -> str:
    """Nom d'affichage sans caractères de contrôle, tronqué."""
    cleaned = "".join(ch for ch in raw if ch.isprintable()).strip()
    return cleaned[:max_length] or "Appareil"
