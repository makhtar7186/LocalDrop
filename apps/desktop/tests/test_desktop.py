"""Application Windows (FR-001, FR-011 à FR-013, FR-020, FR-034, FR-040, §8.6)."""

import hashlib
import socket
import threading
import urllib.request
from pathlib import Path

import pytest
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

from localdrop.core.config import Settings, load_settings
from localdrop.domain.devices.models import DeviceStatus
from localdrop.domain.transfers.models import Direction, TransferStatus
from localdrop.services.container import AppServices
from localdrop.services.events import EventBus
from localdrop_desktop.bridge import EventBridge
from localdrop_desktop.controllers.app_controller import AppController
from localdrop_desktop.single_instance import SingleInstance
from localdrop_desktop.widgets.qr import QrWidget
from localdrop_desktop.windows.main_window import MainWindow

from .conftest import FolderSpy, join_phone

pytestmark = pytest.mark.integration


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def window(qtbot: QtBot, controller: AppController) -> MainWindow:
    win = MainWindow(controller, confirm_quit=lambda: True)
    qtbot.addWidget(win)
    win.show()
    return win


def start(qtbot: QtBot, controller: AppController) -> None:
    with qtbot.waitSignal(controller.worker.started, timeout=10_000):
        controller.start_server()
    qtbot.waitUntil(lambda: controller.server_state == "running", timeout=5_000)


# ----------------------------------------------------------------------------- briques
def test_qr_widget_draws_a_scannable_matrix(qtbot: QtBot) -> None:
    widget = QrWidget()
    qtbot.addWidget(widget)
    widget.resize(300, 300)
    widget.set_data("http://192.168.137.1:8765/#/join?s=abc&k=secret")
    assert widget.module_count >= 21  # version 1 minimum
    image: QImage = widget.grab().toImage()
    colors = {image.pixelColor(x, y).name() for x in range(0, 300, 7) for y in range(0, 300, 7)}
    assert {"#000000", "#ffffff"} <= colors
    widget.set_data(None)
    assert widget.module_count == 0


def test_bridge_relays_events_from_any_thread(qtbot: QtBot) -> None:
    bus = EventBus()
    bridge = EventBridge(bus)
    with qtbot.waitSignal(bridge.event_received, timeout=2_000) as blocker:
        threading.Thread(target=bus.publish, args=("transfer.progress", {"x": 1})).start()
    assert blocker.args == ["transfer.progress", {"x": 1}]
    bridge.close()


def test_single_instance_reactivates_the_existing_window(qtbot: QtBot, tmp_path: Path) -> None:
    first = SingleInstance(tmp_path)
    second = SingleInstance(tmp_path)
    try:
        assert first.acquire() is True
        with qtbot.waitSignal(first.activation_requested, timeout=3_000):
            assert second.acquire() is False
    finally:
        first.release()
        second.release()


# ----------------------------------------------------------------------------- serveur (FR-001)
def test_FR_001_start_and_stop_embedded_server(
    qtbot: QtBot, window: MainWindow, controller: AppController, settings: Settings
) -> None:
    start(qtbot, controller)
    url = f"http://127.0.0.1:{settings.port}/api/v1/health"
    # urllib plutôt que httpx : pas de contexte TLS à préparer pour une URL http (rapide).
    with urllib.request.urlopen(url, timeout=3) as response:
        assert response.status == 200
    assert window.dashboard.state_label.text() == "● Serveur actif"
    assert window.dashboard.qr.module_count > 0  # QR Code affiché une fois le serveur prêt
    assert "secret" not in window.dashboard.addresses_label.text()

    assert controller.stop_server() is True
    assert not controller.worker.running
    with socket.socket() as sock:  # le port est bien libéré
        sock.bind(("127.0.0.1", settings.port))
    assert window.dashboard.toggle_button.text() == "Démarrer"
    assert window.dashboard.qr.module_count == 0


def test_port_in_use_is_reported(
    qtbot: QtBot, window: MainWindow, controller: AppController, settings: Settings
) -> None:
    blocker = socket.socket()
    blocker.bind(("127.0.0.1", settings.port))
    try:
        with qtbot.waitSignal(controller.server_error, timeout=5_000) as error:
            controller.start_server()
        assert f"port {settings.port}" in error.args[0]
        qtbot.waitUntil(lambda: window.dashboard.error_label.isVisible())
    finally:
        blocker.close()


