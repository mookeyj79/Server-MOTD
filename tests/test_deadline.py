"""`Deadline` directly: time left and deadline-bounded gather, no server needed."""

from __future__ import annotations

import threading
import time

import pytest

from server_motd.deadline import Budget, Deadline
from server_motd.failure import TimedOut


def test_gather_returns_results_in_call_order() -> None:
    def slow() -> str:
        time.sleep(0.05)
        return "slow"

    assert Deadline.after(1.0).gather(slow, lambda: "fast") == ["slow", "fast"]


def test_gather_raises_the_first_calls_error() -> None:
    def bad(msg: str) -> None:
        raise ValueError(msg)

    with pytest.raises(ValueError, match="first"):
        Deadline.after(1.0).gather(lambda: 1, lambda: bad("first"), lambda: bad("2nd"))


def test_gather_times_out_promptly_and_leaves_no_blocking_thread() -> None:
    release = threading.Event()
    start = time.monotonic()
    with pytest.raises(TimedOut):
        Deadline.after(0.1).gather(lambda: 1, release.wait)
    assert time.monotonic() - start < 0.5
    blocking = [t for t in threading.enumerate() if t.is_alive() and not t.daemon]
    assert blocking == [threading.main_thread()]
    release.set()


def test_left_raises_once_passed() -> None:
    assert 0 < Deadline.after(1.0).left() <= 1.0
    with pytest.raises(TimedOut):
        Deadline.after(0.0).left()


def test_budget_takes_the_tighter_limit() -> None:
    assert Budget(per_module=10.0, total=0.5).deadline().remaining() <= 0.5
    assert Budget(per_module=0.5, total=10.0).deadline().remaining() <= 0.5
