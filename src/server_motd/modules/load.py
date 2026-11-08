"""System module: load average (Linux only; Windows uses the cpu module).

Thresholds apply to the 1-minute load average divided by the CPU count.
"""

from __future__ import annotations

import sys

import psutil

from server_motd.config import ConfigError, ModuleSpec
from server_motd.model import Deadline, Result, Row


class Load:
    def __init__(self, spec: ModuleSpec) -> None:
        self.limits = spec.take_thresholds()
        if sys.platform == "win32":
            raise ConfigError("load is not available on Windows; use the cpu module")

    def fetch(self, deadline: Deadline) -> Result:
        one, five, fifteen = psutil.getloadavg()
        per_core = one / (psutil.cpu_count() or 1)
        status = self.limits.status(per_core)
        value = f"{one:.2f} {five:.2f} {fifteen:.2f}"
        return Result([Row("Load", value, status)], status)
