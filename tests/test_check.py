"""`server-motd check` and config discovery, through the CLI seam."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.conftest import Run

RunCli = Callable[..., Run]
WriteConfig = Callable[[str], Path]

GOOD = '[[modules]]\nkind = "uptime"\n'


@pytest.mark.usefixtures("pin_uptime")
def test_check_reports_pass_per_module(
    run_cli: RunCli, write_config: WriteConfig
) -> None:
    path = write_config(GOOD)
    r = run_cli("--config", str(path), "check")
    assert r.code == 0
    assert "ok" in r.out and "uptime" in r.out


def test_check_after_subcommand_accepts_options(
    run_cli: RunCli, write_config: WriteConfig
) -> None:
    path = write_config(GOOD)
    r = run_cli("check", "--config", str(path))
    assert r.code == 0


def test_check_fails_on_invalid_module_config(
    run_cli: RunCli, write_config: WriteConfig
) -> None:
    path = write_config(GOOD + '[[modules]]\nkind = "nope"\n')
    r = run_cli("--config", str(path), "check")
    assert r.code != 0
    assert "uptime" in r.out
    assert "FAIL" in r.out and "unknown kind 'nope'" in r.out


def test_check_fails_when_config_missing(run_cli: RunCli, tmp_path: Path) -> None:
    r = run_cli("--config", str(tmp_path / "absent.toml"), "check")
    assert r.code != 0
    assert "no config file found" in r.err


def test_check_probe_failure_hides_trace_unless_verbose(
    run_cli: RunCli, write_config: WriteConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom() -> float:
        raise RuntimeError("kaboom")

    monkeypatch.setattr("psutil.boot_time", boom)
    path = write_config(GOOD)
    quiet = run_cli("--config", str(path), "check")
    assert quiet.code != 0
    assert "kaboom" in quiet.out
    assert "Traceback" not in quiet.out + quiet.err
    loud = run_cli("--config", str(path), "check", "--verbose")
    assert "Traceback" in loud.out + loud.err


def test_check_writes_no_log_file(
    run_cli: RunCli, write_config: WriteConfig, tmp_path: Path
) -> None:
    path = write_config(GOOD)
    before = set(tmp_path.rglob("*"))
    run_cli("--config", str(path), "check")
    assert set(tmp_path.rglob("*")) == before


def test_discovery_linux_uses_etc(
    run_cli: RunCli, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    r = run_cli("check")
    assert r.code != 0
    assert "/etc/server-motd/config.toml" in r.err.replace("\\", "/")


def _win_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path]:
    monkeypatch.setattr(sys, "platform", "win32")
    app, prog = tmp_path / "appdata", tmp_path / "progdata"
    monkeypatch.setenv("APPDATA", str(app))
    monkeypatch.setenv("ProgramData", str(prog))
    for d in (app, prog):
        (d / "server-motd").mkdir(parents=True)
    return app / "server-motd" / "config.toml", prog / "server-motd" / "config.toml"


@pytest.mark.usefixtures("pin_uptime")
def test_discovery_windows_prefers_appdata(
    run_cli: RunCli, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app, prog = _win_env(monkeypatch, tmp_path)
    app.write_text('[[modules]]\nkind = "uptime"\nname = "FromApp"\n', encoding="utf-8")
    prog.write_text(
        '[[modules]]\nkind = "uptime"\nname = "FromProg"\n', encoding="utf-8"
    )
    r = run_cli("check")
    assert "FromApp" in r.out and "FromProg" not in r.out


@pytest.mark.usefixtures("pin_uptime")
def test_discovery_windows_falls_back_to_programdata(
    run_cli: RunCli, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _, prog = _win_env(monkeypatch, tmp_path)
    prog.write_text(
        '[[modules]]\nkind = "uptime"\nname = "FromProg"\n', encoding="utf-8"
    )
    r = run_cli("check")
    assert "FromProg" in r.out


def test_explicit_config_overrides_discovery(
    run_cli: RunCli,
    write_config: WriteConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app, _ = _win_env(monkeypatch, tmp_path)
    app.write_text('[[modules]]\nkind = "nope"\n', encoding="utf-8")
    path = write_config(GOOD)
    r = run_cli("--config", str(path), "check")
    assert r.code == 0
