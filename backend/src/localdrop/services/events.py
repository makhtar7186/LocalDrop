"""Bus d'événements en processus.

Source des événements temps réel : le hub WebSocket (phase 5) et le desktop
(phase 8) s'y abonnent. Publier uniquement après que l'état a été enregistré.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from localdrop.domain.sessions.tokens import generate_id

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Event:
    type: str
    data: dict[str, Any]
    id: str = field(default_factory=generate_id)
    ts: datetime = field(default_factory=lambda: datetime.now(UTC))


Subscriber = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: list[Subscriber] = []

    def subscribe(self, subscriber: Subscriber) -> Callable[[], None]:
        with self._lock:
            self._subscribers.append(subscriber)

        def unsubscribe() -> None:
            with self._lock:
                if subscriber in self._subscribers:
                    self._subscribers.remove(subscriber)

        return unsubscribe

    def publish(self, event_type: str, data: dict[str, Any]) -> Event:
        event = Event(type=event_type, data=data)
        with self._lock:
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            try:
                subscriber(event)
            except Exception:
                logger.exception("Abonné en erreur pour l'événement %s", event_type)
        return event
