# Secrets

API keys and passwords (`api_key`, `password`) can be given three ways. Use at most one per secret.

1. Inline: `api_key = "abc123"`. The config file should then be readable only by the account that runs the MOTD (the Ansible role sets mode 0600).
2. Environment variable: `api_key = "${SONARR_API_KEY}"`. Expanded when the config loads; an unset variable is a validation error for that module. The login hook does not inherit your shell environment, so on Debian prefer a file or an inline vaulted value.
3. File: `api_key_file = "/etc/server-motd/sonarr.key"` (or `password_file`). The file's contents, with surrounding whitespace trimmed, are the secret. An unreadable file is a validation error for that module.

Setting both `api_key` and `api_key_file` is an error. Secrets are never printed; `check --verbose` shows tracebacks, not config values.
