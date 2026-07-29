"""Per-Monitor-V2 DPI bootstrap. Must run before any HWND exists."""

from __future__ import annotations

import ctypes
import sys

_PMV2 = ctypes.c_void_p(-4)
_enabled = False


def enable_pmv2() -> bool:
    """Idempotently set PMv2 for this process; True when effective."""

    global _enabled
    if sys.platform != "win32":
        return False
    if _enabled:
        return True
    result = bool(ctypes.windll.user32.SetProcessDpiAwarenessContext(_PMV2))
    if not result:
        # Already set (e.g. by an embedding host) is acceptable when the
        # active context is PMv2; anything else is a hard failure upstream.
        current = ctypes.windll.user32.GetThreadDpiAwarenessContext()
        result = bool(ctypes.windll.user32.AreDpiAwarenessContextsEqual(
            current, _PMV2))
    _enabled = result
    return result
