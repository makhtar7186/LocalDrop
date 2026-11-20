"""Thème sombre par défaut (§14.1), contrastes suffisants."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

SURFACE = "#0f1115"
RAISED = "#181b22"
BORDER = "#2a2f3a"
TEXT = "#e6e8ec"
MUTED = "#9aa3b2"
ACCENT = "#4f8cff"
SUCCESS = "#3ccf8e"
WARNING = "#f5b84a"
DANGER = "#ff6b6b"

STYLESHEET = f"""
QWidget {{ font-size: 10pt; }}
QLabel#title {{ font-size: 16pt; font-weight: 600; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#warning {{ color: {WARNING}; }}
QLabel#status-ok {{ color: {SUCCESS}; font-weight: 600; }}
QLabel#status-off {{ color: {DANGER}; font-weight: 600; }}
QFrame#card {{ background: {RAISED}; border: 1px solid {BORDER}; border-radius: 8px; }}
QFrame#help {{ background: {RAISED}; border: 1px solid {WARNING}; border-radius: 8px; }}
QFrame#drop {{ border: 2px dashed {BORDER}; border-radius: 8px; }}
QFrame#drop[active="true"] {{ border-color: {ACCENT}; }}
QPushButton {{ padding: 6px 14px; border-radius: 6px; border: 1px solid {BORDER}; }}
QPushButton#primary {{ background: {ACCENT}; color: white; border: none; }}
QPushButton:disabled {{ color: {MUTED}; }}
QPushButton#primary:disabled {{ background: {BORDER}; color: {MUTED}; }}
QPushButton:focus {{ border: 2px solid {ACCENT}; }}
QTabBar::tab {{ padding: 8px 16px; }}
"""


def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: SURFACE,
        QPalette.ColorRole.WindowText: TEXT,
        QPalette.ColorRole.Base: RAISED,
        QPalette.ColorRole.AlternateBase: SURFACE,
        QPalette.ColorRole.ToolTipBase: RAISED,
        QPalette.ColorRole.ToolTipText: TEXT,
        QPalette.ColorRole.Text: TEXT,
        QPalette.ColorRole.Button: RAISED,
        QPalette.ColorRole.ButtonText: TEXT,
        QPalette.ColorRole.Highlight: ACCENT,
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.PlaceholderText: MUTED,
        QPalette.ColorRole.Link: ACCENT,
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(MUTED))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(MUTED))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)
