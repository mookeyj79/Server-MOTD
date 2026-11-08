"""Formatting shared by the modules."""

from __future__ import annotations


def human_bytes(n: float) -> str:
    for unit in "BKMGT":
        if n < 1024 or unit == "T":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    raise AssertionError("unreachable")
