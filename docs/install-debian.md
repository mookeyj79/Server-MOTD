# Install on Debian/Ubuntu (Ansible)

The repository ships an Ansible role, `ansible/roles/server_motd`. It creates a locked-down system user, a virtualenv under `/opt/server-motd/venv`, `/etc/server-motd/config.toml` (mode 0600) and an `update-motd.d` hook (`/etc/update-motd.d/50-server-motd`) that runs the MOTD as that user. It does not wipe the other `update-motd.d` fragments.

## Apply the role

Check out this repository (or copy `ansible/roles/server_motd` into your own roles path) and write a playbook:

```yaml
- hosts: all
  become: true
  roles:
    - role: server_motd
      vars:
        server_motd_config:
          title: media-box
          modules:
            - kind: uptime
            - kind: load
              warn: 0.7
              crit: 1.0
            - kind: sonarr
              url: http://localhost:8989
              api_key: "{{ vault_sonarr_key }}"
```

```bash
ANSIBLE_ROLES_PATH=ansible/roles ansible-playbook -i myhost, site.yml
```

`server_motd_config` is a structured dict rendered to `config.toml`: top-level `title` and `box`, plus a `modules` list with the same keys as the [configuration reference](configuration.md). Inline secrets may be vaulted; the file is `0600` and the task does not log it.

The package is installed from a hash-pinned lockfile (`files/requirements.lock`), which is refreshed after each release (see [releasing](releasing.md)). Until a release has filled it, set `server_motd_package_src` to a wheel path.

Other variables (`server_motd_user`, `server_motd_base_dir`, `server_motd_config_dir`, `server_motd_hook_dir`, `server_motd_hook_name`, `server_motd_apt_packages`) are documented in `meta/argument_specs.yml`. Running the role twice changes nothing the second time.

## Check it

```bash
sudo -u server-motd /opt/server-motd/venv/bin/server-motd check
sudo /etc/update-motd.d/50-server-motd
```

## Remove it

Set `server_motd_state: absent`. This removes the hook, the install directory, the config and the user.

If the venv is missing or broken the hook still exits 0, so a bad install cannot lock you out of SSH.
