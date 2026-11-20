"""Vrai navigateur (Chrome ou Edge sans interface) contre le vrai serveur (phase 10).

Parcours complet de la page mobile, piloté par le protocole DevTools :
lien du QR Code -> appairage -> approbation sur le PC -> envoi d'un fichier par blocs
(hash-wasm, donc WebAssembly sous la CSP) -> fichier proposé par le PC -> historique.
Échoue sur toute exception JavaScript ou violation de CSP.

Limites : Chromium de bureau en émulation mobile (ni Safari iOS ni vrai Wi-Fi), et
127.0.0.1 est un « secure context » contrairement à l'IP du PC sur le réseau.
Captures d'écran : définir LOCALDROP_SCREENSHOTS=<dossier>.
"""

import base64
import contextlib
import hashlib
import itertools
import json
import os
import shutil
import subprocess
import time
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from websockets.sync.client import ClientConnection, connect

from localdrop.bench import RunningServer, bench_settings, file_sha256, write_random_file
from localdrop.core.paths import default_web_dist_dir
from localdrop.domain.devices.models import DeviceStatus
from localdrop.domain.transfers.models import Direction, TransferStatus
from localdrop.infrastructure.network.interfaces import base_url, pairing_url

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(120)]

BROWSERS = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)
ANDROID_UA = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36"
)
CHUNK = 64 * 1024


def _browser() -> str | None:
    found = shutil.which("chrome") or shutil.which("msedge")
    return found or next((b for b in BROWSERS if Path(b).is_file()), None)


WEB_DIST = default_web_dist_dir()
pytestmark.append(
    pytest.mark.skipif(_browser() is None, reason="ni Chrome ni Edge installé"),
)
pytestmark.append(
    pytest.mark.skipif(
        WEB_DIST is None or not (WEB_DIST / "index.html").is_file(),
        reason="interface web non compilée (npm --prefix apps/web run build)",
    ),
)


class DevTools:
    """Client minimal du protocole DevTools (une page)."""

    def __init__(self, ws_url: str) -> None:
        self._stack = contextlib.ExitStack()
        self._ws: ClientConnection = self._stack.enter_context(
            connect(ws_url, max_size=None, open_timeout=10)
        )
        self._ids = itertools.count(1)
        self.events: list[dict[str, Any]] = []

    def call(self, method: str, **params: Any) -> dict[str, Any]:
        call_id = next(self._ids)
        self._ws.send(json.dumps({"id": call_id, "method": method, "params": params}))
        while True:
            message = json.loads(self._ws.recv(timeout=30))
            if message.get("id") == call_id:
                if "error" in message:
                    raise RuntimeError(f"{method} : {message['error']}")
                result: dict[str, Any] = message.get("result", {})
                return result
            if "method" in message:
                self.events.append(message)

    def evaluate(self, expression: str) -> Any:
        result = self.call("Runtime.evaluate", expression=expression, returnByValue=True)
        return result["result"].get("value")

    def wait_for(self, what: str, check: Callable[[], Any], timeout: float = 20) -> Any:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = check()
            if value:
                return value
            time.sleep(0.1)
        body = self.evaluate("document.body.innerText")
        raise AssertionError(f"délai dépassé : {what}\n--- page ---\n{body}\n{self.errors()}")

    def errors(self) -> list[str]:
        found = []
        for event in self.events:
            params = event.get("params", {})
            if event["method"] == "Runtime.exceptionThrown":
                found.append(json.dumps(params.get("exceptionDetails", {}))[:500])
            elif event["method"] == "Log.entryAdded" and params["entry"]["level"] == "error":
                entry = params["entry"]
                found.append(f"{entry.get('text', '')} {entry.get('url', '')}".strip())
            elif event["method"] == "Runtime.consoleAPICalled" and params["type"] == "error":
                found.append(json.dumps(params.get("args", []))[:500])
        return found

    def close(self) -> None:
        self._stack.close()


@pytest.fixture
def server(tmp_path: Path) -> Iterator[RunningServer]:
    settings = bench_settings(tmp_path / "pc", CHUNK).model_copy(update={"web_dist_dir": WEB_DIST})
    running = RunningServer(settings).start()
    yield running
    running.stop()


