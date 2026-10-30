"""System module: usage per mounted filesystem. Thresholds on percent used."""

from __future__ import annotations

import psutil

from server_motd.config import ModuleSpec
from server_motd.model import Result, Row
from server_motd.modules._common import Thresholds, human_bytes, worst


class Disks:
    def __init__(self, spec: ModuleSpec) -> None:
        self.title = spec.name or "Disks"
        self.limits = Thresholds(spec)
        spec.done()

    def fetch(self) -> Result:
        rows = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except OSError:
                continue  # unreadable mount (e.g. empty drive): not worth a row
            value = (
                f"{human_bytes(usage.used)} / {human_bytes(usage.total)} "
                f"({usage.percent:.0f}%)"
            )
            rows.append(Row(part.mountpoint, value, self.limits.status(usage.percent)))
        if not rows:
            raise RuntimeError("no mounted filesystems found")
        return Result(self.title, rows, worst(rows))
