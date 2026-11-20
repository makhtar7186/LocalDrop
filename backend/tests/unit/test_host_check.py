"""En-tête Host : seules les IP littérales et localhost sont acceptées (anti DNS rebinding)."""

import pytest

from localdrop.api.middleware import is_allowed_host

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "host",
    [
        "192.168.1.14:8765",
        "192.168.137.1",
        "127.0.0.1:8765",
        "localhost:5173",
        "LOCALHOST",
        "[::1]:8765",
        "[fe80::1]",
    ],
)
def test_ip_literals_and_localhost_are_allowed(host: str) -> None:
    assert is_allowed_host(host)


@pytest.mark.parametrize(
    "host",
    [
        "",
        "site-malveillant.example",
        "site-malveillant.example:8765",
        "192.168.1.14.nip.io:8765",
        "localhost.example.com",
        "192.168.1.14:",
        "192.168.1.14:port",
        "192.168.1.14:99999",
        "[::1",
        "[::1]x",
        "[::1]:",
        "::1",
        "testserver",
    ],
)
def test_domain_names_and_malformed_hosts_are_refused(host: str) -> None:
    assert not is_allowed_host(host)
