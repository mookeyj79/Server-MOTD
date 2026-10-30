"""System module: logged-in sessions. Thresholds on the session count."""

from __future__ import annotations

import psutil

from server_motd.config import ModuleSpec
from server_motd.model import Result, Row, Status
from server_motd.modules._common import Thresholds


class Logins:
    def __init__(self, spec: ModuleSpec) -> None:
        self.title = spec.name or "Logins"
        self.limits = Thresholds(spec)
        spec.done()

    def fetch(self) -> Result:
        users = psutil.users()
        status = self.limits.status(len(users))
        if not users:
            return Result(self.title, [Row("Sessions", "none", status)], status)
        rows = []
        for u in users:
            where = u.terminal or "-"
            if u.host:
                where += f" ({u.host})"
            rows.append(Row(u.name, where, Status.INFO))
        return Result(self.title, rows, status)
