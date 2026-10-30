# Changelog

Hand-written. Versions follow `pyproject.toml` and stay 0.x until the v1 scope
ships. Each release needs a `## [x.y.z]` heading here; the release workflow
fails without one and uses the section as the GitHub Release notes.

## [Unreleased]

- Added a rewritten README with a golden-tested sample output, a tested `docs/example-config.toml` covering every module kind, and a Markdown docs set (Debian/Ansible and Windows install, configuration reference, secrets, troubleshooting, v1 migration note).
- Documented that the Tautulli bandwidth unit (assumed kbps) is unverified.
- Removed the legacy v1 bash/Python code (`motd/`, `media-server-motd.py`, `utils/`, `install.sh`, `requirements.txt`, `config.json.example`); it remains in the `legacy-v1` git tag.

## [0.1.0]

- Initial release of the `server-motd` rewrite: CI skeleton and package scaffold.
