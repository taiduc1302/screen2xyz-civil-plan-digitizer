"""Deterministic synthetic fixture generation and runtime separation."""

from __future__ import annotations

import csv
import io
import json
import os
import random
import shutil
import struct
import subprocess
from decimal import Decimal
from pathlib import Path
from typing import Any

from .config import (
    CONDITIONS,
    FIXTURE_VERSION,
    SEED,
    canonical_config,
    canonical_json_bytes,
    config_sha256,
    load_config,
)
from .evidence import atomic_write_bytes, atomic_write_json, sha256_file

GROUND_TRUTH_HEADER = (
    "scenario_id",
    "sequence",
    "condition_id",
    "scenario_class",
    "expected_disposition",
    "expected_primary_code",
    "expected_latitude",
    "expected_longitude",
    "expected_elevation_m",
    "reference_scenario_id",
    "condition_scale_percent",
    "font_size_px",
    "variation_id",
    "synthetic_only",
    "fixture_version",
    "config_sha256",
)


def _coordinate(rng: random.Random, maximum_micro: int, sign_index: int) -> Decimal:
    magnitude = rng.randint(100_000, maximum_micro)
    value = magnitude if sign_index % 2 else -magnitude
    return Decimal(value) / Decimal(1_000_000)


def _elevation(rng: random.Random, negative: bool) -> Decimal:
    cents = rng.randint(1, 25_000) if negative else rng.randint(0, 250_000)
    if negative:
        cents = -cents
    return Decimal(cents) / Decimal(100)


def _format_visible(
    variation: int,
    latitude: str,
    longitude: str,
    elevation: str | None,
) -> str:
    if variation == 1:
        fields = [f"LAT: {latitude}", f"LON: {longitude}"]
        if elevation is not None:
            fields.append(f"ELEV: {elevation} m")
        return "   ".join(fields)
    if variation == 2:
        fields = [f"LAT = {latitude}", f"LON = {longitude}"]
        if elevation is not None:
            fields.append(f"ELEV = {elevation} m")
        return "    ".join(fields)
    if variation == 3:
        fields = [f"LAT {latitude} deg", f"LON {longitude} deg"]
        if elevation is not None:
            fields.append(f"ELEV {elevation} m")
        return "     |     ".join(fields)
    fields = [f"LAT: {latitude}", f"LON: {longitude}"]
    if elevation is not None:
        fields.append(f"ELEV: {elevation} m")
    return "\n".join(fields)


