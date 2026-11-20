"""Assainissement des noms de fichiers reçus (FR-032, §8.4, §13.2).

Le nom envoyé par le client est une donnée d'affichage, jamais un chemin.
"""

from __future__ import annotations

import re
import unicodedata

DEFAULT_NAME = "fichier"
MAX_NAME_LENGTH = 200  # marge pour « (9999) » et la longueur du chemin complet
_MAX_EXTENSION = 16

_FORBIDDEN = frozenset('<>:"/\\|?*')
_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
    | {"COM¹", "COM²", "COM³", "LPT¹", "LPT²", "LPT³", "CONIN$", "CONOUT$"}
)


def _split_extension(name: str) -> tuple[str, str]:
    stem, dot, ext = name.rpartition(".")
    if not dot or not stem or len(ext) > _MAX_EXTENSION:
        return name, ""
    return stem, f".{ext}"


def _truncate(name: str, max_length: int) -> str:
    if len(name) <= max_length:
        return name
    stem, ext = _split_extension(name)
    return stem[: max_length - len(ext)].rstrip(". ") + ext


def sanitize_filename(raw: str, max_length: int = MAX_NAME_LENGTH) -> str:
    name = unicodedata.normalize("NFC", raw)
    name = re.split(r"[\\/]", name)[-1]
    name = "".join(ch for ch in name if ch.isprintable() and ch not in _FORBIDDEN)
    name = name.strip().rstrip(". ")
    if not name or name in {".", ".."}:
        return DEFAULT_NAME

    base = name.split(".", 1)[0].rstrip(" ").upper()
    if base in _RESERVED:
        name = f"_{name}"

    name = _truncate(name, max_length)
    return name or DEFAULT_NAME


def candidate_name(safe_name: str, attempt: int, max_length: int = MAX_NAME_LENGTH) -> str:
    """``nom.ext``, puis ``nom (1).ext``, ``nom (2).ext``… (FR-028)."""
    if attempt == 0:
        return safe_name
    stem, ext = _split_extension(safe_name)
    suffix = f" ({attempt})"
    stem = stem[: max(1, max_length - len(ext) - len(suffix))]
    return f"{stem}{suffix}{ext}"
