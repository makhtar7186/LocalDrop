"""Tableau de bord (§14.2) : serveur, QR Code, adresses, appareils, dépôt de fichiers."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from localdrop.domain.devices.models import Device, DeviceStatus
from localdrop_desktop.controllers.app_controller import AppController, connected_devices
from localdrop_desktop.models import OBJECT_ROLE, DevicesModel
from localdrop_desktop.widgets.drop_zone import DropZone
from localdrop_desktop.widgets.qr import QrWidget

STATE_TEXT = {
    "starting": ("Démarrage du serveur…", "muted"),
    "running": ("● Serveur actif", "status-ok"),
    "stopped": ("● Serveur arrêté", "status-off"),
    "error": ("● Serveur en erreur", "status-off"),
}


def _card(*widgets: QWidget, layout: QVBoxLayout | None = None) -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    box = layout or QVBoxLayout()
    frame.setLayout(box)
    for widget in widgets:
        box.addWidget(widget)
    return frame


class DashboardPage(QWidget):
    def __init__(self, controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.devices_model = DevicesModel()

        # --- colonne gauche : serveur et QR Code
        self.state_label = QLabel()
        self.toggle_button = QPushButton()
        self.toggle_button.clicked.connect(self._toggle_server)
        self.error_label = QLabel()
        self.error_label.setObjectName("warning")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        self.qr = QrWidget()
        self.qr_caption = QLabel("Scannez ce QR Code avec l'appareil photo du téléphone.")
        self.qr_caption.setWordWrap(True)
        self.addresses_label = QLabel()
        self.addresses_label.setObjectName("muted")
        self.addresses_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.copy_button = QPushButton("Copier l'adresse")
        self.copy_button.clicked.connect(self._copy_address)
        warning = QLabel(
            "Utilisez un réseau de confiance et évitez les Wi-Fi publics : "
            "la connexion n'est pas chiffrée."
        )
        warning.setObjectName("warning")
        warning.setWordWrap(True)

        header = QHBoxLayout()
        header.addWidget(self.state_label, 1)
        header.addWidget(self.toggle_button)
        left = QVBoxLayout()
        left.addLayout(header)
        left.addWidget(self.error_label)
        left.addWidget(_card(self.qr, self.qr_caption, self.addresses_label, self.copy_button), 1)
        left.addWidget(warning)

        # --- colonne droite : aide, appareils, dépôt
        self.help_label = QLabel()
        self.help_label.setWordWrap(True)
        self.help_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.help_frame = _card(self.help_label)
        self.help_frame.setObjectName("help")
        self.help_frame.hide()

        devices_title = QLabel("Appareils")
        devices_title.setObjectName("title")
        self.devices_view = QListView()
        self.devices_view.setModel(self.devices_model)
        self.devices_view.selectionModel().selectionChanged.connect(self._update_buttons)
        self.devices_empty = QLabel("Aucun appareil. Scannez le QR Code avec le téléphone.")
        self.devices_empty.setObjectName("muted")
        self.approve_button = QPushButton("Autoriser")
        self.approve_button.setObjectName("primary")
        self.reject_button = QPushButton("Refuser")
        self.revoke_button = QPushButton("Déconnecter")
        self.close_session_button = QPushButton("Fermer la session")
        self.close_session_button.setToolTip(
            "Déconnecte tous les appareils et invalide le QR Code actuel."
        )
        self.approve_button.clicked.connect(lambda: self._act(self.controller.approve))
        self.reject_button.clicked.connect(lambda: self._act(self.controller.reject))
        self.revoke_button.clicked.connect(lambda: self._act(self.controller.revoke))
        self.close_session_button.clicked.connect(self.controller.close_session)
        buttons = QHBoxLayout()
        for button in (self.approve_button, self.reject_button, self.revoke_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(self.close_session_button)

        self.drop_zone = DropZone()
        self.drop_zone.files_dropped.connect(self._send_files)

        right = QVBoxLayout()
        right.addWidget(self.help_frame)
        right.addWidget(devices_title)
        right.addWidget(self.devices_empty)
        right.addWidget(self.devices_view, 1)
        right.addLayout(buttons)
        right.addWidget(self.drop_zone)

        root = QHBoxLayout(self)
        root.addLayout(left, 2)
        root.addLayout(right, 3)

        controller.server_state_changed.connect(self._on_state)
        controller.server_error.connect(self._on_server_error)
        controller.pairing_changed.connect(self.refresh_pairing)
        controller.devices_changed.connect(self._on_devices)
        controller.help_available.connect(self._show_help)
        self._on_state(controller.server_state)
        self._update_buttons()

    # ------------------------------------------------------------------ serveur
    def _toggle_server(self) -> None:
        if self.controller.server_state in ("running", "starting"):
            self.controller.stop_server()
        else:
            self.error_label.hide()
            self.controller.start_server()

    def _on_state(self, state: str) -> None:
        text, style = STATE_TEXT.get(state, (state, "muted"))
        self.state_label.setText(text)
        self.state_label.setObjectName(style)
        self.state_label.style().unpolish(self.state_label)
        self.state_label.style().polish(self.state_label)
        running = state in ("running", "starting")
        self.toggle_button.setText("Arrêter" if running else "Démarrer")
        if state != "running":
            self.help_frame.hide()
        self.refresh_pairing()

    def _on_server_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()

    def refresh_pairing(self) -> None:
        view = self.controller.pairing_view()
        self.qr.set_data(view.qr_url)
        if view.qr_url is None:
            if self.controller.server_state != "running":
                reason = "Démarrez le serveur pour afficher le QR Code."
            elif not self.controller.settings.lan_enabled:
                reason = (
                    "Connexions des téléphones désactivées : activez « Accepter les connexions "
                    "du réseau local » dans les Paramètres."
                )
            else:
                reason = (
                    "Aucune adresse réseau privée : connectez le PC au Wi-Fi ou activez son "
                    "point d'accès mobile (LocalDrop le détectera automatiquement)."
                )
            self.qr_caption.setText(reason)
        else:
            self.qr_caption.setText(
                "Scannez ce QR Code avec l'appareil photo du téléphone (usage unique)."
            )
        self._addresses = view.addresses
        self.addresses_label.setText(
            "\n".join(f"{url}  ({interface})" for url, interface in view.addresses)
            or "Aucune adresse disponible"
        )
        self.copy_button.setEnabled(bool(view.addresses))

    def _copy_address(self) -> None:
        if self._addresses:  # adresse de base uniquement : jamais le secret d'appairage
            QGuiApplication.clipboard().setText(self._addresses[0][0])

    def _show_help(self, text: str) -> None:
        self.help_label.setText(text.replace("--- ", "").replace(" ---", ""))
        self.help_frame.show()

    # ------------------------------------------------------------------ appareils
    def _on_devices(self, devices: list[Device]) -> None:
        self.devices_model.set_devices(devices)
        visible = self.devices_model.rowCount() > 0
        self.devices_empty.setVisible(not visible)
        if any(d.status is DeviceStatus.PENDING for d in devices):
            self.help_frame.hide()
        self._devices = devices
        self._update_buttons()

    def selected_device(self) -> Device | None:
        indexes = self.devices_view.selectionModel().selectedIndexes()
        if not indexes:
            return None
        device = indexes[0].data(OBJECT_ROLE)
        return device if isinstance(device, Device) else None

    def _act(self, action: object) -> None:
        device = self.selected_device()
        if device is not None and callable(action):
            action(device.id)

    def _update_buttons(self, *_: object) -> None:
        device = self.selected_device()
        status = device.status if device else None
        self.approve_button.setEnabled(status is DeviceStatus.PENDING)
        self.reject_button.setEnabled(status is DeviceStatus.PENDING)
        self.revoke_button.setEnabled(status in (DeviceStatus.CONNECTED, DeviceStatus.DISCONNECTED))

    # ------------------------------------------------------------------ envoi
    def _send_files(self, paths: list[Path]) -> None:
        device = self.selected_device()
        targets = connected_devices(getattr(self, "_devices", []))
        if device is None or device.status not in (
            DeviceStatus.CONNECTED,
            DeviceStatus.DISCONNECTED,
        ):
            if len(targets) != 1:
                self.controller.error.emit(
                    "Sélectionnez le téléphone destinataire dans la liste des appareils."
                    if targets
                    else "Aucun téléphone autorisé : scannez le QR Code puis autorisez-le."
                )
                return
            device = targets[0]
        self.controller.offer_files(paths, device.id)
