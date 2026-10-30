"""Core system modules through the CLI seam, with psutil pinned at the boundary."""

from __future__ import annotations

import socket
import sys
from collections import namedtuple
from collections.abc import Callable
from pathlib import Path

import psutil
import pytest

from tests.conftest import Run

RunCli = Callable[..., Run]
WriteConfig = Callable[[str], Path]
Golden = Callable[[str, str], None]

GIB = 1024**3
Addr = namedtuple("Addr", "family address netmask broadcast ptp")  # noqa: PYI024
Mem = namedtuple("Mem", "total used percent")  # noqa: PYI024
Part = namedtuple("Part", "device mountpoint fstype opts")  # noqa: PYI024
Usage = namedtuple("Usage", "total used free percent")  # noqa: PYI024
User = namedtuple("User", "name terminal host started pid")  # noqa: PYI024


def render(run_cli: RunCli, write_config: WriteConfig, toml: str) -> Run:
    r = run_cli(
        "--config", str(write_config(toml)), "--width", "50", "--color", "never"
    )
    assert r.code == 0
    return r


def test_ips_golden(
    run_cli: RunCli,
    write_config: WriteConfig,
    assert_golden: Golden,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    v4, v6 = socket.AF_INET, socket.AF_INET6
    addrs = {
        "lo": [Addr(v4, "127.0.0.1", "", None, None)],
        "eth0": [
            Addr(v4, "192.168.1.10", "", None, None),
            Addr(v6, "fe80::1%eth0", "", None, None),
            Addr(v6, "2001:db8::10", "", None, None),
        ],
    }
    monkeypatch.setattr(psutil, "net_if_addrs", lambda: addrs)
    r = render(run_cli, write_config, '[[modules]]\nkind = "ips"\n')
    assert_golden("ips.txt", r.out)


@pytest.mark.skipif(sys.platform == "win32", reason="load is Linux-only")
def test_load_golden_and_thresholds(
    run_cli: RunCli,
    write_config: WriteConfig,
    assert_golden: Golden,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(psutil, "getloadavg", lambda: (2.0, 1.5, 1.0))
    monkeypatch.setattr(psutil, "cpu_count", lambda: 4)
    r = render(run_cli, write_config, '[[modules]]\nkind = "load"\n')
    assert_golden("load.txt", r.out)
    # 2.0 load on 4 cores = 0.5 per core
    for limits, mark in [
        ("warn = 0.4", "\x1b[33m"),
        ("warn = 0.4\ncrit = 0.5", "\x1b[31m"),
    ]:
        cfg = write_config(f'[[modules]]\nkind = "load"\n{limits}\n')
        c = run_cli("--config", str(cfg), "--width", "50", "--color", "always")
        assert mark in c.out
    cfg = write_config('[[modules]]\nkind = "load"\nwarn = 0.9\n')
    c = run_cli("--config", str(cfg), "--width", "50", "--color", "always")
    assert "\x1b[32m" in c.out


def test_memory_golden_and_thresholds(
    run_cli: RunCli,
    write_config: WriteConfig,
    assert_golden: Golden,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(psutil, "virtual_memory", lambda: Mem(8 * GIB, 2 * GIB, 25.0))
    swap = namedtuple("swap", "total used percent")  # noqa: PYI024
    monkeypatch.setattr(psutil, "swap_memory", lambda: swap(2 * GIB, 0, 0.0))
    r = render(run_cli, write_config, '[[modules]]\nkind = "memory"\n')
    assert_golden("memory.txt", r.out)
    cfg = write_config('[[modules]]\nkind = "memory"\nwarn = 20\ncrit = 90\n')
    c = run_cli("--config", str(cfg), "--width", "50", "--color", "always")
    assert "\x1b[33m2.0G / 8.0G (25%)" in c.out


def test_disks_lists_mounts_golden_and_thresholds(
    run_cli: RunCli,
    write_config: WriteConfig,
    assert_golden: Golden,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parts = [
        Part("/dev/sda1", "/", "ext4", ""),
        Part("/dev/sdb1", "/mnt/media", "xfs", ""),
        Part("/dev/sdc1", "/mnt/gone", "xfs", ""),
    ]
    usage = {
        "/": Usage(100 * GIB, 40 * GIB, 60 * GIB, 40.0),
        "/mnt/media": Usage(1024 * GIB, 950 * GIB, 74 * GIB, 92.8),
    }

    def disk_usage(path: str) -> Usage:
        if path not in usage:
            raise OSError("unreadable")
        return usage[path]

    monkeypatch.setattr(psutil, "disk_partitions", lambda all=False: parts)
    monkeypatch.setattr(psutil, "disk_usage", disk_usage)
    r = render(run_cli, write_config, '[[modules]]\nkind = "disks"\n')
    assert_golden("disks.txt", r.out)
    cfg = write_config('[[modules]]\nkind = "disks"\nwarn = 80\ncrit = 95\n')
    c = run_cli("--config", str(cfg), "--width", "50", "--color", "always")
    assert "\x1b[32m40.0G / 100.0G (40%)" in c.out
    assert "\x1b[33m950.0G / 1.0T (93%)" in c.out


def test_logins_golden_and_empty(
    run_cli: RunCli,
    write_config: WriteConfig,
    assert_golden: Golden,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    users = [
        User("alice", "pts/0", "10.0.0.5", 0.0, 1),
        User("bob", "tty1", "", 0.0, 2),
    ]
    monkeypatch.setattr(psutil, "users", lambda: users)
    r = render(run_cli, write_config, '[[modules]]\nkind = "logins"\n')
    assert_golden("logins.txt", r.out)
    monkeypatch.setattr(psutil, "users", lambda: [])
    r = render(run_cli, write_config, '[[modules]]\nkind = "logins"\n')
    assert "none" in r.out


def test_processes_golden_and_thresholds(
    run_cli: RunCli,
    write_config: WriteConfig,
    assert_golden: Golden,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(psutil, "pids", lambda: list(range(150)))
    r = render(run_cli, write_config, '[[modules]]\nkind = "processes"\n')
    assert_golden("processes.txt", r.out)
    cfg = write_config('[[modules]]\nkind = "processes"\nwarn = 100\ncrit = 120\n')
    c = run_cli("--config", str(cfg), "--width", "50", "--color", "always")
    assert "\x1b[31m150" in c.out


def test_bad_thresholds_degrade_only_that_module(
    run_cli: RunCli, write_config: WriteConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(psutil, "pids", lambda: [1])
    cfg = write_config(
        '[[modules]]\nkind = "processes"\nname = "A"\nwarn = 9\ncrit = 5\n'
        '[[modules]]\nkind = "processes"\nname = "B"\n'
    )
    r = run_cli("--config", str(cfg), "--width", "100", "--color", "never")
    assert "'warn' must not exceed 'crit'" in r.out
    assert "Processes  1" in r.out


def test_no_last_login_module(run_cli: RunCli, write_config: WriteConfig) -> None:
    r = run_cli(
        "--config",
        str(write_config('[[modules]]\nkind = "lastlogin"\n')),
        "--width",
        "100",
        "--color",
        "never",
    )
    assert "unknown kind 'lastlogin'" in r.out
