"""TOML config loading, strict per-module validation and secret resolution.

Config shape: an ordered `[[modules]]` array. Each entry has `kind`, optional
`name`, `enabled` (default true) and any kind-specific keys, including
`warn`/`crit`. Those are left in `ModuleSpec.options`; a module's constructor
consumes what it supports with the `take*` helpers, and the pipeline then
calls `done()`, which rejects any key left over. Errors are raised as
`ConfigError` and reported only for the module they belong to.
"""

from __future__ import annotations

import os
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from server_motd.model import Thresholds


class ConfigError(Exception):
    """Invalid configuration (file level or for a single module)."""


@dataclass
class ModuleSpec:
    kind: str
    name: str | None
    enabled: bool
    options: dict[str, Any] = field(default_factory=dict)

    def take(self, key: str, typ: type, default: Any = None) -> Any:
        """Pop an optional option, checking its type."""
        if key not in self.options:
            return default
        value = self.options.pop(key)
        if typ is float and isinstance(value, int) and not isinstance(value, bool):
            value = float(value)
        if not isinstance(value, typ) or (typ is not bool and isinstance(value, bool)):
            raise ConfigError(f"'{key}' must be {typ.__name__}")
        return value

    def take_secret(self, key: str) -> str | None:
        """Resolve a secret given inline, as `${ENV_VAR}`, or via `<key>_file`."""
        value = self.take(key, str)
        file_key = f"{key}_file"
        path = self.take(file_key, str)
        if value is not None and path is not None:
            raise ConfigError(f"set only one of '{key}' and '{file_key}'")
        if path is not None:
            try:
                return Path(path).read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise ConfigError(f"cannot read '{file_key}': {exc.strerror}") from exc
        if value is None:
            return None
        return _expand_env(value, key)

    def take_thresholds(self) -> Thresholds:
        """Take the optional `warn` / `crit` limits."""
        warn: float | None = self.take("warn", float)
        crit: float | None = self.take("crit", float)
        if warn is not None and crit is not None and warn > crit:
            raise ConfigError("'warn' must not exceed 'crit'")
        return Thresholds(warn, crit)

    def take_url(self) -> str:
        """Take the required `url` option, trailing slash stripped."""
        url = self.take("url", str)
        if not url:
            raise ConfigError("'url' is required")
        return str(url).rstrip("/")

    def done(self) -> None:
        if self.options:
            keys = ", ".join(sorted(self.options))
            raise ConfigError(f"unknown option(s): {keys}")


_ENV = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _expand_env(value: str, key: str) -> str:
    def sub(m: re.Match[str]) -> str:
        name = m.group(1)
        if name not in os.environ:
            raise ConfigError(f"'{key}' references unset variable {name}")
        return os.environ[name]

    return _ENV.sub(sub, value)


@dataclass
class BadEntry:
    """A `[[modules]]` entry too malformed to build a ModuleSpec from."""

    label: str
    message: str


def default_config_paths() -> list[Path]:
    if sys.platform == "win32":
        paths = []
        for var in ("APPDATA", "ProgramData"):
            if os.environ.get(var):
                paths.append(Path(os.environ[var]) / "server-motd" / "config.toml")
        return paths
    return [Path("/etc/server-motd/config.toml")]


@dataclass
class Settings:
    """Top-level (non-module) config keys: `title` and `box`."""

    title: str | None = None
    box: str = "single"


@dataclass
class Config:
    settings: Settings
    entries: list[ModuleSpec | BadEntry]


def load(path: Path | None) -> Config:
    """Find, read and parse the config once.

    File-level problems (no file, bad TOML, bad top-level types) raise
    ConfigError; a malformed module entry becomes a BadEntry instead.
    """
    data = _read(path)
    title, box = data.get("title"), data.get("box", "single")
    if title is not None and not isinstance(title, str):
        raise ConfigError("'title' must be a string")
    if not isinstance(box, str):
        raise ConfigError("'box' must be a string")
    entries = data.get("modules", [])
    if not isinstance(entries, list):
        raise ConfigError("'modules' must be an array of tables")
    return Config(Settings(title, box), [_parse_entry(e) for e in entries])


def _read(path: Path | None) -> dict[str, Any]:
    candidates = [path] if path else default_config_paths()
    for candidate in candidates:
        if candidate.is_file():
            chosen = candidate
            break
    else:
        shown = ", ".join(str(c) for c in candidates) or "(none)"
        raise ConfigError(f"no config file found (looked in {shown})")
    try:
        data = tomllib.loads(chosen.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"{chosen}: {exc}") from exc
    return data


def _parse_entry(entry: Any) -> ModuleSpec | BadEntry:
    if not isinstance(entry, dict):
        return BadEntry("?", "module entry must be a table")
    entry = dict(entry)
    kind = entry.pop("kind", None)
    name = entry.pop("name", None)
    enabled = entry.pop("enabled", True)
    label = name if isinstance(name, str) else (kind if isinstance(kind, str) else "?")
    if not isinstance(kind, str):
        return BadEntry(label, "'kind' is required and must be a string")
    if name is not None and not isinstance(name, str):
        return BadEntry(label, "'name' must be a string")
    if not isinstance(enabled, bool):
        return BadEntry(label, "'enabled' must be a boolean")
    return ModuleSpec(kind=kind, name=name, enabled=enabled, options=entry)
