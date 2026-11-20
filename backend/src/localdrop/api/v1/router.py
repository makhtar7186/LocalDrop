from __future__ import annotations

from fastapi import APIRouter

from localdrop.api.v1 import health, sessions, transfers

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(sessions.router)
api_router.include_router(transfers.router)
