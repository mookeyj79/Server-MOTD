"""System module: pending updates and reboot-required (Ubuntu).

Reads the files maintained by update-notifier-common (not packaged on
Debian): the updates-available summary and the reboot-required flag. Without
a readable, recognisable summary file the module is UNAVAILABLE, since the
pending count is unknown; the reason names the file and what is wrong with it.
"""

from __future__ import annotations

import re
from pathlib import Path

from server_motd.config import ModuleSpec
from server_motd.deadline import Deadline
from server_motd.failure import ModuleError
from server_motd.model import Result, Row, Status

UPDATES_FILE = "/var/lib/update-notifier/updates-available"
REBOOT_FILE = "/var/run/reboot-required"


def _count(text: str, pattern: str) -> int | None:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else None


class Updates:
    def __init__(self, spec: ModuleSpec) -> None:
        self.updates_file = Path(spec.take("updates_file", str, UPDATES_FILE))
        self.reboot_file = Path(spec.take("reboot_file", str, REBOOT_FILE))

    def fetch(self, deadline: Deadline) -> Result:
        text = self._read_updates_file()
        pending = _count(text, r"(\d+) updates? can be")
        if pending is None:
            raise ModuleError(f"unrecognised contents in {self.updates_file}")
        security = _count(text, r"(\d+) of these updates are") or 0
        rows = [
            Row(
                "Updates",
                f"{pending} pending" if pending else "up to date",
                Status.WARN if pending else Status.OK,
            )
        ]
        if security:
            rows.append(Row("Security", str(security), Status.CRIT))
        reboot = self.reboot_file.exists()
        rows.append(
            Row(
                "Reboot",
                "required" if reboot else "not required",
                Status.WARN if reboot else Status.OK,
            )
        )
        return Result(rows)

    def _read_updates_file(self) -> str:
        path = self.updates_file
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            raise ModuleError(
                f"{path} not found; is update-notifier-common installed?"
            ) from None
        except OSError as exc:
            raise ModuleError(f"cannot read {path}: {exc.strerror or exc}") from exc
        if not text.strip():
            raise ModuleError(f"{path} is empty")
        return text
