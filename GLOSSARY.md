# server-motd

A cross-platform login banner that shows a server's identity, system health and the status of the services it runs.

## Language

**Module**:
One self-contained unit of MOTD output, either a system section or a service integration.
_Avoid_: Plugin, fragment, section

**Instance**:
One named configuration of a service module, so the same service can appear more than once (e.g. two Sonarrs).
_Avoid_: Profile, server entry

**System module**:
A module reporting on the host itself (uptime, memory, disks, pending updates).
_Avoid_: Stat, system section

**Service module**:
A module reporting on an external application the host runs (Sonarr, qBittorrent, Tautulli).
_Avoid_: Integration, provider

**Banner**:
The identity header at the top of the MOTD, showing the server's title.
_Avoid_: Header, logo

**Host integration**:
The OS-specific hook that makes the MOTD print at login (`update-motd.d` on Debian-family, a PowerShell profile on Windows).
_Avoid_: Installer, shim
