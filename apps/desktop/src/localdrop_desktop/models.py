"""Modèles Qt pour les appareils et les transferts (mis à jour par signaux)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtCore import (
    QAbstractListModel,
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionProgressBar,
    QStyleOptionViewItem,
)

from localdrop.domain.devices.models import Device, DeviceStatus
from localdrop.domain.transfers.models import Direction, Transfer, TransferStatus

Index = QModelIndex | QPersistentModelIndex
OBJECT_ROLE = Qt.ItemDataRole.UserRole + 1

DEVICE_STATUS = {
    DeviceStatus.PENDING: "en attente d'autorisation",
    DeviceStatus.CONNECTED: "connecté",
    DeviceStatus.DISCONNECTED: "hors ligne",
    DeviceStatus.REJECTED: "refusé",
    DeviceStatus.REVOKED: "révoqué",
}
PLATFORM = {"android": "Android", "ios": "iPhone/iPad", "windows": "Windows", "other": "Autre"}
TRANSFER_STATUS = {
    TransferStatus.CREATED: "Créé",
    TransferStatus.WAITING: "En attente",
    TransferStatus.TRANSFERRING: "En cours",
    TransferStatus.PAUSED: "En pause",
    TransferStatus.VERIFYING: "Vérification",
    TransferStatus.COMPLETED: "Terminé",
    TransferStatus.FAILED: "Échec",
    TransferStatus.CANCELLED: "Annulé",
}


def format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("o", "Ko", "Mo", "Go"):
        if value < 1024 or unit == "Go":
            text = f"{value:.0f}" if unit == "o" or value >= 100 else f"{value:.1f}"
            return f"{text.replace('.', ',')} {unit}"
        value /= 1024
    return f"{size} o"  # pragma: no cover


def format_date(value: datetime) -> str:
    return value.astimezone().strftime("%d/%m/%Y %H:%M")


def transfer_status_label(transfer: Transfer) -> str:
    if transfer.status is TransferStatus.CANCELLED and transfer.error_code == "EXPIRED":
        return "Annulé (expiré)"
    if transfer.direction is Direction.DOWNLOAD and transfer.status is TransferStatus.WAITING:
        return "Proposé au téléphone"
    if transfer.status is TransferStatus.FAILED and transfer.error_code:
        return f"Échec ({transfer.error_code})"
    return TRANSFER_STATUS.get(transfer.status, transfer.status.value)


class DevicesModel(QAbstractListModel):
    def __init__(self) -> None:
        super().__init__()
        self._devices: list[Device] = []

    def set_devices(self, devices: list[Device]) -> None:
        self.beginResetModel()
        self._devices = [d for d in devices if d.status is not DeviceStatus.REVOKED]
        self.endResetModel()

    def device(self, row: int) -> Device | None:
        return self._devices[row] if 0 <= row < len(self._devices) else None

    def rowCount(self, parent: Index = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self._devices)

    def data(self, index: Index, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        device = self.device(index.row())
        if device is None:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return (
                f"{device.display_name} — {PLATFORM.get(device.platform.value, 'Autre')} — "
                f"{DEVICE_STATUS[device.status]} ({device.client_ip})"
            )
        if role == Qt.ItemDataRole.ForegroundRole:
            colors = {
                DeviceStatus.PENDING: "#f5b84a",
                DeviceStatus.CONNECTED: "#3ccf8e",
                DeviceStatus.REJECTED: "#ff6b6b",
            }
            return QColor(colors.get(device.status, "#9aa3b2"))
        if role == OBJECT_ROLE:
            return device
        return None


class TransfersModel(QAbstractTableModel):
    COLUMNS = ("Fichier", "Sens", "Taille", "Progression", "Statut", "Date")
    PROGRESS_COLUMN = 3

    def __init__(self) -> None:
        super().__init__()
        self._transfers: list[Transfer] = []

    def set_transfers(self, transfers: list[Transfer]) -> None:
        self.beginResetModel()
        self._transfers = list(transfers)
        self.endResetModel()

    def transfer(self, row: int) -> Transfer | None:
        return self._transfers[row] if 0 <= row < len(self._transfers) else None

    def rowCount(self, parent: Index = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self._transfers)

    def columnCount(self, parent: Index = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self.COLUMNS)

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if orientation is Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section]
        return None

    def data(self, index: Index, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        transfer = self.transfer(index.row())
        if transfer is None:
            return None
        if role == OBJECT_ROLE:
            return transfer
        if role == Qt.ItemDataRole.ToolTipRole and index.column() == 0:
            return transfer.final_path or transfer.source_path or transfer.safe_filename
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        column = index.column()
        if column == 0:
            return transfer.safe_filename
        if column == 1:
            return "Téléphone → PC" if transfer.direction is Direction.UPLOAD else "PC → téléphone"
        if column == 2:
            return format_bytes(transfer.total_size)
        if column == self.PROGRESS_COLUMN:
            return progress_percent(transfer)
        if column == 4:
            return transfer_status_label(transfer)
        return format_date(transfer.created_at)


def progress_percent(transfer: Transfer) -> int:
    if transfer.status is TransferStatus.COMPLETED or transfer.total_size == 0:
        return 100
    return min(100, transfer.received_bytes * 100 // transfer.total_size)


class ProgressDelegate(QStyledItemDelegate):
    """Dessine la colonne Progression sous forme de barre."""

    def paint(self, painter: Any, option: QStyleOptionViewItem, index: Index) -> None:
        value = index.data(Qt.ItemDataRole.DisplayRole)
        if not isinstance(value, int):
            super().paint(painter, option, index)
            return
        bar = QStyleOptionProgressBar()
        bar.rect = option.rect.adjusted(4, 6, -4, -6)
        bar.minimum = 0
        bar.maximum = 100
        bar.progress = value
        bar.text = f"{value} %"
        bar.textVisible = True
        style = QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ProgressBar, bar, painter)
