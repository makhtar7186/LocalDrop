"""Pont bus d'événements backend -> signaux Qt.

Les événements sont publiés depuis n'importe quel thread (serveur, threads de travail).
Émettre un Signal depuis un thread quelconque est sûr : les connexions vers des objets
du thread GUI sont mises en file (QueuedConnection). Ne jamais toucher un widget ici.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Signal

from localdrop.services.events import Event, EventBus


class EventBridge(QObject):
    event_received = Signal(str, dict)

    def __init__(self, events: EventBus, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._unsubscribe: Callable[[], None] | None = events.subscribe(self._forward)

    def _forward(self, event: Event) -> None:
        data: dict[str, Any] = dict(event.data)
        self.event_received.emit(event.type, data)

    def close(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
