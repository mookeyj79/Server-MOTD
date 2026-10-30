"""Layout, banner, box styles and colour through the CLI seam (ticket #18)."""

from __future__ import annotations

import re
import sys
import types
from collections.abc import Callable
from pathlib import Path

import pytest

from server_motd.config import ModuleSpec
from server_motd.model import Result, Row, Status
from server_motd.modules import REGISTRY
from tests.conftest import Run

RunCli = Callable[..., Run]
WriteConfig = Callable[[str], Path]
Golden = Callable[[str, str], None]


class Stub:
    """Fixed content: one row per status, one overlong value."""

    def __init__(self, spec: ModuleSpec) -> None:
        self.title = spec.name or "Stub"
        spec.done()

    def fetch(self) -> Result:
        return Result(
            self.title,
            [
                Row("Info", "plain"),
                Row("Fine", "all good", Status.OK),
                Row("Hmm", "getting full", Status.WARN),
                Row("Bad", "on fire", Status.CRIT),
                Row("Long", "x" * 70),
            ],
        )


@pytest.fixture(autouse=True)
def stub_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(REGISTRY, "stub", Stub)
    monkeypatch.setitem(sys.modules, "pyfiglet", None)  # absent unless a test fakes it


CONFIG = 'title = "media-box"\n' + "".join(
    f'[[modules]]\nkind = "stub"\nname = "{n}"\n' for n in ("Alpha", "Beta", "Gamma")
)


@pytest.mark.parametrize("width", [110, 80, 50])
def test_layout_golden(
    run_cli: RunCli, write_config: WriteConfig, assert_golden: Golden, width: int
) -> None:
    cfg = write_config(CONFIG)
    r = run_cli("--config", str(cfg), "--width", str(width), "--color", "never")
    assert r.code == 0
    assert_golden(f"layout-{width}.txt", r.out)
    assert {len(line) for line in r.out.splitlines()} == {width}


def test_two_columns_only_when_wide(run_cli: RunCli, write_config: WriteConfig) -> None:
    cfg = write_config(CONFIG)
    wide = run_cli("--config", str(cfg), "--width", "70", "--color", "never").out
    narrow = run_cli("--config", str(cfg), "--width", "69", "--color", "never").out
    assert "┬" in wide
    assert "┬" not in narrow


def test_ascii_box_has_no_box_drawing(
    run_cli: RunCli, write_config: WriteConfig, assert_golden: Golden
) -> None:
    cfg = write_config('box = "ascii"\n' + CONFIG)
    r = run_cli("--config", str(cfg), "--width", "90", "--color", "never")
    assert not re.search("[─-╿]", r.out)
    assert_golden("layout-ascii.txt", r.out)


def test_unknown_box_style_falls_back_with_warning(
    run_cli: RunCli, write_config: WriteConfig
) -> None:
    cfg = write_config('box = "bogus"\n' + CONFIG)
    r = run_cli("--config", str(cfg), "--width", "90", "--color", "never")
    assert r.code == 0
    assert "bogus" in r.err
    assert "media-box" in r.out


def test_banner_uses_figlet_when_available(
    run_cli: RunCli,
    write_config: WriteConfig,
    monkeypatch: pytest.MonkeyPatch,
    assert_golden: Golden,
) -> None:
    fake = types.ModuleType("pyfiglet")
    fake.figlet_format = lambda text, **kw: "ART1\nART2\n\n"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pyfiglet", fake)
    cfg = write_config(CONFIG)
    r = run_cli("--config", str(cfg), "--width", "80", "--color", "never")
    assert "ART1" in r.out
    assert "media-box" not in r.out
    assert_golden("layout-figlet.txt", r.out)


def test_banner_plain_when_figlet_too_wide(
    run_cli: RunCli, write_config: WriteConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = types.ModuleType("pyfiglet")
    fake.figlet_format = lambda text, **kw: "#" * 200  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pyfiglet", fake)
    cfg = write_config(CONFIG)
    r = run_cli("--config", str(cfg), "--width", "80", "--color", "never")
    assert "media-box" in r.out
    assert "#" * 20 not in r.out


def test_color_never_has_no_escapes_and_always_maps_status(
    run_cli: RunCli, write_config: WriteConfig
) -> None:
    cfg = write_config(CONFIG)
    never = run_cli("--config", str(cfg), "--width", "90", "--color", "never")
    assert "\x1b" not in never.out
    always = run_cli("--config", str(cfg), "--width", "90", "--color", "always").out
    for code in ("32", "33", "31"):
        assert f"\x1b[{code}m" in always
