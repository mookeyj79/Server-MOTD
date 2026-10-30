"""Windows rendering and the cpu module through the CLI seam (ticket #28).

Windows behaviour is simulated at two boundaries: `sys.platform` and the
`ctypes.windll` console API, so these run on every OS.
"""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable
from pathlib import Path

import psutil
import pytest

from tests.conftest import Run

RunCli = Callable[..., Run]
WriteConfig = Callable[[str], Path]
Golden = Callable[[str, str], None]

HEAD = 'title = "host"\n'
VT_FLAG = 0x0004


class FakeConsole:
    """Stand-in for ctypes.windll.kernel32 console calls."""

    def __init__(self, mode: int = 0x0003, fail_set: bool = False) -> None:
        self.mode = mode
        self.fail_set = fail_set
        self.set_calls: list[int] = []

    def GetStdHandle(self, which: int) -> int:  # noqa: N802
        return 7

    def GetConsoleMode(self, handle: int, ref: object) -> int:  # noqa: N802
        ref._obj.value = self.mode  # type: ignore[attr-defined]
        return 1

    def SetConsoleMode(self, handle: int, mode: int) -> int:  # noqa: N802
        self.set_calls.append(mode)
        if self.fail_set:
            return 0
        self.mode = mode
        return 1


def _windows(monkeypatch: pytest.MonkeyPatch, console: FakeConsole | None) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    if console is not None:
        kernel = type("W", (), {"kernel32": console})()
        monkeypatch.setattr(ctypes, "windll", kernel, raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)


def _cfg(write_config: WriteConfig) -> str:
    return str(write_config(HEAD + '[[modules]]\nkind = "processes"\nwarn = 1\n'))


@pytest.fixture(autouse=True)
def pids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(psutil, "pids", lambda: [1, 2, 3])


def test_windows_tty_enables_vt_and_colours(
    run_cli: RunCli, write_config: WriteConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    console = FakeConsole()
    _windows(monkeypatch, console)
    r = run_cli("--config", _cfg(write_config), "--width", "50")
    assert console.set_calls == [0x0003 | VT_FLAG]
    assert "\x1b[33m3" in r.out


def test_windows_vt_failure_falls_back_to_plain_text(
    run_cli: RunCli, write_config: WriteConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    _windows(monkeypatch, FakeConsole(fail_set=True))
    r = run_cli("--config", _cfg(write_config), "--width", "50")
    assert r.code == 0
    assert "\x1b" not in r.out


def test_windows_without_console_api_is_plain_and_exits_zero(
    run_cli: RunCli, write_config: WriteConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    _windows(monkeypatch, None)
    monkeypatch.delattr(ctypes, "windll", raising=False)
    r = run_cli("--config", _cfg(write_config), "--width", "50")
    assert r.code == 0
    assert "\x1b" not in r.out
    assert "Processes" in r.out


def test_vt_not_touched_when_not_a_tty(
    run_cli: RunCli, write_config: WriteConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    console = FakeConsole()
    _windows(monkeypatch, console)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    r = run_cli("--config", _cfg(write_config), "--width", "50")
    assert console.set_calls == []
    assert "\x1b" not in r.out


def test_windows_load_is_rejected_pointing_at_cpu(
    run_cli: RunCli, write_config: WriteConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    cfg = write_config(HEAD + '[[modules]]\nkind = "load"\n')
    r = run_cli("--config", str(cfg), "--width", "200", "--color", "never")
    assert r.code == 0
    assert "use the cpu module" in r.out


def test_cpu_golden_and_thresholds(
    run_cli: RunCli,
    write_config: WriteConfig,
    assert_golden: Golden,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(psutil, "cpu_percent", lambda interval=None: 42.0)
    monkeypatch.setattr(psutil, "cpu_count", lambda: 4)
    base = ["--width", "50", "--color", "never"]
    cfg = write_config(HEAD + '[[modules]]\nkind = "cpu"\n')
    r = run_cli("--config", str(cfg), *base)
    assert_golden("cpu.txt", r.out)
    for limits, mark in [
        ("warn = 40", "\x1b[33m"),
        ("warn = 40\ncrit = 42", "\x1b[31m"),
    ]:
        cfg = write_config(HEAD + f'[[modules]]\nkind = "cpu"\n{limits}\n')
        c = run_cli("--config", str(cfg), "--width", "50", "--color", "always")
        assert mark + "42%" in c.out


def test_cpu_samples_over_an_interval(
    run_cli: RunCli, write_config: WriteConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[float | None] = []

    def cpu_percent(interval: float | None = None) -> float:
        seen.append(interval)
        return 5.0

    monkeypatch.setattr(psutil, "cpu_percent", cpu_percent)
    cfg = write_config(HEAD + '[[modules]]\nkind = "cpu"\n')
    run_cli("--config", str(cfg), "--width", "50", "--color", "never")
    assert seen and seen[0]  # a first call with no interval would report 0.0