def build_scenarios() -> list[dict[str, Any]]:
    """Build exactly 60 evaluator-side scenarios without reading external data."""

    rng = random.Random(SEED)
    scenarios: list[dict[str, Any]] = []
    sequence = 0
    used: set[tuple[Decimal, Decimal, Decimal]] = set()

    for condition_index, condition in enumerate(CONDITIONS):
        generated: list[tuple[Decimal, Decimal, Decimal]] = []
        for local_unique_index in range(14):
            negative_elevation = local_unique_index >= 12
            while True:
                latitude = _coordinate(rng, 75_000_000, condition_index * 14 + local_unique_index)
                longitude = _coordinate(rng, 170_000_000, condition_index * 14 + local_unique_index + 1)
                elevation = _elevation(rng, negative_elevation)
                triplet = (latitude, longitude, elevation)
                if triplet not in used:
                    used.add(triplet)
                    generated.append(triplet)
                    break

        unique_positions = [1, 3, *range(5, 17)]
        position_values = dict(zip(unique_positions, generated, strict=True))
        position_values[2] = position_values[1]
        position_values[4] = position_values[3]
        position_values[19] = position_values[1]
        position_values[20] = position_values[3]

        # Separate synthetic values for the malformed and missing-field cases.
        malformed_lon = _coordinate(rng, 170_000_000, condition_index + 100)
        malformed_elev = _elevation(rng, False)
        missing_lat = _coordinate(rng, 75_000_000, condition_index + 110)
        missing_lon = _coordinate(rng, 170_000_000, condition_index + 111)
        position_values[18] = (missing_lat, missing_lon, Decimal("0"))

        for position in range(1, 21):
            sequence += 1
            scenario_id = f"S{sequence:03d}"
            variation = ((sequence - 1) % 4) + 1
            reference = ""
            expected_code = ""
            expected_disposition = "ACCEPT"
            scenario_class = "valid"

            if position == 17:
                latitude_text = f"{condition_index + 1}2A.345678"
                longitude_text = format(malformed_lon, ".6f")
                elevation_text = format(malformed_elev, ".2f")
                expected_latitude = ""
                expected_longitude = longitude_text
                expected_elevation = elevation_text
                scenario_class = "malformed_missing"
                expected_disposition = "REJECT_MALFORMED"
                expected_code = "MALFORMED_LAT"
            else:
                latitude, longitude, elevation = position_values[position]
                latitude_text = format(latitude, ".6f")
                longitude_text = format(longitude, ".6f")
                elevation_text = format(elevation, ".2f") if position != 18 else None
                expected_latitude = latitude_text
                expected_longitude = longitude_text
                expected_elevation = format(elevation, ".2f") if position != 18 else ""

            if position in (2, 4):
                scenario_class = "stale"
                expected_disposition = "REJECT_STALE"
                expected_code = "STALE_READING"
                reference = f"S{sequence - 1:03d}"
            elif position in (15, 16):
                scenario_class = "valid_negative_elevation"
            elif position == 18:
                scenario_class = "malformed_missing"
                expected_disposition = "REJECT_MISSING"
                expected_code = "MISSING_ELEV"
            elif position in (19, 20):
                scenario_class = "duplicate"
                expected_disposition = "REJECT_DUPLICATE"
                expected_code = "DUPLICATE_READING"
                reference_sequence = sequence - 18 if position == 19 else sequence - 17
                reference = f"S{reference_sequence:03d}"

            visible = _format_visible(variation, latitude_text, longitude_text, elevation_text)
            scenarios.append(
                {
                    "scenario_id": scenario_id,
                    "sequence": sequence,
                    "condition_id": condition["condition_id"],
                    "scenario_class": scenario_class,
                    "expected_disposition": expected_disposition,
                    "expected_primary_code": expected_code,
                    "expected_latitude": expected_latitude,
                    "expected_longitude": expected_longitude,
                    "expected_elevation_m": expected_elevation,
                    "visible_text": visible,
                    "reference_scenario_id": reference,
                    "condition_scale_percent": condition["scale_percent"],
                    "font_size_px": condition["font_size_px"],
                    "variation_id": f"V{variation}",
                    "synthetic_only": True,
                }
            )
    return scenarios


def ground_truth_bytes(scenarios: list[dict[str, Any]], config_hash: str) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=GROUND_TRUTH_HEADER, lineterminator="\r\n")
    writer.writeheader()
    for scenario in scenarios:
        writer.writerow(
            {
                key: (
                    "true"
                    if key == "synthetic_only"
                    else FIXTURE_VERSION
                    if key == "fixture_version"
                    else config_hash
                    if key == "config_sha256"
                    else scenario[key]
                )
                for key in GROUND_TRUTH_HEADER
            }
        )
    return output.getvalue().encode("utf-8")


def render_jobs_value(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "fixture_version": FIXTURE_VERSION,
        "jobs": [
            {
                "scenario_id": row["scenario_id"],
                "condition_id": row["condition_id"],
                "font_size_px": row["font_size_px"],
                "visible_text": row["visible_text"],
                "image_relpath": f"images/{row['scenario_id']}.png",
            }
            for row in scenarios
        ],
    }


