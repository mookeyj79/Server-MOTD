"""Core schema: Status, Row, Result, Thresholds, Deadline and the Module protocol.

The schema carries no layout. The renderer maps Status to colour.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class Status(Enum):
    """Health of a row or result, least to most severe."""

    INFO = "info"
    OK = "ok"
    WARN = "warn"
    CRIT = "crit"
    UNAVAILABLE = "unavailable"

    @property
    def severity(self) -> int:
        return _SEVERITY.index(self)

    @staticmethod
    def worst(statuses: Iterable[Status]) -> Status:
        """The most severe status, or INFO for none."""
        return max(statuses, key=lambda s: s.severity, default=Status.INFO)


_SEVERITY = list(Status)


@dataclass(frozen=True)
class Row:
    label: str
    value: str
    status: Status = Status.INFO


@dataclass(frozen=True)
class Result:
    """What a module returns. The pipeline stamps `title` from the Instance.

    Status lives on rows only: a module says something is wrong by putting a
    status on the row that shows it.
    """

    rows: list[Row] = field(default_factory=list)
    title: str = ""

    @property
    def status(self) -> Status:
        """Overall status: the most severe row status."""
        return Status.worst(r.status for r in self.rows)


@dataclass(frozen=True)
class Thresholds:
    """Optional warn / crit limits; a value >= a limit takes that status."""

    warn: float | None = None
    crit: float | None = None

    def status(self, value: float, under: Status = Status.OK) -> Status:
        """CRIT / WARN at or over a limit; `under` below them; INFO with none set."""
        if self.warn is None and self.crit is None:
            return Status.INFO
        if self.crit is not None and value >= self.crit:
            return Status.CRIT
        if self.warn is not None and value >= self.warn:
            return Status.WARN
        return under


@dataclass(frozen=True)
class Deadline:
    """A point in `time.monotonic()` time by which a module must finish."""

    at: float

    @classmethod
    def after(cls, seconds: float) -> Deadline:
        return cls(time.monotonic() + seconds)

    def remaining(self) -> float:
        return max(0.0, self.at - time.monotonic())


class Module(Protocol):
    """A synchronous unit of MOTD output.

    Constructed from a `ModuleSpec` (take options; raise `ConfigError`).
    `fetch` must finish by `deadline` and raises on failure (see `failure`).
    Status goes on the rows; the Result's overall status is derived.
    """

    def fetch(self, deadline: Deadline) -> Result: ...
