"""QR Code dessiné avec QPainter (sans PIL). Le contenu (secret) n'est jamais affiché."""

from __future__ import annotations

import qrcode
from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QSizePolicy, QWidget

QUIET_ZONE = 4  # modules blancs autour du code (norme QR)


def qr_matrix(data: str) -> list[list[bool]]:
    code = qrcode.QRCode(border=0, error_correction=qrcode.constants.ERROR_CORRECT_M)
    code.add_data(data)
    code.make(fit=True)
    return [list(row) for row in code.get_matrix()]


class QrWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._matrix: list[list[bool]] | None = None
        self.setMinimumSize(220, 220)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.setAccessibleName("QR Code d'appairage")

    def set_data(self, data: str | None) -> None:
        self._matrix = qr_matrix(data) if data else None
        self.update()

    @property
    def module_count(self) -> int:
        return len(self._matrix) if self._matrix else 0

    def sizeHint(self) -> QSize:  # noqa: N802 - API Qt
        return QSize(280, 280)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - API Qt
        painter = QPainter(self)
        try:
            side = min(self.width(), self.height())
            left = (self.width() - side) / 2
            top = (self.height() - side) / 2
            if self._matrix is None:
                painter.setPen(QColor("#9aa3b2"))
                painter.drawText(
                    QRectF(left, top, side, side),
                    Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                    "QR Code indisponible",
                )
                return
            painter.fillRect(QRectF(left, top, side, side), QColor("white"))
            count = len(self._matrix) + 2 * QUIET_ZONE
            module = side / count
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("black"))
            for y, row in enumerate(self._matrix):
                for x, dark in enumerate(row):
                    if dark:
                        painter.drawRect(
                            QRectF(
                                left + (x + QUIET_ZONE) * module,
                                top + (y + QUIET_ZONE) * module,
                                module + 0.5,  # évite les fines lignes blanches à l'écran
                                module + 0.5,
                            )
                        )
        finally:
            painter.end()