# ----------------------------------------------------------------------------- appareils
def test_FR_011_new_phone_triggers_approval_dialog(
    qtbot: QtBot, window: MainWindow, services: AppServices, controller: AppController
) -> None:
    start(qtbot, controller)
    before = window.dashboard.qr.module_count and window.dashboard.qr._matrix
    device = join_phone(services)

    qtbot.waitUntil(lambda: len(window.pending_approvals()) == 1, timeout=3_000)
    dialog = window.pending_approvals()[0]
    assert "Pixel 8" in dialog.findChildren(type(window.status_message))[0].text()
    assert dialog.refuse_button.isDefault()  # Entrée ne doit pas autoriser par mégarde
    # Le QR Code (à usage unique) a été renouvelé après le scan.
    qtbot.waitUntil(lambda: window.dashboard.qr._matrix != before, timeout=3_000)

    dialog.accept_button.click()
    qtbot.waitUntil(lambda: _status(services, device.id) is DeviceStatus.CONNECTED, timeout=3_000)
    qtbot.waitUntil(lambda: not window.pending_approvals(), timeout=3_000)
    qtbot.waitUntil(
        lambda: (
            "connecté"
            in window.dashboard.devices_model.data(window.dashboard.devices_model.index(0))
        ),
        timeout=3_000,
    )


def test_FR_011_refuse_and_FR_013_revoke(
    qtbot: QtBot, window: MainWindow, services: AppServices, controller: AppController
) -> None:
    intruder = join_phone(services, "Inconnu")
    qtbot.waitUntil(lambda: len(window.pending_approvals()) == 1, timeout=3_000)
    window.pending_approvals()[0].refuse_button.click()
    qtbot.waitUntil(lambda: _status(services, intruder.id) is DeviceStatus.REJECTED, timeout=3_000)

    phone = join_phone(services)
    qtbot.waitUntil(lambda: len(window.pending_approvals()) == 1, timeout=3_000)
    controller.approve(phone.id)  # décidé ailleurs (ex. devtools) : le dialogue se ferme
    qtbot.waitUntil(lambda: not window.pending_approvals(), timeout=3_000)

    dashboard = window.dashboard
    qtbot.waitUntil(lambda: dashboard.devices_model.rowCount() == 2, timeout=3_000)
    row = next(
        r
        for r in range(dashboard.devices_model.rowCount())
        if (d := dashboard.devices_model.device(r)) is not None and d.id == phone.id
    )
    dashboard.devices_view.setCurrentIndex(dashboard.devices_model.index(row))
    assert dashboard.revoke_button.isEnabled()
    dashboard.revoke_button.click()
    qtbot.waitUntil(lambda: _status(services, phone.id) is DeviceStatus.REVOKED, timeout=3_000)


def _status(services: AppServices, device_id: str) -> DeviceStatus | None:
    device = services.pairing._repo.get_device(device_id)
    return device.status if device else None


# ----------------------------------------------------------------------------- transferts
def test_FR_020_dropped_files_are_offered_to_the_phone(
    qtbot: QtBot, window: MainWindow, services: AppServices, tmp_path: Path
) -> None:
    phone = services.pairing.approve(join_phone(services).id)
    qtbot.waitUntil(lambda: window.dashboard.devices_model.rowCount() == 1, timeout=3_000)
    document = tmp_path / "Devis été.pdf"
    document.write_bytes(b"%PDF")
    folder = tmp_path / "dossier"
    folder.mkdir()

    window.dashboard.drop_zone.files_dropped.emit([document, folder])

    qtbot.waitUntil(lambda: len(services.transfers.list_all()) == 1, timeout=3_000)
    offer = services.transfers.list_all()[0]
    assert (offer.direction, offer.device_id, offer.safe_filename) == (
        Direction.DOWNLOAD,
        phone.id,
        "Devis été.pdf",
    )
    qtbot.waitUntil(lambda: window.transfers.model.rowCount() == 1, timeout=3_000)
    assert "dossiers ignorés" in window.status_message.text()


def test_drop_without_authorized_phone_explains_why(
    qtbot: QtBot, window: MainWindow, services: AppServices, tmp_path: Path
) -> None:
    document = tmp_path / "a.txt"
    document.write_text("a")
    window.dashboard.drop_zone.files_dropped.emit([document])
    qtbot.waitUntil(lambda: "Aucun téléphone autorisé" in window.status_message.text())
    assert services.transfers.list_all() == []


