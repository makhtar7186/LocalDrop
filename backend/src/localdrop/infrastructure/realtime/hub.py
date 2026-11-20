"""Hub WebSocket (§8.5, §10.4).

- Authentification par premier message (jamais de jeton dans l'URL), délai court.
- Les événements du bus sont publiés depuis n'importe quel thread : ils sont reportés
  sur la boucle asyncio **de chaque connexion** (``call_soon_threadsafe``) puis placés
  dans sa file d'envoi. Tous les messages sortants passent par cette file : ordre garanti.
- Le WebSocket n'est pas la source de vérité : un client trop lent est déconnecté
  (4409) et se resynchronise par REST.

Codes de fermeture : 4401 non autorisé/révoqué, 4403 origine ou appareil refusé,
4408 authentification trop tardive, 4409 client trop lent, 1001 arrêt du serveur.
"""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import ipaddress
import logging
import threading
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from localdrop.core.errors import ForbiddenError, LocalDropError
from localdrop.services.container import AppServices
from localdrop.services.events import Event

logger = logging.getLogger(__name__)

CLOSE_UNAUTHORIZED = 4401
CLOSE_FORBIDDEN = 4403
CLOSE_AUTH_TIMEOUT = 4408
CLOSE_TOO_SLOW = 4409
CLOSE_GOING_AWAY = 1001

_REVOKING_EVENTS = frozenset({"device.revoked", "device.rejected"})
_DEVICE_EVENT_PREFIXES = ("transfer.", "device.")


@dataclass(frozen=True, slots=True)
class _Close:
    code: int


@dataclass(eq=False)
class _Connection:
    websocket: WebSocket
    device_id: str | None  # None = administration (PC)
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[dict[str, Any] | _Close] = field(default_factory=asyncio.Queue)
    closing: bool = False


def envelope(event: Event) -> dict[str, Any]:
    return {"id": event.id, "type": event.type, "ts": event.ts.isoformat(), "data": event.data}


