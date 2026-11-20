"""Détection des adresses IPv4 privées utilisables (FR-002, §8.1).

La sélection est une fonction pure (testable avec des fixtures) ; seule
``detect_candidates`` interroge le système via psutil.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import quote

DEFAULT_EXCLUDED_PATTERNS: tuple[str, ...] = (
    "vethernet",
    "hyper-v",
    "wsl",
    "virtualbox",
    "vmware",
    "docker",
    "loopback",
    "tailscale",
    "zerotier",
    "tap-",
    "vpn",
    "bluetooth",
)

# Réseaux de partage de connexion : le téléphone est l'AP ou le PC est l'AP.
_HOTSPOT_NETWORKS = (
    ipaddress.ip_network("192.168.137.0/24"),  # point d'accès mobile Windows
    ipaddress.ip_network("172.20.10.0/28"),  # hotspot iPhone
    ipaddress.ip_network("192.168.43.0/24"),  # hotspot Android (historique)
)
# Réseaux host-only d'hyperviseurs souvent nommés « Ethernet N » : dernier choix.
_VIRTUAL_NETWORKS = (
    ipaddress.ip_network("192.168.56.0/24"),  # VirtualBox host-only
    ipaddress.ip_network("192.168.99.0/24"),  # Docker Machine
)

_WIRELESS_HINTS = ("wi-fi", "wifi", "wlan", "wireless", "sans fil")
_ETHERNET_HINTS = ("ethernet", "lan", "réseau local", "local area")


class _AddrInfo(Protocol):
    @property
    def family(self) -> Any: ...

    @property
    def address(self) -> str: ...


class _IfStat(Protocol):
    @property
    def isup(self) -> bool: ...


@dataclass(frozen=True, order=True)
class AddressCandidate:
    priority: int  # plus petit = plus probable
    ip: str
    interface: str


def _priority(interface: str, ip: ipaddress.IPv4Address) -> int:
    if any(ip in net for net in _HOTSPOT_NETWORKS):
        return 0
    if any(ip in net for net in _VIRTUAL_NETWORKS):
        return 9
    name = interface.lower()
    if any(h in name for h in _WIRELESS_HINTS):
        return 1
    if any(h in name for h in _ETHERNET_HINTS):
        return 2
    return 5


def select_candidates(
    addrs: Mapping[str, Sequence[_AddrInfo]],
    stats: Mapping[str, _IfStat],
    excluded_patterns: Iterable[str] = DEFAULT_EXCLUDED_PATTERNS,
) -> list[AddressCandidate]:
    """IPv4 privées des interfaces actives, hors virtuelles, triées par probabilité."""
    patterns = tuple(p.lower() for p in excluded_patterns)
    candidates: set[AddressCandidate] = set()
    for interface, infos in addrs.items():
        stat = stats.get(interface)
        if stat is None or not stat.isup:
            continue
        if any(p in interface.lower() for p in patterns):
            continue
        for info in infos:
            if info.family != socket.AF_INET:
                continue
            try:
                ip = ipaddress.IPv4Address(info.address)
            except ValueError:
                continue
            if not ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_unspecified:
                continue
            candidates.add(AddressCandidate(_priority(interface, ip), str(ip), interface))
    return sorted(candidates)


def detect_candidates(
    excluded_patterns: Iterable[str] = DEFAULT_EXCLUDED_PATTERNS,
) -> list[AddressCandidate]:
    import psutil

    return select_candidates(psutil.net_if_addrs(), psutil.net_if_stats(), excluded_patterns)


def base_url(ip: str, port: int) -> str:
    return f"http://{ip}:{port}"


def pairing_url(base: str, session_id: str, secret: str) -> str:
    """URL du QR Code. Le secret est dans le fragment : jamais envoyé au serveur (ADR-006)."""
    return f"{base}/#/join?s={quote(session_id, safe='')}&k={quote(secret, safe='')}"
