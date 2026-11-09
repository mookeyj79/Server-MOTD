"""Service module: qBittorrent (WebUI API v2).

Options: `url` (required), `username` and `password` (optional, for setups with
local auth bypass; `password` also accepts `${ENV}` or `password_file`).
Logs in on every run (the session's cookie jar carries whatever session
cookie the server sets, which differs across 4.x, 5.0 and 5.2) and makes one
`sync/maindata` call for rates and per-state torrent counts.
"""

from __future__ import annotations

from collections import Counter

from server_motd.config import ModuleSpec
from server_motd.failure import AuthFailed
from server_motd.model import Deadline, Result, Row, Status
from server_motd.modules._common import human_bytes
from server_motd.modules._http import Http, take_endpoint

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
    def __init__(self, spec: ModuleSpec) -> None:
        self.http = Http(take_endpoint(spec, "/api/v2"), auth_hint="login failed")
        self.username: str = spec.take("username", str, "")
        self.password: str = spec.take_secret("password") or ""

    def fetch(self, deadline: Deadline) -> Result:
        session = self.http.session(deadline)
        creds = {"username": self.username, "password": self.password}
        if session.post_form("/auth/login", creds).strip() == "Fails.":
            raise AuthFailed("bad credentials")
        data = session.get_json("/sync/maindata")
        state = data["server_state"]
        counts = Counter(t["state"] for t in data.get("torrents", {}).values())
        rows = [
            Row("Down", f"{human_bytes(state['dl_info_speed'])}/s"),
            Row("Up", f"{human_bytes(state['up_info_speed'])}/s"),
        ]
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
        return Result(rows)
