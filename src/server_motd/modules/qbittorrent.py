"""Service module: qBittorrent (WebUI API v2).

Options: `url` (required), `username` and `password` (optional, for setups with
local auth bypass; `password` also accepts `${ENV}` or `password_file`).
Logs in on every run (the cookie jar carries whatever session cookie the
server sets, which differs across 4.x, 5.0 and 5.2) and makes one
`sync/maindata` call for rates and per-state torrent counts.
"""

from __future__ import annotations

import http.cookiejar
import json
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from typing import Any

from server_motd.config import ConfigError, ModuleSpec
from server_motd.model import Result, Row, Status
from server_motd.modules._common import human_bytes, worst

REQUEST_TIMEOUT = 2.5

# State names differ between 4.x (paused*) and 5.x (stopped*).
_BUCKETS = {
    "Downloading": {
        "downloading", "metaDL", "forcedMetaDL", "forcedDL",
        "stalledDL", "queuedDL", "checkingDL",
    },
    "Seeding": {"uploading", "forcedUP", "stalledUP", "queuedUP", "checkingUP"},
    "Stopped": {"stoppedUP", "stoppedDL", "pausedUP", "pausedDL"},
    "Error": {"error", "missingFiles"},
}  # fmt: skip


class QBittorrent:
    default_title = "qBittorrent"

    def __init__(self, spec: ModuleSpec) -> None:
        self.title = spec.name or self.default_title
        url = spec.take("url", str)
        if not url:
            raise ConfigError("'url' is required")
        self.base = url.rstrip("/") + "/api/v2"
        self.username: str = spec.take("username", str, "")
        self.password: str = spec.take_secret("password") or ""
        spec.done()

    def _open(
        self, opener: urllib.request.OpenerDirector, path: str, data: Any = None
    ) -> str:
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        try:
            with opener.open(self.base + path, body, timeout=REQUEST_TIMEOUT) as resp:
                return str(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise RuntimeError(f"login failed (HTTP {exc.code})") from exc
            raise RuntimeError(f"HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"unreachable: {exc.reason}") from exc
        except OSError as exc:
            raise RuntimeError(f"bad response: {exc}") from exc

    def fetch(self) -> Result:
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        creds = {"username": self.username, "password": self.password}
        if self._open(opener, "/auth/login", creds).strip() == "Fails.":
            raise RuntimeError("login failed (bad credentials)")
        try:
            data = json.loads(self._open(opener, "/sync/maindata"))
            state = data["server_state"]
            counts = Counter(t["state"] for t in data["torrents"].values())
            rows = [
                Row("Down", f"{human_bytes(state['dl_info_speed'])}/s"),
                Row("Up", f"{human_bytes(state['up_info_speed'])}/s"),
            ]
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise RuntimeError(f"bad response: {exc}") from exc
        known = set().union(*_BUCKETS.values())
        for label, states in _BUCKETS.items():
            n = sum(counts[s] for s in states)
            if label == "Error" and n:
                rows.append(Row(label, str(n), Status.CRIT))
            elif label != "Error":
                rows.append(Row(label, str(n)))
        other = sum(n for s, n in counts.items() if s not in known)
        if other:
            rows.append(Row("Other", str(other)))
        return Result(self.title, rows, worst(rows))
