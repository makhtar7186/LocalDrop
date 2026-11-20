"""Exécution des appels de service hors du thread GUI (accès SQLite, disque).

Le résultat (ou l'erreur) revient dans le thread GUI via un signal en file.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

OnDone = Callable[[Any], None]
OnError = Callable[[BaseException], None]


class TaskRunner(QObject):
    _finished = Signal(object, object)  # (callback, valeur)

    def __init__(self, parent: QObject | None = None, workers: int = 2) -> None:
        super().__init__(parent)
        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="localdrop-ui")
        self._finished.connect(self._dispatch)
        self._closed = False

    def run(
        self,
        function: Callable[..., Any],
        *args: Any,
        on_done: OnDone | None = None,
        on_error: OnError | None = None,
    ) -> Future[Any] | None:
        if self._closed:
            return None
        future = self._executor.submit(function, *args)

        def relay(done: Future[Any]) -> None:
            error = done.exception()
            if error is not None:
                if on_error is not None:
                    self._finished.emit(on_error, error)
                else:
                    logger.error("Tâche en erreur : %s", error, exc_info=error)
            elif on_done is not None:
                self._finished.emit(on_done, done.result())

        future.add_done_callback(relay)
        return future

    def _dispatch(self, callback: Callable[[Any], None], value: Any) -> None:
        callback(value)

    def shutdown(self) -> None:
        self._closed = True
        self._executor.shutdown(wait=True, cancel_futures=True)
