"""rTorrent module through the CLI seam, against a fake SCGI server."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.conftest import Run
from tests.fakescgi import FakeScgi, closed_scgi_address

RunCli = Callable[..., Run]
WriteConfig = Callable[[str], Path]
MakeScgi = Callable[[str], FakeScgi]

HEAD = 'title = "host"\n'


def cfg_for(scgi: str, extra: str = "") -> str:
    return f'[[modules]]\nkind = "rtorrent"\nscgi = "{scgi}"\n{extra}'


def show(run_cli: RunCli, cfg: Path) -> Run:
    return run_cli("--config", str(cfg), "--width", "200", "--color", "never")


def test_rates_and_counts_match_fixture(
    run_cli: RunCli, write_config: WriteConfig, fake_scgi: MakeScgi
) -> None:
    srv = fake_scgi("rtorrent/multicall.json")
    out = show(run_cli, write_config(HEAD + cfg_for(srv.address))).out
    assert "Down" in out
    # 1572864 B/s and 262144 B/s exactly: no bit conversion, no 4.9% overstatement.
    assert "1.5M/s" in out
    assert "256.0K/s" in out
    assert "1.6M/s" not in out
    assert "2 downloading, 1 seeding, 1 stopped" in out
    # One request, one system.multicall.
    assert len(srv.requests) == 1
    assert "d.multicall2" in srv.requests[0]


@pytest.mark.skipif(sys.platform == "win32", reason="no unix sockets on Windows")
def test_unix_socket(
    run_cli: RunCli, write_config: WriteConfig, fake_scgi: MakeScgi
) -> None:
    srv = fake_scgi("rtorrent/multicall.json")
    assert srv.unix_address is not None
    out = show(run_cli, write_config(HEAD + cfg_for(srv.unix_address))).out
    assert "1.5M/s" in out


def test_unreachable_is_unavailable(run_cli: RunCli, write_config: WriteConfig) -> None:
    r = show(run_cli, write_config(HEAD + cfg_for(closed_scgi_address())))
    assert r.code == 0
    assert "rtorrent" in r.out
    assert "UNAVAILABLE" in r.out


def test_missing_scgi_is_invalid_config(
    run_cli: RunCli, write_config: WriteConfig
) -> None:
    out = show(run_cli, write_config(HEAD + '[[modules]]\nkind = "rtorrent"\n')).out
    assert "scgi" in out
