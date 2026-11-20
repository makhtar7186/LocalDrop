"""Fenêtre principale (§14.2) et arrêt propre (§8.6)."""

from __future__ import annotations

import time
from html import escape
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QLabel, QMainWindow, QMessageBox, QStatusBar, QTabWidget, QWidget

from localdrop_desktop.controllers.app_controller import AppController
from localdrop_desktop.theme import use_dark_title_bar
from localdrop_desktop.windows.approval import ApprovalDialog
from localdrop_desktop.windows.dashboard import DashboardPage
from localdrop_desktop.windows.history_page import HistoryPage
from localdrop_desktop.windows.settings_page import SettingsPage
from localdrop_desktop.windows.transfers_page import TransfersPage

PAIRING_REFRESH_MS = 30_000  # le secret d'appairage expire : QR Code renouvelé
ERROR_DISPLAY_SECONDS = 6.0


class MainWindow(QMainWindow):
    def __init__(
        self,
        controller: AppController,
        parent: QWidget | None = None,
        confirm_quit: Any = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self._confirm_quit = confirm_quit or self._ask_quit
        self._approvals: dict[str, ApprovalDialog] = {}
        self._shut_down = False
        self._error_until = 0.0
        self.setWindowTitle("LocalDrop")
        use_dark_title_bar(self)
        self.resize(1000, 680)

        self.dashboard = DashboardPage(controller)
        self.transfers = TransfersPage(controller)
        self.history = HistoryPage(controller)
        self.settings_page = SettingsPage(controller)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.dashboard, "Tableau de bord")
        self.tabs.addTab(self.transfers, "Transferts")
        self.tabs.addTab(self.history, "Historique")
        self.tabs.addTab(self.settings_page, "Paramètres")
        self.setCentralWidget(self.tabs)

        self.status_message = QLabel()
        bar = QStatusBar()
        bar.addWidget(self.status_message, 1)
        self.setStatusBar(bar)

        controller.approval_requested.connect(self.request_approval)
        controller.approval_resolved.connect(self._close_approval)
        controller.notification.connect(lambda text: self._status(text, error=False))
        controller.error.connect(lambda text: self._status(text, error=True))

        self._pairing_timer = QTimer(self)
        self._pairing_timer.setInterval(PAIRING_REFRESH_MS)
        self._pairing_timer.timeout.connect(self.dashboard.refresh_pairing)
        self._pairing_timer.start()

        controller.refresh_devices()
        controller.refresh_transfers()
        self.history.reload()

    # ------------------------------------------------------------------ approbation
    def request_approval(self, device: dict[str, Any]) -> None:
        device_id = str(device.get("device_id", ""))
        if not device_id or device_id in self._approvals:
            return
        dialog = ApprovalDialog(device, self)
        dialog.decided.connect(self._on_decision)
        dialog.destroyed.connect(lambda *_: self._approvals.pop(device_id, None))
        self._approvals[device_id] = dialog
        dialog.show()
        dialog.raise_()
        self.bring_to_front()

    def _on_decision(self, device_id: str, allowed: bool) -> None:
        (self.controller.approve if allowed else self.controller.reject)(device_id)

    def _close_approval(self, device_id: str) -> None:
        dialog = self._approvals.pop(device_id, None)
        if dialog is not None:
            dialog.close()

    def pending_approvals(self) -> list[ApprovalDialog]:
        return list(self._approvals.values())

    # ------------------------------------------------------------------ divers
    def bring_to_front(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _status(self, text: str, *, error: bool) -> None:
        # Une erreur reste visible quelques secondes : une notification de succès
        # arrivant juste après ne doit pas l'effacer.
        now = time.monotonic()
        if not error and now < self._error_until:
            return
        if error:
            self._error_until = now + ERROR_DISPLAY_SECONDS
        color = "#ff6b6b" if error else "#3ccf8e"
        self.status_message.setTextFormat(Qt.TextFormat.RichText)
        self.status_message.setText(f'<span style="color:{color}">{escape(text)}</span>')

    # ------------------------------------------------------------------ fermeture
    def _ask_quit(self) -> bool:
        answer = QMessageBox.question(
            self,
            "Quitter LocalDrop",
            "Des transferts sont en cours. Quitter maintenant ?\n"
            "Ils pourront reprendre au prochain démarrage.",
        )
        return answer == QMessageBox.StandardButton.Yes

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - API Qt
        if self._shut_down:
            event.accept()
            return
        if self.controller.has_active_transfers() and not self._confirm_quit():
            event.ignore()
            return
        for dialog in list(self._approvals.values()):
            dialog.close()
        self._pairing_timer.stop()
        self.controller.shutdown()
        self._shut_down = True
        event.accept()
