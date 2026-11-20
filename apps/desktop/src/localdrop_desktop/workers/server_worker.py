"""Serveur LocalDrop embarqué dans un thread de travail (§8.6, FR-001).

Réutilise ``LocalServer`` (liaison des sockets, redémarrage sur changement réseau, aide).
Jamais dans le thread Qt : la boucle événementielle de l'interface reste libre.
"""

from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QObject, Signal

from localdrop.core.config import Settings
from localdrop.server import LocalServer, PortUnavailableError
from localdrop.services.container import AppServices

logger = logging.getLogger(__name__)

HELP_MARKER = "Aucun téléphone ne s'est encore connecté"


class ServerWorker(QObject):
    started = Signal()  # le serveur accepte des connexions (aussi après un redémarrage réseau)
    stopped = Signal()
    failed = Signal(str)
    help_available = Signal(str)  # aide de connexion (§3.3)

    def __init__(
        self, settings: Settings, services: AppServices, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._services = services
        self._server: LocalServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._server = LocalServer(self._settings, self._services, output=self._on_output)
        self._thread = threading.Thread(
            target=self._run, args=(self._server,), name="localdrop-server", daemon=False
        )
        self._thread.start()
        threading.Thread(target=self._watch, args=(self._server, self._thread), daemon=True).start()

    def stop(self, timeout: float = 10.0) -> bool:
        """Arrêt propre. Renvoie False si le thread n'a pas terminé dans le délai."""
        server, thread = self._server, self._thread
        if server is None or thread is None:
            return True
        server.stop()
        thread.join(timeout)
        if thread.is_alive():
            logger.error("Le serveur ne s'est pas arrêté dans le délai imparti")
            return False
        self._thread = None
        return True

    # ------------------------------------------------------------------ thread serveur
    def _run(self, server: LocalServer) -> None:
        try:
            server.run()
        except PortUnavailableError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            logger.exception("Arrêt inattendu du serveur")
            self.failed.emit(f"Erreur inattendue du serveur : {exc}")
        finally:
            self.stopped.emit()

    def _watch(self, server: LocalServer, thread: threading.Thread) -> None:
        """Signale chaque (re)démarrage effectif, y compris après un changement de réseau."""
        was_started = False
        while thread.is_alive():
            now_started = server.started.wait(0.1)
            if now_started and not was_started:
                self.started.emit()
            was_started = now_started

    def _on_output(self, text: str) -> None:
        if HELP_MARKER in text:
            self.help_available.emit(text.strip())
