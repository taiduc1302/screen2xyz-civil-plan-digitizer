"""Global Windows capture hotkeys implemented with the Win32 API."""

from __future__ import annotations

import sys
import threading
from collections.abc import Callable

HOTKEYS = {
    1: (0x0002 | 0x0004, 0x78, "start/pause"),  # Ctrl+Shift+F9
    2: (0x0002 | 0x0004, 0x79, "stop"),         # Ctrl+Shift+F10
    3: (0x0002 | 0x0004, 0x7A, "force capture"),# Ctrl+Shift+F11
}


class GlobalHotkeys:
    """RegisterHotKey wrapper; callbacks are marshalled by the caller."""

    def __init__(self, callbacks: dict[str, Callable[[], None]]) -> None:
        self.callbacks = callbacks
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._ready = threading.Event()
        self.error: str | None = None

    @property
    def supported(self) -> bool:
        return sys.platform == "win32"

    def start(self) -> bool:
        if not self.supported:
            self.error = "Global hotkeys require Windows."
            return False
        if self._thread is not None:
            return True
        self._ready.clear()
        self._thread = threading.Thread(target=self._message_loop, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=2)
        return self.error is None

    def stop(self) -> None:
        if self._thread_id is None:
            return
        import ctypes

        ctypes.windll.user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._thread = None
        self._thread_id = None

    def register_with(self, user32) -> list[int]:
        """Register the declared keys against a Win32-compatible API object."""
        registered: list[int] = []
        for hotkey_id, (modifiers, virtual_key, _name) in HOTKEYS.items():
            if not user32.RegisterHotKey(None, hotkey_id, modifiers, virtual_key):
                for prior_id in registered:
                    user32.UnregisterHotKey(None, prior_id)
                raise RuntimeError("A Screen2XYZ global hotkey is already in use.")
            registered.append(hotkey_id)
        return registered

    def dispatch(self, hotkey_id: int) -> bool:
        descriptor = HOTKEYS.get(hotkey_id)
        callback = None if descriptor is None else self.callbacks.get(descriptor[2])
        if callback is None:
            return False
        callback()
        return True

    def _message_loop(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = int(kernel32.GetCurrentThreadId())
        registered: list[int] = []
        try:
            try:
                registered = self.register_with(user32)
            except RuntimeError as exc:
                self.error = str(exc)
                return
            self._ready.set()
            message = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                if message.message == 0x0312:
                    self.dispatch(int(message.wParam))
        finally:
            for hotkey_id in registered:
                user32.UnregisterHotKey(None, hotkey_id)
            self._ready.set()

    def __enter__(self) -> "GlobalHotkeys":
        self.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.stop()
