"""The MOTD pipeline: config file in, one ordered Outcome per Instance out.

`collect` reads the config once, validates the settings and every Instance,
fetches the modules concurrently (unless `probe=False`) and returns a Report.
Rendering and `check` are both presentations of a Report.
"""

from __future__ import annotations

import dataclasses
import socket
from dataclasses import dataclass, field
from pathlib import Path

from server_motd import config, runner
from server_motd.config import BadEntry, ConfigError, ModuleSpec
from server_motd.failure import Failure, FailureKind
from server_motd.model import Module, Result, Row, Status
from server_motd.modules import REGISTRY
from server_motd.render import BOX_STYLES


@dataclass(frozen=True)
class Outcome:
    """One enabled Instance: its title, and what it showed or why it failed.

    `result` is the Result to render: the module's own, or an UNAVAILABLE one
    built from `failure`. It is None only when the report was not probed and
    the Instance built cleanly.
    """

    title: str
    result: Result | None
    failure: Failure | None = None
    traceback: str | None = None


@dataclass(frozen=True)
class Report:
    title: str  # the banner: `title` from the config, else the host name
    box: str  # a key of render.BOX_STYLES
    outcomes: list[Outcome]
    warnings: list[str] = field(default_factory=list)  # settings problems

    @property
    def results(self) -> list[Result]:
        return [o.result for o in self.outcomes if o.result is not None]

    @property
    def failed(self) -> bool:
        return bool(self.warnings) or any(o.failure for o in self.outcomes)


def unavailable(title: str, failure: Failure) -> Result:
    row = Row("Status", f"UNAVAILABLE: {failure.reason}", Status.UNAVAILABLE)
    return Result([row], title)


def collect(path: Path | None, *, probe: bool = True) -> Report:
    """Build the Report for the config at `path` (or the discovered one).

    File-level config problems raise ConfigError. Everything about a single
    Instance, including its config errors, lands in its Outcome.
    """
    loaded = config.load(path)
    warnings: list[str] = []
    box = loaded.settings.box
    if box not in BOX_STYLES:
        warnings.append(f"unknown box style '{box}', using single")
        box = "single"
    title = loaded.settings.title or socket.gethostname()

    slots: list[Outcome | tuple[str, Module]] = []
    for entry in loaded.entries:
        if isinstance(entry, BadEntry):
            slots.append(
                _failed(entry.label, FailureKind.INVALID_CONFIG, entry.message)
            )
        elif entry.enabled:
            slots.append(_build(entry))

    to_run = [s[1] for s in slots if isinstance(s, tuple)]
    fetched = iter(runner.run(to_run) if probe else [None] * len(to_run))
    outcomes = [
        s if isinstance(s, Outcome) else _finish(s[0], next(fetched)) for s in slots
    ]
    return Report(title, box, outcomes, warnings)


def _build(spec: ModuleSpec) -> Outcome | tuple[str, Module]:
    kind = REGISTRY.get(spec.kind)
    title = spec.name or (kind.title if kind else spec.kind)
    if kind is None:
        return _failed(title, FailureKind.INVALID_CONFIG, f"unknown kind '{spec.kind}'")
    try:
        module = kind.factory(spec)
        spec.done()
    except ConfigError as exc:
        return _failed(title, FailureKind.INVALID_CONFIG, str(exc))
    return title, module


def _failed(
    title: str, kind: FailureKind, detail: str, traceback: str | None = None
) -> Outcome:
    failure = Failure(kind, detail)
    return Outcome(title, unavailable(title, failure), failure, traceback)


def _finish(title: str, fetched: Result | runner.Failed | None) -> Outcome:
    if fetched is None:
        return Outcome(title, None)
    if isinstance(fetched, runner.Failed):
        f = fetched.failure
        return _failed(title, f.kind, f.detail, fetched.traceback)
    return Outcome(title, dataclasses.replace(fetched, title=title))
