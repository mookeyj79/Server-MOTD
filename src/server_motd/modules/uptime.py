"""System module: time since boot."""

from __future__ import annotations

import time

import psutil

from server_motd.config import ModuleSpec
from server_motd.deadline import Deadline
from server_motd.model import Result, Row


def format_duration(seconds: float) -> str:
    total = int(seconds)
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    parts = []
    if days:
        parts.append(f"{days}d")
    if days or hours:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


class Uptime:
    def __init__(self, spec: ModuleSpec) -> None:
        pass  # no options

    def fetch(self, deadline: Deadline) -> Result:
        seconds = time.time() - psutil.boot_time()
        return Result([Row("Uptime", format_duration(seconds))])
