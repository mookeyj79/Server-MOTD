# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

`server-motd` is a single Python package (`src/server_motd`) with an Ansible role in `ansible/`. The plan and decisions live in GitHub issue #1 (the wayfinder map) and `docs/adr/`; user docs are in `README.md` and `docs/`. Domain terms are in `GLOSSARY.md`. The old v1 bash/Python code was removed; it is preserved in the local git tag `legacy-v1` (never pushed) for reference.

The Windows host has no working `python3` or `jq` (`python3` is a Store stub that hangs or fails silently, and a bare `python -` waits on stdin forever); script and run everything in the Debian WSL distro.

Research notes behind the decisions (APIs, Debian and Windows mechanics) are in `docs/research/`.

## Agent skills

### Issue tracker

Issues are tracked in GitHub Issues for this repo (via `gh`). See `docs/agents/issue-tracker.md`.

### Triage labels

Label vocabulary (`ready-for-agent`): `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
