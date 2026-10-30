"""System module: CPU utilisation percent (works everywhere; replaces load on Windows).

Thresholds apply to the utilisation percentage.
"""

from __future__ import annotations

import psutil

from server_motd.config import ModuleSpec
from server_motd.model import Result, Row
from server_motd.modules._common import Thresholds

SAMPLE_SECONDS = 0.2  # cpu_percent(None) reports a meaningless 0.0 on first call


class Cpu:
    def __init__(self, spec: ModuleSpec) -> None:
        self.title = spec.name or "CPU"
        self.limits = Thresholds(spec)
        spec.done()

    def fetch(self) -> Result:
        percent = psutil.cpu_percent(interval=SAMPLE_SECONDS)
        cores = psutil.cpu_count() or 1
        status = self.limits.status(percent)
        return Result(
            self.title, [Row("Usage", f"{percent:.0f}% ({cores} cores)", status)], status
        )
