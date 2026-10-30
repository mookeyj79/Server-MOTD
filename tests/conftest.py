"""CLI-seam test harness: run the CLI, write configs, compare golden files."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import psutil
import pytest

from server_motd.cli import main

GOLDEN = Path(__file__).parent / "golden"


class Run(NamedTuple):
    code: int
    out: str
    err: str


@pytest.fixture
def run_cli(capsys: pytest.CaptureFixture[str]) -> Callable[..., Run]:
    def run(*args: str) -> Run:
        code = main(list(args))
        cap = capsys.readouterr()
        return Run(code, cap.out, cap.err)

    return run


@pytest.fixture
def write_config(tmp_path: Path) -> Callable[[str], Path]:
    def write(text: str) -> Path:
        path = tmp_path / "config.toml"
        path.write_text(text, encoding="utf-8")
        return path

    return write


@pytest.fixture
def pin_uptime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin uptime to exactly 3 days 4 hours 5 minutes."""
    monkeypatch.setattr("time.time", lambda: 1_000_000.0)
    boot = 1_000_000.0 - (3 * 86400 + 4 * 3600 + 5 * 60)
    monkeypatch.setattr(psutil, "boot_time", lambda: boot)


@pytest.fixture
def assert_golden() -> Callable[[str, str], None]:
    """Compare text with tests/golden/<name>; set UPDATE_GOLDEN=1 to rewrite."""

    def check(name: str, actual: str) -> None:
        path = GOLDEN / name
        if os.environ.get("UPDATE_GOLDEN"):
            path.write_text(actual, encoding="utf-8", newline="\n")
        assert actual == path.read_text(encoding="utf-8").replace("\r\n", "\n")

    return check
