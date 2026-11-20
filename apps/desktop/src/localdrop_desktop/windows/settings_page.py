"""Paramètres (§14.2 Settings, FR-030). Enregistrés dans settings.json, appliqués au
prochain démarrage (les variables d'environnement LOCALDROP_* restent prioritaires)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from localdrop.core.config import MIB
from localdrop_desktop.controllers.app_controller import AppController


class SettingsPage(QWidget):
    def __init__(self, controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        s = controller.settings

        self.receive_dir = QLineEdit(str(s.receive_dir))
        browse = QPushButton("Parcourir…")
        browse.clicked.connect(self._browse)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.receive_dir, 1)
        folder_row.addWidget(browse)

        self.port = QSpinBox()
        self.port.setRange(1024, 65535)
        self.port.setValue(s.port)
        self.chunk_mib = QSpinBox()
        self.chunk_mib.setRange(1, 64)
        self.chunk_mib.setSuffix(" Mio")
        self.chunk_mib.setValue(max(1, s.chunk_size // MIB))
        self.concurrent = QSpinBox()
        self.concurrent.setRange(1, 8)
        self.concurrent.setValue(s.max_concurrent_transfers)
        self.temp_hours = QSpinBox()
        self.temp_hours.setRange(1, 24 * 30)
        self.temp_hours.setSuffix(" h")
        self.temp_hours.setValue(s.temp_retention_hours)
        self.session_hours = QDoubleSpinBox()
        self.session_hours.setRange(0.5, 24 * 7)
        self.session_hours.setSuffix(" h")
        self.session_hours.setValue(s.session_ttl_hours)
        self.keep_history = QCheckBox("Limiter la durée de l'historique")
        self.history_days = QSpinBox()
        self.history_days.setRange(1, 3650)
        self.history_days.setSuffix(" jours")
        self.keep_history.setChecked(s.history_retention_days is not None)
        self.history_days.setValue(int(s.history_retention_days or 30))
        self.history_days.setEnabled(self.keep_history.isChecked())
        self.keep_history.toggled.connect(self.history_days.setEnabled)
        self.lan = QCheckBox("Accepter les connexions du réseau local (téléphones)")
        self.lan.setChecked(s.lan_enabled)

        form = QFormLayout()
        form.addRow("Dossier de réception", folder_row)
        form.addRow("Port", self.port)
        form.addRow("Taille des blocs", self.chunk_mib)
        form.addRow("Transferts simultanés", self.concurrent)
        form.addRow("Conservation des fichiers temporaires", self.temp_hours)
        form.addRow("Durée d'une session", self.session_hours)
        form.addRow(self.keep_history, self.history_days)
        form.addRow(self.lan)

        self.status = QLabel()
        self.status.setWordWrap(True)
        save = QPushButton("Enregistrer")
        save.setObjectName("primary")
        save.clicked.connect(self.save)
        note = QLabel(
            "Les modifications s'appliquent au prochain démarrage de LocalDrop. "
            "Les fichiers déjà reçus ne sont pas déplacés."
        )
        note.setObjectName("muted")
        note.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addWidget(self.status)
        layout.addWidget(save)
        layout.addStretch(1)

    def values(self) -> dict[str, Any]:
        return {
            "receive_dir": Path(self.receive_dir.text().strip()),
            "port": self.port.value(),
            "chunk_size": self.chunk_mib.value() * MIB,
            "max_concurrent_transfers": self.concurrent.value(),
            "temp_retention_hours": self.temp_hours.value(),
            "session_ttl_hours": self.session_hours.value(),
            "history_retention_days": (
                float(self.history_days.value()) if self.keep_history.isChecked() else None
            ),
            "lan_enabled": self.lan.isChecked(),
        }

    def save(self) -> None:
        values = self.values()
        if not str(values["receive_dir"]).strip() or str(values["receive_dir"]) == ".":
            self.status.setObjectName("warning")
            self.status.setText("Choisissez un dossier de réception.")
            return
        try:
            self.controller.save_settings(values)
        except (ValueError, OSError) as exc:
            self.status.setObjectName("warning")
            self.status.setText(f"Paramètres non enregistrés : {exc}")
            return
        self.status.setObjectName("status-ok")
        self.status.setText("Enregistré. Redémarrez LocalDrop pour appliquer les modifications.")

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Dossier de réception", self.receive_dir.text()
        )
        if folder:
            self.receive_dir.setText(folder)
