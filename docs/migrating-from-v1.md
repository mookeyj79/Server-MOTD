# Migrating from v1

v1 (Cloudbox-MOTD era bash fragments plus a Python helper, `config.json`) is not compatible with the rewrite: there is no `/opt/motd`, no `update-motd.d` fragment names to keep and no `config.json`. The old code is preserved in the git tag `legacy-v1` of the repository (`git checkout legacy-v1`).

There is no automatic converter. To migrate: remove the old install, then install via the [Ansible role](install-debian.md) and translate your settings with the table below. v1's `install.sh` wiped `/etc/update-motd.d`; the new role leaves other fragments in place, so restore any you still want.

## Key mapping

| v1 `config.json` | v2 `config.toml` |
| --- | --- |
| `motd.banner_title` | `title` |
| `motd.banner_type` (`shell`) | none; the renderer draws a box. Figlet is optional (`server-motd[figlet]`). |
| `motd.text_color`, `motd.title_color` | dropped; colours come from each row's status. Use `box` for border style. |
| `motd.show.plexpy` | a `[[modules]]` entry with `kind = "tautulli"`; remove it to hide it, or set `enabled = false` |
| `motd.show.rtorrent` | `kind = "rtorrent"` entry |
| `motd.show.qbittorrent` | `kind = "qbittorrent"` entry |
| `motd.show.sabnzbd` | `kind = "sabnzbd"` entry |
| `motd.show.nzbget`, `autoscan`, `autoscan-cb` | dropped; no equivalent |
| `plexpy.url` | `url` of the tautulli module |
| `plexpy.api_key` | `api_key` (or `${ENV}` / `api_key_file`) |
| `rtorrent.url` (`https://user:pass@host`, ruTorrent) | `scgi = "host:port"` or `unix:/path`; rTorrent is now spoken to over SCGI, not HTTP |
| `nzbget.url`, `autoscan.url`, `autoscan.api_key` | dropped |

Added in v2 with no v1 counterpart: system modules (`ips`, `uptime`, `load`, `cpu`, `memory`, `disks`, `logins`, `processes`, `updates`), Sonarr/Radarr/Lidarr, and several instances of any service.

## Example

v1:

```json
{
  "motd": { "banner_title": "Server1", "show": { "plexpy": true, "rtorrent": true } },
  "plexpy": { "url": "https://plexpy.example.com", "api_key": "SET_YOUR_API_KEY" },
  "rtorrent": { "url": "https://user:pass@rutorrent.example.com" }
}
```

v2:

```toml
title = "Server1"

[[modules]]
kind = "tautulli"
url = "https://plexpy.example.com"
api_key = "${TAUTULLI_API_KEY}"

[[modules]]
kind = "rtorrent"
scgi = "127.0.0.1:5000"
```
