"""PC -> téléphone par l'API (§6.3, §16.2 : téléchargement d'un fichier)."""

import os
from pathlib import Path
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from localdrop.services.container import AppServices

pytestmark = pytest.mark.integration


@pytest.fixture
def phone(client: TestClient, services: AppServices) -> TestClient:
    info = services.pairing.current_pairing()
    joined = client.post(
        "/api/v1/sessions/join",
        json={"session_id": info.session_id, "secret": info.secret, "display_name": "Pixel"},
    ).json()
    services.pairing.approve(joined["device_id"])
    client.headers["Authorization"] = f"Bearer {joined['device_token']}"
    client.device_id = joined["device_id"]  # type: ignore[attr-defined]
    return client


@pytest.fixture
def source(tmp_path: Path) -> Path:
    path = tmp_path / "Photo d'été.jpg"
    path.write_bytes(os.urandom(5000))
    return path


def _offer(admin: TestClient, phone: TestClient, path: Path) -> dict[str, object]:
    response = admin.post(
        "/api/v1/admin/transfers/outgoing",
        json={"path": str(path), "device_id": phone.device_id},  # type: ignore[attr-defined]
    )
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def _ticket_url(phone: TestClient, transfer_id: object) -> str:
    response = phone.post(f"/api/v1/transfers/{transfer_id}/download-ticket")
    assert response.status_code == 200, response.text
    return str(response.json()["url"])


def test_FR_020_FR_029_full_download_then_confirmation(
    phone: TestClient, admin: TestClient, source: Path
) -> None:
    offered = _offer(admin, phone, source)
    listed = phone.get("/api/v1/transfers").json()
    assert [(t["id"], t["direction"], t["status"]) for t in listed] == [
        (offered["id"], "download", "waiting")
    ]

    url = _ticket_url(phone, offered["id"])
    # Lien sans en-tête Authorization, comme un <a href> du navigateur.
    response = phone.get(url, headers={"Authorization": ""})
    assert response.status_code == 200
    assert response.content == source.read_bytes()
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-security-policy"] == "sandbox"
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert "Photo d'été.jpg" in unquote(disposition)

    state = phone.get(f"/api/v1/transfers/{offered['id']}").json()
    assert state["status"] == "transferring"  # servi ≠ reçu (§6.3)
    assert state["fully_served"] is True

    confirmed = phone.post(f"/api/v1/transfers/{offered['id']}/confirm")
    assert confirmed.json()["status"] == "completed"
    assert phone.get(url, headers={"Authorization": ""}).status_code == 401


def test_FR_026_range_requests_allow_resuming(
    phone: TestClient, admin: TestClient, source: Path
) -> None:
    offered = _offer(admin, phone, source)
    url = _ticket_url(phone, offered["id"])
    data = source.read_bytes()

    first = phone.get(url, headers={"Range": "bytes=0-999"})
    assert first.status_code == 206
    assert first.content == data[:1000]
    assert phone.get(f"/api/v1/transfers/{offered['id']}").json()["fully_served"] is False

    rest = phone.get(url, headers={"Range": "bytes=1000-"})
    assert rest.status_code == 206
    assert first.content + rest.content == data
    assert phone.get(f"/api/v1/transfers/{offered['id']}").json()["fully_served"] is True


def test_html_file_is_never_rendered_inline(
    phone: TestClient, admin: TestClient, tmp_path: Path
) -> None:
    page = tmp_path / "piege.html"
    page.write_text("<script>alert(localStorage.getItem('localdrop.device'))</script>")
    url = _ticket_url(phone, _offer(admin, phone, page)["id"])
    response = phone.get(url)
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-disposition"].startswith("attachment")
    assert response.headers["content-security-policy"] == "sandbox"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_download_requires_valid_ticket(phone: TestClient, admin: TestClient, source: Path) -> None:
    offered = _offer(admin, phone, source)
    bad = phone.get(f"/api/v1/transfers/{offered['id']}/download?ticket=faux")
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "TICKET_INVALID"
    missing = phone.get(f"/api/v1/transfers/{offered['id']}/download")
    assert missing.status_code == 422


def test_modified_source_returns_410(phone: TestClient, admin: TestClient, source: Path) -> None:
    offered = _offer(admin, phone, source)
    url = _ticket_url(phone, offered["id"])
    source.write_bytes(b"modifie")
    response = phone.get(url)
    assert response.status_code == 410
    assert response.json()["error"]["code"] == "SOURCE_CHANGED"


def test_outgoing_transfer_refuses_upload_operations(
    phone: TestClient, admin: TestClient, source: Path
) -> None:
    offered = _offer(admin, phone, source)
    tid = offered["id"]
    put = phone.put(
        f"/api/v1/transfers/{tid}/chunks/0", content=b"x", headers={"X-Chunk-SHA256": "0" * 64}
    )
    assert put.status_code == 404
    complete = phone.post(f"/api/v1/transfers/{tid}/complete", json={"sha256": "0" * 64})
    assert complete.status_code == 404


def test_FR_025_cancellation_from_both_sides(
    phone: TestClient, admin: TestClient, source: Path
) -> None:
    by_pc = _offer(admin, phone, source)
    assert admin.post(f"/api/v1/admin/transfers/{by_pc['id']}/cancel").json()["status"] == (
        "cancelled"
    )
    by_phone = _offer(admin, phone, source)
    assert phone.post(f"/api/v1/transfers/{by_phone['id']}/cancel").json()["status"] == (
        "cancelled"
    )
    assert phone.post(f"/api/v1/transfers/{by_phone['id']}/download-ticket").status_code == 409


def test_admin_offer_validates_inputs(phone: TestClient, admin: TestClient, tmp_path: Path) -> None:
    missing = admin.post(
        "/api/v1/admin/transfers/outgoing",
        json={"path": str(tmp_path / "absent"), "device_id": phone.device_id},  # type: ignore[attr-defined]
    )
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "INVALID_SOURCE"
    unknown_device = admin.post(
        "/api/v1/admin/transfers/outgoing", json={"path": str(tmp_path), "device_id": "inconnu"}
    )
    assert unknown_device.status_code == 401
    forbidden = phone.post(
        "/api/v1/admin/transfers/outgoing", json={"path": "C:/Windows/win.ini", "device_id": "x"}
    )
    assert forbidden.status_code == 403
