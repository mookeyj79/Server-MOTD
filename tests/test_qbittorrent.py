"""qBittorrent module through the CLI seam, against a fake WebUI v2 server."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.conftest import Run
from tests.fakeserver import FakeServer, closed_port_url

RunCli = Callable[..., Run]
WriteConfig = Callable[[str], Path]
MakeServer = Callable[..., FakeServer]

HEAD = 'title = "host"\n'
LOGIN = "/api/v2/auth/login"
MAINDATA = "/api/v2/sync/maindata"

# (fixture, cookie, login status, login body) per qBittorrent generation.
VERSIONS = [
    ("maindata_4x.json", "SID=abc", 200, "Ok."),
    ("maindata_50.json", "SID=abc", 200, "Ok."),
    ("maindata_52.json", "QBT_SID_8080=abc", 200, ""),
]


def qbit(
    make: MakeServer, fixture: str, cookie: str, status: int, body: str
) -> FakeServer:
    srv = make()
    srv.add(
        LOGIN,
        text=body,
        status=status,
        headers={"Set-Cookie": f"{cookie}; HTTP-Only; path=/"},
    )
    srv.add(MAINDATA, fixture=f"qbittorrent/{fixture}", need_cookie=cookie)
    return srv


def cfg(url: str, extra: str = "") -> str:
    return (
        f'{HEAD}[[modules]]\nkind = "qbittorrent"\nurl = "{url}"\n'
        f'username = "admin"\npassword = "pw"\n{extra}'
    )


def run(run_cli: RunCli, write_config: WriteConfig, text: str) -> Run:
    path = write_config(text)
    return run_cli("--config", str(path), "--width", "200", "--color", "never")


@pytest.mark.parametrize(("fixture", "cookie", "status", "body"), VERSIONS)
def test_rates_and_states_across_versions(
    run_cli: RunCli,
    write_config: WriteConfig,
    fake_server: MakeServer,
    fixture: str,
    cookie: str,
    status: int,
    body: str,
) -> None:
    srv = qbit(fake_server, fixture, cookie, status, body)
    r = run(run_cli, write_config, cfg(srv.url))
    assert r.code == 0
    assert "qBittorrent" in r.out
    assert "2.0M/s" in r.out
    assert "512.0K/s" in r.out
    for label, n in [("Downloading", 2), ("Seeding", 3), ("Stopped", 2), ("Error", 1)]:
        assert re.search(rf"{label}\s+{n}\b", r.out), label
    # Login then exactly one sync call; credentials posted form-encoded.
    assert [q.path for q in srv.requests] == [LOGIN, MAINDATA]
    assert "username=admin" in srv.requests[0].body
    assert "password=pw" in srv.requests[0].body


@pytest.mark.parametrize(
    ("status", "body"), [(200, "Fails."), (401, "Unauthorized"), (403, "banned")]
)
def test_failed_login_is_unavailable(
    run_cli: RunCli,
    write_config: WriteConfig,
    fake_server: MakeServer,
    status: int,
    body: str,
) -> None:
    srv = fake_server()
    srv.add(LOGIN, text=body, status=status)
    r = run(run_cli, write_config, cfg(srv.url))
    assert "UNAVAILABLE" in r.out.upper()
    assert MAINDATA not in [q.path for q in srv.requests]


def test_unreachable_is_unavailable(run_cli: RunCli, write_config: WriteConfig) -> None:
    r = run(run_cli, write_config, cfg(closed_port_url()))
    assert "UNAVAILABLE" in r.out.upper()


def test_empty_credentials_allowed(
    run_cli: RunCli, write_config: WriteConfig, fake_server: MakeServer
) -> None:
    srv = qbit(fake_server, *VERSIONS[0])
    text = f'{HEAD}[[modules]]\nkind = "qbittorrent"\nurl = "{srv.url}"\n'
    r = run(run_cli, write_config, text)
    assert "Downloading" in r.out
