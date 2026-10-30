"""Core schema: Status, Row, Result and the Module protocol.

The schema carries no layout. The renderer maps Status to colour.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class Status(Enum):
    INFO = "info"
    OK = "ok"
    WARN = "warn"
    CRIT = "crit"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class Row:
    label: str
    value: str
    status: Status = Status.INFO


@dataclass(frozen=True)
class Result:
    title: str
    rows: list[Row] = field(default_factory=list)
    status: Status = Status.INFO


class Module(Protocol):
    """A synchronous unit of MOTD output. `fetch` raises on failure."""

    def fetch(self) -> Result: ...
