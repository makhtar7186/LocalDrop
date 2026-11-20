"""Historique (§14.2 History, FR-034) : recherche, filtres, « Ouvrir le dossier »."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from localdrop.domain.transfers.models import Direction, Transfer
from localdrop.domain.transfers.query import TransferPage, TransferQuery
from localdrop_desktop.controllers.app_controller import AppController
from localdrop_desktop.models import OBJECT_ROLE, ProgressDelegate, TransfersModel

PAGE_SIZE = 200


class HistoryPage(QWidget):
    def __init__(self, controller: AppController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.model = TransfersModel()

        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher un fichier…")
        self.search.setClearButtonEnabled(True)
        self.direction = QComboBox()
        self.direction.addItem("Tous les sens", None)
        self.direction.addItem("Téléphone → PC", Direction.UPLOAD)
        self.direction.addItem("PC → téléphone", Direction.DOWNLOAD)
        self.total_label = QLabel()
        self.total_label.setObjectName("muted")

        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setItemDelegateForColumn(TransfersModel.PROGRESS_COLUMN, ProgressDelegate(self))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.selectionModel().selectionChanged.connect(self._update_buttons)
        self.table.doubleClicked.connect(lambda _: self._reveal())

        self.reveal_button = QPushButton("Ouvrir le dossier")
        self.reveal_button.setToolTip("Affiche le fichier dans l'Explorateur (sans l'ouvrir).")
        self.reveal_button.clicked.connect(self._reveal)

        filters = QHBoxLayout()
        filters.addWidget(self.search, 1)
        filters.addWidget(self.direction)
        bottom = QHBoxLayout()
        bottom.addWidget(self.total_label, 1)
        bottom.addWidget(self.reveal_button)
        layout = QVBoxLayout(self)
        layout.addLayout(filters)
        layout.addWidget(self.table, 1)
        layout.addLayout(bottom)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        self._debounce.timeout.connect(self.reload)
        self.search.textChanged.connect(lambda _: self._debounce.start())
        self.direction.currentIndexChanged.connect(lambda _: self.reload())
        controller.transfers_changed.connect(lambda _: self.reload())
        self._update_buttons()

    def reload(self) -> None:
        direction = self.direction.currentData()
        query = TransferQuery(
            direction=direction if isinstance(direction, Direction) else None,
            text=self.search.text().strip() or None,
            limit=PAGE_SIZE,
        )
        self.controller.search_history(query, self._on_page)

    def _on_page(self, page: TransferPage) -> None:
        self.model.set_transfers(page.items)
        shown = len(page.items)
        self.total_label.setText(
            f"{page.total} transfert(s)" if shown == page.total else f"{shown} sur {page.total}"
        )
        self._update_buttons()

    def selected(self) -> Transfer | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        transfer = rows[0].data(OBJECT_ROLE)
        return transfer if isinstance(transfer, Transfer) else None

    def _update_buttons(self, *_: object) -> None:
        transfer = self.selected()
        self.reveal_button.setEnabled(
            transfer is not None and bool(transfer.final_path or transfer.source_path)
        )

    def _reveal(self) -> None:
        transfer = self.selected()
        if transfer is not None:
            self.controller.reveal(transfer)
