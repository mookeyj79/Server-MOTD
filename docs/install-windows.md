# Install on Windows (pipx)

Requires Python 3.11+ and [pipx](https://pipx.pypa.io). Installation is per user.

```powershell
py -m pip install --user pipx
py -m pipx ensurepath        # then open a new terminal
pipx install server-motd
```

## Config

Create `%APPDATA%\server-motd\config.toml` (or `%ProgramData%\server-motd\config.toml` for all users). Start from [example-config.toml](example-config.toml). The `load` module is Linux only; use `cpu` on Windows, and drop `updates`.

```powershell
server-motd check
server-motd
```

## Run at login

```powershell
server-motd install-profile
```

This adds a marked block (`# >>> server-motd >>>` ... `# <<< server-motd <<<`) to the current-user profile of every installed PowerShell edition (PowerShell 7 and Windows PowerShell 5.1). Everything outside the markers is left alone, file encoding and line endings are preserved, and running it again changes nothing. The block only runs in the console host and only if `server-motd` is on `PATH`.

Remove it with `server-motd uninstall-profile`.

If your execution policy is `Restricted`, profiles do not run at all. `install-profile` warns but does not change the policy; to allow profiles run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
