"""Headless operator policies shared by the controller and Tk UI."""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class SessionOptions:
    min_xy_delta: float = 0.0
    point_prefix: str = ""
    point_start: int = 1
    zone_failure_limit: int = 3

    def __post_init__(self) -> None:
        if self.min_xy_delta < 0:
            raise ValueError("minimum XY delta cannot be negative")
        if self.point_start < 0:
            raise ValueError("point number start cannot be negative")
        if self.zone_failure_limit < 1:
            raise ValueError("zone failure limit must be at least one")
        if any(character in "\r\n\t" for character in self.point_prefix):
            raise ValueError("point prefix cannot contain control whitespace")

    def point_number(self, retained_index: int) -> str:
        return f"{self.point_prefix}{self.point_start + retained_index}"

    def accepts(self, prior_xy: tuple[float, float] | None, x: float, y: float) -> bool:
        if prior_xy is None or self.min_xy_delta == 0:
            return True
        return math.hypot(x - prior_xy[0], y - prior_xy[1]) >= self.min_xy_delta


@dataclass(frozen=True)
class DisplaySignature:
    width: int
    height: int
    dpi: int


def current_display_signature() -> DisplaySignature:
    """Return the virtual-desktop size and system DPI without creating Tk objects."""
    try:
        import mss

        with mss.MSS() as capture:
            monitor = capture.monitors[0]
            width, height = int(monitor["width"]), int(monitor["height"])
    except Exception:
        width = height = 0
    dpi = 96
    if sys.platform == "win32":
        try:
            import ctypes

            dpi = int(ctypes.windll.user32.GetDpiForSystem())
        except (AttributeError, OSError):
            pass
    return DisplaySignature(width, height, dpi)


@dataclass(frozen=True)
class ZoneHealthSnapshot:
    ok: bool
    paused: bool
    message: str
    consecutive_failures: int
    readouts: dict[str, str] = field(default_factory=dict)


class ZoneHealthMonitor:
    def __init__(
        self,
        failure_limit: int,
        *,
        signature_probe: Callable[[], DisplaySignature] = current_display_signature,
    ) -> None:
        if failure_limit < 1:
            raise ValueError("failure limit must be at least one")
        self.failure_limit = failure_limit
        self.signature_probe = signature_probe
        self.initial_signature = signature_probe()
        self.consecutive_failures = 0

    def check_display(self) -> ZoneHealthSnapshot | None:
        current = self.signature_probe()
        if current != self.initial_signature:
            return ZoneHealthSnapshot(
                False,
                True,
                "Screen resolution or DPI changed. Capture paused; re-pick the zones.",
                self.consecutive_failures,
            )
        return None

    def success(self, readouts: dict[str, str]) -> ZoneHealthSnapshot:
        self.consecutive_failures = 0
        return ZoneHealthSnapshot(True, False, "Zones are reading normally.", 0, readouts)

    def failure(self, error: Exception) -> ZoneHealthSnapshot:
        self.consecutive_failures += 1
        paused = self.consecutive_failures >= self.failure_limit
        message = (
            f"Zone read failed {self.consecutive_failures}/{self.failure_limit}: {error}"
        )
        if paused:
            message += " Capture paused; re-pick the zones."
        return ZoneHealthSnapshot(False, paused, message, self.consecutive_failures)
