"""Outcomes through the `report.collect` seam: titles, failure kinds and reasons.

Rendered output is covered through the CLI elsewhere; these tests pin what
each Instance resolved to, without reading a box.
"""

from __future__ import annotations

import socket
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from server_motd import report
from server_motd.failure import FailureKind
from server_motd.model import Status
from tests.fakescgi import closed_scgi_address
from tests.fakeserver import FakeServer, closed_port_url

WriteConfig = Callable[[str], Path]
MakeServer = Callable[..., FakeServer]
KEY = "k"


def only(write_config: WriteConfig, body: str, probe: bool = True) -> report.Outcome:
    rep = report.collect(write_config('title = "t"\n' + body), probe=probe)
    assert len(rep.outcomes) == 1
    return rep.outcomes[0]


def service(kind: str, url: str) -> str:
    return f'[[modules]]\nkind = "{kind}"\nurl = "{url}"\napi_key = "{KEY}"\n'


@pytest.fixture
def silent_scgi() -> Iterator[str]:
    """An SCGI address that accepts connections and never answers."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        yield f"127.0.0.1:{s.getsockname()[1]}"


def test_title_is_the_kind_title_whether_healthy_or_not(
    write_config: WriteConfig, fake_server: MakeServer
) -> None:
    down = only(write_config, service("sabnzbd", closed_port_url()))
    assert down.title == "SABnzbd"
    assert down.result is not None and down.result.title == "SABnzbd"
    srv = fake_server()
    srv.add("/api", fixture="sabnzbd/queue_idle.json", query={"mode": "queue"})
    srv.add("/api", fixture="sabnzbd/server_stats.json", query={"mode": "server_stats"})
    up = only(write_config, service("sabnzbd", srv.url))
    assert up.failure is None
    assert up.result is not None and up.result.title == "SABnzbd"


def test_name_overrides_the_kind_title(write_config: WriteConfig) -> None:
    o = only(write_config, service("sonarr", closed_port_url()) + 'name = "TV"\n')
    assert o.title == "TV"


def test_missing_reply_field_is_bad_response(
    write_config: WriteConfig, fake_server: MakeServer
) -> None:
    srv = fake_server()
    srv.add("/api", json={"queue": {}, "total": 0})
    o = only(write_config, service("sabnzbd", srv.url))
    assert o.failure is not None
    assert o.failure.kind is FailureKind.BAD_RESPONSE
    assert o.failure.reason == "bad response: missing 'kbpersec'"


def test_servarr_missing_field_is_bad_response(
    write_config: WriteConfig, fake_server: MakeServer
) -> None:
    srv = fake_server()
    for path in ("queue/status", "wanted/missing", "health", "calendar"):
        srv.add(f"/api/v3/{path}", json={} if path != "health" else [])
    o = only(write_config, service("sonarr", srv.url))
    assert o.failure is not None and o.failure.kind is FailureKind.BAD_RESPONSE


def test_rejected_key_is_auth_failed(
    write_config: WriteConfig, fake_server: MakeServer
) -> None:
    srv = fake_server(auth=("X-Api-Key", "other"))
    o = only(write_config, service("tautulli", srv.url))
    assert o.failure is not None
    assert o.failure.reason == "auth failed: bad API key (HTTP 401)"


def test_server_error_is_api_error(
    write_config: WriteConfig, fake_server: MakeServer
) -> None:
    srv = fake_server()
    srv.add("/api/v2", json={}, status=500)
    o = only(write_config, service("tautulli", srv.url))
    assert o.failure is not None
    assert o.failure.reason == "API error: HTTP 500"


def test_unreachable_http_and_scgi_share_a_kind(write_config: WriteConfig) -> None:
    http = only(write_config, service("radarr", closed_port_url()))
    scgi = only(
        write_config,
        f'[[modules]]\nkind = "rtorrent"\nscgi = "{closed_scgi_address()}"\n',
    )
    assert http.failure is not None and http.failure.kind is FailureKind.UNREACHABLE
    assert scgi.failure is not None and scgi.failure.kind is FailureKind.UNREACHABLE


def test_unavailable_result_carries_the_reason(write_config: WriteConfig) -> None:
    o = only(write_config, service("lidarr", closed_port_url()))
    assert o.result is not None and o.result.status is Status.UNAVAILABLE
    assert o.failure is not None
    assert o.result.rows[0].value == f"UNAVAILABLE: {o.failure.reason}"


def test_unknown_option_is_invalid_config_without_module_help(
    write_config: WriteConfig,
) -> None:
    o = only(write_config, '[[modules]]\nkind = "uptime"\nbogus = 1\n')
    assert o.failure is not None
    assert o.failure.reason == "invalid config: unknown option(s): bogus"


def test_no_probe_builds_without_contacting_anything(
    write_config: WriteConfig, fake_server: MakeServer
) -> None:
    srv = fake_server()
    o = only(write_config, service("sonarr", srv.url), probe=False)
    assert o.failure is None and o.result is None
    assert srv.requests == []


def test_unknown_box_is_a_warning_and_falls_back(write_config: WriteConfig) -> None:
    rep = report.collect(write_config('box = "fancy"\n'))
    assert rep.box == "single"
    assert rep.warnings and rep.failed


def test_bad_title_type_is_a_file_level_error(write_config: WriteConfig) -> None:
    from server_motd.config import ConfigError

    with pytest.raises(ConfigError, match="'title' must be a string"):
        report.collect(write_config('title = 5\n[[modules]]\nkind = "uptime"\n'))


def test_silent_scgi_is_timed_out(
    write_config: WriteConfig, silent_scgi: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from server_motd import runner

    monkeypatch.setattr(runner, "MODULE_TIMEOUT", 0.3)
    o = only(write_config, f'[[modules]]\nkind = "rtorrent"\nscgi = "{silent_scgi}"\n')
    assert o.failure is not None and o.failure.kind is FailureKind.TIMED_OUT
