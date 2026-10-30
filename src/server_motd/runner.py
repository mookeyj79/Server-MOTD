"""Concurrent module runner.

Modules run in daemon threads; a module that raises or overruns its timeout
becomes an UNAVAILABLE result.
"""

from __future__ import annotations

import threading
import time
import traceback
from collections.abc import Sequence

from server_motd.model import Module, Result, Row, Status

MODULE_TIMEOUT = 3.0
TOTAL_TIMEOUT = 6.0


def unavailable(title: str, reason: str) -> Result:
    row = Row("Status", f"UNAVAILABLE: {reason}", Status.UNAVAILABLE)
    return Result(title, [row], Status.UNAVAILABLE)


def run(
    modules: Sequence[tuple[str, Module]], verbose_log: list[str] | None = None
) -> list[Result]:
    """Fetch all modules concurrently; results keep the input order.

    Each item is (fallback title, module). `verbose_log` collects tracebacks.
    """
    slots: list[Result | None] = [None] * len(modules)

    def work(i: int, title: str, module: Module) -> None:
        try:
            slots[i] = module.fetch()
        except Exception as exc:
            if verbose_log is not None:
                verbose_log.append(f"{title}:\n{traceback.format_exc()}")
            slots[i] = unavailable(title, str(exc) or type(exc).__name__)

    start = time.monotonic()
    threads = []
    for i, (title, module) in enumerate(modules):
        t = threading.Thread(target=work, args=(i, title, module), daemon=True)
        t.start()
        threads.append(t)
    deadline = start + min(MODULE_TIMEOUT, TOTAL_TIMEOUT)
    for t in threads:
        t.join(max(0.0, deadline - time.monotonic()))
    return [
        slot if slot is not None else unavailable(modules[i][0], "timed out")
        for i, slot in enumerate(slots)
    ]
