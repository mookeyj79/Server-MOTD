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

**Result**:
What a module returns: a title, a list of rows and an overall status.
_Avoid_: Output, section

**Row**:
One labelled value line within a result, with its own status.
_Avoid_: Line, stat

**Status**:
The semantic health of a row or result (info, ok, warn, crit, unavailable); the renderer maps it to colour.
_Avoid_: Level, severity, colour

**Profile block**:
The marked span `install-profile` writes into a PowerShell profile to run the MOTD at login; everything outside the markers belongs to the user.
_Avoid_: Snippet, hook

**Report**:
What one run produces from a config: the banner title, the box style, and one outcome per enabled instance, in config order. The MOTD and `check` are two presentations of the same report.
_Avoid_: Run result, summary

**Outcome**:
What one instance came to in a report: its title, the result to show, and the failure if it was unavailable.
_Avoid_: Slot, entry

**Failure kind**:
Why a module is unavailable: invalid config, unreachable, auth failed, API error, bad response, timed out (or a plain error). The reason shown after `UNAVAILABLE:` always starts with it.
_Avoid_: Error type, error code

**Deadline**:
The moment by which a module's fetch must finish; every request it makes takes its timeout from the time left.
_Avoid_: Timeout (for the whole budget), TTL