def test_FR_025_cancel_incoming_upload_from_pc(
    qtbot: QtBot, window: MainWindow, services: AppServices, monkeypatch: pytest.MonkeyPatch
) -> None:
    phone = services.pairing.approve(join_phone(services).id)
    upload = services.transfers.create_upload(phone, "film.mp4", 10)
    qtbot.waitUntil(lambda: window.transfers.model.rowCount() == 1, timeout=3_000)

    window.transfers.table.selectRow(0)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    window.transfers.cancel_button.click()

    qtbot.waitUntil(
        lambda: services.transfers.find(upload.id).status is TransferStatus.CANCELLED,  # type: ignore[union-attr]
        timeout=3_000,
    )
    qtbot.waitUntil(lambda: window.transfers.model.rowCount() == 0, timeout=3_000)
    assert not services.storage.temp_exists(upload.id)


def test_FR_034_history_search_and_reveal_without_opening(
    qtbot: QtBot, window: MainWindow, services: AppServices, folders: FolderSpy
) -> None:
    phone = services.pairing.approve(join_phone(services).id)
    for name, data in (("Photo été.jpg", b"jpg"), ("notes.txt", b"txt")):
        upload = services.transfers.create_upload(phone, name, len(data))
        services.transfers.put_chunk(phone, upload.id, 0, data, sha(data))
        services.transfers.complete(phone, upload.id, sha(data))

    history = window.history
    qtbot.waitUntil(lambda: history.model.rowCount() == 2, timeout=3_000)
    history.search.setText("ÉTÉ")
    qtbot.waitUntil(lambda: history.model.rowCount() == 1, timeout=3_000)
    history.table.selectRow(0)
    history.reveal_button.click()
    assert len(folders.revealed) == 1
    assert folders.revealed[0].name == "Photo été.jpg"  # dossier ouvert, fichier sélectionné


# ----------------------------------------------------------------------------- paramètres
def test_settings_are_saved_and_applied_at_next_start(
    qtbot: QtBot,
    window: MainWindow,
    settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = window.settings_page
    page.receive_dir.setText(str(tmp_path / "Mes réceptions"))
    page.port.setValue(9123)
    page.keep_history.setChecked(False)
    page.save()
    assert "Redémarrez" in page.status.text()

    reloaded = load_settings(data_dir=settings.data_dir)
    assert reloaded.port == 9123
    assert reloaded.receive_dir == tmp_path / "Mes réceptions"
    assert reloaded.history_retention_days is None
    monkeypatch.setenv("LOCALDROP_PORT", "9200")  # l'environnement reste prioritaire
    assert load_settings(data_dir=settings.data_dir).port == 9200


# ----------------------------------------------------------------------------- arrêt propre
def test_close_asks_confirmation_when_transfers_are_active(
    qtbot: QtBot, controller: AppController, services: AppServices, settings: Settings
) -> None:
    answers = iter([False, True])
    win = MainWindow(controller, confirm_quit=lambda: next(answers))
    qtbot.addWidget(win)
    win.show()
    start(qtbot, controller)
    settings.state_dir.mkdir(parents=True, exist_ok=True)
    settings.admin_token_file.write_text("jeton")
    phone = services.pairing.approve(join_phone(services).id)
    services.transfers.create_upload(phone, "en-cours.bin", 10)

    assert win.close() is False  # l'utilisateur renonce : tout continue
    assert controller.worker.running

    assert win.close() is True
    assert not controller.worker.running
    assert not settings.admin_token_file.exists()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", settings.port))


def test_enter_key_in_approval_dialog_refuses(
    qtbot: QtBot, window: MainWindow, services: AppServices
) -> None:
    """Un appui réflexe sur Entrée ne doit jamais autoriser un appareil inconnu."""
    from PySide6.QtCore import Qt

    intruder = join_phone(services, "Inconnu")
    qtbot.waitUntil(lambda: len(window.pending_approvals()) == 1, timeout=3_000)
    dialog = window.pending_approvals()[0]
    qtbot.waitExposed(dialog)
    qtbot.keyClick(dialog, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: _status(services, intruder.id) is DeviceStatus.REJECTED, timeout=3_000)


def test_device_name_cannot_inject_html_in_approval_dialog(
    qtbot: QtBot, window: MainWindow, services: AppServices
) -> None:
    """Audit phase 10 : le nom vient du téléphone, il ne doit pas maquiller le dialogue."""
    from PySide6.QtWidgets import QLabel

    join_phone(services, '<span style="font-size:1px">x</span>Mon PC (iOS, 127.0.0.1)')
    qtbot.waitUntil(lambda: len(window.pending_approvals()) == 1, timeout=3_000)
    label = window.pending_approvals()[0].findChild(QLabel)
    assert label is not None
    assert "&lt;span" in label.text()
    assert "<span" not in label.text()
