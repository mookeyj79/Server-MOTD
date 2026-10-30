# Debian and Ubuntu MOTD mechanics

Research for ticket #5 (map #1). Question: how do login messages work on Debian 12 and Ubuntu 22.04/24.04, and what is the minimum safe hook that works on all three?

Versions examined: Debian 12 (pam 1.5.2-6+deb12u2, openssh 1:9.2p1-2+deb12u7, shadow 1:4.13+dfsg1-1+deb12u2, util-linux 2.38.1-5+deb12u3, debianutils 5.7-0.5~deb12u1); Ubuntu 24.04 (pam 1.5.3-5ubuntu5, update-motd 3.12, util-linux 2.39.3); Ubuntu 22.04 (pam 1.4.0-11ubuntu2, update-motd 3.10, util-linux 2.37.2). "Not verified" marks claims I could not trace to a primary source.

## Summary

- **The `/etc/update-motd.d` mechanism is a PAM patch, not a package.** Debian's `pam` source carries the same `update-motd` patch as Ubuntu's, so `pam_motd` runs `/etc/update-motd.d` on Debian 12 too. The Ubuntu `update-motd` package is not needed on any of the three targets.
- **Minimum safe hook: drop one executable file, e.g. `/etc/update-motd.d/50-server-motd`.** Nothing else is required: no PAM edits, no `/etc/motd` changes, no `sshd_config` changes.
- **The scripts run once per login, as root, with an empty environment, and the output is shared.** Per-user or per-session content cannot come from there. Scripts that fail make the whole refresh get dropped.
- **install.sh currently does several things that are unnecessary or broken** (see "Findings against install.sh").

## 1. How the pieces fit

### 1.1 pam_motd

`pam_motd` is a PAM session module. Upstream man page (linux-pam, master):

- `motd=` default `/etc/motd:/run/motd:/usr/lib/motd`; `motd_dir=` default `/etc/motd.d:/run/motd.d:/usr/lib/motd.d`. Giving either option disables the defaults for both.
- Single files: `/etc/motd` is shown if present, else `/run/motd`, else `/usr/lib/motd`.
- Directories: same-named files in `/etc/motd.d` override `/run/motd.d`, which overrides `/usr/lib/motd.d`. Files display in lexicographic order. Each message is capped at 64KB. Files are read with the credentials of the user logging in.
- A symlink to `/dev/null` in `/etc/motd.d` silences a same-named message.
- `MOTD_SHOWN=pam` is set afterwards.

Source: https://raw.githubusercontent.com/linux-pam/linux-pam/master/modules/pam_motd/pam_motd.8.xml (also https://manpages.debian.org/bookworm/libpam-modules/pam_motd.8.en.html, https://manpages.ubuntu.com/manpages/jammy/en/man8/pam_motd.8.html, https://manpages.ubuntu.com/manpages/noble/en/man8/pam_motd.8.html, which document the same options on all three targets).

Caveat: the upstream man page does not describe `motd.dynamic` or `/etc/update-motd.d`. That is the distro patch (next section). Whether Ubuntu 22.04's older pam 1.4.0 supports `/run/motd.d` is shown only by its man page (documented there); I did not read its C source.

### 1.2 The `update-motd` patch is in Debian too

`debian/patches-applied/update-motd` in Debian's pam (bookworm 1.5.2-6+deb12u2) adds a `noupdate` option and, unless it is given, runs:

```c
if (do_update && (stat("/etc/update-motd.d", &st) == 0) && S_ISDIR(st.st_mode)) {
    mode_t old_mask = umask(0022);
    if (!system("/usr/bin/env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin run-parts --lsbsysinit /etc/update-motd.d > /run/motd.dynamic.new"))
        rename("/run/motd.dynamic.new", "/run/motd.dynamic");
    umask(old_mask);
}
```

Source: https://sources.debian.org/data/main/p/pam/1.5.2-6+deb12u2/debian/patches-applied/update-motd . Ubuntu 24.04 carries the same patch (`debian/patches/update-motd`, listed in `debian/patches/series` on branch `ubuntu/noble`): https://git.launchpad.net/ubuntu/+source/pam/plain/debian/patches/update-motd?h=ubuntu/noble . I did not find the 22.04 patch file by name; its sshd and login PAM files are identical (below) and its man page documents `noupdate`, so I treat it as the same mechanism.

