"""Limitation des tentatives par fenêtre glissante (§12.2-5). Horloge injectée."""

from __future__ import annotations

from collections import deque


class SlidingWindowRateLimiter:
    def __init__(self, max_attempts: int, window_seconds: float, max_keys: int = 10_000) -> None:
        if max_attempts < 1 or window_seconds <= 0:
            raise ValueError("Paramètres de limitation invalides")
        self._max = max_attempts
        self._window = window_seconds
        self._max_keys = max_keys
        self._hits: dict[str, deque[float]] = {}

    def hit(self, key: str, now: float) -> bool:
        """Enregistre une tentative. Renvoie False si la limite est dépassée."""
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= self._window:
            hits.popleft()
        if len(hits) >= self._max:
            return False
        hits.append(now)
        if len(self._hits) > self._max_keys:
            self._prune(now)
        return True

    def _prune(self, now: float) -> None:
        stale = [k for k, h in self._hits.items() if not h or now - h[-1] >= self._window]
        for key in stale:
            del self._hits[key]
