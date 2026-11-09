"""System module: process count. Thresholds on the count."""

from __future__ import annotations

import psutil

from server_motd.config import ModuleSpec
from server_motd.model import Deadline, Result, Row


class Processes:
    def __init__(self, spec: ModuleSpec) -> None:
        self.limits = spec.take_thresholds()

    def fetch(self, deadline: Deadline) -> Result:
        count = len(psutil.pids())
        status = self.limits.status(count)
        return Result([Row("Processes", str(count), status)])
