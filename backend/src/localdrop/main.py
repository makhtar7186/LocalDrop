"""Fabrique de l'application FastAPI.

Pas d'état global à l'import : l'application est créée par ``create_app`` pour les
tests, le développement (``uvicorn --factory``) et le desktop embarqué.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.routing import Match, Mount
from starlette.types import Scope

from localdrop import __version__
from localdrop.api.errors import install_error_handlers
from localdrop.api.middleware import PrivateNetworkOnlyMiddleware, SecurityHeadersMiddleware
from localdrop.api.v1.router import api_router
from localdrop.api.ws import router as ws_router
from localdrop.core.config import Settings
from localdrop.infrastructure.realtime.hub import RealtimeHub
from localdrop.services.container import AppServices, build_services

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, services: AppServices | None = None) -> FastAPI:
    settings = settings or (services.settings if services else Settings())
    services = services or build_services(settings)
    hub = RealtimeHub(services, auth_timeout=settings.ws_auth_timeout_seconds)

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        hub.start()
        monitor: asyncio.Task[None] | None = None
        if settings.network_poll_seconds > 0:
            monitor = asyncio.create_task(services.network.run(settings.network_poll_seconds))
        tasks: list[asyncio.Task[None]] = [] if monitor is None else [monitor]
        if settings.maintenance_interval_minutes > 0:
            tasks.append(
                asyncio.create_task(
                    services.maintenance.run_periodically(
                        settings.maintenance_interval_minutes * 60
                    )
                )
            )
        try:
            yield
        finally:
            await hub.stop()
            for task in tasks:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(
        title="LocalDrop",
        version=__version__,
        docs_url="/api/docs" if settings.debug else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.services = services
    app.state.hub = hub

    install_error_handlers(app)
    if not settings.allow_public_clients:
        app.add_middleware(PrivateNetworkOnlyMiddleware)
    # Ajouté en dernier = le plus externe : les en-têtes couvrent aussi les refus.
    app.add_middleware(SecurityHeadersMiddleware)
    app.include_router(api_router)
    app.include_router(ws_router)
    _mount_web_ui(app, settings)
    return app


_RESERVED_PREFIXES = ("/api", "/ws")


class _WebUIMount(Mount):
    """Montage de l'UI sur "/" qui ignore /api et /ws.

    Sans cela, le montage attrape-tout masquerait les 404/405 JSON de l'API.
    """

    def matches(self, scope: Scope) -> tuple[Match, Scope]:
        path = str(scope.get("path", ""))
        if any(path == p or path.startswith(p + "/") for p in _RESERVED_PREFIXES):
            return Match.NONE, {}
        return super().matches(scope)


def _mount_web_ui(app: FastAPI, settings: Settings) -> None:
    web_dir = settings.web_dist_dir
    if web_dir is None or not (web_dir / "index.html").is_file():
        logger.warning("Interface web introuvable (%s) : seule l'API est servie", web_dir)
        return
    app.router.routes.append(
        _WebUIMount("/", app=StaticFiles(directory=web_dir, html=True), name="web")
    )
