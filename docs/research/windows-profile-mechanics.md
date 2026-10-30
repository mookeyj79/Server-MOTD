# Windows terminal and PowerShell profile mechanics

Research for ticket #6 (map #1). Question: where PowerShell 7 and Windows PowerShell 5.1 profile files live, how to add and remove a guarded block idempotently, whether ANSI colour works in Windows Terminal and legacy conhost, how pipx puts the command on PATH, and what psutil gives on Windows.

Sources are primary: Microsoft Learn, the pipx docs source (`pypa/pipx`, `docs/`), the psutil docs source (`giampaolo/psutil`, `docs/api.rst`). Where a claim could not be confirmed from a primary source it is listed under "Not verified".

## 1. Profile file locations

Source: [about_Profiles, PowerShell 7.6](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_profiles) and [about_Profiles, 5.1](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_profiles?view=powershell-5.1).

| Scope | PowerShell 7 (`pwsh`) | Windows PowerShell 5.1 (`powershell.exe`) |
|---|---|---|
| All users, all hosts | `$PSHOME\Profile.ps1` | `$PSHOME\Profile.ps1` |
| All users, current host | `$PSHOME\Microsoft.PowerShell_profile.ps1` | `$PSHOME\Microsoft.PowerShell_profile.ps1` |
| Current user, all hosts | `$HOME\Documents\PowerShell\Profile.ps1` | `$HOME\Documents\WindowsPowerShell\Profile.ps1` |
| Current user, current host | `$HOME\Documents\PowerShell\Microsoft.PowerShell_profile.ps1` | `$HOME\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1` |

Facts that matter for design:

- The two editions use different folders (`PowerShell` vs `WindowsPowerShell`), so both profiles must be written to cover both.
- "PowerShell supports several profiles ... However, it doesn't create the profiles for you." The file and its folder may not exist; the docs create them with `New-Item -ItemType File -Path <profile> -Force`.
- Order of execution: AllUsersAllHosts, AllUsersCurrentHost, CurrentUserAllHosts, CurrentUserCurrentHost. "The CurrentUserCurrentHost profile always runs last" and is "the profile most often referred to as your PowerShell profile".
- All-users profiles live under `$PSHOME` (the install directory) and "To create 'All Users' profiles ... start PowerShell with the Run as administrator option." Per-user pipx cannot sensibly write these, so v1 should target current-user only. For MSIX installs of PowerShell 7 the all-users profiles are unsupported outright (same page, "Profiles for MSIX-based installations").
- Host-specific profiles exist: the `*CurrentHost` file name is `Microsoft.PowerShell_profile.ps1` for the console, `Microsoft.VSCode_profile.ps1` for the VS Code terminal. Using CurrentUserCurrentHost therefore does not run inside the VS Code integrated terminal or ISE; CurrentUserAllHosts (`Profile.ps1`) does run in every host. Choosing between them is a product decision (see Recommendations).
- Documents folder redirection: "the location of the Documents folder can be changed by folder redirection or OneDrive". The paths above are defaults. Observed on the author's machine: `$PROFILE` resolved to `C:\Users\mooke\OneDrive\Documents\PowerShell\Microsoft.PowerShell_profile.ps1`, and `[Environment]::GetFolderPath('MyDocuments')` is `C:\Users\mooke\OneDrive\Documents`. So `install-profile` must not build `~\Documents\...` by hand.
- `$PROFILE` is the current-user, current-host path of the running session; the other three are note properties (`$PROFILE.CurrentUserAllHosts`, etc.). `$PROFILE` "isn't populated in remote sessions".
- Profiles run only if the execution policy allows it: the effective default on Windows clients is `Restricted`, which "Prevents running of all script files, including ... PowerShell profiles (`.ps1`)" ([about_Execution_Policies, 5.1](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies?view=powershell-5.1)). Windows servers default to `RemoteSigned`. Policy is a registry setting under `...\PowerShell\1\ShellIds\Microsoft.PowerShell`, set with `Set-ExecutionPolicy`. `install-profile` should detect a blocking policy and tell the user, not change it.
- `pwsh -NoProfile` / `powershell -NoProfile` skip profiles entirely, which is also the escape hatch if the block misbehaves.

