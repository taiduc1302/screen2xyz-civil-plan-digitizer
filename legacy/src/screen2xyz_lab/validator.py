"""Numeric and metadata validation for parsed synthetic readings."""

from __future__ import annotations

from decimal import Decimal

from .models import ParseResult
from .parser import order_codes


def validate_metadata(config: dict) -> None:
    expected = {
        "source_crs": "EPSG:4326",
        "axis_order": "longitude_latitude",
        "elevation_unit": "m",
        "vertical_reference": "SYNTHETIC_LOCAL",
    }
    if any(config.get(key) != value for key, value in expected.items()):
        from .config import ConfigError

        raise ConfigError("required coordinate metadata is missing or conflicting")


def validate_reading(parsed: ParseResult, config: dict) -> tuple[str, ...]:
    codes = set(parsed.codes)
    if parsed.latitude is not None and not Decimal("-90") <= parsed.latitude <= Decimal("90"):
        codes.add("OUT_OF_RANGE_LAT")
    if parsed.longitude is not None and not Decimal("-180") <= parsed.longitude <= Decimal("180"):
        codes.add("OUT_OF_RANGE_LON")
    if parsed.elevation_m is not None:
        minimum = Decimal(config["elevation_min_m"])
        maximum = Decimal(config["elevation_max_m"])
        if not minimum <= parsed.elevation_m <= maximum:
            codes.add("OUT_OF_RANGE_ELEV")
    return order_codes(codes)
