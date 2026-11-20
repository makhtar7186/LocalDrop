"""Surveillance des adresses réseau (FR-003).

Les sockets sont liés au démarrage ; si une nouvelle adresse apparaît, elle n'est
pas joignable tant que le serveur n'a pas été relancé (le desktop s'en chargera).
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable

from localdrop.infrastructure.network.interfaces import AddressCandidate
from localdrop.services.events import EventBus

logger = logging.getLogger(__name__)

AddressProvider = Callable[[], list[AddressCandidate]]


class NetworkMonitor:
    def __init__(
        self,
        provider: AddressProvider,
        events: EventBus,
        bound_ips: frozenset[str] | None = None,
    ) -> None:
        self._provider = provider
        self._events = events
        self._lock = threading.Lock()
        self._candidates: list[AddressCandidate] = []
        # None = adresses liées inconnues (tests, uvicorn --factory) :
        # on considère tous les candidats comme joignables.
        self.bound_ips = bound_ips

    @property
    def candidates(self) -> list[AddressCandidate]:
        with self._lock:
            return list(self._candidates)

    def reachable_candidates(self) -> list[AddressCandidate]:
        """Candidats effectivement servis (liés au démarrage)."""
        candidates = self.candidates
        if self.bound_ips is None:
            return candidates
        return [c for c in candidates if c.ip in self.bound_ips]

    def refresh_quietly(self) -> None:
        """Relit les interfaces sans publier d'événement (juste avant de lier les sockets)."""
        try:
            fresh = self._provider()
        except Exception:
            logger.exception("Détection des interfaces réseau impossible")
            return
        with self._lock:
            self._candidates = fresh

    def refresh(self) -> bool:
        """Relit les interfaces. Renvoie True si l'ensemble des adresses a changé."""
        try:
            fresh = self._provider()
        except Exception:
            logger.exception("Détection des interfaces réseau impossible")
            return False
        with self._lock:
            changed = {c.ip for c in fresh} != {c.ip for c in self._candidates}
            self._candidates = fresh
        if changed:
            ips = [c.ip for c in fresh]
            restart_required = self.bound_ips is not None and not set(ips) <= self.bound_ips
            logger.info("Adresses réseau : %s", ", ".join(ips) or "aucune")
            if restart_required:
                logger.warning("Nouvelle adresse détectée : redémarrez le serveur pour l'exposer")
            self._events.publish(
                "server.network_changed",
                {"addresses": ips, "restart_required": restart_required},
            )
        return changed

    async def run(self, interval_seconds: float) -> None:
        while True:
            await asyncio.sleep(interval_seconds)
            await asyncio.to_thread(self.refresh)
