"""Autotest de l'application (``LocalDrop.exe --self-test``), exécuté ici en mode source."""

import json
from pathlib import Path

import pytest

from localdrop_desktop import selftest
from localdrop_desktop.selftest import default_report_path, report_path_from_argv

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["LocalDrop.exe", "--self-test"], None),
        (["LocalDrop.exe", "--self-test", "C:/r.json"], Path("C:/r.json")),
        (["LocalDrop.exe", "--self-test=C:/r.json"], Path("C:/r.json")),
        (["LocalDrop.exe", "--self-test", "--autre"], None),
    ],
)
def test_report_path_from_arguments(argv: list[str], expected: Path | None) -> None:
    assert report_path_from_argv(argv) == (expected or default_report_path())


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[3] / "apps" / "web" / "dist" / "index.html").is_file(),
    reason="interface web non compilée",
)
def test_self_test_passes_and_writes_a_report(tmp_path: Path) -> None:
    report = tmp_path / "rapport.json"
    assert selftest.main(["LocalDrop.exe", f"--self-test={report}"]) == 0
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["ok"] is True
    assert data["frozen"] is False
    assert [c["name"] for c in data["checks"]] == [
        "ressources embarquées",
        "serveur, base, page, WebSocket, transferts",
        "interface Qt",
    ]
