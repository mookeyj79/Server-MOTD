"""System module: RAM (and swap, when present) usage. Thresholds on RAM percent."""

from __future__ import annotations

import psutil

from server_motd.config import ModuleSpec
from server_motd.model import Deadline, Result, Row, Status
from server_motd.modules._common import human_bytes


class Memory:
    def __init__(self, spec: ModuleSpec) -> None:
        self.limits = spec.take_thresholds()

    def fetch(self, deadline: Deadline) -> Result:
        mem = psutil.virtual_memory()
        rows = [
            Row(
                "Memory",
                f"{human_bytes(mem.used)} / {human_bytes(mem.total)} "
                f"({mem.percent:.0f}%)",
                self.limits.status(mem.percent),
            )
        ]
        swap = psutil.swap_memory()
        if swap.total:
            rows.append(
                Row(
                    "Swap",
                    f"{human_bytes(swap.used)} / {human_bytes(swap.total)} "
                    f"({swap.percent:.0f}%)",
                    Status.INFO,
                )
            )
        return Result(rows)
