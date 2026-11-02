# CLAUDE.md

Run all Python through `uv`: `uv run --extra dev pytest` (dev tools are the `dev` extra), `uv run python …`, `uv tool` in place of pipx. `uv` works on the Windows host; a bare `python3` there is a Store stub that hangs or fails silently, and there is no `jq`. Ansible needs the Debian WSL distro, which has no `uv` installed.

Plan and decisions: GitHub issue #1 (the wayfinder map) and `docs/adr/`. Before touching an external API, the Debian MOTD, or the Windows profile hook, read the matching note in `docs/research/`.

The removed v1 bash/Python code lives in the local git tag `legacy-v1`; keep that tag local (never push it).

## Agent skills

- Issue tracker: GitHub Issues via `gh`. See `docs/agents/issue-tracker.md`.
- Triage labels: `docs/agents/triage-labels.md`.
- Domain docs (single-context): `GLOSSARY.md` and `docs/adr/`. See `docs/agents/domain.md`.
