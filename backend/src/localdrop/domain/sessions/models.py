from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from localdrop.domain.sessions.tokens import secret_matches


class SessionStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass(slots=True)
class Session:
    id: str
    created_at: datetime
    expires_at: datetime
    status: SessionStatus
    # Secret d'appairage courant (QR Code) : hash uniquement, rotation fréquente.
    pairing_secret_hash: str
    pairing_expires_at: datetime

    def is_active(self, now: datetime) -> bool:
        return self.status is SessionStatus.ACTIVE and now < self.expires_at

    def accepts_pairing_secret(self, secret: str, now: datetime) -> bool:
        return now < self.pairing_expires_at and secret_matches(secret, self.pairing_secret_hash)
