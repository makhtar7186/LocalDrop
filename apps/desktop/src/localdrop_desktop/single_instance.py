"""Instance unique : une seconde instance réactive la fenêtre existante puis se ferme."""

from __future__ import annotations

import getpass
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


def _server_name() -> str:
    safe_user = "".join(ch for ch in getpass.getuser() if ch.isalnum()) or "utilisateur"
    return f"LocalDrop-{safe_user}"


class SingleInstance(QObject):
    activation_requested = Signal()

    def __init__(self, state_dir: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        state_dir.mkdir(parents=True, exist_ok=True)
        self._lock = QLockFile(str(state_dir / "desktop.lock"))
        self._lock.setStaleLockTime(0)
        self._server: QLocalServer | None = None
        self.name = _server_name()

    def acquire(self) -> bool:
        """True si cette instance est la seule ; sinon l'existante est réactivée."""
        if not self._lock.tryLock(100):
            self._notify_existing()
            return False
        QLocalServer.removeServer(self.name)
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_connection)
        self._server.listen(self.name)
        return True

    def release(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None
        if self._lock.isLocked():
            self._lock.unlock()

    def _notify_existing(self) -> None:
        socket = QLocalSocket()
        socket.connectToServer(self.name)
        if socket.waitForConnected(500):
            socket.write(b"show")
            socket.waitForBytesWritten(500)
            socket.disconnectFromServer()

    def _on_connection(self) -> None:
        if self._server is None:
            return
        connection = self._server.nextPendingConnection()
        if connection is not None:
            connection.disconnected.connect(connection.deleteLater)
            connection.close()
        self.activation_requested.emit()
