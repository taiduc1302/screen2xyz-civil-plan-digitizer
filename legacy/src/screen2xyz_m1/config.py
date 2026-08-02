"""M1 configuration: intake limits and validation bounds."""

from __future__ import annotations

# Intake limits for explicitly user-selected PNG files. These bound memory
# and OCR cost; they are far above the synthetic fixtures but reject
# decompression-heavy or absurd inputs before any decoding work.
MAX_SOURCE_BYTES = 25_000_000
MAX_SOURCE_WIDTH_PX = 8_192
MAX_SOURCE_HEIGHT_PX = 8_192
MAX_SOURCE_PIXELS = 40_000_000

OCR_TIMEOUT_SECONDS = 30.0

# Validation bounds reused by the baseline validator contract.
M1_VALIDATION_CONFIG = {
    "elevation_min_m": "-500.00",
    "elevation_max_m": "9000.00",
}

# Export metadata. The vertical reference of an arbitrary user-selected
# image is unknown; it is recorded as unspecified rather than claimed.
EXPORT_METADATA = {
    "source_crs": "EPSG:4326",
    "axis_order": "longitude_latitude",
    "elevation_unit": "m",
    "vertical_reference": "UNSPECIFIED_LOCAL",
    "coordinate_precision": 6,
    "elevation_precision": 2,
}

OUTPUT_CLASSIFICATION = "Conceptual and preliminary estimating data only."
