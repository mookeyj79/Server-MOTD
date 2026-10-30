"""Jinja filter rendering one structured dict as the server-motd TOML config."""

from __future__ import annotations

import json
import re
from typing import Any

_BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")


def _key(key: Any) -> str:
    key = str(key)
    return key if _BARE_KEY.match(key) else _string(key)


def _string(value: str) -> str:
    # JSON escapes are a subset of TOML basic-string escapes; DEL needs adding.
    return json.dumps(value, ensure_ascii=False).replace("\x7f", "\u007f")


def _scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, dict):
        inner = ", ".join(f"{_key(k)} = {_scalar(v)}" for k, v in value.items())
        return "{ " + inner + " }" if inner else "{}"
    if isinstance(value, list | tuple):
        return "[" + ", ".join(_scalar(v) for v in value) + "]"
    # str and str-like (e.g. decrypted ansible-vault values)
    return _string(str(value))


def _is_table_array(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(v, dict) for v in value)


def _emit_table(header: str, data: dict[str, Any], lines: list[str]) -> None:
    subtables: list[tuple[str, Any]] = []
    for k, v in data.items():
        if v is None:
            continue
        if isinstance(v, dict) or _is_table_array(v):
            subtables.append((k, v))
        else:
            lines.append(f"{_key(k)} = {_scalar(v)}")
    for k, v in subtables:
        path = f"{header}.{_key(k)}" if header else _key(k)
        if isinstance(v, dict):
            lines.extend(["", f"[{path}]"])
            _emit_table(path, v, lines)
        else:
            for item in v:
                lines.extend(["", f"[[{path}]]"])
                _emit_table(path, item, lines)


def to_server_motd_toml(config: Any) -> str:
    """Render a dict (top-level keys plus a `modules` list) as TOML text."""
    if not isinstance(config, dict):
        raise TypeError("server_motd_config must be a dict")
    lines: list[str] = []
    _emit_table("", config, lines)
    return "\n".join(lines).lstrip("\n") + "\n"


class FilterModule:
    def filters(self) -> dict[str, Any]:
        return {"server_motd_toml": to_server_motd_toml}
