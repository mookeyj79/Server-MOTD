"""Hook script behaviour and the role's TOML filter (no Ansible needed)."""

from __future__ import annotations

import importlib.util
import os
import shutil
import stat
import subprocess
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

ROLE = Path(__file__).parent.parent / "ansible" / "roles" / "server_motd"
HOOK = ROLE / "files" / "50-server-motd"


def _load_filter() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "server_motd_filter", ROLE / "filter_plugins" / "server_motd.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _render(config: object) -> str:
    return str(_load_filter().to_server_motd_toml(config))


def test_filter_roundtrips_modules_and_top_level_keys() -> None:
    cfg = {
        "title": 'My "box" ☃ \U0001f600',
        "box": "double",
        "modules": [
            {"kind": "load", "warn": 2.5, "crit": 4},
            {"kind": "radarr", "name": "main", "api_key": "a\b\nc", "enabled": False},
            {"kind": "disks", "paths": ["/", "/mnt"], "labels": {"/": "root"}},
        ],
    }
    assert tomllib.loads(_render(cfg)) == cfg


def test_filter_output_loads_with_the_real_config_loader(tmp_path: Path) -> None:
    from server_motd import config

    path = tmp_path / "config.toml"
    path.write_text(_render({"title": "t", "modules": [{"kind": "load"}]}))
    entries = config.load(path)
    assert [getattr(e, "kind", None) for e in entries] == ["load"]
    assert config.load_settings(path).title == "t"


def test_filter_rejects_non_dict() -> None:
    with pytest.raises(TypeError):
        _render(["x"])


def test_filter_str_like_values_are_rendered_as_strings() -> None:
    class Vaulted:
        def __str__(self) -> str:
            return "s3cret"

    assert (
        tomllib.loads(_render({"modules": [{"kind": "x", "k": Vaulted()}]}))["modules"][
            0
        ]["k"]
        == "s3cret"
    )


posix_only = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("timeout") is None, reason="POSIX only"
)


def _run_hook(script: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/sh", str(script)], capture_output=True, text=True, env={}, check=False
    )


def _hook_for(tmp_path: Path, venv: Path) -> Path:
    text = HOOK.read_text().replace("/opt/server-motd/venv", str(venv))
    script = tmp_path / "hook"
    script.write_text(text)
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


@posix_only
def test_hook_exits_zero_silently_when_venv_missing(tmp_path: Path) -> None:
    result = _run_hook(_hook_for(tmp_path, tmp_path / "nope"))
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


@posix_only
def test_hook_exits_zero_and_prints_nothing_when_binary_fails(tmp_path: Path) -> None:
    binary = tmp_path / "venv" / "bin" / "server-motd"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\necho partial\nexit 3\n")
    binary.chmod(0o755)
    result = _run_hook(_hook_for(tmp_path, tmp_path / "venv"))
    assert (result.returncode, result.stdout) == (0, "")


@posix_only
def test_hook_passes_width_and_color_flags(tmp_path: Path) -> None:
    binary = tmp_path / "venv" / "bin" / "server-motd"
    binary.parent.mkdir(parents=True)
    binary.write_text('#!/bin/sh\necho "args: $*"\n')
    binary.chmod(0o755)
    if getattr(os, "geteuid", lambda: 1)() == 0:
        pytest.skip("root would require the server-motd user")
    result = _run_hook(_hook_for(tmp_path, tmp_path / "venv"))
    assert result.returncode == 0
    assert result.stdout == "args: --width 80 --color always\n"
