"""Thin adapters over the Civil source, PDF, transform, and assisted capture core."""

from __future__ import annotations

from pathlib import Path

from screen2xyz_civil.assisted_capture import ElevationUnderCursorService
from screen2xyz_civil.models import Calibration, PixelPoint
from screen2xyz_civil.pdf import inspect_pdf, render_pdf_page
from screen2xyz_civil.source import inspect_image
from screen2xyz_civil.transform import to_local


def inspect_plan(path: Path):
    return inspect_pdf(path) if path.suffix.lower() == ".pdf" else inspect_image(path)


def render_plan_page(path: Path, output_png: Path, *, page_index: int = 0, dpi: int = 200):
    return render_pdf_page(path, page_index, output_png, dpi=dpi)


def plan_click_xy(point: PixelPoint, calibration: Calibration) -> tuple[float, float]:
    return to_local(point, calibration)


def plan_label_z(
    point: PixelPoint,
    service: ElevationUnderCursorService,
    *,
    capture_mode: str,
) -> tuple[float, float | None]:
    suggestion = service.suggest(point, capture_mode=capture_mode)
    if not suggestion.capturable or suggestion.evidence is None:
        raise ValueError(f"no capturable elevation near click: {suggestion.snap_status}")
    return float(suggestion.evidence.elevation), suggestion.evidence.confidence

