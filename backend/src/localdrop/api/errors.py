"""Conversion de toutes les erreurs vers le format JSON unique de l'API."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from localdrop.core.errors import LocalDropError

logger = logging.getLogger(__name__)

_HTTP_CODES: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    429: "TOO_MANY_REQUESTS",
}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details or {}}},
        headers=headers,
    )


async def _handle_localdrop_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, LocalDropError):  # pragma: no cover - garanti par l'enregistrement
        raise exc
    return error_response(exc.status_code, exc.code, exc.message, exc.details)


async def _handle_http_exception(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):  # pragma: no cover
        raise exc
    code = _HTTP_CODES.get(exc.status_code, "HTTP_ERROR")
    return error_response(exc.status_code, code, str(exc.detail), headers=exc.headers)


async def _handle_validation_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):  # pragma: no cover
        raise exc
    # On ne renvoie jamais "input" : il peut contenir un secret soumis par le client.
    errors = [
        {"loc": list(err.get("loc", ())), "type": err.get("type"), "msg": err.get("msg")}
        for err in exc.errors()
    ]
    return error_response(422, "VALIDATION_ERROR", "Requête invalide", {"errors": errors})


async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Erreur inattendue", exc_info=exc)
    return error_response(500, "INTERNAL_ERROR", "Erreur interne du serveur")


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(LocalDropError, _handle_localdrop_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(Exception, _handle_unexpected)
