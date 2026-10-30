# server-motd

A login banner that shows a server's identity, system health and the status of the services it runs. Pure Python 3.11+ (`psutil` is the only required dependency), on Debian/Ubuntu and Windows.

<!-- sample-output -->
```text
┌──────────────────────────────────────────────────────────────┐
│ media-box                                                    │
├──────────────────────────────────────────────────────────────┤
│ Uptime                                                       │
│ Uptime  3d 4h 5m                                             │
│                                                              │
│ Sonarr                                                       │
│ Queue     5 (errors)                                         │
│ Missing   12                                                 │
│ Health    Indexers unavailable due to failures: NZBgeek      │
│ Upcoming  2                                                  │
│                                                              │
│ Tautulli                                                     │
│ Plex       up                                                │
│ Streams    3 (1 direct play, 1 direct stream, 1 transcode)   │
│ Bandwidth  31.5 Mbps                                         │
└──────────────────────────────────────────────────────────────┘
```

Bad or unreachable services never block your login: a failing module shows `UNAVAILABLE: <reason>` and the rest still print.

## What it shows

- System modules: `ips`, `uptime`, `load`, `cpu`, `memory`, `disks`, `logins`, `processes`, `updates` (pending updates and reboot-required)
- Service modules: `tautulli`, `qbittorrent`, `sabnzbd`, `rtorrent`, `sonarr`, `radarr`, `lidarr`
- Several named instances of any service (for example two Sonarrs)
- TOML config with `${ENV_VAR}` and `*_file` secrets
- Built-in ANSI renderer: two-column boxed layout on wide terminals, optional figlet banner (`pip install "server-motd[figlet]"`)

## Quick start

```bash
pipx install server-motd
# start from docs/example-config.toml, saved as config.toml
server-motd --config config.toml check   # validate and probe
server-motd --config config.toml         # render once
```

Make it run at login:

- Debian/Ubuntu: the bundled Ansible role, see [docs/install-debian.md](docs/install-debian.md)
- Windows: `pipx install server-motd` then `server-motd install-profile`, see [docs/install-windows.md](docs/install-windows.md)

## Documentation

- [Install on Debian/Ubuntu (Ansible)](docs/install-debian.md)
- [Install on Windows (pipx)](docs/install-windows.md)
- [Configuration reference](docs/configuration.md) and a complete [example config](docs/example-config.toml)
- [Secrets](docs/secrets.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Migrating from v1](docs/migrating-from-v1.md)
- [Releasing](docs/releasing.md), [glossary](GLOSSARY.md), [decisions](docs/adr/), [research notes](docs/research/)

## Credits

This project is a fork of Cloudbox-MOTD, renamed and now independent; the v1 code is kept in the `legacy-v1` git tag.

- Based on and inspired by https://github.com/ryanleonard1/PlexMOTD
- Further enhanced by l3uddz https://github.com/Cloudbox/Cloudbox-MOTD
