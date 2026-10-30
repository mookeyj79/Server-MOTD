# server-motd

A login banner that shows a server's identity, system health and the status of the services it runs.

> **Status: rewrite in progress.** The code in this repository is **legacy v1** (Debian/Ubuntu bash fragments plus a Python helper). It is being replaced by `server-motd`, a single cross-platform Python package. The plan is in [issue #1](https://github.com/mookeyj79/Server-MOTD/issues/1); nothing of the new package is built yet.

This project is a fork of Cloudbox-MOTD, renamed and now independent. The new version does not keep the old `config.json` schema, the `/opt/motd` path or the `update-motd.d` fragment names.

## Planned (v1 of the rewrite)

 - Pure Python 3.11+, with `psutil` the only third-party dependency
 - Linux (Debian/Ubuntu) and Windows (PowerShell 7 and 5.1)
 - System modules: IPs, last login, uptime, load, memory, disks, logins, processes, pending updates and reboot
 - Service modules: Tautulli, qBittorrent, SABnzbd, Sonarr, Radarr, Lidarr, rTorrent
 - Several named instances of any service (for example two Sonarrs)
 - TOML config with `${ENV_VAR}` and `*_file` secrets
 - Built-in ANSI renderer with a two-column boxed layout and an optional figlet banner
 - An Ansible role in the same repository

NZBGet and Autoscan support are dropped. See [`GLOSSARY.md`](GLOSSARY.md) for the domain terms, [`docs/adr/`](docs/adr/) for the decisions made so far and [`docs/research/`](docs/research/) for the API and platform research behind them.

## Legacy v1

Quick status updates on login for the following services:

 - Server Identification Banner
 - Server Stats
 - Plex Streams
 - Plex Autoscan Stats
 - Cloudbox Autoscan Stats
 - rTorrent Stats
 - qBittorrent Stats
 - NZBGet Stats
 - SABnzbd Stats

### Installation

Copy `config.json.example` to `config.json`, modify it to your liking, then run:

```bash
sudo mkdir -m755 /opt/motd
sudo chown $USER:$USER /opt/motd
git clone https://github.com/mookeyj79/Server-MOTD.git /opt/motd
cd /opt/motd
sudo ./install.sh
```

**Warning:** `install.sh` wipes `/etc/update-motd.d`, `/etc/motd` and `/etc/motd.dynamic`, and sets `PrintLastLog no` in `sshd_config`. Do not run it on a machine whose existing MOTD you want to keep.

## Credits

 - Based on and inspired by https://github.com/ryanleonard1/PlexMOTD
 - Further enhanced by l3uddz https://github.com/Cloudbox/Cloudbox-MOTD
