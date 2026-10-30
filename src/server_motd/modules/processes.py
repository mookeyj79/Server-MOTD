"""System module: process count. Thresholds on the count."""

from __future__ import annotations

import psutil

from server_motd.config import ModuleSpec
from server_motd.model import Result, Row
from server_motd.modules._common import Thresholds


class Processes:
    def __init__(self, spec: ModuleSpec) -> None:
        self.title = spec.name or "Processes"
        self.limits = Thresholds(spec)
        spec.done()

    def fetch(self) -> Result:
        count = len(psutil.pids())
        status = self.limits.status(count)
        return Result(self.title, [Row("Processes", str(count), status)], status)