Consequences that follow directly from that code:

1. The refresh only happens if `/etc/update-motd.d` exists as a directory (Debian does not appear to ship one by default; not verified).
2. Scripts run **as the PAM caller's uid, which is root** in the sshd and login paths. `update-motd(5)` states "run by pam_motd(8) as root at each login": https://manpages.ubuntu.com/manpages/noble/en/man5/update-motd.5.html .
3. The environment is **empty except `PATH`** (`env -i`). No `HOME`, `USER`, `SSH_CONNECTION`, `SSH_CLIENT`, `TERM`, or locale. A script cannot tell who is logging in or from where.
4. The output goes to **one shared file**, `/run/motd.dynamic`, written with umask 022 (world-readable). Every user sees whatever the most recent login produced. The temp name `/run/motd.dynamic.new` is fixed, so truly simultaneous logins race. Scripts' own stderr is not redirected.
5. If `run-parts` exits non-zero the `rename` is skipped, so the **previous** `/run/motd.dynamic` stays (or none exists). `run-parts` returns its accumulated exit status when any script exits non-zero (`return exitstatus;`, debianutils `run-parts.c`; https://sources.debian.org/data/main/d/debianutils/5.7-0.5~deb12u1/run-parts.c ), so one failing script discards the whole refresh. Every script should therefore end in `exit 0`.
6. The scripts run synchronously inside the login, so slow network calls delay the login prompt. `update-motd(5)` itself advises caching output of slow tasks.
7. **File naming:** `run-parts --lsbsysinit` only runs names in the LSB/Debian-cron namespaces (the cron one is `^[a-zA-Z0-9_-]+$`) and skips `.dpkg-old/-dist/-new/-tmp`. Names with a dot, like `colors.txt`, are skipped (also the reason `colors.txt` in install.sh is not run). `50-server-motd` is valid. Source: https://manpages.debian.org/bookworm/debianutils/run-parts.8.en.html . `update-motd(5)` recommends `NN-name` with no extension.

### 1.3 Where PAM calls pam_motd (SSH, console, su)

On all three targets the sshd and login PAM stacks contain the same two lines:

```
session    optional     pam_motd.so  motd=/run/motd.dynamic
session    optional     pam_motd.so noupdate
```

The first run refreshes `/run/motd.dynamic` (the `update` step is on by default) and prints it; the second prints the static `/etc/motd` (plus `/etc/motd.d`) without re-running scripts. Comments in the files say the same.

Sources:
- Debian sshd: https://sources.debian.org/data/main/o/openssh/1:9.2p1-2+deb12u7/debian/openssh-server.sshd.pam.in
- Debian login (console): https://sources.debian.org/data/main/s/shadow/1:4.13+dfsg1-1+deb12u2/debian/login.pam
- Ubuntu 22.04 and 24.04: `debian/openssh-server.sshd.pam.in` and `debian/login.pam` on `ubuntu/jammy` and `ubuntu/noble` in https://git.launchpad.net/ubuntu/+source/openssh and https://git.launchpad.net/ubuntu/+source/shadow (same lines, 33-34).

**`su` does not show the MOTD.** Debian's `su`/`su -l` PAM files (util-linux 2.38.1) have no `pam_motd` line: https://sources.debian.org/data/main/u/util-linux/2.38.1-5+deb12u3/debian/util-linux.su.pam . Not checked for Ubuntu's `su`, `sudo -i`, or non-PAM paths. Ubuntu also ships a separate `show-motd` package that runs the scripts from `/etc/profile.d` "when pam_motd does not show it" (https://git.launchpad.net/ubuntu/+source/update-motd/plain/debian/control?h=ubuntu/noble ); it is not installed by default as far as I know (not verified).

### 1.4 What sshd itself does with the MOTD

From OpenSSH source (V_9_2_P1, Debian 12) `session.c`:

- `do_login()` calls `check_quietlogin()` first. A `~/.hushlogin` in the user's home, **or an exec'd command** (`ssh host cmd`), makes it return early, so neither the PAM messages nor `/etc/motd` are shown.
- Otherwise it calls `display_loginmsg()` (messages queued from PAM, which include `pam_motd` output) and then `do_motd()`.
- `do_motd()` prints `/etc/motd` only if `PrintMotd` is on.

`sshd_config(5)` Debian: `PrintMotd` default `yes`, but the Debian package sets `PrintMotd no` (the PAM stack prints it instead, so there is no double print). `UsePAM yes` in the stock config. The stock file contains `#PrintLastLog yes`. Sources: https://manpages.debian.org/bookworm/openssh-server/sshd_config.5.en.html , https://sources.debian.org/data/main/o/openssh/1:9.2p1-2+deb12u7/sshd_config (lines 86, 95, 96). The Ubuntu Debian-config patch has the same `PrintMotd no` / `UsePAM yes` / `#PrintLastLog yes`.

The sshd config's first line is `Include /etc/ssh/sshd_config.d/*.conf`, and "for each keyword, the first obtained value will be used", so a drop-in overrides the main file.

### 1.5 Last login and PrintLastLog

- sshd itself builds the `Last login: <time> from <host>` line (`sshlogin.c`, `store_lastlog_message`), if `PrintLastLog` is on (default `yes`), and queues it in the same login-message buffer as PAM output. It is per-user (looked up by uid) and independent of `update-motd.d`: https://raw.githubusercontent.com/openssh/openssh-portable/V_9_2_P1/sshlogin.c
- An `update-motd.d` script has no user identity (empty env, root), so a "last login" module there cannot reproduce this reliably. The existing `motd/03-last-login` shows the last row of `lastlog2` output, which is whichever account logged in last, not necessarily the user who is now logging in. (sshd generates its own message before it updates lastlog, per the comment on `store_lastlog_message`; the ordering relative to PAM scripts was not traced.)
- `lastlog2` is **not packaged** in Debian 12 (package search for `lastlog2` in bookworm: no results; https://packages.debian.org/search?keywords=lastlog2&searchon=names&suite=bookworm&section=all ) or in Ubuntu 22.04/24.04 (Launchpad published-binaries query for `lastlog2` in jammy and noble returned 0). util-linux there is 2.38 / 2.37 / 2.39, which predate `lastlog2`.

### 1.6 `/etc/motd`, `/run/motd.dynamic`, Ubuntu extras

- On Ubuntu, per `update-motd(5)`, `/etc/motd` is typically a symlink to `/run/motd.dynamic`. Not verified against base-files for each release. Either way the PAM stack above prints both paths.
- Ubuntu ships its own scripts in `/etc/update-motd.d`: `update-notifier-common` installs `90-updates-available`, `95-hwe-eol`, `98-reboot-required`, `98-fsck-at-reboot` (https://git.launchpad.net/ubuntu/+source/update-notifier/plain/debian/update-notifier-common.install?h=ubuntu/noble ) and `base-files` provides `50-motd-news`. Wiping the directory removes these, and package upgrades may restore some of them.
- **motd-news:** `50-motd-news` reads `/etc/default/motd-news`, exits if `ENABLED` is not `1`, and otherwise prints a cached copy (max 10 lines, 80 columns) of news fetched by systemd (https://git.launchpad.net/ubuntu/+source/base-files/plain/motd/50-motd-news?h=ubuntu/noble ). It is Ubuntu-only; `/etc/default/motd-news` is shipped by `motd-news-config`. Our script does not need to touch it: leave it alone. It sits at `50-` so a script named `50-server-motd` sorts after it (`50-motd-news` < `50-server-motd`).

### 1.7 The Ubuntu `update-motd` package

The Ubuntu source packages `update-motd` 3.10 (22.04) and 3.12 (24.04) both exist. Its description: "The functionality formerly provided by this package is now integrated into pam_motd, in libpam-modules"; it also builds `show-motd` (https://git.launchpad.net/ubuntu/+source/update-motd/plain/debian/control?h=ubuntu/noble ). There is no `update-motd` package in Debian 12 (package search: no results). So install.sh's `apt install update-motd` is unnecessary on Ubuntu and is Ubuntu-only anyway.

## 2. Minimum safe hook

One file, shipped by installer or package:

```
/etc/update-motd.d/50-server-motd     (root:root, 0755)
```

- Name matches `^[a-zA-Z0-9_-]+$`, so `run-parts --lsbsysinit` runs it.
- Nothing to change in PAM, `/etc/motd`, `sshd_config` or `motd-news`.
- On Debian, create `/etc/update-motd.d` (`0755`) if missing; this is what turns on the refresh step. Never remove or chown it.
- Uninstall = delete that one file (and the directory only if the installer created it and it is now empty).

Script requirements that follow from section 1.2:

1. `exit 0` on every path, and never print partial garbage on failure: a non-zero exit discards the entire MOTD refresh, including other packages' scripts.
2. Use absolute paths or the PATH given (`/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`); do not rely on `HOME`, `USER`, `TERM`, `SSH_*` or locale. Colour has to be unconditional or config-driven (no TTY check against the login terminal is possible).
3. Output is shared and generated once per login: no per-user data, no secrets in output beyond what every user may see (`/run/motd.dynamic` is 0644 and shown to everyone).
4. Keep it fast. All module timeouts add to login latency (this feeds the "running network calls as root" item in the map's "not yet specified"). Config read by a root process should be root-owned and not user-writable; stderr is not captured.
5. The 64KB pam_motd cap is per message file, and the whole `/run/motd.dynamic` is one file, so total output of all scripts combined must stay under it.

Optional, strictly opt-in: suppress sshd's own "Last login" line by writing `PrintLastLog no` to `/etc/ssh/sshd_config.d/<name>.conf` (not by editing `sshd_config`). Because `Include` is at the top and first value wins, the drop-in takes effect. Validate with `sshd -t` before reload. The `Include` line is verified for Debian 12's file; for Ubuntu 22.04 I did not read the shipped file (not verified).

## 3. Findings against install.sh

| install.sh step | Finding |
|---|---|
| `apt install ... lastlog2` | The package is not in Debian 12 or Ubuntu 22.04/24.04. With `set -e` the installer fails at the first `apt install`. |
| `apt install update-motd update-notifier-common` (Ubuntu) | `update-motd` is a legacy shell; pam_motd has the feature built in. Not needed. |
| `rm -rf /etc/update-motd.d /etc/motd /etc/motd.dynamic` | Destroys distro and package scripts (`90-updates-available`, `98-reboot-required`, `50-motd-news` etc.). Unnecessary: our file sorts among them. Also `/etc/motd.dynamic` is not a path used by PAM (it is `/run/motd.dynamic`). |
| Edit `/etc/default/motd-news` | Unnecessary, and touching it affects a different feature. Leave as-is; opt-in only if the user wants it off. |
| `chown $REAL_USER /etc/update-motd.d /etc/motd` | Root-run scripts from a non-root-owned directory is a local privilege escalation: that user (and anyone who can write the directory) controls code executed as root at every login. Must stay `root:root`. |
| `sed 's/PrintLastLog yes/PrintLastLog no/'` | The stock line is `#PrintLastLog yes`, so the sed turns it into `#PrintLastLog no`, a comment, i.e. no effect. Even if it matched, it edits a package-owned conffile; use a drop-in. |

## 4. Not verified / open

- Ubuntu 22.04: read the PAM stack lines and the man page, not the pam 1.4.0 patch file itself.
- Ubuntu's own `/etc/motd` target, `show-motd` default install state, and the `sshd_config` shipped by openssh 8.9 (`Include` line).
- `su`/`sudo -i` on Ubuntu; `login` handling of `~/.hushlogin` (only sshd's was read).
- Whether Debian 12 creates `/etc/update-motd.d` on a fresh install.
- Behaviour with non-default `UsePAM no` or custom PAM stacks (e.g. `pam_motd` lines removed) is out of scope: the hook silently shows nothing there.
