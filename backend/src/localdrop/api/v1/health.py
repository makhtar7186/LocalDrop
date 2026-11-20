from __future__ import annotations

from fastapi import APIRouter

from localdrop import __version__
from localdrop.schemas.health import HealthResponse

router = APIRouter(tags=["santé"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Disponibilité du serveur (route publique, §10.3)."""
    return HealthResponse(status="ok", version=__version__)
