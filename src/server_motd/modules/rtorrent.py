"""rTorrent module over raw SCGI (one `system.multicall`).

Options: `scgi` (required): `host:port` or `unix:/path/to/socket` (unix sockets
are unavailable on Windows). Shows Down/Up rates (bytes/s, shown as-is, never
converted to bits) and torrent counts by state.
"""

from __future__ import annotations

import socket
import sys
import xmlrpc.client
from typing import Any

from server_motd.config import ConfigError, ModuleSpec
from server_motd.deadline import Deadline
from server_motd.failure import ApiError, BadResponse, TimedOut, Unreachable
from server_motd.model import Result, Row
from server_motd.modules._common import human_bytes

_CALLS = [
    ("throttle.global_down.rate", []),
    ("throttle.global_up.rate", []),
    ("d.multicall2", ["", "main", "d.state=", "d.complete="]),
]


class ScgiTransport(xmlrpc.client.Transport):
    """xmlrpc.client transport speaking SCGI to a TCP address or unix socket.

    Every socket operation is bounded by the time left before `deadline`.
    """

    def __init__(self, address: tuple[str, int] | str, deadline: Deadline) -> None:
        super().__init__()
        self.address = address
        self.deadline = deadline

    def request(
        self, host: Any, handler: Any, request_body: Any, verbose: bool = False
    ) -> tuple[Any, ...]:
        hdr = (
            b"CONTENT_LENGTH\0" + str(len(request_body)).encode() + b"\0SCGI\0001\0"
            b"REQUEST_METHOD\0POST\0CONTENT_TYPE\0text/xml\0"
        )
        msg = str(len(hdr)).encode() + b":" + hdr + b"," + request_body
        try:
            buf = self._exchange(msg)
        except TimeoutError as exc:
            raise TimedOut() from exc
        except OSError as exc:
            raise Unreachable(str(exc)) from exc
        _, sep, body = buf.partition(b"\r\n\r\n")
        if not sep:
            raise BadResponse("not an SCGI reply")
        parser, unmarshaller = self.getparser()
        parser.feed(body)
        parser.close()
        return unmarshaller.close()

    def _exchange(self, msg: bytes) -> bytes:
        if isinstance(self.address, tuple):
            sock = socket.create_connection(self.address, timeout=self.deadline.left())
        elif sys.platform == "win32":  # rejected at config time; keeps mypy happy
            raise ConfigError("unix sockets are not supported on Windows")
        else:
            sock = socket.socket(socket.AF_UNIX)
            sock.settimeout(self.deadline.left())
            sock.connect(self.address)
        with sock:
            sock.sendall(msg)
            buf = b""
            while True:
                sock.settimeout(self.deadline.left())
                chunk = sock.recv(65536)
                if not chunk:
                    return buf
                buf += chunk


class Rtorrent:
    def __init__(self, spec: ModuleSpec) -> None:
        target = spec.take("scgi", str)
        if not target:
            raise ConfigError("'scgi' is required (host:port or unix:/path)")
        self.address: tuple[str, int] | str
        if target.startswith("unix:"):
            if sys.platform == "win32":
                raise ConfigError("unix sockets are not supported on Windows")
            self.address = target[5:]
        else:
            host, _, port = target.rpartition(":")
            if not host or not port.isdigit():
                raise ConfigError("'scgi' must be host:port or unix:/path")
            self.address = (host, int(port))

    def fetch(self, deadline: Deadline) -> Result:
        proxy = xmlrpc.client.ServerProxy(
            "http://localhost/RPC2", transport=ScgiTransport(self.address, deadline)
        )
        calls = [{"methodName": n, "params": p} for n, p in _CALLS]
        try:
            res: Any = proxy.system.multicall(calls)
        except xmlrpc.client.Fault as exc:
            raise ApiError(exc.faultString) from exc
        except xmlrpc.client.Error as exc:
            raise BadResponse(str(exc)) from exc
        for item in res:
            if isinstance(item, dict):
                raise ApiError(f"rTorrent fault: {item.get('faultString')}")
        down, up, rows = (r[0] for r in res)
        downloading = sum(1 for s, c in rows if s == 1 and c == 0)
        seeding = sum(1 for s, c in rows if s == 1 and c == 1)
        stopped = sum(1 for s, _ in rows if s == 0)
        return Result(
            [
                Row("Down", f"{human_bytes(down)}/s"),
                Row("Up", f"{human_bytes(up)}/s"),
                Row(
                    "Torrents",
                    f"{downloading} downloading, {seeding} seeding, {stopped} stopped",
                ),
            ]
        )
