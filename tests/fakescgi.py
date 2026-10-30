"""Fake rTorrent SCGI server for CLI-seam tests.

Usage (the `fake_scgi` fixture is registered in conftest.py)::

    srv = fake_scgi("rtorrent/multicall.json")  # method name -> result
    srv.address      # "127.0.0.1:PORT"
    srv.unix_address # "unix:/path" (POSIX only; a second listener)
    srv.requests     # list of decoded calls, each a list of method names

It speaks real SCGI framing (netstring headers + body) and answers a
`system.multicall` with one-element lists per call, as rTorrent does.
Unknown methods come back as faults.
"""

from __future__ import annotations

import json
import socket
import socketserver
import sys
import threading
import xmlrpc.client
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def _read_request(sock: socket.socket) -> bytes:
    buf = b""
    while b":" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("closed")
        buf += chunk
    length, _, rest = buf.partition(b":")
    hdr_len = int(length)
    while len(rest) < hdr_len + 1:
        rest += sock.recv(4096)
    headers = rest[:hdr_len].split(b"\0")
    fields = dict(zip(headers[0::2], headers[1::2], strict=False))
    assert fields[b"SCGI"] == b"1"
    body = rest[hdr_len + 1 :]
    want = int(fields[b"CONTENT_LENGTH"])
    while len(body) < want:
        body += sock.recv(4096)
    return body


class FakeScgi:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        self.requests: list[list[str]] = []
        outer = self

        class Handler(socketserver.BaseRequestHandler):
            def handle(self) -> None:
                outer._serve(self.request)

        class Tcp(socketserver.ThreadingTCPServer):
            allow_reuse_address = True
            daemon_threads = True

        tcp = Tcp(("127.0.0.1", 0), Handler)
        self._servers: list[socketserver.BaseServer] = [tcp]
        self.address = f"127.0.0.1:{tcp.server_address[1]}"
        self.unix_address: str | None = None
        self._unix_path: Path | None = None
        if sys.platform != "win32":
            import tempfile

            class Unix(socketserver.ThreadingUnixStreamServer):
                daemon_threads = True

            self._unix_path = Path(tempfile.mkdtemp()) / "scgi.sock"
            self._servers.append(Unix(str(self._unix_path), Handler))
            self.unix_address = f"unix:{self._unix_path}"
        for server in self._servers:
            threading.Thread(target=server.serve_forever, daemon=True).start()

    def _serve(self, sock: socket.socket) -> None:
        body = _read_request(sock)
        params: Any
        params, method = xmlrpc.client.loads(body)
        assert method == "system.multicall"
        calls = params[0]
        self.requests.append([c["methodName"] for c in calls])
        results: list[Any] = []
        for call in calls:
            name = call["methodName"]
            if name in self.data:
                results.append([self.data[name]])
            else:
                results.append({"faultCode": -506, "faultString": "no such"})
        payload = xmlrpc.client.dumps((results,), methodresponse=True)
        head = b"Status: 200 OK\r\nContent-Type: text/xml\r\n\r\n"
        sock.sendall(head + payload.encode())

    def close(self) -> None:
        for server in self._servers:
            server.shutdown()
            server.server_close()
        if self._unix_path is not None:
            self._unix_path.unlink(missing_ok=True)


def closed_scgi_address() -> str:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return f"127.0.0.1:{s.getsockname()[1]}"


@pytest.fixture
def fake_scgi() -> Iterator[Callable[[str], FakeScgi]]:
    made: list[FakeScgi] = []

    def make(fixture: str) -> FakeScgi:
        data = json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))
        srv = FakeScgi(data)
        made.append(srv)
        return srv

    yield make
    for srv in made:
        srv.close()
