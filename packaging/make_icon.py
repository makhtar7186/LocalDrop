"""Génère packaging/localdrop.ico (multi-tailles) avec Qt, sans dépendance supplémentaire.

Même dessin que l'icône de la page mobile (apps/web/index.html) : carré arrondi bleu,
flèche de dépôt blanche. Usage : ``.venv/Scripts/python packaging/make_icon.py``.
Le fichier généré est versionné : ce script ne sert qu'à le refaire.
"""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPainterPath, QPen

SIZES = (16, 24, 32, 48, 64, 128, 256)
ACCENT = QColor("#4f8cff")
TARGET = Path(__file__).resolve().parent / "localdrop.ico"


def render(size: int) -> bytes:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scale = size / 32
    painter.scale(scale, scale)

    background = QPainterPath()
    background.addRoundedRect(QRectF(0, 0, 32, 32), 8, 8)
    painter.fillPath(background, ACCENT)

    pen = QPen(QColor("white"), 3)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.drawLine(QPointF(16, 7), QPointF(16, 20))
    painter.drawPolyline([QPointF(10, 14), QPointF(16, 20), QPointF(22, 14)])
    painter.drawLine(QPointF(9, 25), QPointF(23, 25))
    painter.end()

    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data.data())


def ico(images: list[tuple[int, bytes]]) -> bytes:
    """Fichier ICO à entrées PNG (format accepté par Windows depuis Vista)."""
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, payload = b"", b""
    for size, png in images:
        dim = 0 if size >= 256 else size  # 0 signifie 256 dans le format ICO
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset)
        payload += png
        offset += len(png)
    return header + entries + payload


def main() -> int:
    app = QGuiApplication(sys.argv[:1])
    TARGET.write_bytes(ico([(size, render(size)) for size in SIZES]))
    print(f"{TARGET} ({TARGET.stat().st_size} octets)")
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
