"""End-to-end renders through the CLI seam (spec #15, seam 1)."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import pytest

from server_motd import runner
from server_motd.config import ConfigError, ModuleSpec
from server_motd.model import Result, Row
from server_motd.modules import REGISTRY
from tests.conftest import Run

RunCli = Callable[..., Run]
WriteConfig = Callable[[str], Path]
Golden = Callable[[str, str], None]


class Boom:
    def __init__(self, spec: ModuleSpec) -> None:
        spec.done()

    def fetch(self) -> Result:
        raise RuntimeError("kaboom")


class Slow:
    def __init__(self, spec: ModuleSpec) -> None:
        spec.done()

    def fetch(self) -> Result:
        time.sleep(5)
        return Result("Slow")


class Secret:
    """Shows the resolved secret so tests can observe resolution."""

    def __init__(self, spec: ModuleSpec) -> None:
        secret = spec.take_secret("token")
        spec.done()
        if secret is None:
            raise ConfigError("'token' is required")
        self.secret = secret

    def fetch(self) -> Result:
        return Result("Secret", [Row("Token", self.secret)])


@pytest.fixture(autouse=True)
def test_kinds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(REGISTRY, "boom", Boom)
    monkeypatch.setitem(REGISTRY, "slow", Slow)
    monkeypatch.setitem(REGISTRY, "secret", Secret)
    monkeypatch.setattr(runner, "MODULE_TIMEOUT", 0.3)


def test_uptime_golden(
    run_cli: RunCli, write_config: WriteConfig, pin_uptime: None, assert_golden: Golden
) -> None:
    cfg = write_config('[[modules]]\nkind = "uptime"\n')
    r = run_cli("--config", str(cfg), "--width", "40", "--color", "never")
    assert r.code == 0
    assert_golden("uptime.txt", r.out)


def test_disabled_omitted_and_order_preserved(
    run_cli: RunCli, write_config: WriteConfig, pin_uptime: None
) -> None:
    cfg = write_config(
        '[[modules]]\nkind = "secret"\nname = "Zed"\ntoken = "t"\n'
        '[[modules]]\nkind = "uptime"\nenabled = false\n'
        '[[modules]]\nkind = "uptime"\nname = "Alpha"\n'
    )
    r = run_cli("--config", str(cfg), "--width", "40", "--color", "never")
    assert r.code == 0
    assert "Hidden" not in r.out
    assert r.out.index("Secret") < r.out.index("Alpha")


def test_raising_and_slow_modules_are_unavailable(
    run_cli: RunCli, write_config: WriteConfig, pin_uptime: None
) -> None:
    cfg = write_config(
        '[[modules]]\nkind = "boom"\nname = "B"\n'
        '[[modules]]\nkind = "slow"\nname = "S"\n'
        '[[modules]]\nkind = "uptime"\n'
    )
    r = run_cli("--config", str(cfg), "--width", "80", "--color", "never")
    assert r.code == 0
    assert "UNAVAILABLE: kaboom" in r.out
    assert "UNAVAILABLE: timed out" in r.out
    assert "3d 4h 5m" in r.out


def test_verbose_shows_exception_detail(
    run_cli: RunCli, write_config: WriteConfig
) -> None:
    cfg = write_config('[[modules]]\nkind = "boom"\n')
    r = run_cli("--config", str(cfg), "--width", "80", "--verbose")
    assert r.code == 0
    assert "RuntimeError: kaboom" in r.err


def test_invalid_config_is_scoped_to_its_module(
    run_cli: RunCli, write_config: WriteConfig, pin_uptime: None
) -> None:
    cfg = write_config(
        '[[modules]]\nkind = "uptime"\nname = "Bad"\nbogus = 1\n'
        '[[modules]]\nkind = "nope"\nname = "Worse"\n'
        '[[modules]]\nkind = "uptime"\nname = "Good"\n'
    )
    r = run_cli("--config", str(cfg), "--width", "80", "--color", "never")
    assert r.code == 0
    assert "invalid config: unknown option(s): bogus" in r.out
    assert "invalid config: unknown kind 'nope'" in r.out
    assert "3d 4h 5m" in r.out  # the good one still renders


def test_env_secret_resolves(
    run_cli: RunCli, write_config: WriteConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MOTD_TEST_TOKEN", "from-env")
    cfg = write_config('[[modules]]\nkind = "secret"\ntoken = "${MOTD_TEST_TOKEN}"\n')
    r = run_cli("--config", str(cfg), "--width", "40", "--color", "never")
    assert "from-env" in r.out


def test_file_secret_resolves(
    run_cli: RunCli, write_config: WriteConfig, tmp_path: Path
) -> None:
    (tmp_path / "tok").write_text("from-file\n", encoding="utf-8")
    tok = (tmp_path / "tok").as_posix()
    cfg = write_config(f'[[modules]]\nkind = "secret"\ntoken_file = "{tok}"\n')
    r = run_cli("--config", str(cfg), "--width", "40", "--color", "never")
    assert "from-file" in r.out


def test_unset_env_secret_degrades_only_that_module(
    run_cli: RunCli, write_config: WriteConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MOTD_TEST_MISSING", raising=False)
    cfg = write_config('[[modules]]\nkind = "secret"\ntoken = "${MOTD_TEST_MISSING}"\n')
    r = run_cli("--config", str(cfg), "--width", "80", "--color", "never")
    assert r.code == 0
    assert "MOTD_TEST_MISSING" in r.out


def test_missing_config_exits_zero(run_cli: RunCli, tmp_path: Path) -> None:
    r = run_cli("--config", str(tmp_path / "absent.toml"))
    assert r.code == 0
    assert "no config file found" in r.err


def test_color_always_paints_status(run_cli: RunCli, write_config: WriteConfig) -> None:
    cfg = write_config('[[modules]]\nkind = "boom"\n')
    r = run_cli("--config", str(cfg), "--width", "80", "--color", "always")
    assert "\x1b[31m" in r.out
