"""SABnzbd module through the CLI seam, against a fake server."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from tests.conftest import Run
from tests.fakeserver import FakeServer, closed_port_url

RunCli = Callable[..., Run]
WriteConfig = Callable[[str], Path]
MakeServer = Callable[..., FakeServer]

HEAD = 'title = "host"\n'
KEY = "s3cret"


def sab(make: MakeServer, queue: str = "queue_active.json") -> FakeServer:
    srv = make()
    srv.add("/api", fixture=f"sabnzbd/{queue}", query={"mode": "queue"})
    srv.add("/api", fixture="sabnzbd/server_stats.json", query={"mode": "server_stats"})
    return srv


def cfg_for(url: str, extra: str = "") -> str:
    return f'[[modules]]\nkind = "sabnzbd"\nurl = "{url}"\napi_key = "{KEY}"\n{extra}'


def render(run_cli: RunCli, write_config: WriteConfig, url: str) -> Run:
    cfg = write_config(HEAD + cfg_for(url))
    return run_cli("--config", str(cfg), "--width", "200", "--color", "never")


def test_active_shows_speed_in_bytes_and_queue(
    run_cli: RunCli, write_config: WriteConfig, fake_server: MakeServer
) -> None:
    srv = sab(fake_server)
    out = render(run_cli, write_config, srv.url).out
    assert "SABnzbd" in out
    assert "2.0M/s" in out  # 2048.5 KiB/s -> bytes, human-formatted
    assert "3 jobs" in out
    assert "4.0G left" in out  # 4096 MiB
    assert "5.0T" in out  # lifetime total from server_stats
    assert {q.query["mode"] for q in srv.requests} == {"queue", "server_stats"}
    assert all(q.query["apikey"] == KEY for q in srv.requests)
    assert all(q.query["output"] == "json" for q in srv.requests)


def test_idle(
    run_cli: RunCli, write_config: WriteConfig, fake_server: MakeServer
) -> None:
    srv = sab(fake_server, "queue_idle.json")
    out = render(run_cli, write_config, srv.url).out
    assert "0B/s" in out
    assert "empty" in out


def test_error_response_is_unavailable(
    run_cli: RunCli, write_config: WriteConfig, fake_server: MakeServer
) -> None:
    srv = fake_server()
    srv.add("/api", fixture="sabnzbd/error.json")
    out = render(run_cli, write_config, srv.url).out
    assert "UNAVAILABLE" in out
    assert "Internal error" in out


def test_bad_api_key_is_unavailable(
    run_cli: RunCli, write_config: WriteConfig, fake_server: MakeServer
) -> None:
    srv = fake_server()
    srv.add("/api", json={}, status=403)
    out = render(run_cli, write_config, srv.url).out
    assert "UNAVAILABLE" in out
    assert "API key" in out


def test_unreachable_is_unavailable(run_cli: RunCli, write_config: WriteConfig) -> None:
    out = render(run_cli, write_config, closed_port_url()).out
    assert "UNAVAILABLE" in out
