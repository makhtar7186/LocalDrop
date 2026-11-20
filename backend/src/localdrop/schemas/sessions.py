from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from localdrop.domain.devices.models import Device, DeviceStatus, Platform


class JoinRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=64)
    secret: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=64)
    platform: Platform = Platform.OTHER


class JoinResponse(BaseModel):
    device_id: str
    device_token: str
    status: DeviceStatus


class SessionStatusResponse(BaseModel):
    device_id: str
    display_name: str
    status: DeviceStatus
    server_name: str
    session_expires_at: datetime


class DeviceOut(BaseModel):
    id: str
    display_name: str
    platform: Platform
    status: DeviceStatus
    client_ip: str
    created_at: datetime
    connected_at: datetime | None
    last_seen_at: datetime

    @classmethod
    def from_domain(cls, device: Device) -> DeviceOut:
        return cls(
            id=device.id,
            display_name=device.display_name,
            platform=device.platform,
            status=device.status,
            client_ip=device.client_ip,
            created_at=device.created_at,
            connected_at=device.connected_at,
            last_seen_at=device.last_seen_at,
        )


class ApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=1, max_length=64)
    approve: bool = True


class RevokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # None = fermer toute la session (tous les appareils, nouveau QR Code).
    device_id: str | None = Field(default=None, min_length=1, max_length=64)


class RevokeResponse(BaseModel):
    revoked: str  # "device" | "session"
    session_id: str


class PairingAddress(BaseModel):
    interface: str
    ip: str
    url: str
    pairing_url: str


class PairingInfoResponse(BaseModel):
    session_id: str
    expires_at: datetime
    addresses: list[PairingAddress]
