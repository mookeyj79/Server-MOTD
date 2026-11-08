"""Concurrent module runner, internal to `report`.

Each module runs in a daemon thread and is handed its deadline: MODULE_TIMEOUT
from its own start, capped by TOTAL_TIMEOUT for the whole run. A module that
raises, or is still running at its deadline, becomes a `Failed`.
"""

from __future__ import annotations

import threading
import time
import traceback
from collections.abc import Sequence
from dataclasses import dataclass

from server_motd.failure import Failure, FailureKind, classify
from server_motd.model import Deadline, Module, Result

MODULE_TIMEOUT = 3.0
TOTAL_TIMEOUT = 6.0


@dataclass(frozen=True)
class Failed:
    failure: Failure
    traceback: str | None = None


def run(modules: Sequence[Module]) -> list[Result | Failed]:
    """Fetch all modules concurrently; results keep the input order."""
    slots: list[Result | Failed | None] = [None] * len(modules)

    def work(i: int, module: Module, deadline: Deadline) -> None:
        try:
            slots[i] = module.fetch(deadline)
        except Exception as exc:
            slots[i] = Failed(classify(exc), traceback.format_exc())

    run_end = time.monotonic() + TOTAL_TIMEOUT
    threads: list[tuple[threading.Thread, Deadline]] = []
    for i, module in enumerate(modules):
        deadline = Deadline(min(time.monotonic() + MODULE_TIMEOUT, run_end))
        t = threading.Thread(target=work, args=(i, module, deadline), daemon=True)
        t.start()
        threads.append((t, deadline))
    for t, deadline in threads:
        t.join(deadline.remaining())
    timed_out = Failed(Failure(FailureKind.TIMED_OUT))
    return [slot if slot is not None else timed_out for slot in slots]
