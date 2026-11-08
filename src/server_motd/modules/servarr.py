"""Service modules: Sonarr, Radarr and Lidarr (the Servarr family).

Options: `url` and `api_key` (required; `api_key` also accepts `${ENV}` or
`api_key_file`), `warn` / `crit` (Missing count thresholds; Missing only),
`calendar_days` (default 7). Only cheap endpoints are called, concurrently:
`/queue/status`, `/wanted/missing?pageSize=1`, `/health`, `/calendar`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from server_motd.config import ModuleSpec
from server_motd.model import Deadline, Result, Row, Status, worst
from server_motd.modules._http import Http, take_url_and_key


class Servarr:
    api_prefix = "/api/v3"
    calendar_params: dict[str, str] = {}

    def __init__(self, spec: ModuleSpec) -> None:
        url, key = take_url_and_key(spec)
        self.http = Http(url + self.api_prefix, headers={"X-Api-Key": key})
        self.thresholds = spec.take_thresholds()
        self.days: int = spec.take("calendar_days", int, 7)

    def fetch(self, deadline: Deadline) -> Result:
        now = datetime.now(UTC)
        window = {
            "start": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": (now + timedelta(days=self.days)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            **self.calendar_params,
        }
        s = self.http.session(deadline)

        def calendar() -> Any:
            try:
                return s.get_json("/calendar", **window)
            except Exception:  # the calendar is optional
                return None

        queue, missing, health, upcoming = s.gather(
            lambda: s.get_json("/queue/status"),
            lambda: s.get_json("/wanted/missing", pageSize="1"),
            lambda: s.get_json("/health"),
            calendar,
        )
        rows = [
            self._queue_row(queue),
            self._missing_row(missing),
            self._health_row(health),
        ]
        if isinstance(upcoming, list):
            rows.append(Row("Upcoming", str(len(upcoming))))
        return Result(rows, worst(rows))

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
        # Missing stays neutral when no threshold is hit.
        return Row("Missing", str(count), self.thresholds.status(count, Status.INFO))

    @staticmethod
    def _health_row(data: list[dict[str, Any]]) -> Row:
        issues = [h for h in data if h.get("type") in ("warning", "error")]
        if not issues:
            return Row("Health", "OK", Status.OK)
        crit = any(h["type"] == "error" for h in issues)
        message = "; ".join(str(h["message"]) for h in issues)
        return Row("Health", message, Status.CRIT if crit else Status.WARN)


class Sonarr(Servarr):
    calendar_params = {"includeSeries": "true"}


class Radarr(Servarr):
    pass


class Lidarr(Servarr):
    api_prefix = "/api/v1"
    calendar_params = {"includeArtist": "true"}
