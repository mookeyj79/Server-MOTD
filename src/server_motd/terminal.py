"""Windows console setup: switch on ANSI (VT) processing for stdout.

Legacy conhost ignores escape codes unless ENABLE_VIRTUAL_TERMINAL_PROCESSING is
set on the output handle. Everything here is defensive: any failure means
"no VT", and the caller falls back to plain text.
"""

from __future__ import annotations

import ctypes
import sys

_STD_OUTPUT_HANDLE = -11
_ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004


def enable_vt() -> bool:
    """Enable VT processing on the console; True if escape codes will render.

    Non-Windows platforms always handle escape codes, so they return True.
    """
    if sys.platform != "win32":
        return True
    try:
        kernel32 = getattr(ctypes, "windll").kernel32  # noqa: B009
        handle = kernel32.GetStdHandle(_STD_OUTPUT_HANDLE)
        mode = ctypes.c_ulong()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        if mode.value & _ENABLE_VIRTUAL_TERMINAL_PROCESSING:
            return True
        new_mode = mode.value | _ENABLE_VIRTUAL_TERMINAL_PROCESSING
        return bool(kernel32.SetConsoleMode(handle, new_mode))
    except Exception:
        return False
