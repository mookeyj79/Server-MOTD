"""Helpers shared by system modules: warn/crit thresholds and size formatting."""

from __future__ import annotations

from collections.abc import Iterable

from server_motd.config import ConfigError, ModuleSpec
from server_motd.model import Row, Status

_SEVERITY = [Status.INFO, Status.OK, Status.WARN, Status.CRIT]


class Thresholds:
    """Optional `warn` / `crit` options; a value >= a limit takes that status."""

    def __init__(self, spec: ModuleSpec) -> None:
        self.warn: float | None = spec.take("warn", float)
        self.crit: float | None = spec.take("crit", float)
        if self.warn is not None and self.crit is not None and self.warn > self.crit:
            raise ConfigError("'warn' must not exceed 'crit'")

    def status(self, value: float) -> Status:
        if self.warn is None and self.crit is None:
            return Status.INFO
        if self.crit is not None and value >= self.crit:
            return Status.CRIT
        if self.warn is not None and value >= self.warn:
            return Status.WARN
        return Status.OK


def worst(rows: Iterable[Row]) -> Status:
    """Overall status: the most severe row status."""
    return max((r.status for r in rows), key=_SEVERITY.index, default=Status.INFO)


def human_bytes(n: float) -> str:
    for unit in "BKMGT":
        if n < 1024 or unit == "T":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    raise AssertionError("unreachable")
