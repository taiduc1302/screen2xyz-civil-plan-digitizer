"""Deterministic screen-pixel to local East/North transformation."""

from __future__ import annotations

import math

from . import contracts as C
from .models import Calibration, CivilModelError, PixelPoint, ScaleCheck


def pixel_distance(point_1: PixelPoint, point_2: PixelPoint) -> float:
    return math.hypot(point_2.x - point_1.x, point_2.y - point_1.y)


def metres_per_pixel(
    point_1: PixelPoint, point_2: PixelPoint, known_distance_m: float
) -> float:
    if known_distance_m <= 0 or not math.isfinite(known_distance_m):
        raise CivilModelError("known distance must be a positive finite number")
    distance_px = pixel_distance(point_1, point_2)
    if distance_px <= 0:
        raise CivilModelError("scale calibration points must be distinct")
    return known_distance_m / distance_px


def east_basis(origin: PixelPoint, east_reference: PixelPoint) -> tuple[float, float]:
    # Screen Y grows downward; invert it before deriving the local basis.
    delta_x = east_reference.x - origin.x
    delta_y = origin.y - east_reference.y
    length = math.hypot(delta_x, delta_y)
    if length <= 0:
        raise CivilModelError("origin and East-axis reference must be distinct")
    return delta_x / length, delta_y / length


def verify_scale(
    point_1: PixelPoint,
    point_2: PixelPoint,
    known_distance_m: float,
    scale_m_per_px: float,
    *,
    warning_threshold_percent: float = C.DEFAULT_SCALE_CHECK_WARNING_PERCENT,
) -> ScaleCheck:
    if known_distance_m <= 0:
        raise CivilModelError("scale-check distance must be positive")
    if warning_threshold_percent < 0:
        raise CivilModelError("warning threshold must be non-negative")
    measured = pixel_distance(point_1, point_2) * scale_m_per_px
    error_percent = abs(measured - known_distance_m) / known_distance_m * 100.0
    return ScaleCheck(
        point_1=point_1,
        point_2=point_2,
        known_distance_m=known_distance_m,
        measured_distance_m=measured,
        error_percent=error_percent,
        warning_threshold_percent=warning_threshold_percent,
    )


def build_calibration(
    *,
    revision: int,
    created_at: str,
    scale_point_1: PixelPoint,
    scale_point_2: PixelPoint,
    known_distance_m: float,
    origin_pixel: PixelPoint,
    east_reference: PixelPoint,
    origin_east_m: float = 0.0,
    origin_north_m: float = 0.0,
    check_point_1: PixelPoint | None = None,
    check_point_2: PixelPoint | None = None,
    check_known_distance_m: float | None = None,
    warning_threshold_percent: float = C.DEFAULT_SCALE_CHECK_WARNING_PERCENT,
) -> Calibration:
    scale = metres_per_pixel(scale_point_1, scale_point_2, known_distance_m)
    east_x, east_y = east_basis(origin_pixel, east_reference)
    check_values = (check_point_1, check_point_2, check_known_distance_m)
    if any(value is not None for value in check_values) and not all(
        value is not None for value in check_values
    ):
        raise CivilModelError("scale check requires two points and a known distance")
    check = None
    if check_point_1 is not None:
        check = verify_scale(
            check_point_1,
            check_point_2,  # type: ignore[arg-type]
            float(check_known_distance_m),
            scale,
            warning_threshold_percent=warning_threshold_percent,
        )
    return Calibration(
        revision=revision,
        created_at=created_at,
        scale_point_1=scale_point_1,
        scale_point_2=scale_point_2,
        known_distance_m=known_distance_m,
        metres_per_pixel=scale,
        origin_pixel=origin_pixel,
        east_unit_x=east_x,
        east_unit_y=east_y,
        origin_east_m=float(origin_east_m),
        origin_north_m=float(origin_north_m),
        scale_check=check,
    )


def to_local(point: PixelPoint, calibration: Calibration) -> tuple[float, float]:
    delta_x = point.x - calibration.origin_pixel.x
    delta_y = calibration.origin_pixel.y - point.y
    east_delta_px = (
        delta_x * calibration.east_unit_x
        + delta_y * calibration.east_unit_y
    )
    north_delta_px = (
        delta_x * calibration.north_unit_x
        + delta_y * calibration.north_unit_y
    )
    return (
        calibration.origin_east_m
        + east_delta_px * calibration.metres_per_pixel,
        calibration.origin_north_m
        + north_delta_px * calibration.metres_per_pixel,
    )


def to_pixel(
    east_m: float, north_m: float, calibration: Calibration
) -> PixelPoint:
    east_delta_px = (
        float(east_m) - calibration.origin_east_m
    ) / calibration.metres_per_pixel
    north_delta_px = (
        float(north_m) - calibration.origin_north_m
    ) / calibration.metres_per_pixel
    delta_x = (
        east_delta_px * calibration.east_unit_x
        + north_delta_px * calibration.north_unit_x
    )
    delta_y_up = (
        east_delta_px * calibration.east_unit_y
        + north_delta_px * calibration.north_unit_y
    )
    return PixelPoint(
        calibration.origin_pixel.x + delta_x,
        calibration.origin_pixel.y - delta_y_up,
    )
