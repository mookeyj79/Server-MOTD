"""Service modules: Sonarr, Radarr and Lidarr (the Servarr family).

Options: `url` and `api_key` (required; `api_key` also accepts `${ENV}` or
`api_key_file`), `warn` / `crit` (Missing count thresholds; Missing only),
`calendar_days` (default 7). Only cheap endpoints are called, concurrently:
`/queue/status`, `/wanted/missing?pageSize=1`, `/health`, `/calendar`.
"""

from __future__ import annotations

import contextlib
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

from server_motd.config import ModuleSpec
from server_motd.model import Result, Row, Status
from server_motd.modules import _http
from server_motd.modules._common import Thresholds, worst


class Servarr:
    default_title = "Servarr"
    api_prefix = "/api/v3"
    calendar_params: dict[str, str] = {}

    def __init__(self, spec: ModuleSpec) -> None:
        self.title = spec.name or self.default_title
        url, self.key = _http.take_url_and_key(spec)
        self.base = url + self.api_prefix
        self.thresholds = Thresholds(spec)
        self.days: int = spec.take("calendar_days", int, 7)
        spec.done()

    def _get(self, path: str, **params: str) -> Any:
        url = f"{self.base}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"X-Api-Key": self.key})
        return _http.get_json(req)

    def fetch(self) -> Result:
        now = datetime.now(UTC)
        window = {
            "start": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": (now + timedelta(days=self.days)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            **self.calendar_params,
        }
        with ThreadPoolExecutor(max_workers=4) as pool:
            queue = pool.submit(self._get, "/queue/status")
            missing = pool.submit(self._get, "/wanted/missing", pageSize="1")
            health = pool.submit(self._get, "/health")
            calendar = pool.submit(self._get, "/calendar", **window)
            rows = [
                self._queue_row(queue.result()),
                self._missing_row(missing.result()),
                self._health_row(health.result()),
            ]
            with contextlib.suppress(Exception):  # the calendar is optional
                rows.append(Row("Upcoming", str(len(calendar.result()))))
        return Result(self.title, rows, worst(rows))

    @staticmethod
    def _queue_row(data: dict[str, Any]) -> Row:
        value = str(data["totalCount"])
        if data.get("errors") or data.get("unknownErrors"):
            value += " (errors)"
        elif data.get("warnings") or data.get("unknownWarnings"):
            value += " (warnings)"
        return Row("Queue", value)

    def _missing_row(self, data: dict[str, Any]) -> Row:
        count = int(data["totalRecords"])
        status = self.thresholds.status(count)
        if status is Status.OK:  # Missing stays neutral when no threshold is hit
            status = Status.INFO
        return Row("Missing", str(count), status)

    @staticmethod
    def _health_row(data: list[dict[str, Any]]) -> Row:
        issues = [h for h in data if h.get("type") in ("warning", "error")]
        if not issues:
            return Row("Health", "OK", Status.OK)
        crit = any(h["type"] == "error" for h in issues)
        message = "; ".join(str(h["message"]) for h in issues)
        return Row("Health", message, Status.CRIT if crit else Status.WARN)


class Sonarr(Servarr):
    default_title = "Sonarr"
    calendar_params = {"includeSeries": "true"}


class Radarr(Servarr):
    default_title = "Radarr"


class Lidarr(Servarr):
    default_title = "Lidarr"
    api_prefix = "/api/v1"
    calendar_params = {"includeArtist": "true"}