def png_dimensions(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError("not a valid PNG header")
    return struct.unpack(">II", header[16:24])


def png_chunk_types(path: Path) -> tuple[str, ...]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    chunks: list[str] = []
    offset = 8
    while offset + 12 <= len(data):
        length = int.from_bytes(data[offset : offset + 4], "big")
        name = data[offset + 4 : offset + 8].decode("ascii", errors="strict")
        chunks.append(name)
        offset += 12 + length
        if name == "IEND":
            break
    if not chunks or chunks[-1] != "IEND" or offset != len(data):
        raise ValueError("invalid PNG chunk structure")
    return tuple(chunks)


def _runtime_manifest(stage: Path, scenarios: list[dict[str, Any]], config_hash: str) -> dict[str, Any]:
    entries = []
    for row in scenarios:
        relpath = f"images/{row['scenario_id']}.png"
        image = stage / Path(relpath)
        width, height = png_dimensions(image)
        entries.append(
            {
                "scenario_id": row["scenario_id"],
                "sequence": row["sequence"],
                "condition_id": row["condition_id"],
                "image_relpath": relpath,
                "image_sha256": sha256_file(image),
                "image_bytes": image.stat().st_size,
                "width_px": width,
                "height_px": height,
                "config_sha256": config_hash,
            }
        )
    return {
        "schema_version": "1.0",
        "fixture_version": FIXTURE_VERSION,
        "config_sha256": config_hash,
        "scenario_count": len(entries),
        "scenarios": entries,
    }


RUNTIME_MANIFEST_KEYS = {
    "schema_version", "fixture_version", "config_sha256", "scenario_count", "scenarios",
}
RUNTIME_SCENARIO_KEYS = {
    "scenario_id", "sequence", "condition_id", "image_relpath", "image_sha256",
    "image_bytes", "width_px", "height_px", "config_sha256",
}


def validate_runtime_fixture(fixture_root: Path) -> dict[str, Any]:
    """Validate only runtime-safe configuration and manifest data.

    This function intentionally does not read render_jobs.json, ground_truth.csv,
    or reconstruct evaluator scenarios. Image bytes are checked per scenario by
    the runtime input boundary immediately before OCR.
    """

    config_path = fixture_root / "fixture_config.json"
    config = load_config(config_path)
    expected_hash = config_sha256(config)
    if config_path.read_bytes() != canonical_json_bytes(config):
        raise ValueError("fixture configuration is not canonical")
    manifest = json.loads((fixture_root / "fixture_manifest.json").read_text(encoding="utf-8"))
    if set(manifest) != RUNTIME_MANIFEST_KEYS:
        raise ValueError("fixture manifest keys differ")
    if (
        manifest["schema_version"] != "1.0"
        or manifest["fixture_version"] != FIXTURE_VERSION
        or manifest["config_sha256"] != expected_hash
        or manifest["scenario_count"] != 60
        or not isinstance(manifest["scenarios"], list)
        or len(manifest["scenarios"]) != 60
    ):
        raise ValueError("fixture manifest configuration/count mismatch")

    expected_ids = [f"S{index:03d}" for index in range(1, 61)]
    observed_ids: list[str] = []
    forbidden = {"visible_text", "expected_disposition", "expected_primary_code", "reference_scenario_id", "scenario_class"}
    for sequence, row in enumerate(manifest["scenarios"], start=1):
        if not isinstance(row, dict) or set(row) != RUNTIME_SCENARIO_KEYS:
            raise ValueError("runtime manifest scenario keys differ")
        if forbidden.intersection(row) or any(key.startswith("expected_") for key in row):
            raise ValueError("runtime manifest leaks evaluator fields")
        scenario_id = f"S{sequence:03d}"
        condition_id = CONDITIONS[(sequence - 1) // 20]["condition_id"]
        if (
            row["scenario_id"] != scenario_id
            or row["sequence"] != sequence
            or row["condition_id"] != condition_id
            or row["image_relpath"] != f"images/{scenario_id}.png"
            or row["config_sha256"] != expected_hash
            or row["width_px"] != config["image_width_px"]
            or row["height_px"] != config["image_height_px"]
            or not isinstance(row["image_bytes"], int)
            or row["image_bytes"] <= 0
            or row["image_bytes"] > config["max_image_bytes"]
            or not isinstance(row["image_sha256"], str)
            or len(row["image_sha256"]) != 64
            or any(character not in "0123456789abcdef" for character in row["image_sha256"])
        ):
            raise ValueError("runtime manifest scenario identity differs")
        observed_ids.append(row["scenario_id"])
    if observed_ids != expected_ids or len(set(observed_ids)) != 60:
        raise ValueError("runtime manifest scenario ordering differs")
    return manifest


def validate_fixture(fixture_root: Path) -> dict[str, Any]:
    manifest = validate_runtime_fixture(fixture_root)
    config_path = fixture_root / "fixture_config.json"
    config = load_config(config_path)
    expected_hash = config_sha256(config)
    scenarios = build_scenarios()
    if (fixture_root / "ground_truth.csv").read_bytes() != ground_truth_bytes(scenarios, expected_hash):
        raise ValueError("ground truth differs from deterministic generation")
    if (fixture_root / "render_jobs.json").read_bytes() != canonical_json_bytes(render_jobs_value(scenarios)):
        raise ValueError("render jobs differ from deterministic generation")
    for row in manifest["scenarios"]:
        image = fixture_root / Path(row["image_relpath"])
        if sha256_file(image) != row["image_sha256"]:
            raise ValueError(f"fixture image hash mismatch: {row['scenario_id']}")
        if image.stat().st_size != row["image_bytes"]:
            raise ValueError(f"fixture image byte-count mismatch: {row['scenario_id']}")
        if png_dimensions(image) != (row["width_px"], row["height_px"]):
            raise ValueError(f"fixture image dimension mismatch: {row['scenario_id']}")
        if not set(png_chunk_types(image)).issubset({"IHDR", "sRGB", "gAMA", "pHYs", "IDAT", "IEND"}):
            raise ValueError(f"fixture image metadata/chunk violation: {row['scenario_id']}")
    expected_manifest = _runtime_manifest(fixture_root, scenarios, expected_hash)
    if canonical_json_bytes(manifest) != canonical_json_bytes(expected_manifest):
        raise ValueError("runtime manifest differs from deterministic generation")
    return manifest


def generate_fixture(repository_root: Path, fixture_root: Path | None = None) -> dict[str, Any]:
    fixture_root = fixture_root or repository_root / "test_data/synthetic/s2xyz_fixture_v0.1"
    if fixture_root.exists():
        manifest = validate_fixture(fixture_root)
        return {"status": "VERIFIED_EXISTING", "scenario_count": manifest["scenario_count"]}

    stage = fixture_root.with_name(f".{fixture_root.name}.staging-{os.getpid()}")
    if stage.exists():
        raise RuntimeError("fixture staging collision")
    stage.mkdir(parents=True)
    try:
        config = canonical_config()
        config_hash = config_sha256(config)
        scenarios = build_scenarios()
        atomic_write_json(stage / "fixture_config.json", config)
        atomic_write_json(stage / "render_jobs.json", render_jobs_value(scenarios))
        atomic_write_bytes(stage / "ground_truth.csv", ground_truth_bytes(scenarios, config_hash))

        renderer = repository_root / "src/screen2xyz_lab/adapters/render_windows.ps1"
        command = [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(renderer),
            "-RenderJobsPath",
            str(stage / "render_jobs.json"),
            "-OutputRoot",
            str(stage),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"renderer failed with bounded exit {completed.returncode}")
        result = json.loads(completed.stdout.strip())
        if result.get("status") != "SUCCESS" or result.get("rendered_count") != 60:
            raise RuntimeError("renderer returned an invalid result")

        manifest = _runtime_manifest(stage, scenarios, config_hash)
        atomic_write_json(stage / "fixture_manifest.json", manifest)
        validate_fixture(stage)
        fixture_root.parent.mkdir(parents=True, exist_ok=True)
        os.replace(stage, fixture_root)
        return {"status": "GENERATED", "scenario_count": 60, "config_sha256": config_hash}
    except Exception:
        safe_parent = fixture_root.parent.resolve()
        safe_stage = stage.resolve()
        if safe_stage.parent == safe_parent and safe_stage.name.startswith(f".{fixture_root.name}.staging-"):
            shutil.rmtree(safe_stage, ignore_errors=True)
        raise