### Obtaining the real paths

Only the PowerShell executable knows its `$PROFILE`. Options for a Python tool:

1. Run each installed edition and ask it: `pwsh -NoProfile -Command '$PROFILE.CurrentUserAllHosts'` and `powershell -NoProfile -Command '$PROFILE.CurrentUserAllHosts'`. Handles OneDrive and redirected Documents correctly; an edition that is not on PATH is simply skipped. This is the recommended approach.
2. Derive from the Known Folder API (`SHGetKnownFolderPath(FOLDERID_Documents)`) plus `PowerShell` / `WindowsPowerShell`. Not verified against a primary source for edge cases, and unnecessary if option 1 works.

Hard-coding `Path.home() / "Documents"` is wrong whenever Documents is redirected.

## 2. Guarded block: add and remove idempotently

There is no primary source that prescribes a marker format; this is a design built from the facts above.

- Use start and end marker comment lines, for example `# >>> server-motd >>>` and `# <<< server-motd <<<` (PowerShell comments begin with `#`). Everything between is owned by the tool.
- Install: read file (if absent, create the parent directory and file); if the start marker is present, replace the span in place (so upgrades refresh the block, and a second run is a no-op when contents match); otherwise append the block with a leading newline.
- Uninstall: remove the span including both marker lines; if the file is then empty or whitespace only and the tool created it, deleting it is optional. Never touch text outside the markers.
- Treat a start marker without an end marker as corruption: refuse and report rather than guess.
- Preserve the existing line endings and avoid rewriting unrelated bytes; write via a temp file and replace, to avoid truncating a user's profile on failure.
- The block body should be defensive: skip when the session is not interactive, and guard on the command existing, for example `if (Get-Command server-motd -ErrorAction SilentlyContinue) { server-motd }`. This keeps the profile working if the package is uninstalled without `uninstall-profile`.

### Encoding hazard (verified)

Source: [about_Character_Encoding, 5.1](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_character_encoding?view=powershell-5.1).

- Windows PowerShell reads a BOM-less file as the legacy ANSI code page: "Without the BOM, Windows PowerShell misinterprets your script as being encoded in the legacy 'ANSI' codepage." and "ANSI is also what the PowerShell engine uses when it reads source code from files."
- PowerShell 7 defaults to UTF-8 without BOM.
- Consequence: keep the generated block pure ASCII (then both editions read it identically), and when modifying an existing file preserve its existing encoding and BOM rather than re-encoding it. Do not let Python's default text mode (which uses the locale encoding) rewrite the file; read and write bytes or specify the encoding explicitly based on BOM detection.

## 3. ANSI colour

