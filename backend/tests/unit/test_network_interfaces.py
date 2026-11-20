import socket
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

import pytest

from localdrop.infrastructure.network.interfaces import pairing_url, select_candidates

pytestmark = pytest.mark.unit


@dataclass
class Addr:
    family: int
    address: str


@dataclass
class Stat:
    isup: bool


def v4(ip: str) -> Addr:
    return Addr(socket.AF_INET, ip)


# Reproduit une vraie machine Windows : Wi-Fi + VirtualBox host-only + WSL + Tailscale.
WINDOWS_ADDRS = {
    "Ethernet 2": [v4("192.168.56.1")],
    "Connexion au réseau local* 1": [v4("169.254.227.12")],
    "Wi-Fi": [v4("192.168.1.14"), Addr(socket.AF_INET6, "fe80::1")],
    "vEthernet (WSL (Hyper-V firewall))": [v4("172.25.112.1")],
    "Tailscale": [v4("100.65.90.44")],
    "Loopback Pseudo-Interface 1": [v4("127.0.0.1")],
    "Ethernet débranché": [v4("10.0.0.5")],
}
WINDOWS_STATS = {name: Stat(True) for name in WINDOWS_ADDRS} | {"Ethernet débranché": Stat(False)}


def test_FR_002_selects_private_ipv4_and_ranks_wifi_first() -> None:
    candidates = select_candidates(WINDOWS_ADDRS, WINDOWS_STATS)
    assert [(c.ip, c.interface) for c in candidates] == [
        ("192.168.1.14", "Wi-Fi"),
        ("192.168.56.1", "Ethernet 2"),  # host-only VirtualBox : gardé, mais en dernier
    ]


def test_windows_mobile_hotspot_is_preferred() -> None:
    addrs = WINDOWS_ADDRS | {"Connexion au réseau local* 1": [v4("192.168.137.1")]}
    candidates = select_candidates(addrs, WINDOWS_STATS)
    assert candidates[0].ip == "192.168.137.1"


def test_exclusion_patterns_are_configurable() -> None:
    candidates = select_candidates(WINDOWS_ADDRS, WINDOWS_STATS, excluded_patterns=("wi-fi",))
    ips = {c.ip for c in candidates}
    assert "192.168.1.14" not in ips
    assert "172.25.112.1" in ips  # vEthernet n'est plus exclu


def test_no_interface_means_no_candidate() -> None:
    assert select_candidates({}, {}) == []


def test_FR_004_pairing_secret_travels_in_fragment_only() -> None:
    url = pairing_url("http://192.168.1.14:8765", "sess", "s3cr-et_")
    parts = urlsplit(url)
    assert parts.query == ""  # rien n'est envoyé au serveur
    assert parts.fragment.startswith("/join?")
    assert parse_qs(parts.fragment.split("?", 1)[1]) == {"s": ["sess"], "k": ["s3cr-et_"]}
