"""Target-window and monitor enumeration plus environment snapshots."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any

from . import contracts as C

if sys.platform == "win32":
    user32 = ctypes.windll.user32
    _ENUM_WINDOWS = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND,
                                       wintypes.LPARAM)
    _ENUM_MONITORS = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
        ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)


@dataclass(frozen=True)
class WindowTarget:
    hwnd: int
    pid: int
    title: str


@dataclass(frozen=True)
class MonitorTarget:
    index: int
    x: int
    y: int
    w: int
    h: int


def _window_pid(hwnd: int) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def bounded_title(title: str) -> str:
    printable = "".join(ch if ch.isprintable() else " " for ch in title)
    return printable.encode("utf-8")[:C.TITLE_MAX_BYTES] \
        .decode("utf-8", errors="ignore")


def list_windows() -> list[WindowTarget]:
    found: list[WindowTarget] = []

    @_ENUM_WINDOWS
    def visit(hwnd: int, _lparam: int) -> bool:
        if user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buffer = ctypes.create_unicode_buffer(length + 1)
                if user32.GetWindowTextW(hwnd, buffer, length + 1) > 0:
                    pid = _window_pid(hwnd)
                    if pid:
                        found.append(WindowTarget(int(hwnd), pid,
                                                  bounded_title(buffer.value)))
        return True

    user32.EnumWindows(visit, 0)
    return found


def list_monitors() -> list[MonitorTarget]:
    monitors: list[MonitorTarget] = []

    @_ENUM_MONITORS
    def visit(_hmon, _hdc, rect_ptr, _lparam) -> bool:
        rect = rect_ptr.contents
        monitors.append(MonitorTarget(len(monitors), rect.left, rect.top,
                                      rect.right - rect.left,
                                      rect.bottom - rect.top))
        return True

    user32.EnumDisplayMonitors(None, None, visit, 0)
    return monitors


def window_alive(target: WindowTarget) -> bool:
    return bool(user32.IsWindow(target.hwnd)
                and _window_pid(target.hwnd) == target.pid)


def window_client_info(hwnd: int) -> dict[str, Any]:
    rect = wintypes.RECT()
    exists = bool(user32.IsWindow(hwnd))
    iconic = bool(user32.IsIconic(hwnd)) if exists else False
    info: dict[str, Any] = {"exists": exists, "iconic": iconic,
                            "client_w": 0, "client_h": 0,
                            "origin_x": 0, "origin_y": 0, "dpi": 0}
    if exists and user32.GetClientRect(hwnd, ctypes.byref(rect)):
        info["client_w"] = rect.right
        info["client_h"] = rect.bottom
        point = wintypes.POINT(0, 0)
        user32.ClientToScreen(hwnd, ctypes.byref(point))
        info["origin_x"], info["origin_y"] = point.x, point.y
        info["dpi"] = int(user32.GetDpiForWindow(hwnd))
    return info


def window_visibility(client_w: int, client_h: int, origin_x: int,
                      origin_y: int,
                      virtual_screen: dict[str, Any]) -> dict[str, Any]:
    """Pure check of whether a window's client rect is fully contained in
    the virtual (all-monitors) screen bounds. CopyFromScreen can only ever
    see on-screen pixels, so a partially off-screen window loses whatever
    falls outside these bounds regardless of occlusion by other windows."""

    vx = virtual_screen.get("x", 0)
    vy = virtual_screen.get("y", 0)
    vw = virtual_screen.get("w", 0)
    vh = virtual_screen.get("h", 0)
    left_off = max(0, vx - origin_x)
    top_off = max(0, vy - origin_y)
    right_off = max(0, (origin_x + client_w) - (vx + vw))
    bottom_off = max(0, (origin_y + client_h) - (vy + vh))
    fully_visible = not (left_off or top_off or right_off or bottom_off)
    return {"fully_visible": fully_visible,
            "off_screen_px": {"left": left_off, "top": top_off,
                              "right": right_off, "bottom": bottom_off}}


def environment_snapshot(scope: dict[str, Any],
                         backend: str | None = None) -> dict[str, Any]:
    window: dict[str, Any] = {}
    if scope.get("type") == "window":
        window = window_client_info(int(scope.get("hwnd", 0)))
    monitors = [{"index": m.index, "x": m.x, "y": m.y, "w": m.w, "h": m.h}
                for m in list_monitors()]
    virtual = {
        "x": user32.GetSystemMetrics(76), "y": user32.GetSystemMetrics(77),
        "w": user32.GetSystemMetrics(78), "h": user32.GetSystemMetrics(79),
    }
    visibility = None
    if window and window.get("exists"):
        visibility = window_visibility(window.get("client_w", 0),
                                       window.get("client_h", 0),
                                       window.get("origin_x", 0),
                                       window.get("origin_y", 0), virtual)
    return {"window": window, "monitors": monitors,
            "virtual_screen": virtual, "backend": backend,
            "window_visibility": visibility}
