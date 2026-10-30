"""System module: IP addresses per interface (loopback and link-local skipped)."""

from __future__ import annotations

import ipaddress
import socket

import psutil

from server_motd.config import ModuleSpec
from server_motd.model import Result, Row


class Ips:
    def __init__(self, spec: ModuleSpec) -> None:
        self.title = spec.name or "IPs"
        spec.done()

    def fetch(self) -> Result:
        rows = []
        for iface, addrs in sorted(psutil.net_if_addrs().items()):
            for addr in addrs:
                if addr.family not in (socket.AF_INET, socket.AF_INET6):
                    continue
                ip = ipaddress.ip_address(addr.address.split("%")[0])
                if ip.is_loopback or ip.is_link_local:
                    continue
                rows.append(Row(iface, str(ip)))
        if not rows:
            raise RuntimeError("no non-loopback addresses found")
        return Result(self.title, rows)
