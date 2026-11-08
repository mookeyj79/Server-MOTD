# CLAUDE.md

Plan and decisions: GitHub issue #1 (the wayfinder map) and `docs/adr/`. Before touching an external API, the Debian MOTD, or the Windows profile hook, read the matching note in `docs/research/`.

The removed v1 bash/Python code lives in the local git tag `legacy-v1`; keep that tag local (never push it).

## Agent skills

- Issue tracker: GitHub Issues via `gh`. See `docs/agents/issue-tracker.md`.
- Triage labels: `docs/agents/triage-labels.md`.
- Domain docs (single-context): `GLOSSARY.md` and `docs/adr/`. See `docs/agents/domain.md`.
