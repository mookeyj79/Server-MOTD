# Legacy v1

## Running v1

Linux only; no build, lint or test tooling. Run scripts in the Debian WSL distro (`wsl -d Debian -- bash -c 'cd /mnt/d/Dev/Server-MOTD && python3 media-server-motd.py plexpy get_stream_counts'`). The fragments hardcode `/opt/motd` and `/etc/update-motd.d`, so a full render needs the repo installed there.

## v1 architecture notes

- Each `motd/NN-name` bash fragment shells out to `media-server-motd.py <type> <func>`, which prints plain text. Multi-value results are packed into one string (`.`-joined for stream/torrent/nzb counts, `|`-joined for `disk usage`) and unpacked in bash with `IFS='.' read -a`. Changing field order or count in Python means editing the matching fragment. Fragments treat an `ERROR*` prefix as "fall back to zeros".
- `utils/config.py` rewrites the user's `config.json` on every load to merge in missing `base_config` keys. `config.json.example` has drifted from `base_config` (`autoscan-cb`, `sabnzbd`, `qbittorrent` flags have no client).
- `install.sh` wipes `/etc/update-motd.d`, `/etc/motd` and `/etc/motd.dynamic`, and sets `PrintLastLog no` in sshd_config.
