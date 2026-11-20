"""Middlewares ASGI purs (compatibles streaming)."""

from __future__ import annotations

import ipaddress
import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_COMMON_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"x-frame-options", b"DENY"),
)

# Pages de l'interface mobile (audit phase 10). Le jeton de l'appareil vit dans le
# localStorage : la CSP interdit tout script en ligne ou externe, première voie d'une
# injection. 'unsafe-eval' reste nécessaire au WebAssembly de hash-wasm sur Safari < 16
# (qui ignore 'wasm-unsafe-eval') ; il ne sert qu'à du code déjà en cours d'exécution.
# connect-src liste ws: car les anciens Safari n'associent pas 'self' aux WebSocket.
WEB_UI_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'wasm-unsafe-eval' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "connect-src 'self' ws:; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
).encode("ascii")


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        is_api = str(scope.get("path", "")).startswith("/api/")

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                for name, value in _COMMON_HEADERS:
                    if name not in present:
                        headers.append((name, value))
                if is_api and b"cache-control" not in present:
                    headers.append((b"cache-control", b"no-store"))
                if not is_api and b"content-security-policy" not in present:
                    headers.append((b"content-security-policy", WEB_UI_CSP))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


def is_private_client(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_loopback or (ip.is_private and not ip.is_unspecified)


_LOCAL_HOSTNAMES = frozenset({"localhost"})


def is_allowed_host(host_header: str) -> bool:
    """Vrai si l'en-tête Host désigne une IP littérale ou ``localhost`` (port facultatif).

    Le QR Code et le desktop n'utilisent que des adresses IP : un nom de domaine dans
    Host signale une attaque par DNS rebinding (un site tiers dont le nom pointe vers
    le PC), qui contournerait sinon la vérification d'origine du WebSocket.
    """
    host = host_header.strip().lower()
    if not host:
        return False
    if host.startswith("["):  # IPv6 littérale : [::1]:8765
        candidate, bracket, rest = host[1:].partition("]")
        if not bracket or (rest and not (rest.startswith(":") and _is_port(rest[1:]))):
            return False
    else:
        candidate, sep, port = host.partition(":")
        if sep and not _is_port(port):
            return False
    if candidate in _LOCAL_HOSTNAMES:
        return True
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return False
    return True


def _is_port(port: str) -> bool:
    return port.isdigit() and 0 < int(port) < 65536


class AllowedHostMiddleware:
    """Refuse un en-tête Host qui n'est ni une IP ni localhost (anti DNS rebinding)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        host = ""
        for name, value in scope.get("headers", []):
            if name == b"host":
                host = value.decode("latin-1")
                break
        if is_allowed_host(host):
            await self.app(scope, receive, send)
            return
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        await _send_json_error(send, 400, "HOST_NOT_ALLOWED", "Adresse du serveur non reconnue")


async def _send_json_error(send: Send, status: int, code: str, message: str) -> None:
    body = json.dumps({"error": {"code": code, "message": message, "details": {}}}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class PrivateNetworkOnlyMiddleware:
    """Refuse tout client hors réseau privé / loopback (§12.2-11, défense en profondeur)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        client = scope.get("client")
        if client and is_private_client(str(client[0])):
            await self.app(scope, receive, send)
            return

        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        await _send_json_error(send, 403, "CLIENT_NOT_ALLOWED", "Accès limité au réseau local")
