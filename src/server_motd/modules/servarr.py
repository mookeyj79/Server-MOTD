"""Service modules: Sonarr, Radarr and Lidarr (the Servarr family).

Options: `url` and `api_key` (required; `api_key` also accepts `${ENV}` or
`api_key_file`), `warn` / `crit` (Missing count thresholds; Missing only),
`calendar_days` (default 7). Only cheap endpoints are called, concurrently:
`/queue/status`, `/wanted/missing?pageSize=1`, `/health`, `/calendar`.
"""

from __future__ import annotations

import contextlib
import json
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

from server_motd.config import ConfigError, ModuleSpec
from server_motd.model import Result, Row, Status

REQUEST_TIMEOUT = 2.5
_ORDER = [Status.INFO, Status.OK, Status.WARN, Status.CRIT, Status.UNAVAILABLE]


class Servarr:
    default_title = "Servarr"
    api_prefix = "/api/v3"
    calendar_params: dict[str, str] = {}

    def __init__(self, spec: ModuleSpec) -> None:
        self.title = spec.name or self.default_title
        url = spec.take("url", str)
        key = spec.take_secret("api_key")
        if not url:
            raise ConfigError("'url' is required")
        if not key:
            raise ConfigError("'api_key' is required")
        self.base = url.rstrip("/") + self.api_prefix
        self.key = key
        self.warn: int | None = spec.take("warn", int)
        self.crit: int | None = spec.take("crit", int)
        self.days: int = spec.take("calendar_days", int, 7)
        spec.done()

    def _get(self, path: str, **params: str) -> Any:
        url = f"{self.base}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"X-Api-Key": self.key})
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise RuntimeError(f"bad API key (HTTP {exc.code})") from exc
            raise RuntimeError(f"HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"unreachable: {exc.reason}") from exc
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"bad response: {exc}") from exc

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
        status = max((r.status for r in rows), key=_ORDER.index)
        return Result(self.title, rows, status)

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
        status = Status.INFO
        if self.crit is not None and count >= self.crit:
            status = Status.CRIT
        elif self.warn is not None and count >= self.warn:
            status = Status.WARN
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
