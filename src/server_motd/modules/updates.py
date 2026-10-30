"""System module: pending updates and reboot-required (Debian family).

Reads the files maintained by update-notifier-common: the updates-available
summary and the reboot-required flag. Without the summary file the module is
UNAVAILABLE, since the pending count is unknown.
"""

from __future__ import annotations

import re
from pathlib import Path

from server_motd.config import ModuleSpec
from server_motd.model import Result, Row, Status

UPDATES_FILE = "/var/lib/update-notifier/updates-available"
REBOOT_FILE = "/var/run/reboot-required"


def _count(text: str, pattern: str) -> int | None:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else None


class Updates:
    def __init__(self, spec: ModuleSpec) -> None:
        self.title = spec.name or "Updates"
        self.updates_file = Path(spec.take("updates_file", str, UPDATES_FILE))
        self.reboot_file = Path(spec.take("reboot_file", str, REBOOT_FILE))
        spec.done()

    def fetch(self) -> Result:
        text = self.updates_file.read_text(encoding="utf-8")
        pending = _count(text, r"(\d+) updates? can be")
        if pending is None:
            raise ValueError(f"cannot parse {self.updates_file}")
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
        return Result(self.title, rows, max((r.status for r in rows), key=_rank))


_ORDER = [Status.INFO, Status.OK, Status.WARN, Status.CRIT]


def _rank(s: Status) -> int:
    return _ORDER.index(s)
