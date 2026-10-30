"""PowerShell profile install and uninstall (marker-delimited block, byte-safe).

Edits are done on bytes: the file's BOM/encoding and newline style are kept,
and nothing outside the markers is touched. The generated block is pure ASCII
so both PowerShell 7 and 5.1 read it identically. `discover()` is the boundary
to the real machine (it asks each installed PowerShell edition); tests
monkeypatch `server_motd.profile.discover`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

START = "# >>> server-motd >>>"
END = "# <<< server-motd <<<"
_BODY = (
    "if ($Host.Name -eq 'ConsoleHost' -and "
    "(Get-Command server-motd -ErrorAction SilentlyContinue)) { server-motd }"
)
_BOMS: tuple[tuple[bytes, str], ...] = (
    (b"\xef\xbb\xbf", "utf-8"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
)


class ProfileError(Exception):
    """A profile cannot be safely edited."""


@dataclass
class Environment:
    """Current-user profile files by edition label, plus effective policies."""

    profiles: dict[str, Path] = field(default_factory=dict)
    policies: dict[str, str] = field(default_factory=dict)


def discover() -> Environment:
    """Ask each installed PowerShell edition for its profile path and policy."""
    env = Environment()
    command = "$PROFILE.CurrentUserCurrentHost; Get-ExecutionPolicy"
    editions = (("PowerShell 7", "pwsh"), ("Windows PowerShell 5.1", "powershell"))
    for label, exe in editions:
        found = shutil.which(exe)
        if not found:
            continue
        try:
            out = subprocess.run(
                [found, "-NoProfile", "-Command", command],
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            ).stdout.splitlines()
        except (OSError, subprocess.SubprocessError):
            continue
        lines = [line.strip() for line in out if line.strip()]
        if lines:
            env.profiles[label] = Path(lines[0])
            if len(lines) > 1:
                env.policies[label] = lines[1]
    return env


def _split(data: bytes) -> tuple[bytes, str, str]:
    for bom, codec in _BOMS:
        if data.startswith(bom):
            return bom, codec, data[len(bom) :].decode(codec)
    return b"", "latin-1", data.decode("latin-1")  # byte-preserving


def _newline(text: str) -> str:
    if "\r\n" in text:
        return "\r\n"
    return "\n" if "\n" in text else "\r\n"


def _span(text: str, path: Path) -> tuple[int, int] | None:
    """Return (start, end) of the block incl. its trailing newline, or None."""
    s = text.find(START)
    e = text.find(END)
    if s == -1 and e == -1:
        return None
    if s == -1 or e == -1 or e < s or text.count(START) > 1 or text.count(END) > 1:
        raise ProfileError(
            f"{path}: unmatched server-motd markers; fix the file by hand"
        )
    end = e + len(END)
    for nl in ("\r\n", "\n"):
        if text.startswith(nl, end):
            end += len(nl)
            break
    return s, end


def _write(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".server-motd.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _install_one(path: Path) -> str:
    exists = path.exists()
    bom, codec, text = _split(path.read_bytes() if exists else b"")
    nl = _newline(text)
    block = f"{START}{nl}{_BODY}{nl}{END}{nl}"
    span = _span(text, path)
    if span:
        new = text[: span[0]] + block + text[span[1] :]
    else:
        new = text + (nl if text else "") + block
    if exists and new == text:
        return "already installed"
    path.parent.mkdir(parents=True, exist_ok=True)
    _write(path, bom + new.encode(codec))
    return "updated" if span else "installed"


def _uninstall_one(path: Path) -> str:
    if not path.exists():
        return "not installed"
    bom, codec, text = _split(path.read_bytes())
    span = _span(text, path)
    if span is None:
        return "not installed"
    start = span[0]
    for nl in ("\r\n", "\n"):  # the separator install added before the block
        if start and text.endswith(nl, 0, start):
            start -= len(nl)
            break
    new = text[:start] + text[span[1] :]
    if not new and not bom:
        path.unlink()
        return "removed (file deleted, it held only the block)"
    _write(path, bom + new.encode(codec))
    return "removed"


def run(action: str) -> int:
    """Run `install-profile` or `uninstall-profile`. Returns the exit code."""
    env = discover()
    if not env.profiles:
        print("server-motd: no PowerShell found; nothing to do", file=sys.stderr)
        return 1
    code = 0
    install = action == "install-profile"
    for label, path in env.profiles.items():
        try:
            result = (_install_one if install else _uninstall_one)(path)
            print(f"{label}: {path}: {result}")
        except (ProfileError, OSError) as exc:
            print(f"server-motd: {label}: {exc}", file=sys.stderr)
            code = 1
        if install and env.policies.get(label, "").lower() == "restricted":
            print(
                f"server-motd: warning: {label} execution policy is Restricted, so its "
                "profile will not run. Run: "
                "Set-ExecutionPolicy -Scope CurrentUser RemoteSigned",
                file=sys.stderr,
            )
    return code
