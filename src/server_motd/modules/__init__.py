"""Module registry. Extension conventions for adding a module kind:

1. Create one file, `modules/<kind>.py`, defining a class with
   `__init__(self, spec: ModuleSpec)` (read options with `spec.take*`, then call
   `spec.done()`; raise `ConfigError` for bad config) and `fetch() -> Result`
   (raise on failure; the runner turns that into UNAVAILABLE).
2. Add ONE import and ONE line to `REGISTRY` below: `"<kind>": <kind>.Class,`.
   Keep entries alphabetical so parallel tickets merge cleanly.
3. Test only through the CLI (tests/conftest.py `run_cli`, `write_config`,
   `assert_golden`). Pin anything non-deterministic at the boundary it comes
   from (e.g. monkeypatch `psutil` / `time`), not inside the module.
"""

from __future__ import annotations

from collections.abc import Callable

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
    rtorrent,
    sabnzbd,
    servarr,
    updates,
    uptime,
)

REGISTRY: dict[str, Callable[[ModuleSpec], Module]] = {
    "cpu": cpu.Cpu,
    "disks": disks.Disks,
    "ips": ips.Ips,
    "lidarr": servarr.Lidarr,
    "load": load.Load,
    "logins": logins.Logins,
    "memory": memory.Memory,
    "processes": processes.Processes,
    "radarr": servarr.Radarr,
    "rtorrent": rtorrent.Rtorrent,
    "sabnzbd": sabnzbd.Sabnzbd,
    "sonarr": servarr.Sonarr,
    "updates": updates.Updates,
    "uptime": uptime.Uptime,
}