@pytest.fixture
def page(tmp_path: Path) -> Iterator[DevTools]:
    exe = _browser()
    assert exe is not None
    profile = tmp_path / "profil"
    process = subprocess.Popen(  # noqa: S603 - navigateur local, arguments fixes
        [
            exe,
            "--headless=new",
            "--remote-debugging-port=0",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-gpu",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        port_file = profile / "DevToolsActivePort"
        deadline = time.monotonic() + 20
        while not port_file.is_file() and time.monotonic() < deadline:
            time.sleep(0.1)
        port = port_file.read_text().splitlines()[0]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10) as r:
            targets = json.load(r)
        target = next(t for t in targets if t["type"] == "page")
        tools = DevTools(target["webSocketDebuggerUrl"])
        for domain in ("Runtime.enable", "Log.enable", "Page.enable", "DOM.enable"):
            tools.call(domain)
        tools.call(
            "Emulation.setDeviceMetricsOverride",
            width=390,
            height=844,
            deviceScaleFactor=2,
            mobile=True,
        )
        tools.call("Emulation.setUserAgentOverride", userAgent=ANDROID_UA)
        tools.call("Emulation.setTouchEmulationEnabled", enabled=True)
        yield tools
        tools.close()
    finally:
        process.terminate()
        process.wait(15)


def _screenshot(page: DevTools, name: str) -> None:
    target = os.environ.get("LOCALDROP_SCREENSHOTS")
    if not target:
        return
    Path(target).mkdir(parents=True, exist_ok=True)
    data = page.call("Page.captureScreenshot", format="png")["data"]
    (Path(target) / f"{name}.png").write_bytes(base64.b64decode(data))


def _text(page: DevTools) -> str:
    return str(page.evaluate("document.body.innerText"))


def _show(page: DevTools, screen: str) -> None:
    page.evaluate(f"location.hash = '#/{screen}'")
    time.sleep(0.3)  # rendu et défilement


def test_mobile_page_full_journey_in_a_real_browser(
    server: RunningServer, page: DevTools, tmp_path: Path
) -> None:
    services = server.services
    info = services.pairing.current_pairing()
    url = pairing_url(base_url("127.0.0.1", server.settings.port), info.session_id, info.secret)

    # 1. Scan du QR Code : la page s'ouvre et demande l'appairage.
    page.call("Page.navigate", url=url)
    pending = page.wait_for(
        "demande d'appairage",
        lambda: [d for d in services.pairing.list_devices() if d.status is DeviceStatus.PENDING],
    )
    assert pending[0].platform.value == "android"
    assert "k=" not in page.evaluate("location.href"), "le secret doit quitter l'URL"
    _screenshot(page, "1-attente-approbation")

    # 2. Approbation sur le PC.
    services.pairing.approve(pending[0].id)
    page.wait_for("écran connecté", lambda: "Connecté à" in _text(page))
    _screenshot(page, "2-accueil")

    # 3. Envoi d'un fichier de 5 blocs (hash-wasm sous CSP).
    source = write_random_file(tmp_path / "photo.jpg", CHUNK * 4 + 1000)
    _show(page, "envoyer")
    root = page.call("DOM.getDocument")["root"]["nodeId"]
    node = page.call("DOM.querySelector", nodeId=root, selector="input[type=file]")["nodeId"]
    page.call("DOM.setFileInputFiles", nodeId=node, files=[str(source)])

    def completed_uploads() -> list[Any]:
        return [
            t
            for t in services.transfers.list_all()
            if t.direction is Direction.UPLOAD and t.status is TransferStatus.COMPLETED
        ]

    page.wait_for("envoi terminé sur le PC", completed_uploads, timeout=40)
    published = server.settings.receive_dir / "photo.jpg"
    assert file_sha256(published) == hashlib.sha256(source.read_bytes()).hexdigest()
    page.wait_for("envoi affiché terminé", lambda: "Reçu sur le PC" in _text(page))
    _screenshot(page, "3-envoyer")

    # 4. Le PC propose un fichier : il apparaît sur l'écran Recevoir.
    offer = write_random_file(tmp_path / "rapport annuel.pdf", 2048)
    services.downloads.offer(offer, pending[0].id)
    _show(page, "recevoir")
    page.wait_for(
        "fichier proposé visible",
        lambda: "rapport annuel.pdf" in page.evaluate("document.body.innerText"),
    )
    _screenshot(page, "4-recevoir")

    # 5. Historique.
    _show(page, "historique")
    page.wait_for("historique", lambda: "photo.jpg" in page.evaluate("document.body.innerText"))
    _screenshot(page, "5-historique")

    assert page.errors() == []
