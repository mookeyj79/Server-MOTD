"""Service module: Tautulli (Plex activity).

Options: `url` and `api_key` (required; `api_key` also accepts `${ENV}` or
`api_key_file`). One `get_activity` call gives Streams and Bandwidth;
`server_status` gives Plex connectivity (Plex down is crit). An empty
`get_activity` reply while Plex is up is an error, not "no streams".
The key is sent in the `X-Api-Key` header (Tautulli 2.18+).

Bandwidth: Tautulli sums Plex's per-session `bandwidth`, which Plex reports in
kilobits per second. Tautulli does not document the unit; this is unverified
against a live instance (docs/research/tautulli-api.md).
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

REQUEST_TIMEOUT = 5.0
_COUNTS = (
    ("stream_count_direct_play", "direct play"),
    ("stream_count_direct_stream", "direct stream"),
    ("stream_count_transcode", "transcode"),
)


def format_kbps(kbps: int) -> str:
    if kbps < 1000:
        return f"{kbps} kbps"
    if kbps < 1_000_000:
        return f"{kbps / 1000:.1f} Mbps"
    return f"{kbps / 1_000_000:.1f} Gbps"


class Tautulli:
    default_title = "Tautulli"

    def __init__(self, spec: ModuleSpec) -> None:
        self.title = spec.name or self.default_title
        url = spec.take("url", str)
        key = spec.take_secret("api_key")
        if not url:
            raise ConfigError("'url' is required")
        if not key:
            raise ConfigError("'api_key' is required")
        self.base = url.rstrip("/") + "/api/v2"
        self.key = key
        spec.done()

    def _call(self, cmd: str) -> Any:
        req = urllib.request.Request(
            f"{self.base}?{urllib.parse.urlencode({'cmd': cmd})}",
            headers={"X-Api-Key": self.key},
        )
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                body = json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise RuntimeError(f"bad API key (HTTP {exc.code})") from exc
            raise RuntimeError(f"HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"unreachable: {exc.reason}") from exc
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"bad response: {exc}") from exc
        try:
            response = body["response"]
            if response["result"] != "success":
                raise RuntimeError(f"API error: {response.get('message')}")
            return response["data"]
        except (KeyError, TypeError) as exc:
            raise RuntimeError("bad response: unexpected shape") from exc

    def fetch(self) -> Result:
        with ThreadPoolExecutor(max_workers=2) as pool:
            activity = pool.submit(self._call, "get_activity")
            status = pool.submit(self._call, "server_status")
            connected = status.result().get("connected")
            data = activity.result()
        if connected is False:
            return Result(self.title, [Row("Plex", "down", Status.CRIT)], Status.CRIT)
        rows = [Row("Plex", "up", Status.OK)] if connected else []
        if "stream_count_transcode" not in data:
            raise RuntimeError("empty get_activity reply")
        try:
            counts = [int(data[key]) for key, _ in _COUNTS]
            bandwidth = int(data["total_bandwidth"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("bad response: unexpected activity fields") from exc
        total = sum(counts)
        detail = ", ".join(
            f"{n} {name}" for n, (_, name) in zip(counts, _COUNTS, strict=True) if n
        )
        rows.append(Row("Streams", f"{total} ({detail})" if detail else str(total)))
        rows.append(Row("Bandwidth", format_kbps(bandwidth)))
        return Result(self.title, rows, Status.OK if connected else Status.INFO)
