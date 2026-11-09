"""Deadlines: the time budget a module's fetch must finish within.

A `Deadline` is a point in `time.monotonic()` time. Everything that waits
takes its timeout from the time left (`left()`, which raises TimedOut once it
has passed), and concurrent work is bounded by it (`gather`). The run's
budget (per module, and for the whole run) is a `Budget`.

`settle` is the one fan-out: each job runs in a daemon thread, so work that
overruns its deadline never delays process exit.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from server_motd.failure import TimedOut


@dataclass(frozen=True)
class Deadline:
    at: float

    @classmethod
    def after(cls, seconds: float) -> Deadline:
        return cls(time.monotonic() + seconds)

    def remaining(self) -> float:
        return max(0.0, self.at - time.monotonic())

    def left(self) -> float:
        """Seconds left, for a socket timeout; raise TimedOut if none."""
        left = self.remaining()
        if left <= 0:
            raise TimedOut()
        return left

    def gather(self, *calls: Callable[[], Any]) -> list[Any]:
        """Run calls concurrently; their results in order.

        Raises TimedOut if any is still running at the deadline, otherwise the
        first call's error.
        """
        settled = settle([(call, self) for call in calls])
        if any(not s.done for s in settled):
            raise TimedOut()
        for s in settled:
            if s.error is not None:
                raise s.error
        return [s.value for s in settled]


@dataclass(frozen=True)
class Budget:
    """How long modules get: each from its own start, all within `total`."""

    per_module: float = 3.0
    total: float = 6.0

    def deadline(self) -> Deadline:
        """The deadline for modules starting now. They all start together,
        so the tighter of the two limits applies."""
        return Deadline.after(min(self.per_module, self.total))


DEFAULT_BUDGET = Budget()


@dataclass
class Settled:
    """How one job ended: `done` with a `value` or an `error`, or not done."""

    done: bool = False
    value: Any = None
    error: BaseException | None = None


def settle(jobs: Sequence[tuple[Callable[[], Any], Deadline]]) -> list[Settled]:
    """Run each job in a daemon thread and wait for each until its deadline."""
    slots = [Settled() for _ in jobs]

    def work(slot: Settled, fn: Callable[[], Any]) -> None:
        try:
            slot.value = fn()
        except BaseException as exc:
            slot.error = exc
        slot.done = True

    threads = []
    for slot, (fn, deadline) in zip(slots, jobs, strict=True):
        t = threading.Thread(target=work, args=(slot, fn), daemon=True)
        t.start()
        threads.append((t, deadline))
    for t, deadline in threads:
        t.join(deadline.remaining())
    return slots
