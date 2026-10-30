"""Command line entry point. The login invocation always exits 0."""

from __future__ import annotations

import argparse
import shutil
import socket
import sys
from collections.abc import Sequence
from pathlib import Path

from server_motd import config, render, runner
from server_motd.config import BadEntry, ConfigError, ModuleSpec
from server_motd.model import Module, Result, Status
from server_motd.modules import REGISTRY


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="server-motd")
    p.add_argument("--config", type=Path, help="config file (overrides discovery)")
    p.add_argument("--width", type=int, help="output width in columns")
    p.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    p.add_argument("--verbose", action="store_true", help="show exception detail")
    sub = p.add_subparsers(dest="command")  # no subcommand = render
    check = sub.add_parser("check", help="validate the config and probe every module")
    # SUPPRESS keeps values given before the subcommand from being overwritten.
    check.add_argument("--config", type=Path, default=argparse.SUPPRESS)
    check.add_argument("--verbose", action="store_true", default=argparse.SUPPRESS)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "check":
            return _check(args)
        return _render(args)
    except Exception as exc:  # never block login
        print(f"server-motd: {exc}", file=sys.stderr)
        return 0


def _bad(title: str, message: str) -> Result:
    return runner.unavailable(title, f"invalid config: {message}")


def _build_items(
    entries: list[ModuleSpec | BadEntry],
) -> list[tuple[str, Module | Result]]:
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
    return items


def _check(args: argparse.Namespace) -> int:
    try:
        entries = config.load(args.config)
    except ConfigError as exc:
        print(f"server-motd: {exc}", file=sys.stderr)
        return 1
    items = _build_items(entries)
    log: list[str] = []
    to_run = [(t, m) for t, m in items if not isinstance(m, Result)]
    fetched = iter(runner.run(to_run, log))
    failed = False
    for title, item in items:
        result = item if isinstance(item, Result) else next(fetched)
        if result.status is Status.UNAVAILABLE:
            failed = True
            reason = result.rows[0].value.removeprefix("UNAVAILABLE: ")
            print(f"FAIL  {title}: {reason}")
        else:
            print(f"ok    {title}")
    if args.verbose:
        for entry_log in log:
            print(entry_log, file=sys.stderr)
    return 1 if failed else 0


def _render(args: argparse.Namespace) -> int:
    try:
        entries = config.load(args.config)
        settings = config.load_settings(args.config)
    except ConfigError as exc:
        print(f"server-motd: {exc}", file=sys.stderr)
        return 0
    items = _build_items(entries)

    log: list[str] = []
    to_run = [(t, m) for t, m in items if not isinstance(m, Result)]
    fetched = iter(runner.run(to_run, log))
    results = [m if isinstance(m, Result) else next(fetched) for _, m in items]

    width = args.width or shutil.get_terminal_size((80, 24)).columns
    color = args.color == "always" or (args.color == "auto" and sys.stdout.isatty())
    box = settings.box
    if box not in render.BOX_STYLES:
        print(f"server-motd: unknown box style '{box}', using single", file=sys.stderr)
        box = "single"
    title = settings.title or socket.gethostname()
    sys.stdout.write(render.render(results, width, color, title, box))
    if args.verbose:
        for entry_log in log:
            print(entry_log, file=sys.stderr)
    return 0
