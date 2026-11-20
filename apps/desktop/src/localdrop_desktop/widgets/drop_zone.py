"""Zone de dépôt de fichiers (§14.2 Dashboard) : glisser-déposer ou bouton."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtWidgets import QFileDialog, QFrame, QLabel, QPushButton, QVBoxLayout, QWidget


class DropZone(QFrame):
    files_dropped = Signal(list)  # list[Path]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("drop")
        self.setAcceptDrops(True)
        self.setMinimumHeight(120)
        layout = QVBoxLayout(self)
        self.label = QLabel("Glissez des fichiers ici pour les envoyer au téléphone")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)
        self.button = QPushButton("Choisir des fichiers…")
        self.button.clicked.connect(self._choose)
        layout.addWidget(self.label)
        layout.addWidget(self.button, alignment=Qt.AlignmentFlag.AlignCenter)

    def _choose(self) -> None:
        names, _ = QFileDialog.getOpenFileNames(self, "Fichiers à envoyer au téléphone")
        if names:
            self.files_dropped.emit([Path(n) for n in names])

    def _set_active(self, active: bool) -> None:
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 - API Qt
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_active(True)

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:  # noqa: N802 - API Qt
        self._set_active(False)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 - API Qt
        self._set_active(False)
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            event.acceptProposedAction()
            self.files_dropped.emit(paths)
