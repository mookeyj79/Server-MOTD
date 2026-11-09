"""Service module: SABnzbd.

Options: `url` and `api_key` (required; `api_key` also accepts `${ENV}` or
`api_key_file`). Two concurrent GETs to `/api` with the key as a query
parameter: `mode=queue` (speed, jobs, remaining) and `mode=server_stats`
(lifetime total). Speeds and sizes are shown in bytes (1024-based units).
"""

from __future__ import annotations

from typing import Any

from server_motd.config import ModuleSpec
from server_motd.deadline import Deadline
from server_motd.failure import ApiError, BadResponse
from server_motd.model import Result, Row
from server_motd.modules._common import human_bytes
from server_motd.modules._http import Http, take_endpoint_and_key


def _unwrap(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise BadResponse("not a JSON object")
    if data.get("status") is False:
        raise ApiError(str(data.get("error") or ""))
    return data


class Sabnzbd:
    def __init__(self, spec: ModuleSpec) -> None:
        base, key = take_endpoint_and_key(spec, "/api")
        self.http = Http(base, params={"output": "json", "apikey": key}, unwrap=_unwrap)

    def fetch(self, deadline: Deadline) -> Result:
        s = self.http.session(deadline)
        queue, stats = deadline.gather(
            lambda: s.get_json(mode="queue"),
            lambda: s.get_json(mode="server_stats"),
        )
        q = queue["queue"]
        total = int(stats["total"])
        speed = float(q["kbpersec"]) * 1024
        jobs = int(q["noofslots_total"])
        if jobs:
            left = float(q["mbleft"]) * 1024 * 1024
            queue_value = f"{jobs} jobs, {human_bytes(left)} left"
        else:
            queue_value = "empty"
        if q.get("paused"):
            queue_value += " (paused)"
        return Result(
            [
                Row("Speed", f"{human_bytes(speed)}/s"),
                Row("Queue", queue_value),
                Row("Total", human_bytes(total)),
            ]
        )
