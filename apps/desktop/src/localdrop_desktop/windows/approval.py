"""Demande d'approbation d'un appareil (FR-011) : dialogue non bloquant."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QWidget

from localdrop_desktop.models import PLATFORM


class ApprovalDialog(QDialog):
    decided = Signal(str, bool)  # (device_id, autorisé)

    def __init__(self, device: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.device_id = str(device.get("device_id", ""))
        self.setWindowTitle("Nouvel appareil")
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        name = str(device.get("display_name", "Appareil"))
        platform = PLATFORM.get(str(device.get("platform", "other")), "Autre")
        ip = str(device.get("client_ip", "?"))
        text = QLabel(
            f"<b>« {name} »</b> ({platform}, {ip}) demande à se connecter à ce PC.<br><br>"
            "Autorisez-le uniquement si c'est votre téléphone et qu'il vient de scanner "
            "le QR Code."
        )
        text.setWordWrap(True)
        text.setTextFormat(Qt.TextFormat.RichText)

        buttons = QDialogButtonBox()
        self.accept_button = buttons.addButton("Autoriser", QDialogButtonBox.ButtonRole.AcceptRole)
        self.refuse_button = buttons.addButton("Refuser", QDialogButtonBox.ButtonRole.RejectRole)
        self.accept_button.setObjectName("primary")
        # Entrée ne doit JAMAIS autoriser par mégarde : « Autoriser » ne peut pas devenir
        # le bouton par défaut (QDialogButtonBox le réattribue sinon à l'affichage).
        self.accept_button.setAutoDefault(False)
        self.refuse_button.setAutoDefault(True)
        self.refuse_button.setDefault(True)
        self.accept_button.clicked.connect(lambda: self._decide(True))
        self.refuse_button.clicked.connect(lambda: self._decide(False))

        layout = QVBoxLayout(self)
        layout.addWidget(text)
        layout.addWidget(buttons)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 - API Qt
        super().showEvent(event)
        self.accept_button.setDefault(False)
        self.refuse_button.setDefault(True)
        self.refuse_button.setFocus()

    def _decide(self, allowed: bool) -> None:
        self.decided.emit(self.device_id, allowed)
        self.close()
