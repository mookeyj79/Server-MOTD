"""Hook script behaviour and the role's TOML filter (no Ansible needed)."""

from __future__ import annotations

import importlib.util
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

ROLE = Path(__file__).parent.parent / "ansible" / "roles" / "server_motd"
HOOK = ROLE / "templates" / "50-server-motd.j2"


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
    loaded = config.load(path)
    assert [getattr(e, "kind", None) for e in loaded.entries] == ["load"]
    assert loaded.settings.title == "t"


def test_filter_rejects_non_dict() -> None:
    with pytest.raises(TypeError):
        _render(["x"])


def test_filter_rejects_none_inside_a_list() -> None:
    with pytest.raises(TypeError, match="no null"):
        _render({"modules": [{"kind": "disks", "paths": ["/", None]}]})


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


def _hook_for(tmp_path: Path, venv: Path, config_dir: str = "/etc/server-motd") -> Path:
    """Render the hook template the way Ansible would for these role variables."""
    text = HOOK.read_text()
    for var, value in {
        "server_motd_venv": str(venv),
        "server_motd_user": "server-motd",
        "server_motd_config_dir": config_dir,
    }.items():
        text = text.replace("{{ " + var + " | quote }}", shlex.quote(value))
    assert "{{" not in text and "{%" not in text, "unrendered template syntax"
    script = tmp_path / "hook"
    script.write_text(text)
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


@posix_only
def test_hook_exits_zero_silently_when_venv_missing(tmp_path: Path) -> None:
    result = _run_hook(_hook_for(tmp_path, tmp_path / "nope"))
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def _fake_venv(tmp_path: Path, script: str) -> Path:
    """A venv whose server-motd binary is the given shell script."""
    binary = tmp_path / "venv" / "bin" / "server-motd"
    binary.parent.mkdir(parents=True)
    binary.write_text(script)
    binary.chmod(0o755)
    return tmp_path / "venv"


ECHO_ARGS = '#!/bin/sh\necho "args: $*"\n'
not_root = pytest.mark.skipif(
    getattr(os, "geteuid", lambda: 1)() == 0,
    reason="as root the hook would need the server-motd user",
)


@posix_only
def test_hook_exits_zero_and_prints_nothing_when_binary_fails(tmp_path: Path) -> None:
    venv = _fake_venv(tmp_path, "#!/bin/sh\necho partial\nexit 3\n")
    result = _run_hook(_hook_for(tmp_path, venv))
    assert (result.returncode, result.stdout) == (0, "")


@posix_only
@not_root
def test_hook_passes_config_width_and_color_flags(tmp_path: Path) -> None:
    result = _run_hook(_hook_for(tmp_path, _fake_venv(tmp_path, ECHO_ARGS)))
    assert result.returncode == 0
    assert result.stdout == (
        "args: --config /etc/server-motd/config.toml --width 80 --color always\n"
    )


@posix_only
@not_root
def test_hook_uses_the_role_config_dir(tmp_path: Path) -> None:
    venv = _fake_venv(tmp_path, ECHO_ARGS)
    result = _run_hook(_hook_for(tmp_path, venv, "/srv/my motd"))
    assert result.stdout.startswith("args: --config /srv/my motd/config.toml ")
