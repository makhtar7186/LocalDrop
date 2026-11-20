"""Démarrage de l'application Windows : instance unique, thème, serveur, fenêtre."""

from __future__ import annotations

import logging
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from localdrop import __version__
from localdrop.core.config import load_settings
from localdrop.core.logging import setup_logging
from localdrop.core.paths import app_icon_path
from localdrop.services.container import build_services
from localdrop_desktop import selftest
from localdrop_desktop.controllers.app_controller import AppController
from localdrop_desktop.selftest import SELF_TEST_FLAG
from localdrop_desktop.single_instance import SingleInstance
from localdrop_desktop.theme import apply_dark_theme
from localdrop_desktop.windows.main_window import MainWindow

logger = logging.getLogger(__name__)


APP_USER_MODEL_ID = "LocalDrop.Desktop"


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv)
    if SELF_TEST_FLAG in args or any(a.startswith(SELF_TEST_FLAG + "=") for a in args):
        return selftest.main(args)

    _set_app_user_model_id()
    app = QApplication(args)
    app.setApplicationName("LocalDrop")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(QIcon(str(app_icon_path())))
    apply_dark_theme(app)

    settings = load_settings()
    setup_logging(settings)

    instance = SingleInstance(settings.state_dir)
    if not instance.acquire():
        logger.info("LocalDrop est déjà ouvert : fenêtre existante réactivée")
        return 0

    try:
        services = build_services(settings)
    except Exception as exc:
        logger.exception("Démarrage impossible")
        QMessageBox.critical(None, "LocalDrop", f"Démarrage impossible : {exc}")
        instance.release()
        return 1

    settings.state_dir.mkdir(parents=True, exist_ok=True)
    settings.admin_token_file.write_text(services.admin_token, encoding="utf-8")

    controller = AppController(settings, services)
    window = MainWindow(controller)
    instance.activation_requested.connect(window.bring_to_front)
    window.show()
    controller.start_server()

    try:
        return app.exec()
    finally:
        if not window.isHidden():
            window.close()
        instance.release()


def _set_app_user_model_id() -> None:
    """Icône et regroupement corrects dans la barre des tâches Windows (sinon : python)."""
    if sys.platform != "win32":
        return
    import ctypes

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except (AttributeError, OSError):
        logger.debug("AppUserModelID non défini")
