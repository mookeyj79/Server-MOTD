"""Service module: SABnzbd.

Options: `url` and `api_key` (required; `api_key` also accepts `${ENV}` or
`api_key_file`). Two concurrent GETs to `/api` with the key as a query
parameter: `mode=queue` (speed, jobs, remaining) and `mode=server_stats`
(lifetime total). Speeds and sizes are shown in bytes (1024-based units).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from server_motd.config import ConfigError, ModuleSpec
from server_motd.model import Result, Row, Status
from server_motd.modules._common import human_bytes

REQUEST_TIMEOUT = 2.5


class Sabnzbd:
    def __init__(self, spec: ModuleSpec) -> None:
        self.title = spec.name or "SABnzbd"
        url = spec.take("url", str)
        key = spec.take_secret("api_key")
        if not url:
            raise ConfigError("'url' is required")
        if not key:
            raise ConfigError("'api_key' is required")
        self.base = url.rstrip("/") + "/api"
        self.key = key
        spec.done()

    def _get(self, mode: str) -> dict[str, Any]:
        query = urllib.parse.urlencode(
            {"mode": mode, "output": "json", "apikey": self.key}
        )
        try:
            with urllib.request.urlopen(
                f"{self.base}?{query}", timeout=REQUEST_TIMEOUT
            ) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise RuntimeError(f"bad API key (HTTP {exc.code})") from exc
            raise RuntimeError(f"HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"unreachable: {exc.reason}") from exc
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"bad response: {exc}") from exc
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
