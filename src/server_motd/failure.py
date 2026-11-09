"""Why a module is unavailable: the failure kinds and the one place they're decided.

Transports and modules raise a `ModuleError` subclass when they know the
kind. Anything else a module raises is classified by `classify`:
lookup/type/value errors while reading a reply are a bad response, socket
timeouts are a timeout, `ConfigError` is invalid config.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from server_motd.config import ConfigError


class FailureKind(Enum):
    INVALID_CONFIG = "invalid config"
    UNREACHABLE = "unreachable"
    AUTH_FAILED = "auth failed"
    API_ERROR = "API error"
    BAD_RESPONSE = "bad response"
    TIMED_OUT = "timed out"
    ERROR = "error"  # anything else; the reason is the detail alone


@dataclass(frozen=True)
class Failure:
    kind: FailureKind
    detail: str = ""

    @property
    def reason(self) -> str:
        """The text shown after `UNAVAILABLE: ` and after `FAIL  <title>: `."""
        if self.kind is FailureKind.ERROR:
            return self.detail or "error"
        return f"{self.kind.value}: {self.detail}" if self.detail else self.kind.value


class ModuleError(Exception):
    """A failure whose kind is known where it is raised."""

    kind = FailureKind.ERROR

    def __init__(self, detail: str = "") -> None:
        super().__init__(detail)
        self.detail = detail


class Unreachable(ModuleError):
    kind = FailureKind.UNREACHABLE


class AuthFailed(ModuleError):
    kind = FailureKind.AUTH_FAILED


class ApiError(ModuleError):
    kind = FailureKind.API_ERROR


class BadResponse(ModuleError):
    kind = FailureKind.BAD_RESPONSE


class TimedOut(ModuleError):
    kind = FailureKind.TIMED_OUT


def classify(exc: BaseException) -> Failure:
    if isinstance(exc, ModuleError):
        return Failure(exc.kind, exc.detail)
    if isinstance(exc, ConfigError):
        return Failure(FailureKind.INVALID_CONFIG, str(exc))
    if isinstance(exc, TimeoutError):
        return Failure(FailureKind.TIMED_OUT)
    if isinstance(exc, KeyError):
        return Failure(FailureKind.BAD_RESPONSE, f"missing {exc}")
    if isinstance(exc, IndexError | TypeError | AttributeError | ValueError):
        return Failure(FailureKind.BAD_RESPONSE, str(exc) or type(exc).__name__)
    return Failure(FailureKind.ERROR, str(exc) or type(exc).__name__)
