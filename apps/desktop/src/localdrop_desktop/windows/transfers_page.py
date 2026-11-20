"""Transferts en cours (§14.2 Transfers) : progression, taille, état, annulation."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from localdrop.domain.transfers.models import Transfer
from localdrop_desktop.controllers.app_controller import AppController
from localdrop_desktop.models import OBJECT_ROLE, ProgressDelegate, TransfersModel


class TransfersPage(QWidget):
    def __init__(self, controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.model = TransfersModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setItemDelegateForColumn(TransfersModel.PROGRESS_COLUMN, ProgressDelegate(self))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.selectionModel().selectionChanged.connect(self._update_buttons)

        self.empty = QLabel("Aucun transfert en cours.")
        self.empty.setObjectName("muted")
        hint = QLabel(
            "Les envois du téléphone reprennent automatiquement après une coupure. "
            "Un fichier proposé au téléphone n'est « terminé » qu'après sa confirmation."
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        self.cancel_button = QPushButton("Annuler le transfert")
        self.cancel_button.clicked.connect(self._cancel)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.cancel_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.empty)
        layout.addWidget(self.table, 1)
        layout.addWidget(hint)
        layout.addLayout(buttons)

        controller.transfers_changed.connect(self._on_transfers)
        self._update_buttons()

    def _on_transfers(self, transfers: list[Transfer]) -> None:
        selected = self.selected()
        self.model.set_transfers(transfers)
        self.empty.setVisible(not transfers)
        if selected is not None:
            for row in range(self.model.rowCount()):
                current = self.model.transfer(row)
                if current is not None and current.id == selected.id:
                    self.table.selectRow(row)
        self._update_buttons()

    def selected(self) -> Transfer | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        transfer = rows[0].data(OBJECT_ROLE)
        return transfer if isinstance(transfer, Transfer) else None

    def _update_buttons(self, *_: object) -> None:
        self.cancel_button.setEnabled(self.selected() is not None)

    def _cancel(self) -> None:
        transfer = self.selected()
        if transfer is None:
            return
        answer = QMessageBox.question(
            self,
            "Annuler le transfert",
            f"Annuler « {transfer.safe_filename} » ? La partie déjà transférée sera supprimée.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.controller.cancel_transfer(transfer)
