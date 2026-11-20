"""Route WebSocket ``/ws`` (§10.4). Protocole décrit dans infrastructure/realtime/hub.py."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket

from localdrop.infrastructure.realtime.hub import RealtimeHub

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    hub: RealtimeHub = websocket.app.state.hub
    await hub.serve(websocket)
