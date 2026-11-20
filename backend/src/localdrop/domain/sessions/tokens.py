"""Secrets et jetons (§12.2-1, §12.2-4). Seul le hash est conservé."""

from __future__ import annotations

import hashlib
import hmac
import secrets

SECRET_BYTES = 32


def generate_secret() -> str:
    """Secret aléatoire cryptographique, sûr dans une URL."""
    return secrets.token_urlsafe(SECRET_BYTES)


def generate_id() -> str:
    return secrets.token_hex(16)


def hash_secret(secret: str) -> str:
    # Entropie de 256 bits : un hash rapide suffit, un KDF lent n'apporte rien.
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def secret_matches(secret: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_secret(secret), expected_hash)
