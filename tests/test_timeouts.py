"""Runner time limits through the CLI seam, against a deliberately slow server."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import pytest

from server_motd import runner
from server_motd.modules import _http
from tests.conftest import Run
from tests.fakeserver import FakeServer

RunCli = Callable[..., Run]
WriteConfig = Callable[[str], Path]
MakeServer = Callable[..., FakeServer]


def slow_sabnzbd(
    make: MakeServer, config: WriteConfig, run_cli: RunCli
) -> tuple[Run, float]:
    srv = make()
    srv.add("/api", json={"queue": {}, "total": 0}, delay=3.0)
    cfg = config(
        'title = "host"\n[[modules]]\nkind = "sabnzbd"\n'
        f'url = "{srv.url}"\napi_key = "k"\n'
    )
    start = time.monotonic()
    r = run_cli("--config", str(cfg), "--width", "80", "--color", "never")
    return r, time.monotonic() - start


def test_module_over_its_limit_is_unavailable_promptly(
    run_cli: RunCli,
    write_config: WriteConfig,
    fake_server: MakeServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runner, "MODULE_TIMEOUT", 0.3)
    r, elapsed = slow_sabnzbd(fake_server, write_config, run_cli)
    assert "UNAVAILABLE: timed out" in r.out
    assert elapsed < 2.0


def test_total_limit_applies_when_module_limit_is_larger(
    run_cli: RunCli,
    write_config: WriteConfig,
    fake_server: MakeServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runner, "MODULE_TIMEOUT", 10.0)
    monkeypatch.setattr(runner, "TOTAL_TIMEOUT", 0.3)
    r, elapsed = slow_sabnzbd(fake_server, write_config, run_cli)
    assert "UNAVAILABLE: timed out" in r.out
    assert elapsed < 2.0


def test_request_timeout_fits_inside_module_timeout() -> None:
    assert _http.REQUEST_TIMEOUT <= runner.MODULE_TIMEOUT
