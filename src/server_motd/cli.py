"""Command line entry point. The login invocation always exits 0."""

from __future__ import annotations

import argparse
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

from server_motd import config, render, runner
from server_motd.config import BadEntry, ConfigError
from server_motd.model import Module, Result
from server_motd.modules import REGISTRY


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="server-motd")
    p.add_argument("--config", type=Path, help="config file (overrides discovery)")
    p.add_argument("--width", type=int, help="output width in columns")
    p.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    p.add_argument("--verbose", action="store_true", help="show exception detail")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _render(args)
    except Exception as exc:  # never block login
        print(f"server-motd: {exc}", file=sys.stderr)
        return 0


def _bad(title: str, message: str) -> Result:
    return runner.unavailable(title, f"invalid config: {message}")


def _render(args: argparse.Namespace) -> int:
    try:
        entries = config.load(args.config)
    except ConfigError as exc:
        print(f"server-motd: {exc}", file=sys.stderr)
        return 0
    # Config order is preserved: each item is a ready Result or a Module to run.
    items: list[tuple[str, Module | Result]] = []
    for entry in entries:
        if isinstance(entry, BadEntry):
            items.append((entry.label, _bad(entry.label, entry.message)))
            continue
        if not entry.enabled:
            continue
        title = entry.name or entry.kind
        factory = REGISTRY.get(entry.kind)
        if factory is None:
            items.append((title, _bad(title, f"unknown kind '{entry.kind}'")))
            continue
        try:
            items.append((title, factory(entry)))
        except ConfigError as exc:
            items.append((title, _bad(title, str(exc))))

    log: list[str] = []
    to_run = [(t, m) for t, m in items if not isinstance(m, Result)]
    fetched = iter(runner.run(to_run, log))
    results = [m if isinstance(m, Result) else next(fetched) for _, m in items]

    width = args.width or shutil.get_terminal_size((80, 24)).columns
    color = args.color == "always" or (args.color == "auto" and sys.stdout.isatty())
    sys.stdout.write(render.render(results, width, color))
    if args.verbose:
        for entry_log in log:
            print(entry_log, file=sys.stderr)
    return 0
