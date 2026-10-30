"""Fake HTTP service for CLI-seam tests: a stdlib server replaying fixtures.

Usage in a test (the `fake_server` fixture is registered in conftest.py)::

    def test_x(fake_server, run_cli, write_config):
        srv = fake_server(auth=("X-Api-Key", "secret"))   # header check optional
        srv.add("/api/v3/health", fixture="sonarr/health_ok.json")
        srv.add("/api/v3/boom", json={"a": 1}, status=500)
        cfg = write_config(f'... url = "{srv.url}" ...')
        ...
        srv.requests  # list[Request] (path, query dict, headers dict) seen so far

Rules: routes match on the URL path only (query is recorded, not matched);
unknown paths return 404; a wrong or missing `auth` header returns 401.
Fixtures live in tests/fixtures/<service>/<name>.json and are hand-written
from the OpenAPI schemas in docs/research (replace with recordings when a
live instance is available). Add one directory per service. `srv.url` is the
base URL (no trailing slash). `closed_port_url()` gives a refused-connection URL.
"""

from __future__ import annotations

import json
import socket
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@dataclass(frozen=True)
class Request:
    path: str
    query: dict[str, str]
    headers: dict[str, str]
    body: str = ""


class FakeServer:
    def __init__(self, auth: tuple[str, str] | None = None) -> None:
        self.auth = auth
        self.requests: list[Request] = []
        self._routes: dict[str, tuple[int, bytes, dict[str, str], str | None]] = {}
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                outer._handle(self)

            def do_POST(self) -> None:
                outer._handle(self)

            def log_message(self, format: str, *args: Any) -> None:
                pass

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._httpd.server_address[1]}"

    def add(
        self,
        path: str,
        *,
        fixture: str | None = None,
        json: Any = None,
        status: int = 200,
        text: str | None = None,
        headers: dict[str, str] | None = None,
        need_cookie: str | None = None,
    ) -> None:
        """Serve a fixture file (relative to tests/fixtures), inline JSON or text.

        `headers` are extra response headers (e.g. Set-Cookie); `need_cookie`
        ("NAME=value") makes the route answer 403 unless the Cookie header has it.
        GET and POST are both served; POST bodies are recorded in `Request.body`.
        """
        if fixture is not None:
            body = (FIXTURES / fixture).read_bytes()
        elif text is not None:
            body = text.encode("utf-8")
        else:
            body = _dumps(json)
        self._routes[path] = (status, body, headers or {}, need_cookie)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()

    def _handle(self, h: BaseHTTPRequestHandler) -> None:
        parts = urlsplit(h.path)
        headers = {k.lower(): v for k, v in h.headers.items()}
        length = int(headers.get("content-length", 0))
        posted = h.rfile.read(length).decode("utf-8") if length else ""
        self.requests.append(
            Request(parts.path, dict(parse_qsl(parts.query)), headers, posted)
        )
        extra: dict[str, str] = {}
        if self.auth and headers.get(self.auth[0].lower()) != self.auth[1]:
            status, body = 401, b'{"error": "Unauthorized"}'
        else:
            status, body, extra, need = self._routes.get(
                parts.path, (404, b'{"error": "not found"}', {}, None)
            )
            if need and need not in headers.get("cookie", "").split("; "):
                status, body, extra = 403, b"Forbidden", {}
        h.send_response(status)
        for key, value in extra.items():
            h.send_header(key, value)
        h.send_header("Content-Type", "application/json")
        h.send_header("Content-Length", str(len(body)))
        h.end_headers()
        h.wfile.write(body)


def _dumps(value: Any) -> bytes:
    return json.dumps(value).encode("utf-8")


def closed_port_url() -> str:
    """A URL on localhost where nothing is listening."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    return f"http://127.0.0.1:{port}"


@pytest.fixture
def fake_server() -> Iterator[Callable[..., FakeServer]]:
    """Factory: `fake_server(auth=(header, value))` -> started FakeServer."""
    started: list[FakeServer] = []

    def make(auth: tuple[str, str] | None = None) -> FakeServer:
        srv = FakeServer(auth)
        srv.start()
        started.append(srv)
        return srv

    yield make
    for srv in started:
        srv.stop()
