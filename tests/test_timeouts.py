"""Runner time limits through the CLI seam, against a deliberately slow server."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from server_motd import report, runner
from server_motd.failure import FailureKind
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


def test_sequential_requests_share_one_budget(
    write_config: WriteConfig, fake_server: MakeServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    # qBittorrent logs in, then fetches: two requests that each fit the module
    # limit alone but not together. The second gets only what is left.
    monkeypatch.setattr(runner, "MODULE_TIMEOUT", 0.6)
    srv = fake_server()
    srv.add("/api/v2/auth/login", text="Ok.", delay=0.4)
    srv.add("/api/v2/sync/maindata", fixture="qbittorrent/maindata_50.json", delay=0.4)
    cfg = write_config(f'[[modules]]\nkind = "qbittorrent"\nurl = "{srv.url}"\n')
    start = time.monotonic()
    (o,) = report.collect(cfg).outcomes
    assert time.monotonic() - start < 1.0
    assert o.failure is not None and o.failure.kind is FailureKind.TIMED_OUT


def test_overrun_leaves_no_thread_blocking_exit(
    write_config: WriteConfig, fake_server: MakeServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "MODULE_TIMEOUT", 0.3)
    srv = fake_server()
    srv.add("/api", json={"queue": {}, "total": 0}, delay=2.0)
    cfg = write_config(
        f'[[modules]]\nkind = "sabnzbd"\nurl = "{srv.url}"\napi_key = "k"\n'
    )
    report.collect(cfg)
    blocking = [
        t
        for t in threading.enumerate()
        if not t.daemon and t is not threading.main_thread()
    ]
    assert blocking == []
