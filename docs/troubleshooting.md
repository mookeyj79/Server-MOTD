# Troubleshooting

## Start with `check`

```bash
server-motd check            # uses the default config location
server-motd --config path/to/config.toml check
server-motd check --verbose  # adds exception detail on stderr
```

`check` validates the config, probes every module and prints one line each: `ok  <title>` or `FAIL  <title>: <reason>`. Exit status is 0 when everything is fine and non-zero if the config is missing or any module fails. The normal (login) invocation always exits 0 so it can never block a login.

Config is looked for at `/etc/server-motd/config.toml` on Linux, and `%APPDATA%\server-motd\config.toml` then `%ProgramData%\server-motd\config.toml` on Windows. `--config` overrides discovery.

## Common messages

- `no config file found (looked in ...)`: create the file or pass `--config`.
- `UNAVAILABLE: invalid config: unknown option(s): foo`: a key is misspelt or not valid for that module kind; see the [configuration reference](configuration.md). Only that module is affected.
- `invalid config: unknown kind 'x'`: check the spelling against the list of kinds.
- `invalid config: 'api_key' references unset variable NAME`: the environment variable is not set in the process that runs the MOTD (see [secrets](secrets.md)).
- `UNAVAILABLE: timed out`: a module is limited to 3 seconds and the whole run to 6. Check the service URL and that it is reachable from this host.
- An HTTP error such as 401 from a service usually means a wrong API key.
- `load is not available on Windows`: use the `cpu` module.

## Verbose output

`--verbose` prints per-module exception detail to stderr after the output, for both rendering and `check`:

```bash
server-motd --verbose
```

## Layout

- Output width follows the terminal; force it with `--width 100`.
- `--color never` gives plain text; `--color always` forces colour. The default turns colour on only for a terminal.
- A figlet banner needs `pip install "server-motd[figlet]"` and is skipped when the art does not fit.

## Known limitation

The Tautulli `Bandwidth` row assumes the value Tautulli reports is in kilobits per second (as Plex reports it). Tautulli does not document the unit and this has not been verified against a live instance, so treat the figure as approximate until confirmed. See [the research notes](research/tautulli-api.md).
