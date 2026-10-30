# Configuration reference

The config is a TOML file. Top-level keys, then an ordered `[[modules]]` array; modules render in the order written. A complete working file is [example-config.toml](example-config.toml).

```toml
title = "media-box"   # banner text, default: the hostname
box = "single"        # single | rounded | double | ascii (default single)

[[modules]]
kind = "uptime"
```

Every module entry accepts:

| Key | Meaning |
| --- | --- |
| `kind` | Required. One of the kinds below. |
| `name` | Title shown for the module (default: the kind's own title). Give instances of the same kind distinct names. |
| `enabled` | `false` skips the module (default `true`). |

A key a module does not support is an error for that module only (shown as `UNAVAILABLE: invalid config: ...`); the others still render.

## System modules

`warn` and `crit` are optional numbers: a value at or above the limit gets that status (`warn` must not exceed `crit`).

| Kind | Shows | Options |
| --- | --- | --- |
| `ips` | Address per network interface (loopback and link-local skipped) | none |
| `uptime` | Time since boot | none |
| `load` | 1/5/15 minute load average (Linux only) | `warn`, `crit` on the 1-minute load per core |
| `cpu` | CPU utilisation percent (use this on Windows) | `warn`, `crit` on percent |
| `memory` | RAM and swap usage | `warn`, `crit` on RAM percent |
| `disks` | Usage per mounted filesystem | `warn`, `crit` on percent used |
| `logins` | Logged-in sessions | `warn`, `crit` on the session count |
| `processes` | Process count | `warn`, `crit` on the count |
| `updates` | Pending updates and reboot-required (Debian family) | `updates_file` (default `/var/lib/update-notifier/updates-available`), `reboot_file` (default `/var/run/reboot-required`) |

## Service modules

Secrets (`api_key`, `password`) accept `${ENV_VAR}` or a `*_file` variant; see [secrets](secrets.md). Each module makes a few cheap requests with short timeouts.

| Kind | Options | Shows |
| --- | --- | --- |
| `tautulli` | `url`, `api_key` (required) | Plex status, stream counts by decision, bandwidth |
| `qbittorrent` | `url` (required); `username`, `password` (optional) | Rates and torrent counts by state |
| `sabnzbd` | `url`, `api_key` (required) | Speed, queue and remaining size, lifetime total |
| `rtorrent` | `scgi` (required): `host:port` or `unix:/path/to/socket` (no unix sockets on Windows) | Rates and torrent counts by state |
| `sonarr`, `radarr`, `lidarr` | `url`, `api_key` (required); `warn`, `crit` (integers, on the Missing count); `calendar_days` (default 7) | Queue, Missing, Health, Upcoming |

rTorrent is reached over SCGI directly (configure `network.scgi.open_port` or `open_local` in rTorrent), not through ruTorrent's HTTP.

Tautulli bandwidth is shown assuming Tautulli reports kilobits per second. That unit is unverified; see [troubleshooting](troubleshooting.md#known-limitation).

### Several instances

```toml
[[modules]]
kind = "sonarr"
name = "Sonarr"
url = "http://localhost:8989"
api_key = "${SONARR_API_KEY}"

[[modules]]
kind = "sonarr"
name = "Sonarr 4K"
url = "http://localhost:8990"
api_key = "${SONARR_4K_API_KEY}"
```

## Command line

```text
server-motd [--config FILE] [--width N] [--color auto|always|never] [--verbose]
server-motd check [--config FILE] [--verbose]
server-motd install-profile | uninstall-profile
```
