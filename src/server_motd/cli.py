"""Command line entry point. The login invocation always exits 0."""

from __future__ import annotations

import argparse
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

from server_motd import profile, render, report, terminal
from server_motd.config import ConfigError


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
    check.add_argument(
        "--no-probe",
        action="store_true",
        help="validate the config only; contact nothing",
    )
    sub.add_parser("install-profile", help="add the profile block")
    sub.add_parser("uninstall-profile", help="remove the profile block")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "check":
            return _check(args)
        if args.command in ("install-profile", "uninstall-profile"):
            return profile.run(args.command)
        return _render(args)
    except Exception as exc:  # never block login
        print(f"server-motd: {exc}", file=sys.stderr)
        return 0


def _print_tracebacks(rep: report.Report) -> None:
    for o in rep.outcomes:
        if o.traceback:
            print(f"{o.title}:\n{o.traceback}", file=sys.stderr)


def _check(args: argparse.Namespace) -> int:
    try:
        rep = report.collect(args.config, probe=not args.no_probe)
    except ConfigError as exc:
        print(f"server-motd: {exc}", file=sys.stderr)
        return 1
    for warning in rep.warnings:
        print(f"FAIL  settings: {warning}")
    for o in rep.outcomes:
        print(
            f"FAIL  {o.title}: {o.failure.reason}" if o.failure else f"ok    {o.title}"
        )
    if args.verbose:
        _print_tracebacks(rep)
    return 1 if rep.failed else 0


def _render(args: argparse.Namespace) -> int:
    try:
        rep = report.collect(args.config)
    except ConfigError as exc:
        print(f"server-motd: {exc}", file=sys.stderr)
        return 0
    for warning in rep.warnings:
        print(f"server-motd: {warning}", file=sys.stderr)
    width = args.width or shutil.get_terminal_size((80, 24)).columns
    color = args.color == "always" or (args.color == "auto" and sys.stdout.isatty())
    if color and not terminal.enable_vt() and args.color == "auto":
        color = False  # console cannot render escape codes: plain text
    sys.stdout.write(render.render(rep.results, width, color, rep.title, rep.box))
    if args.verbose:
        _print_tracebacks(rep)
    return 0