class RealtimeHub:
    def __init__(
        self, services: AppServices, *, auth_timeout: float, max_pending: int = 256
    ) -> None:
        self._services = services
        self._auth_timeout = auth_timeout
        self._max_pending = max_pending
        self._lock = threading.Lock()
        self._starts = 0
        self._unsubscribe: Any = None
        self._connections: set[_Connection] = set()
        self._presence: dict[str, int] = {}

    # ------------------------------------------------------------------ cycle de vie
    def start(self) -> None:
        """Idempotent : un seul abonnement au bus, même si le cycle de vie démarre plusieurs
        fois (plusieurs serveurs ou clients de test sur la même application)."""
        with self._lock:
            self._starts += 1
            if self._unsubscribe is None:
                self._unsubscribe = self._services.events.subscribe(self._on_event)

    async def stop(self) -> None:
        loop = asyncio.get_running_loop()
        with self._lock:
            self._starts = max(0, self._starts - 1)
            if self._starts == 0 and self._unsubscribe is not None:
                self._unsubscribe()
                self._unsubscribe = None
            mine = [c for c in self._connections if c.loop is loop]
        for connection in mine:
            self._close(connection, CLOSE_GOING_AWAY)

    @property
    def connection_count(self) -> int:
        with self._lock:
            return len(self._connections)

    # ------------------------------------------------------------------ bus -> boucles
    def _on_event(self, event: Event) -> None:
        with self._lock:
            loops = {c.loop for c in self._connections}
        for loop in loops:
            if loop.is_closed():
                continue
            with contextlib.suppress(RuntimeError):  # boucle arrêtée entre-temps
                loop.call_soon_threadsafe(self._dispatch, event, loop)

    def _dispatch(self, event: Event, loop: asyncio.AbstractEventLoop) -> None:
        payload = envelope(event)
        target_device = event.data.get("device_id")
        with self._lock:
            connections = [c for c in self._connections if c.loop is loop]
        for connection in connections:
            if connection.closing or not self._visible(connection, event, target_device):
                continue
            self._enqueue(connection, payload)
            if event.type in _REVOKING_EVENTS and connection.device_id == target_device:
                self._close(connection, CLOSE_UNAUTHORIZED)

    @staticmethod
    def _visible(connection: _Connection, event: Event, target_device: object) -> bool:
        if connection.device_id is None:
            return True
        return event.type.startswith(_DEVICE_EVENT_PREFIXES) and (
            target_device == connection.device_id
        )

    def _enqueue(self, connection: _Connection, message: dict[str, Any]) -> None:
        if connection.queue.qsize() >= self._max_pending:
            logger.warning("Client WebSocket trop lent : déconnexion pour resynchronisation")
            self._close(connection, CLOSE_TOO_SLOW)
            return
        connection.queue.put_nowait(message)

    def _close(self, connection: _Connection, code: int) -> None:
        if not connection.closing:
            connection.closing = True
            connection.queue.put_nowait(_Close(code))

    # ------------------------------------------------------------------ connexion
    async def serve(self, websocket: WebSocket) -> None:
        if not _same_origin(websocket):
            await websocket.close(code=CLOSE_FORBIDDEN)
            return
        await websocket.accept()

        try:
            device_id = await self._authenticate(websocket)
        except _AuthFailedError as failure:
            await websocket.close(code=failure.code)
            return

        connection = _Connection(websocket, device_id, asyncio.get_running_loop())
        if self._register(connection) and device_id is not None:
            await asyncio.to_thread(self._services.pairing.set_presence, device_id, online=True)
        try:
            connection.queue.put_nowait(
                {"type": "auth.ok", "data": {"device_id": device_id, "role": _role(device_id)}}
            )
            sender = asyncio.create_task(self._send_loop(connection))
            receiver = asyncio.create_task(self._receive_loop(connection))
            _, pending = await asyncio.wait({sender, receiver}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
        finally:
            if self._unregister(connection) and device_id is not None:
                with contextlib.suppress(Exception):
                    await asyncio.to_thread(
                        self._services.pairing.set_presence, device_id, online=False
                    )
            if websocket.application_state is WebSocketState.CONNECTED:
                with contextlib.suppress(Exception):
                    await websocket.close(code=CLOSE_GOING_AWAY)

    async def _authenticate(self, websocket: WebSocket) -> str | None:
        try:
            message = await asyncio.wait_for(websocket.receive_json(), self._auth_timeout)
        except TimeoutError as exc:
            raise _AuthFailedError(CLOSE_AUTH_TIMEOUT) from exc
        except (WebSocketDisconnect, ValueError, KeyError) as exc:
            raise _AuthFailedError(CLOSE_UNAUTHORIZED) from exc

        if not isinstance(message, dict) or message.get("type") != "auth":
            raise _AuthFailedError(CLOSE_UNAUTHORIZED)

        admin_token = message.get("admin_token")
        if isinstance(admin_token, str):
            if _is_loopback(websocket) and hmac.compare_digest(
                admin_token, self._services.admin_token
            ):
                return None
            raise _AuthFailedError(CLOSE_FORBIDDEN)

        token = message.get("token")
        if not isinstance(token, str) or not token:
            raise _AuthFailedError(CLOSE_UNAUTHORIZED)
        try:
            # Les appareils en attente sont admis : ils apprennent ainsi leur approbation.
            device = await asyncio.to_thread(self._services.pairing.device_for_token, token)
        except ForbiddenError as exc:
            raise _AuthFailedError(CLOSE_FORBIDDEN) from exc
        except LocalDropError as exc:
            raise _AuthFailedError(CLOSE_UNAUTHORIZED) from exc
        return device.id

    async def _send_loop(self, connection: _Connection) -> None:
        while True:
            message = await connection.queue.get()
            if isinstance(message, _Close):
                await connection.websocket.close(code=message.code)
                return
            await connection.websocket.send_json(message)

    async def _receive_loop(self, connection: _Connection) -> None:
        while True:
            try:
                message = await connection.websocket.receive_json()
            except WebSocketDisconnect:
                return
            except ValueError:
                continue  # message non JSON ignoré
            if isinstance(message, dict) and message.get("type") == "ping":
                self._enqueue(connection, {"type": "pong"})

    # ------------------------------------------------------------------ présence
    def _register(self, connection: _Connection) -> bool:
        """Enregistre la connexion. True si c'est le premier socket de l'appareil."""
        with self._lock:
            self._connections.add(connection)
            device_id = connection.device_id
            if device_id is None:
                return False
            count = self._presence.get(device_id, 0)
            self._presence[device_id] = count + 1
            return count == 0

    def _unregister(self, connection: _Connection) -> bool:
        """Retire la connexion. True si c'était le dernier socket de l'appareil."""
        with self._lock:
            self._connections.discard(connection)
            device_id = connection.device_id
            if device_id is None:
                return False
            remaining = self._presence.get(device_id, 1) - 1
            if remaining > 0:
                self._presence[device_id] = remaining
                return False
            self._presence.pop(device_id, None)
            return True


class _AuthFailedError(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code


def _role(device_id: str | None) -> str:
    return "admin" if device_id is None else "device"


def _is_loopback(websocket: WebSocket) -> bool:
    host = websocket.client.host if websocket.client else ""
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _same_origin(websocket: WebSocket) -> bool:
    """Protection contre le détournement de WebSocket entre sites (CSWSH).

    Un navigateur envoie toujours Origin ; un client non navigateur peut s'en passer.
    """
    origin = websocket.headers.get("origin")
    if origin is None:
        return True
    host = websocket.headers.get("host", "")
    return urlsplit(origin).netloc.lower() == host.lower()
