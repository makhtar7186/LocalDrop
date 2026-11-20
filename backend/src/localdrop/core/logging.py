"""Journalisation : console + fichier rotatif, avec masquage des secrets (§12.2-10)."""

from __future__ import annotations

import logging
import re
import sys
from logging.handlers import RotatingFileHandler

from localdrop.core.config import Settings

REDACTED = "***"

_PATTERNS: tuple[re.Pattern[str], ...] = (
    # En-tête Authorization: Bearer <jeton>
    re.compile(r"(?i)(bearer\s+)[^\s\"',;]+"),
    # token=..., secret: ..., "password": "...", k=... (secret d'appairage), ticket=...
    re.compile(
        r"(?i)(\b(?:token|device_token|admin_token|secret|password|ticket|k)\b[\"']?\s*[=:]\s*[\"']?)"
        r"[^\s&\"',;}]+"
    ),
)


def redact(text: str) -> str:
    """Masque les secrets connus dans un texte de log."""
    for pattern in _PATTERNS:
        text = pattern.sub(rf"\g<1>{REDACTED}", text)
    return text


class RedactingFilter(logging.Filter):
    """Filtre appliqué à chaque handler : le message final ne contient aucun secret."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = redact(message)
        if redacted != message:
            record.msg = redacted
            record.args = None
        return True


_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(settings: Settings) -> None:
    """Configure le logger racine. À appeler une fois, au point d'entrée du processus."""
    settings.logs_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(_FORMAT)
    redacting = RedactingFilter()

    file_handler = RotatingFileHandler(
        settings.logs_dir / "localdrop.log",
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    handlers: list[logging.Handler] = [file_handler]
    # Exécutable fenêtré (PyInstaller --windowed) : pas de console, sys.stderr vaut None.
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    for handler in handlers:
        handler.setFormatter(formatter)
        handler.addFilter(redacting)

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
        existing.close()
    root.setLevel(settings.log_level)
    for handler in handlers:
        root.addHandler(handler)

    # Les logs d'accès Uvicorn peuvent contenir des query strings : désactivés.
    logging.getLogger("uvicorn.access").disabled = True
