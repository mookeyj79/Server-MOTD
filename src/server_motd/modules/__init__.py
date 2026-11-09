"""Module registry. Extension conventions for adding a module kind:

1. Create one file, `modules/<kind>.py`, defining a class with
   `__init__(self, spec: ModuleSpec)` (read options with `spec.take*`; raise
   `ConfigError` for bad config; the pipeline rejects leftover options) and
   `fetch(self, deadline: Deadline) -> Result` (rows only, each with its own
   status; raise on failure, a `failure.ModuleError` subclass when the kind is
   known). HTTP services use `_http.Http`, which applies the deadline.
2. Add ONE import and ONE line to `REGISTRY` below:
   `"<kind>": Kind(<kind>.Class, "<Display title>"),`.
   Keep entries alphabetical so parallel tickets merge cleanly.
3. Test through `report.collect` for outcomes (status, failure kind, reason)
   and through the CLI (tests/conftest.py `run_cli`, `write_config`,
   `assert_golden`) for rendered output. Pin anything non-deterministic at the
   boundary it comes from (e.g. monkeypatch `psutil` / `time`), not inside the
   module.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import NamedTuple

from server_motd.config import ModuleSpec
from server_motd.model import Module
from server_motd.modules import (
    cpu,
    disks,
    ips,
    load,
    logins,
    memory,
    processes,
    qbittorrent,
    rtorrent,
    sabnzbd,
    servarr,
    tautulli,
    updates,
    uptime,
)


class Kind(NamedTuple):
    factory: Callable[[ModuleSpec], Module]
    title: str  # shown when the Instance has no `name`


REGISTRY: dict[str, Kind] = {
    "cpu": Kind(cpu.Cpu, "CPU"),
    "disks": Kind(disks.Disks, "Disks"),
    "ips": Kind(ips.Ips, "IPs"),
    "lidarr": Kind(servarr.Lidarr, "Lidarr"),
    "load": Kind(load.Load, "Load"),
    "logins": Kind(logins.Logins, "Logins"),
    "memory": Kind(memory.Memory, "Memory"),
    "processes": Kind(processes.Processes, "Processes"),
    "qbittorrent": Kind(qbittorrent.QBittorrent, "qBittorrent"),
    "radarr": Kind(servarr.Radarr, "Radarr"),
    "rtorrent": Kind(rtorrent.Rtorrent, "rTorrent"),
    "sabnzbd": Kind(sabnzbd.Sabnzbd, "SABnzbd"),
    "sonarr": Kind(servarr.Sonarr, "Sonarr"),
    "tautulli": Kind(tautulli.Tautulli, "Tautulli"),
    "updates": Kind(updates.Updates, "Updates"),
    "uptime": Kind(uptime.Uptime, "Uptime"),
}
