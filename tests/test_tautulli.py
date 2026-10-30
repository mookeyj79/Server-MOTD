"""Tautulli module through the CLI seam, against a fake server."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from tests.conftest import Run
from tests.fakeserver import FakeServer, closed_port_url

RunCli = Callable[..., Run]
WriteConfig = Callable[[str], Path]
MakeServer = Callable[..., FakeServer]

HEAD = 'title = "host"\n'
KEY = "k" * 32


def tautulli(
    make: MakeServer, activity: str, status: str = "server_status_up.json"
) -> FakeServer:
    srv = make(auth=("X-Api-Key", KEY))
    srv.add("/api/v2", fixture=f"tautulli/{activity}", query={"cmd": "get_activity"})
    srv.add("/api/v2", fixture=f"tautulli/{status}", query={"cmd": "server_status"})
    return srv


def cfg_for(url: str, extra: str = "") -> str:
    return f'[[modules]]\nkind = "tautulli"\nurl = "{url}"\napi_key = "{KEY}"\n{extra}'


def render(
    run_cli: RunCli, write_config: WriteConfig, url: str, color: str = "never"
) -> str:
    cfg = write_config(HEAD + cfg_for(url))
    return run_cli("--config", str(cfg), "--width", "200", "--color", color).out


def test_active_streams_and_bandwidth(
    run_cli: RunCli, write_config: WriteConfig, fake_server: MakeServer
) -> None:
    srv = tautulli(fake_server, "activity_streams.json")
    out = render(run_cli, write_config, srv.url)
    assert "Tautulli" in out
    assert "3 (1 direct play, 1 direct stream, 1 transcode)" in out
    assert "31.5 Mbps" in out  # total_bandwidth is kbps
    # One get_activity call, one server_status call, header auth.
    cmds = sorted(q.query["cmd"] for q in srv.requests)
    assert cmds == ["get_activity", "server_status"]
    assert all(q.headers["x-api-key"] == KEY for q in srv.requests)


def test_no_streams(
    run_cli: RunCli, write_config: WriteConfig, fake_server: MakeServer
) -> None:
    srv = tautulli(fake_server, "activity_none.json")
    out = render(run_cli, write_config, srv.url)
    assert "UNAVAILABLE" not in out
    streams = next(ln for ln in out.splitlines() if "Streams" in ln)
    assert streams.rstrip(" │|").endswith("0")
    assert "0 kbps" in out


def test_plex_down_is_crit(
    run_cli: RunCli, write_config: WriteConfig, fake_server: MakeServer
) -> None:
    # Tautulli answers get_activity with {} when it cannot reach Plex.
    srv = tautulli(fake_server, "activity_empty.json", "server_status_down.json")
    out = render(run_cli, write_config, srv.url, color="always")
    assert "UNAVAILABLE" not in out
    plex = next(ln for ln in out.splitlines() if "Plex" in ln)
    assert "down" in plex
    assert "\x1b[31m" in plex


def test_empty_reply_with_plex_up_is_an_error(
    run_cli: RunCli, write_config: WriteConfig, fake_server: MakeServer
) -> None:
    srv = tautulli(fake_server, "activity_empty.json")
    out = render(run_cli, write_config, srv.url)
    assert "UNAVAILABLE" in out
    assert "Streams" not in out


def test_api_error_envelope_is_unavailable(
    run_cli: RunCli, write_config: WriteConfig, fake_server: MakeServer
) -> None:
    srv = fake_server(auth=("X-Api-Key", KEY))
    srv.add(
        "/api/v2",
        json={"response": {"result": "error", "message": "Invalid apikey", "data": {}}},
        status=401,
        query={"cmd": "get_activity"},
    )
    out = render(run_cli, write_config, srv.url)
    assert "UNAVAILABLE" in out


def test_unreachable_is_unavailable(run_cli: RunCli, write_config: WriteConfig) -> None:
    out = render(run_cli, write_config, closed_port_url())
    assert "UNAVAILABLE" in out


def test_missing_api_key_is_invalid_config(
    run_cli: RunCli, write_config: WriteConfig
) -> None:
    cfg = write_config(HEAD + '[[modules]]\nkind = "tautulli"\nurl = "http://x"\n')
    out = run_cli("--config", str(cfg), "--width", "200", "--color", "never").out
    assert "invalid config" in out
    assert "api_key" in out
