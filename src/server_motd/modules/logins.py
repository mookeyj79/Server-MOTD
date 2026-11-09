"""System module: logged-in sessions.

Thresholds on the session count colour every session row (or the "none" row).
"""

from __future__ import annotations

import psutil

from server_motd.config import ModuleSpec
from server_motd.model import Deadline, Result, Row


class Logins:
    def __init__(self, spec: ModuleSpec) -> None:
        self.limits = spec.take_thresholds()

    def fetch(self, deadline: Deadline) -> Result:
        users = psutil.users()
        status = self.limits.status(len(users))
        if not users:
            return Result([Row("Sessions", "none", status)])
        rows = []
        for u in users:
            where = u.terminal or "-"
            if u.host:
                where += f" ({u.host})"
            rows.append(Row(u.name, where, status))
        return Result(rows)
