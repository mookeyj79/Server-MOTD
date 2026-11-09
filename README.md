# server-motd

[![CI](https://github.com/mookeyj79/Server-MOTD/actions/workflows/ci.yml/badge.svg)](https://github.com/mookeyj79/Server-MOTD/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/server-motd)](https://pypi.org/project/server-motd/)
[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue)](LICENSE)

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

## Requirements

- Python 3.11 or newer (CI covers 3.11 to 3.14)
- Debian/Ubuntu (login hook via `update-motd.d`) or Windows (PowerShell profile hook)
- For the Debian install: Ansible (`ansible-core`) on the controller

## Quick start

```bash
pipx install server-motd
# start from docs/example-config.toml, saved as config.toml
server-motd --config config.toml check   # validate and probe
server-motd --config config.toml         # render once
```

Without `--config`, it reads `/etc/server-motd/config.toml` on Linux, or `%APPDATA%\server-motd\config.toml` then `%ProgramData%\server-motd\config.toml` on Windows. `server-motd check --no-probe` validates the config without contacting any service. Other flags: `--width <cols>`, `--color auto|always|never`, `--verbose`.

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

## Development

```bash
python -m pip install -e ".[dev]"
ruff check . && ruff format --check .
mypy
pytest
python -m build
```

CI ([ci.yml](.github/workflows/ci.yml)) runs these on Linux and Windows across Python 3.11 to 3.14, plus `ansible-lint`, `actionlint`, and end-to-end runs of the Ansible role and MOTD hook. The README sample above is checked against real output by `tests/test_docs.py`; refresh it with `UPDATE_GOLDEN=1 pytest tests/test_docs.py`. Releases are tag-driven and publish to PyPI, see [docs/releasing.md](docs/releasing.md) and [CHANGELOG.md](CHANGELOG.md).

Bugs and ideas go in [GitHub Issues](https://github.com/mookeyj79/Server-MOTD/issues); pull requests should pass CI.

## License

GPL-3.0, see [LICENSE](LICENSE).

## Credits

- Based on and inspired by https://github.com/ryanleonard1/PlexMOTD
- Further enhanced by l3uddz https://github.com/Cloudbox/Cloudbox-MOTD
