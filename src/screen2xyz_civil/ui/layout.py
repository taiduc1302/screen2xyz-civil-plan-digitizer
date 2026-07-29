"""Headless/testable civil canvas and presentation helpers."""

from __future__ import annotations

ZOOM_LEVELS = (0.25, 0.5, 1.0, 2.0, 3.0, 4.0)

POINT_COLORS = {
    "EXISTING_GROUND": "#2b6cb0",
    "DESIGN_GRADE": "#d97706",
    "CONTOUR_ELEVATION": "#7c3aed",
    "REVIEW_REQUIRED": "#dc2626",
    "REJECTED": "#6b7280",
}


def source_to_canvas(value: float, zoom: float) -> float:
    if zoom <= 0:
        raise ValueError("zoom must be positive")
    return float(value) * zoom


def canvas_to_source(value: float, zoom: float) -> float:
    if zoom <= 0:
        raise ValueError("zoom must be positive")
    return float(value) / zoom


def zoom_operation(zoom: float) -> tuple[str, int]:
    if zoom not in ZOOM_LEVELS:
        raise ValueError("unsupported zoom level")
    if zoom >= 1:
        return "zoom", int(zoom)
    return "subsample", round(1 / zoom)


def next_zoom(current: float, direction: int) -> float:
    if current not in ZOOM_LEVELS:
        current = 1.0
    index = ZOOM_LEVELS.index(current)
    index = max(0, min(len(ZOOM_LEVELS) - 1, index + direction))
    return ZOOM_LEVELS[index]


def point_color(point_type: str, review_status: str) -> str:
    if review_status == "REJECTED":
        return POINT_COLORS["REJECTED"]
    if review_status in {"UNREVIEWED", "REVIEW_REQUIRED", "AUTO_HIGH_CONFIDENCE"}:
        return POINT_COLORS["REVIEW_REQUIRED"]
    return POINT_COLORS.get(point_type, "#111827")


def manual_type(value: str) -> str:
    normalized = value.strip().upper()
    aliases = {
        "E": "EXISTING_GROUND",
        "EX": "EXISTING_GROUND",
        "EXISTING": "EXISTING_GROUND",
        "EXISTING_GROUND": "EXISTING_GROUND",
        "D": "DESIGN_GRADE",
        "DES": "DESIGN_GRADE",
        "DESIGN": "DESIGN_GRADE",
        "DESIGN_GRADE": "DESIGN_GRADE",
        "C": "CONTOUR_ELEVATION",
        "CONTOUR": "CONTOUR_ELEVATION",
        "CONTOUR_ELEVATION": "CONTOUR_ELEVATION",
    }
    if normalized not in aliases:
        raise ValueError("use E for Existing, D for Design, or C for Contour")
    return aliases[normalized]
