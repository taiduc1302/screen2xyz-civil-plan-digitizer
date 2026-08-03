"""Headless operator policies shared by the controller and Tk UI."""

from __future__ import annotations

import math
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping


@dataclass(frozen=True)
class VirtualDesktopBounds:
    left: int
    top: int
    width: int
    height: int


def format_virtual_geometry(bounds: VirtualDesktopBounds) -> str:
    x = f"+{bounds.left}" if bounds.left >= 0 else str(bounds.left)
    y = f"+{bounds.top}" if bounds.top >= 0 else str(bounds.top)
    return f"{bounds.width}x{bounds.height}{x}{y}"


def current_virtual_desktop_bounds() -> VirtualDesktopBounds:
    try:
        import mss

        with mss.MSS() as capture:
            monitor = capture.monitors[0]
            return VirtualDesktopBounds(
                int(monitor["left"]), int(monitor["top"]),
                int(monitor["width"]), int(monitor["height"]),
            )
    except Exception:
        return VirtualDesktopBounds(0, 0, 0, 0)


def preview_without_overlay(*, hide, flush, preview, restore):
    hide()
    try:
        flush()
        return preview()
    finally:
        restore()


@dataclass(frozen=True)
class ZonePreviewAssessment:
    warnings: tuple[str, ...]
    blocking: bool = False


_NUMBER_TOKEN = re.compile(
    r"(?<![\w.])[-+]?(?:\d{1,3}(?:[ ,.']\d{3})+|\d+)(?:[.,]\d+)?(?![\w.])"
)


def zone_preview_assessment(
    zone: tuple[int, int, int, int], preview_text: str
) -> ZonePreviewAssessment:
    _left, _top, _width, height = zone
    warnings: list[str] = []
    blocking = height > 48
    if blocking:
        warnings.append(
            f"Selection is {height} px tall; pick one numeric line no taller than 48 px."
        )
    numbers = _NUMBER_TOKEN.findall(preview_text)
    remainder = _NUMBER_TOKEN.sub("", preview_text)
    if re.search(r"[A-Za-z]", remainder):
        warnings.append("Selection includes label text; tighten it around the number when practical.")
    if len(numbers) > 1:
        warnings.append("Selection contains more than one number; pick a single numeric value.")
    return ZonePreviewAssessment(tuple(warnings), blocking)


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


def zone_indicator_states(
    snapshot: ZoneHealthSnapshot, names: tuple[str, ...] = ("x", "y", "z")
) -> dict[str, tuple[str, bool]]:
    """Return display text and green/red state without depending on Tk."""
    return {
        name: (snapshot.readouts.get(name, "—"), snapshot.ok and name in snapshot.readouts)
        for name in names
    }


def review_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    filter_text: str = "",
    sort_by: str = "id",
    reverse: bool = False,
    visible_columns: tuple[str, ...] = (
        "point_number", "x", "y", "z", "description", "created_utc"
    ),
) -> list[Mapping[str, Any]]:
    """Filter and sort captured rows for UI or headless review."""
    needle = filter_text.casefold().strip()
    selected = [
        row for row in rows
        if not needle
        or needle in " ".join(str(row.get(name, "")) for name in visible_columns).casefold()
    ]
    return sorted(
        selected,
        key=lambda row: (row.get(sort_by) is None, row.get(sort_by)),
        reverse=reverse,
    )
