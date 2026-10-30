"""Service module: SABnzbd.

Options: `url` and `api_key` (required; `api_key` also accepts `${ENV}` or
`api_key_file`). Two concurrent GETs to `/api` with the key as a query
parameter: `mode=queue` (speed, jobs, remaining) and `mode=server_stats`
(lifetime total). Speeds and sizes are shown in bytes (1024-based units).
"""

from __future__ import annotations

import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from server_motd.config import ModuleSpec
from server_motd.model import Result, Row, Status
from server_motd.modules import _http
from server_motd.modules._common import human_bytes


class Sabnzbd:
    def __init__(self, spec: ModuleSpec) -> None:
        self.title = spec.name or "SABnzbd"
        url, self.key = _http.take_url_and_key(spec)
        self.base = url + "/api"
        spec.done()

    def _get(self, mode: str) -> dict[str, Any]:
        query = urllib.parse.urlencode(
            {"mode": mode, "output": "json", "apikey": self.key}
        )
        data = _http.get_json(f"{self.base}?{query}")
        if not isinstance(data, dict):
            raise RuntimeError("bad response: not a JSON object")
        if data.get("status") is False:
            raise RuntimeError(str(data.get("error") or "API error"))
        return data

    def fetch(self) -> Result:
        with ThreadPoolExecutor(max_workers=2) as pool:
            queue = pool.submit(self._get, "queue")
            stats = pool.submit(self._get, "server_stats")
            q = queue.result()["queue"]
            total = int(stats.result()["total"])
        speed = float(q["kbpersec"]) * 1024
        jobs = int(q["noofslots_total"])
        if jobs:
            left = float(q["mbleft"]) * 1024 * 1024
            queue_value = f"{jobs} jobs, {human_bytes(left)} left"
        else:
            queue_value = "empty"
        if q.get("paused"):
            queue_value += " (paused)"
        rows = [
            Row("Speed", f"{human_bytes(speed)}/s"),
            Row("Queue", queue_value),
            Row("Total", human_bytes(total)),
        ]
        return Result(self.title, rows, Status.INFO)