Source: [Console Virtual Terminal Sequences](https://learn.microsoft.com/en-us/windows/console/console-virtual-terminal-sequences), [Windows Terminal FAQ](https://learn.microsoft.com/en-us/windows/terminal/faq).

- Console VT sequences are "intercepted by the console host when written into the output stream, if the ENABLE_VIRTUAL_TERMINAL_PROCESSING flag is set on the screen buffer handle using the SetConsoleMode function." The flag is opt-in per output handle for conhost; the recommended practice is to read the mode with `GetConsoleMode`, OR the flag, and call `SetConsoleMode`, falling back gracefully on `ERROR_INVALID_PARAMETER` ("when running on a down-level system").
- SGR colour (`ESC [ <n> m`) is supported: 16 colours via 30-37/40-47/90-97/100-107, and extended 256-colour (`38;5;n`) and truecolour (`38;2;r;g;b`) sequences are accepted but "the Windows Console will choose the nearest appropriate color from the existing 16 color table for display". So on legacy conhost, 256/truecolour degrade to 16; stick to the basic 16 SGR codes for guaranteed fidelity.
- Box drawing: conhost supports DEC line drawing, but Unicode box characters rely on the font and output encoding. Not verified from a primary source for conhost fonts/code pages; the renderer should offer an ASCII box style as fallback.
- Windows Terminal is a terminal emulator that hosts any shell; the FAQ explains that otherwise "the operating system will create an instance of conhost.exe as the 'terminal'". The FAQ does not state VT support explicitly (it is implicit in a modern terminal emulator); no Microsoft page fetched states Windows Terminal's VT behaviour in a quotable sentence.
- Python does not automatically turn on the flag for a process: a conhost window must have it set by someone. Whether the PowerShell hosts set it before launching an external program such as `server-motd` could not be confirmed from a primary source; a local test here was inconclusive because output was captured rather than attached to a console (`GetConsoleMode` returned 0).
- Windows 10 version in which conhost gained VT support: the page documents "Anniversary Update" features and the down-level fallback but this fetch did not surface a version-to-feature statement. Treat Windows 10 1511+ as the usual lower bound from general knowledge, flagged as not verified here.

Practical guidance: the tool should (a) enable VT processing itself via `SetConsoleMode` on stdout when it is a console (via `ctypes`, no new dependency), (b) fall back to plain text if that call fails, and (c) honour `NO_COLOR` and non-tty output. Use only the 16-colour SGR set by default.

## 4. pipx and PATH on Windows

Source: pipx docs source, `docs/how-to/install-pipx.rst`, `docs/how-to/configure-paths.rst`, `docs/reference/environment-variables.rst`, `docs/explanation/how-pipx-works.rst` (the rendered site at pipx.pypa.io returned 404 for the URLs tried; these are the same pages in the repository).

- Installing: `py -m pip install --user pipx`, or `scoop install pipx`, then `pipx ensurepath`. On Windows: `.\pipx.exe ensurepath` "adds both that directory and `%USERPROFILE%\.local\bin` to your search path. Restart the terminal, then confirm `pipx` runs." Already-open terminals do not see the change: "Open a new terminal after `pipx ensurepath`".
- App directory: `PIPX_BIN_DIR`, default `~/.local/bin` (so `%USERPROFILE%\.local\bin` on Windows). Venvs: `PIPX_HOME`, default `%LOCALAPPDATA%\pipx\pipx` (the configure-paths page words it `%USERPROFILE%\AppData\Local\pipx\pipx`). A legacy `~\pipx` is used if it already exists.
- Mechanism: "pipx symlinks each resource into place. On Windows it copies the file instead when the target directory does not support symlinks." Typing the command finds the link or copy in `PIPX_BIN_DIR` and follows it to the launcher inside the app's venv, which runs that venv's own Python. Consequence: `server-motd` is an `.exe` launcher on PATH; the profile block does not need to know the venv path, only the command name.
- `pipx install --global` / `pipx ensurepath --global` are not available on Windows ("pipx does not support `--global` on Windows"). This confirms per-user is the only pipx mode on Windows, matching the map's decision.
- pipx requires Python 3.11+ itself, matching the project's 3.11+ floor.
- On upgrade pipx rewrites the exposed resources from `pipx_metadata.json`; on Windows "pipx cannot delete its own running executable, so it moves locked files to a trash directory". Not a problem for a short-lived MOTD process, but an upgrade running while a shell is mid-launch of `server-motd` could briefly fail.
- Uninstalling the package with `pipx uninstall` does not run `uninstall-profile`; hence the defensive `Get-Command` guard in section 2, and docs should tell users to run `server-motd uninstall-profile` first.

## 5. psutil on Windows

Source: [psutil API docs source](https://github.com/giampaolo/psutil/blob/master/docs/api.rst) (rendered at https://psutil.io/api/; `psutil.readthedocs.io` redirects there).

| Need | API | Windows behaviour |
|---|---|---|
| CPU % | `cpu_percent(interval=None)` | Works. First call with no interval returns a meaningless `0.0`; call with a short `interval` (e.g. 0.1 s) or call twice. No Windows-specific caveat. |
| Load | `getloadavg()` | "On Windows, this is emulated via a background thread that updates every 5 seconds; the first call (and for the following 5 seconds) returns `(0.0, 0.0, 0.0)`." Short-lived MOTD runs will always show zeros. Recommendation: do not show load on Windows; use `cpu_percent(interval=...)` instead. |
| Memory | `virtual_memory()` | `total`, `used` ("In use") and `available` match Task Manager's Performance > Memory tab; `free` equals `available`. |
| Swap | `swap_memory()` | Derived as `CommitLimit - PhysicalTotal`; `sin`/`sout` always `0`. Effectively the page-file/commit figure, not a classic swap. |
| Disks | `disk_partitions()`, `disk_usage(path)` | `device` and `mountpoint` are the drive letter (`C:\`); `fstype` e.g. `NTFS`. With `all=False` it keeps "physical devices (e.g., hard disks, CD-ROM drives, USB keys)", so empty CD/removable drives are included; `disk_usage` on them may raise, so wrap per-partition in a try/except. The docs have no Windows-specific note on CD-ROM filtering (not documented). |
| Uptime | `boot_time()` | Epoch seconds from the system clock; no Windows caveat. |
| Logged-in users | `users()` | Available; `pid` is always `None` on Windows. Whether it lists RDP sessions is not stated in the docs (not verified). |
| IPs | `net_if_addrs()` | Works; `broadcast` is computed from the netmask, `ptp` always `None` on Windows. |
| Processes | `process_iter(attrs, ad_value)` | Works; no Windows-specific note. Access-denied on system processes is expected without elevation, use `ad_value`/catch `AccessDenied`. |
| Windows-only | `win_service_iter()`, `win_service_get()` | Enumerates services with name, status, start type; could back an optional services module. |

Not available/relevant on Windows per the availability tags: `sensors_temperatures` (Linux, FreeBSD only), `sensors_fans` (Linux only). `sensors_battery` and `cpu_freq` exist on Windows.

Gaps vs Linux system modules in the map: no load average (see above), no "last login" from `users()` (that lists current sessions, not history), and no "pending updates / reboot" in psutil; these need Windows-specific modules (registry or Windows Update API), which the map already lists as optional.

## 6. Recommendations for the architecture

1. `install-profile` targets CurrentUserAllHosts or CurrentUserCurrentHost only; never the all-users files (need admin, unsupported under MSIX).
2. Discover paths by asking each installed edition (`pwsh`, `powershell`) for `$PROFILE.<scope>`; never construct `~\Documents\...`. Skip an edition that is not installed; report what was written.
3. Pick the scope deliberately: CurrentUserCurrentHost gives console-only MOTD; CurrentUserAllHosts also fires in the VS Code terminal and ISE. Decide and document.
4. Marker-delimited block, ASCII-only, replace-in-place on re-run, remove-by-markers, refuse on unmatched markers, preserve the file's existing encoding/BOM and newlines.
5. Block body guarded by `Get-Command server-motd`, interactive-only.
6. Detect a `Restricted` effective execution policy (it silently disables profiles on Windows clients) and warn; do not change it.
7. Enable VT processing in-process via `SetConsoleMode`, degrade to plain text on failure, default to the 16-colour SGR set and an ASCII box fallback.
8. Windows system modules: omit load average; use `cpu_percent(interval=...)`; tolerate failing `disk_usage` on empty drives; users list is sessions only.
9. Docs: install via `pipx install server-motd`, run `pipx ensurepath`, open a new terminal; uninstall order is `server-motd uninstall-profile` then `pipx uninstall server-motd`.

## Not verified (needs a follow-up or a test on a real Windows box)

- Whether PowerShell 5.1 and PowerShell 7 hosts enable `ENABLE_VIRTUAL_TERMINAL_PROCESSING` before spawning a native child like `server-motd`, in Windows Terminal versus legacy conhost.
- The exact Windows 10 build at which conhost gained VT support, and conhost font/code-page behaviour for Unicode box characters.
- Whether `psutil.users()` includes RDP sessions.
- Behaviour of `Add-Content`/redirection vs Python byte-level writes for an existing profile with unusual encoding (the guidance above follows the documented encoding rules but was not exercised).
