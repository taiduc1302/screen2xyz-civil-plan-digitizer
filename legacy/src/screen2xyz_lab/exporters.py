"""Exact deterministic CSV, XYZ and metadata serializers."""

from __future__ import annotations

import csv
import io
import os
import shutil
from pathlib import Path
from typing import Any, Callable, Iterable

from .config import FIXTURE_VERSION, OUTPUT_CLASSIFICATION, TASK_ID
from .evidence import atomic_write_bytes, atomic_write_json, sha256_file

RAW_HEADER = (
    "scenario_id", "sequence", "condition_id", "image_relpath", "image_sha256",
    "config_sha256", "ocr_engine", "ocr_engine_version", "ocr_language", "ocr_status",
    "raw_text_utf8_b64", "raw_text_sha256", "raw_text_display", "duration_ms", "ocr_error_code",
)
ACCEPTED_HEADER = (
    "scenario_id", "sequence", "condition_id", "image_relpath", "image_sha256",
    "config_sha256", "longitude", "latitude", "elevation_m", "source_crs", "axis_order",
    "elevation_unit", "vertical_reference", "classification",
)
REJECTED_HEADER = (
    "scenario_id", "sequence", "condition_id", "image_relpath", "image_sha256",
    "config_sha256", "raw_text_utf8_b64", "raw_text_sha256", "raw_text_display",
    "parsed_longitude", "parsed_latitude", "parsed_elevation_m", "classification",
    "primary_code", "all_codes", "reference_scenario_id",
)


def csv_bytes(rows: Iterable[dict[str, Any]], header: tuple[str, ...]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=header,
        lineterminator="\r\n",
        quoting=csv.QUOTE_MINIMAL,
        extrasaction="raise",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in header})
    return output.getvalue().encode("utf-8")


def formula_safe_display(raw_text: str) -> str:
    display = raw_text.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    if display.startswith(("=", "+", "-", "@")):
        display = "'" + display
    return display


def xyz_bytes(accepted: list[dict[str, Any]]) -> bytes:
    lines = [f"{row['longitude']} {row['latitude']} {row['elevation_m']}" for row in accepted]
    return (("\n".join(lines) + "\n") if lines else "").encode("utf-8")


def sidecar_value(
    *,
    config_hash: str,
    accepted_count: int,
    rejected_count: int,
    xyz_hash: str,
) -> dict[str, Any]:
    limitations = [
        "No coordinate transformation was performed.",
        "Only generated images were evaluated; live-source capture was not performed.",
        "Kubla suitability and import were not tested; geographic degree coordinates are not proven suitable.",
    ]
    projection = {
        "schema_version": "1.0",
        "fixture_version": FIXTURE_VERSION,
        "config_sha256": config_hash,
        "source_crs": "EPSG:4326",
        "axis_order": "longitude_latitude",
        "x_field": "longitude",
        "y_field": "latitude",
        "z_field": "elevation_m",
        "elevation_unit": "m",
        "vertical_reference": "SYNTHETIC_LOCAL",
        "coordinate_precision": 6,
        "elevation_precision": 2,
        "ocr_engine": "Windows.Media.Ocr",
        "ocr_engine_version": "not_exposed",
        "ocr_language": "en-US",
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "points_source_xyz_sha256": xyz_hash,
        "output_classification": OUTPUT_CLASSIFICATION,
        "limitations": limitations,
    }
    return {
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "fixture_version": FIXTURE_VERSION,
        "config_sha256": config_hash,
        "source_crs": "EPSG:4326",
        "axis_order": "longitude_latitude",
        "x_field": "longitude",
        "y_field": "latitude",
        "z_field": "elevation_m",
        "elevation_unit": "m",
        "vertical_reference": "SYNTHETIC_LOCAL",
        "coordinate_precision": 6,
        "elevation_precision": 2,
        "ocr_engine": "Windows.Media.Ocr",
        "ocr_engine_version": "not_exposed",
        "ocr_language": "en-US",
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "artifact_sha256": {"points_source_xyz.txt": xyz_hash},
        "output_classification": OUTPUT_CLASSIFICATION,
        "limitations": limitations,
        "deterministic_projection": projection,
    }


def write_evaluation_outputs(
    output_root: Path,
    *,
    raw_rows: list[dict[str, Any]],
    accepted_rows: list[dict[str, Any]],
    rejected_rows: list[dict[str, Any]],
    classifications: list[dict[str, Any]],
    config_hash: str,
    before_publish: Callable[[], None] | None = None,
) -> dict[str, str]:
    output_root.parent.mkdir(parents=True, exist_ok=True)
    if output_root.exists():
        raise FileExistsError("evaluation output root must be fresh")
    stage = output_root.with_name(f".{output_root.name}.staging-{os.getpid()}")
    if stage.exists():
        raise FileExistsError("evaluation staging collision")
    stage.mkdir()
    try:
        atomic_write_bytes(stage / "raw_ocr_readings.csv", csv_bytes(raw_rows, RAW_HEADER))
        atomic_write_bytes(stage / "accepted_points.csv", csv_bytes(accepted_rows, ACCEPTED_HEADER))
        atomic_write_bytes(stage / "rejected_readings.csv", csv_bytes(rejected_rows, REJECTED_HEADER))
        xyz_path = stage / "points_source_xyz.txt"
        atomic_write_bytes(xyz_path, xyz_bytes(accepted_rows))
        sidecar = sidecar_value(
            config_hash=config_hash,
            accepted_count=len(accepted_rows),
            rejected_count=len(rejected_rows),
            xyz_hash=sha256_file(xyz_path),
        )
        atomic_write_json(stage / "points_source_xyz_metadata.json", sidecar)
        atomic_write_json(stage / "classifications.json", classifications)
        projection = [
            {
                "scenario_id": row["scenario_id"],
                "sequence": row["sequence"],
                "condition_id": row["condition_id"],
                "image_relpath": row["image_relpath"],
                "image_sha256": row["image_sha256"],
                "ocr_status": row["ocr_status"],
                "raw_text_utf8_b64": row["raw_text_utf8_b64"],
                "raw_text_sha256": row["raw_text_sha256"],
                "ocr_error_code": row["ocr_error_code"],
            }
            for row in raw_rows
        ]
        atomic_write_json(stage / "raw_ocr_projection.json", projection)
        hashes = {
            path.name: sha256_file(path)
            for path in sorted(stage.iterdir())
            if path.is_file()
        }
        if before_publish is not None:
            before_publish()
        os.replace(stage, output_root)
        return hashes
    except Exception:
        safe_stage = stage.resolve()
        if safe_stage.parent == output_root.parent.resolve() and safe_stage.name.startswith(f".{output_root.name}.staging-"):
            shutil.rmtree(safe_stage, ignore_errors=True)
        raise
