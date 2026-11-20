"""Dépôt en mémoire, thread-safe (serveur + desktop).

Phase 2 : les sessions vivent le temps du processus. Le dépôt SQLite (phase 6/7)
implémentera le même port ``SessionRepository``.
"""

from __future__ import annotations

import copy
import threading
from datetime import datetime

from localdrop.domain.devices.models import Device
from localdrop.domain.sessions.models import Session, SessionStatus


class InMemorySessionRepository:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, Session] = {}
        self._devices: dict[str, Device] = {}

    def save_session(self, session: Session) -> None:
        with self._lock:
            self._sessions[session.id] = copy.copy(session)

    def get_session(self, session_id: str) -> Session | None:
        with self._lock:
            session = self._sessions.get(session_id)
            return copy.copy(session) if session else None

    def find_active_session(self, now: datetime) -> Session | None:
        with self._lock:
            active = [s for s in self._sessions.values() if s.is_active(now)]
        return copy.copy(max(active, key=lambda s: s.created_at)) if active else None

    def expire_sessions(self, now: datetime) -> int:
        with self._lock:
            expired = [
                s
                for s in self._sessions.values()
                if s.status is SessionStatus.ACTIVE and s.expires_at <= now
            ]
            for session in expired:
                session.status = SessionStatus.EXPIRED
            return len(expired)

    def save_device(self, device: Device) -> None:
        with self._lock:
            self._devices[device.id] = copy.copy(device)

    def get_device(self, device_id: str) -> Device | None:
        with self._lock:
            device = self._devices.get(device_id)
            return copy.copy(device) if device else None

    def get_device_by_token_hash(self, token_hash: str) -> Device | None:
        with self._lock:
            for device in self._devices.values():
                if device.token_hash == token_hash:
                    return copy.copy(device)
            return None

    def list_devices(self, session_id: str) -> list[Device]:
        with self._lock:
            devices = [copy.copy(d) for d in self._devices.values() if d.session_id == session_id]
        return sorted(devices, key=lambda d: d.created_at)
