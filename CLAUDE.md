# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

The code below is **legacy v1** (Debian/Ubuntu bash fragments plus a Python helper). It is being replaced by `server-motd`, a single Python package; the plan lives in GitHub issue #1 (the wayfinder map) and `docs/adr/`. Domain terms are in `GLOSSARY.md`.

The Windows host has no working `python3` or `jq` (`python3` is a Store stub that hangs or fails silently, and a bare `python -` waits on stdin forever); script and run everything in the Debian WSL distro.

Touching `motd/`, `media-server-motd.py`, `utils/` or `install.sh`: read `docs/legacy-v1.md` first.

Research notes behind the decisions (APIs, Debian and Windows mechanics) are in `docs/research/`.

## Agent skills

### Issue tracker

Issues are tracked in GitHub Issues for this repo (via `gh`). See `docs/agents/issue-tracker.md`.

### Triage labels

Label vocabulary (`ready-for-agent`): `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
