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

from typing import Any

from server_motd.config import ModuleSpec
from server_motd.failure import ApiError, BadResponse
from server_motd.model import Deadline, Result, Row, Status
from server_motd.modules._http import Http, take_endpoint_and_key

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


def _unwrap(body: Any) -> Any:
    response = body["response"]
    if response["result"] != "success":
        raise ApiError(str(response.get("message") or ""))
    return response["data"]


class Tautulli:
    def __init__(self, spec: ModuleSpec) -> None:
        base, key = take_endpoint_and_key(spec, "/api/v2")
        self.http = Http(base, headers={"X-Api-Key": key}, unwrap=_unwrap)

    def fetch(self, deadline: Deadline) -> Result:
        s = self.http.session(deadline)
        data, status = s.gather(
            lambda: s.get_json(cmd="get_activity"),
            lambda: s.get_json(cmd="server_status"),
        )
        connected = status.get("connected")
        if connected is False:
            return Result([Row("Plex", "down", Status.CRIT)])
        rows = [Row("Plex", "up", Status.OK)] if connected else []
        if "stream_count_transcode" not in data:
            raise BadResponse("empty get_activity reply")
        counts = [int(data[key]) for key, _ in _COUNTS]
        bandwidth = int(data["total_bandwidth"])
        total = sum(counts)
        detail = ", ".join(
            f"{n} {name}" for n, (_, name) in zip(counts, _COUNTS, strict=True) if n
        )
        rows.append(Row("Streams", f"{total} ({detail})" if detail else str(total)))
        rows.append(Row("Bandwidth", format_kbps(bandwidth)))
        return Result(rows)
