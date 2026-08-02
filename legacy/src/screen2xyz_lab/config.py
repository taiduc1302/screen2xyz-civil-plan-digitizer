"""Canonical configuration and fail-closed validation."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

TASK_ID = "S2XYZ-CODEX-003"
FIXTURE_VERSION = "s2xyz_fixture_v0.1"
SEED = 20260715
OUTPUT_CLASSIFICATION = "Conceptual and preliminary estimating data only."
LIVE_CAPTURE_STATUS = "Not executed"
ARIAL_FILE_BYTES = 1045720
ARIAL_FILE_SHA256 = "b3658eadae55e682b5f69eb64c439c1ecc8f196c0bb8d4756d145d13bc86476a"
CONDITIONS = (
    {"condition_id": "baseline", "scale_percent": 100, "font_size_px": 32},
    {"condition_id": "scale_125", "scale_percent": 125, "font_size_px": 40},
    {"condition_id": "scale_150", "scale_percent": 150, "font_size_px": 48},
)

REQUIRED_CONFIG = {
    "schema_version": "1.0",
    "fixture_version": FIXTURE_VERSION,
    "seed": SEED,
    "conditions": [dict(item) for item in CONDITIONS],
    "language": "en-US",
    "labels": {"lat": "LAT", "lon": "LON", "elev": "ELEV"},
    "source_crs": "EPSG:4326",
    "axis_order": "longitude_latitude",
    "elevation_unit": "m",
    "vertical_reference": "SYNTHETIC_LOCAL",
    "coordinate_precision": 6,
    "elevation_precision": 2,
    "elevation_min_m": "-500.00",
    "elevation_max_m": "9000.00",
    "input_root": "test_data/synthetic/s2xyz_fixture_v0.1",
    "output_root": "runs/evidence/S2XYZ-CODEX-003",
    "ocr_timeout_seconds": 30,
    "run_timeout_seconds": 1800,
    "image_width_px": 1600,
    "image_height_px": 260,
    "max_image_bytes": 5000000,
}


class ConfigError(ValueError):
    """A bounded run-fatal configuration failure."""

    code = "RUN_CONFIG_INVALID"


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_config() -> dict[str, Any]:
    return deepcopy(REQUIRED_CONFIG)


def config_sha256(config: dict[str, Any]) -> str:
    validate_config(config)
    return sha256_bytes(canonical_json_bytes(config))


def validate_config(config: dict[str, Any]) -> None:
    if not isinstance(config, dict):
        raise ConfigError("configuration must be an object")
    missing = sorted(set(REQUIRED_CONFIG) - set(config))
    extra = sorted(set(config) - set(REQUIRED_CONFIG))
    if missing or extra:
        raise ConfigError(f"configuration keys differ; missing={missing}; extra={extra}")
    for key, expected in REQUIRED_CONFIG.items():
        if config[key] != expected:
            raise ConfigError(f"conflicting configuration value: {key}")
    if not isinstance(config["seed"], int) or config["seed"] < 0:
        raise ConfigError("seed must be a non-negative integer")
    for key in ("input_root", "output_root"):
        value = Path(config[key])
        if value.is_absolute() or ".." in value.parts:
            raise ConfigError(f"{key} must be a bounded relative path")
    if config["ocr_timeout_seconds"] <= 0 or config["run_timeout_seconds"] <= 0:
        raise ConfigError("timeouts must be positive")


def load_config(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigError("configuration could not be read") from exc
    validate_config(value)
    return value
