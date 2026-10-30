"""Pending updates and reboot module, through the CLI seam."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from tests.conftest import Run

RunCli = Callable[..., Run]
WriteConfig = Callable[[str], Path]
Golden = Callable[[str, str], None]

PENDING = (
    "5 updates can be applied immediately.\n"
    "2 of these updates are standard security updates.\n"
)


def render(
    run_cli: RunCli, write_config: WriteConfig, tmp_path: Path, extra: str = ""
) -> Run:
    cfg = write_config(
        '[[modules]]\nkind = "updates"\n'
        f'updates_file = "{(tmp_path / "updates-available").as_posix()}"\n'
        f'reboot_file = "{(tmp_path / "reboot-required").as_posix()}"\n' + extra
    )
    r = run_cli("--config", str(cfg), "--width", "40", "--color", "never")
    assert r.code == 0
    return r


def test_updates_pending_golden(
    run_cli: RunCli, write_config: WriteConfig, tmp_path: Path, assert_golden: Golden
) -> None:
    (tmp_path / "updates-available").write_text(PENDING)
    assert_golden("updates_pending.txt", render(run_cli, write_config, tmp_path).out)


def test_none_pending_golden(
    run_cli: RunCli, write_config: WriteConfig, tmp_path: Path, assert_golden: Golden
) -> None:
    (tmp_path / "updates-available").write_text(
        "0 updates can be applied immediately.\n"
    )
    assert_golden("updates_none.txt", render(run_cli, write_config, tmp_path).out)


def test_reboot_required_golden(
    run_cli: RunCli, write_config: WriteConfig, tmp_path: Path, assert_golden: Golden
) -> None:
    (tmp_path / "updates-available").write_text(PENDING)
    (tmp_path / "reboot-required").write_text("*** System restart required ***\n")
    assert_golden("updates_reboot.txt", render(run_cli, write_config, tmp_path).out)


def test_missing_files_are_unavailable(
    run_cli: RunCli, write_config: WriteConfig, tmp_path: Path
) -> None:
    r = render(run_cli, write_config, tmp_path)
    assert "UNAVAILABLE" in r.out


def test_unparseable_updates_file_is_unavailable(
    run_cli: RunCli, write_config: WriteConfig, tmp_path: Path
) -> None:
    (tmp_path / "updates-available").write_text("garbage\n")
    assert "UNAVAILABLE" in render(run_cli, write_config, tmp_path).out
