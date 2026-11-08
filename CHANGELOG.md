# Changelog

Hand-written. Versions follow `pyproject.toml` and stay 0.x until the v1 scope
ships. Each release needs a `## [x.y.z]` heading here; the release workflow
fails without one and uses the section as the GitHub Release notes.

## [0.1.1]

- `check` now validates the top-level `title` and `box` settings, so it no longer passes a config whose MOTD would print nothing. New `check --no-probe` validates without contacting anything; the Ansible role uses it to validate `config.toml` before writing it.
- Unavailable reasons are one consistent set: `invalid config`, `unreachable`, `auth failed`, `API error`, `bad response` and `timed out`. A malformed service reply shows `bad response: missing '<field>'` instead of a bare field name, and timeouts read `timed out` for every module.
- A module's title no longer changes when it is unavailable (`SABnzbd`, not `sabnzbd`), and a `name` is always used for named Instances.
- A module's requests share its 3 s budget: each request's timeout is the time left, rather than a fixed 2.5 s (2 s for rTorrent) per request. A module that overruns no longer delays process exit.
- The Ansible TOML filter rejects `None` inside a list instead of writing the string `"None"`.

## [0.1.0]

First release of `server-motd`, a from-scratch rewrite of the Cloudbox-MOTD
fork as an independent project. Nothing is compatible with v1 (`config.json`,
`/opt/motd`, the old fragment names); see `docs/migrating-from-v1.md`.

- One pure-Python package for Python 3.11+, with `psutil` as its only required dependency; HTTP and XML-RPC use the standard library.
- System modules: `ips`, `uptime`, `load`, `cpu`, `memory`, `disks`, `logins`, `processes` and `updates` (pending updates and reboot-required).
- Service modules, each with any number of named instances: Tautulli, qBittorrent, SABnzbd, rTorrent, Sonarr, Radarr and Lidarr.
- Modules are fetched concurrently, with a 3 s timeout per module and a 6 s total; a failing module is shown as unavailable instead of breaking the MOTD.
- TOML config with an ordered `[[modules]]` list, per-module `warn`/`crit` thresholds, `${ENV_VAR}` and `*_file` secrets, and strict validation scoped to each module.
- Built-in ANSI renderer: two-column boxed layout on wide terminals, a single column on narrow ones, several box styles (including ASCII), and an optional figlet banner (the `figlet` extra).
- CLI: `server-motd`, `server-motd check`, `install-profile` and `uninstall-profile`, with `--config`, `--width`, `--color` and `--verbose`.
- Debian/Ubuntu: an Ansible role (`ansible/roles/server_motd`) installs the package and the figlet banner from a hash-pinned lockfile into a root-owned venv, adds a single `update-motd.d` hook that runs as a dedicated user and always exits 0, writes `config.toml` as `root:<user> 0640`, and removes everything with `state: absent`. It never wipes the distro's other MOTD fragments.
- Windows: a guarded block in the current user's PowerShell 7 and 5.1 profiles, with a per-user `%APPDATA%` config and a read-only `%ProgramData%` fallback.
- Documentation: README with a golden-tested sample output, a tested example config covering every module kind, install guides for Debian and Windows, and pages on configuration, secrets, troubleshooting, releasing and migrating from v1.
- Tautulli's bandwidth unit (assumed kbps) is not yet verified against a real server.
- The legacy v1 bash/Python code is removed; it is kept in the `legacy-v1` git tag.
