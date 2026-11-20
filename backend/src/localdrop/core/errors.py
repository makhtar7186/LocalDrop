"""Erreurs applicatives. Le code est stable (anglais, MAJUSCULES) ; le client traduit."""

from __future__ import annotations

from typing import Any


class LocalDropError(Exception):
    """Erreur de base, convertie en ``{"error": {"code", "message", "details"}}``."""

    code: str = "LOCALDROP_ERROR"
    status_code: int = 400

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details: dict[str, Any] = details or {}


class NotFoundError(LocalDropError):
    code = "NOT_FOUND"
    status_code = 404


class ConflictError(LocalDropError):
    code = "CONFLICT"
    status_code = 409


class UnauthorizedError(LocalDropError):
    code = "UNAUTHORIZED"
    status_code = 401


class ForbiddenError(LocalDropError):
    code = "FORBIDDEN"
    status_code = 403


class TooManyRequestsError(LocalDropError):
    code = "TOO_MANY_REQUESTS"
    status_code = 429
