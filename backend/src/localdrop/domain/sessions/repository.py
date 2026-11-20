"""Port de persistance des sessions et appareils (implémenté dans infrastructure/)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from localdrop.domain.devices.models import Device
from localdrop.domain.sessions.models import Session


class SessionRepository(Protocol):
    def save_session(self, session: Session) -> None: ...

    def get_session(self, session_id: str) -> Session | None: ...

    def find_active_session(self, now: datetime) -> Session | None:
        """Session active la plus récente (reprise après redémarrage du serveur)."""
        ...

    def save_device(self, device: Device) -> None: ...

    def get_device(self, device_id: str) -> Device | None: ...

    def get_device_by_token_hash(self, token_hash: str) -> Device | None: ...

    def list_devices(self, session_id: str) -> list[Device]: ...
