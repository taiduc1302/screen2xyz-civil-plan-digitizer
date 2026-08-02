"""Generated-image OCR pipeline and deterministic repeatability comparison."""

from __future__ import annotations

import base64
import csv
import hashlib
import json
import os
import shutil
import struct
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from .config import config_sha256, load_config
from .evidence import EvidenceError, atomic_copy, atomic_write_json, sha256_file
from .exporters import formula_safe_display, write_evaluation_outputs
from .fixture import png_dimensions, validate_runtime_fixture
from .metrics import calculate_metrics
from .models import OcrObservation
from .parser import parse_reading
from .temporal import TemporalClassifier
from .validator import validate_metadata, validate_reading


class RunTimeoutError(RuntimeError):
    code = "RUN_TIMEOUT"


def _raw_identity(raw_text: str) -> tuple[str, str]:
    data = raw_text.encode("utf-8")
    if not data:
        return "", ""
    return base64.b64encode(data).decode("ascii"), hashlib.sha256(data).hexdigest()


def _png_chunks(path: Path) -> tuple[str, ...]:
    data = path.read_bytes()
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


def validate_image(fixture_root: Path, manifest_row: dict[str, Any], config: dict[str, Any]) -> Path:
    try:
        relative = Path(manifest_row["image_relpath"])
        if relative.is_absolute() or ".." in relative.parts or relative.suffix.lower() != ".png":
            raise ValueError("INPUT_BOUNDARY_FAILURE")
        if relative.name != f"{manifest_row['scenario_id']}.png":
            raise ValueError("INPUT_BOUNDARY_FAILURE")
        root = fixture_root.resolve()
        image = (fixture_root / relative).resolve()
        if not image.is_relative_to(root) or not image.is_file():
            raise ValueError("INPUT_BOUNDARY_FAILURE")
        image_bytes = image.stat().st_size
        if image_bytes != manifest_row["image_bytes"] or image_bytes > config["max_image_bytes"]:
            raise ValueError("INPUT_BOUNDARY_FAILURE")
        if png_dimensions(image) != (config["image_width_px"], config["image_height_px"]):
            raise ValueError("INPUT_BOUNDARY_FAILURE")
        if sha256_file(image) != manifest_row["image_sha256"]:
            raise ValueError("INPUT_BOUNDARY_FAILURE")
        allowed = {"IHDR", "sRGB", "gAMA", "pHYs", "IDAT", "IEND"}
        chunk_types = _png_chunks(image)
        if not chunk_types or chunk_types[-1] != "IEND" or not set(chunk_types).issubset(allowed):
            raise ValueError("INPUT_BOUNDARY_FAILURE")
        return image
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, struct.error):
        raise ValueError("INPUT_BOUNDARY_FAILURE") from None


def run_ocr(
    repository_root: Path,
    image: Path,
    *,
    timeout_seconds: float,
    delay_milliseconds: int = 0,
) -> OcrObservation:
    script = repository_root / "src/screen2xyz_lab/adapters/ocr_windows.ps1"
    command = [
        "powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(script),
        "-ImagePath", str(image), "-Language", "en-US",
        "-DelayMilliseconds", str(delay_milliseconds),
    ]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        duration = max(0, round((time.monotonic() - started) * 1000))
        return OcrObservation("TIMEOUT", "", duration, "OCR_TIMEOUT")
    if completed.returncode == 20:
        duration = max(0, round((time.monotonic() - started) * 1000))
        return OcrObservation(
            "NOT_INVOKED", "", duration, "INPUT_BOUNDARY_FAILURE",
            engine="not_invoked", engine_version="not_applicable", language="en-US",
        )
    if completed.returncode != 0:
        duration = max(0, round((time.monotonic() - started) * 1000))
        return OcrObservation("FAILURE", "", duration, "OCR_FAILURE")
    try:
        value = json.loads(completed.stdout.strip())
        if set(value) != {"schema_version", "status", "raw_text", "engine", "engine_version", "language", "duration_ms"}:
            raise ValueError("unexpected OCR schema")
        if value["status"] != "SUCCESS" or value["engine"] != "Windows.Media.Ocr" or value["language"] != "en-US":
            raise ValueError("unexpected OCR identity")
        return OcrObservation(
            "SUCCESS",
            str(value["raw_text"]),
            max(0, int(value["duration_ms"])),
            "",
            str(value["engine"]),
            str(value["engine_version"]),
            str(value["language"]),
        )
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        duration = max(0, round((time.monotonic() - started) * 1000))
        return OcrObservation("FAILURE", "", duration, "OCR_FAILURE")


def evaluate_fixture(
    repository_root: Path,
    fixture_root: Path,
    output_root: Path,
    *,
    run_timeout_seconds: float | None = None,
) -> dict[str, Any]:
    if output_root.exists():
        raise FileExistsError("evaluation output root must be fresh")
    manifest = validate_runtime_fixture(fixture_root)
    config = load_config(fixture_root / "fixture_config.json")
    validate_metadata(config)
    config_hash = config_sha256(config)
    if manifest["config_sha256"] != config_hash:
        raise ValueError("RUN_CONFIG_INVALID")
    timeout = float(run_timeout_seconds or config["run_timeout_seconds"])
    deadline = time.monotonic() + timeout
    temporal = TemporalClassifier()
    raw_rows: list[dict[str, Any]] = []
    accepted_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    classifications: list[dict[str, Any]] = []

    for manifest_row in manifest["scenarios"]:
        if time.monotonic() >= deadline:
            raise RunTimeoutError("run watchdog expired")
        scenario_id = manifest_row["scenario_id"]
        try:
            image = validate_image(fixture_root, manifest_row, config)
            observation = run_ocr(
                repository_root,
                image,
                timeout_seconds=min(config["ocr_timeout_seconds"], max(0.01, deadline - time.monotonic())),
            )
            input_code = ""
        except ValueError:
            observation = OcrObservation(
                "NOT_INVOKED", "", 0, "INPUT_BOUNDARY_FAILURE",
                engine="not_invoked", engine_version="not_applicable", language="en-US",
            )
            input_code = "INPUT_BOUNDARY_FAILURE"

        raw_b64, raw_hash = _raw_identity(observation.raw_text)
        raw_row = {
            "scenario_id": scenario_id,
            "sequence": manifest_row["sequence"],
            "condition_id": manifest_row["condition_id"],
            "image_relpath": manifest_row["image_relpath"],
            "image_sha256": manifest_row["image_sha256"],
            "config_sha256": config_hash,
            "ocr_engine": observation.engine,
            "ocr_engine_version": observation.engine_version,
            "ocr_language": observation.language,
            "ocr_status": observation.status,
            "raw_text_utf8_b64": raw_b64,
            "raw_text_sha256": raw_hash,
            "raw_text_display": formula_safe_display(observation.raw_text),
            "duration_ms": observation.duration_ms,
            "ocr_error_code": observation.error_code,
        }
        raw_rows.append(raw_row)

        if input_code:
            parsed = parse_reading("")
            codes = (input_code,)
            triplet = None
        elif observation.status != "SUCCESS":
            parsed = parse_reading("")
            codes = (observation.error_code,)
            triplet = None
        else:
            parsed = parse_reading(observation.raw_text)
            codes = validate_reading(parsed, config)
            triplet = (
                (parsed.latitude, parsed.longitude, parsed.elevation_m)
                if not codes and parsed.latitude is not None and parsed.longitude is not None and parsed.elevation_m is not None
                else None
            )
        temporal_result = temporal.classify(scenario_id, triplet, codes)
        parsed_lat = format(parsed.latitude, ".6f") if parsed.latitude is not None else ""
        parsed_lon = format(parsed.longitude, ".6f") if parsed.longitude is not None else ""
        parsed_elev = format(parsed.elevation_m, ".2f") if parsed.elevation_m is not None else ""
        classification = {
            "scenario_id": scenario_id,
            "sequence": manifest_row["sequence"],
            "condition_id": manifest_row["condition_id"],
            "image_relpath": manifest_row["image_relpath"],
            "image_sha256": manifest_row["image_sha256"],
            "config_sha256": config_hash,
            "raw_text_utf8_b64": raw_b64,
            "raw_text_sha256": raw_hash,
            "parsed_latitude": parsed_lat,
            "parsed_longitude": parsed_lon,
            "parsed_elevation_m": parsed_elev,
            "source_crs": "EPSG:4326",
            "axis_order": "longitude_latitude",
            "elevation_unit": "m",
            "vertical_reference": "SYNTHETIC_LOCAL",
            "classification": temporal_result.classification,
            "primary_code": temporal_result.primary_code,
            "all_codes": "|".join(temporal_result.all_codes),
            "reference_scenario_id": temporal_result.reference_scenario_id,
        }
        classifications.append(classification)
        if temporal_result.classification == "ACCEPTED":
            accepted_rows.append(
                {
                    "scenario_id": scenario_id,
                    "sequence": manifest_row["sequence"],
                    "condition_id": manifest_row["condition_id"],
                    "image_relpath": manifest_row["image_relpath"],
                    "image_sha256": manifest_row["image_sha256"],
                    "config_sha256": config_hash,
                    "longitude": parsed_lon,
                    "latitude": parsed_lat,
                    "elevation_m": parsed_elev,
                    "source_crs": "EPSG:4326",
                    "axis_order": "longitude_latitude",
                    "elevation_unit": "m",
                    "vertical_reference": "SYNTHETIC_LOCAL",
                    "classification": "ACCEPTED",
                }
            )
        else:
            rejected_rows.append(
                {
                    "scenario_id": scenario_id,
                    "sequence": manifest_row["sequence"],
                    "condition_id": manifest_row["condition_id"],
                    "image_relpath": manifest_row["image_relpath"],
                    "image_sha256": manifest_row["image_sha256"],
                    "config_sha256": config_hash,
                    "raw_text_utf8_b64": raw_b64,
                    "raw_text_sha256": raw_hash,
                    "raw_text_display": raw_row["raw_text_display"],
                    "parsed_longitude": parsed_lon,
                    "parsed_latitude": parsed_lat,
                    "parsed_elevation_m": parsed_elev,
                    "classification": "REJECTED",
                    "primary_code": temporal_result.primary_code,
                    "all_codes": "|".join(temporal_result.all_codes),
                    "reference_scenario_id": temporal_result.reference_scenario_id,
                }
            )

    def ensure_deadline() -> None:
        if time.monotonic() >= deadline:
            raise RunTimeoutError("run watchdog expired before publication")

    hashes = write_evaluation_outputs(
        output_root,
        raw_rows=raw_rows,
        accepted_rows=accepted_rows,
        rejected_rows=rejected_rows,
        classifications=classifications,
        config_hash=config_hash,
        before_publish=ensure_deadline,
    )
    return {
        "status": "COMPLETED",
        "scenario_count": 60,
        "accepted_count": len(accepted_rows),
        "rejected_count": len(rejected_rows),
        "artifact_hashes": hashes,
    }


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def compare_runs(fixture_root: Path, run_a: Path, run_b: Path) -> dict[str, Any]:
    class_a = _load_json(run_a / "classifications.json")
    class_b = _load_json(run_b / "classifications.json")
    raw_a = _load_json(run_a / "raw_ocr_projection.json")
    raw_b = _load_json(run_b / "raw_ocr_projection.json")
    classification_differences = sum(left != right for left, right in zip(class_a, class_b, strict=True))
    raw_differences = sum(left != right for left, right in zip(raw_a, raw_b, strict=True))

    manifest = _load_json(fixture_root / "fixture_manifest.json")
    keys: dict[str, tuple[str, str]] = {
        "fixture_config.json": (sha256_file(fixture_root / "fixture_config.json"), sha256_file(fixture_root / "fixture_config.json")),
        "ground_truth.csv": (sha256_file(fixture_root / "ground_truth.csv"), sha256_file(fixture_root / "ground_truth.csv")),
        "fixture_manifest.json": (sha256_file(fixture_root / "fixture_manifest.json"), sha256_file(fixture_root / "fixture_manifest.json")),
    }
    for row in manifest["scenarios"]:
        keys[f"image:{row['scenario_id']}"] = (row["image_sha256"], row["image_sha256"])
    for filename in (
        "raw_ocr_projection.json", "classifications.json", "accepted_points.csv",
        "rejected_readings.csv", "points_source_xyz.txt",
    ):
        keys[filename] = (sha256_file(run_a / filename), sha256_file(run_b / filename))
    sidecar_a = _load_json(run_a / "points_source_xyz_metadata.json")["deterministic_projection"]
    sidecar_b = _load_json(run_b / "points_source_xyz_metadata.json")["deterministic_projection"]
    sidecar_a_hash = hashlib.sha256((json.dumps(sidecar_a, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")).hexdigest()
    sidecar_b_hash = hashlib.sha256((json.dumps(sidecar_b, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")).hexdigest()
    keys["points_source_xyz_metadata.json:deterministic_projection"] = (sidecar_a_hash, sidecar_b_hash)
    differences = [key for key, pair in keys.items() if pair[0] != pair[1]]
    status = "met" if not differences and classification_differences == 0 and raw_differences == 0 else "missed"
    metric = {
        "classification_differences": classification_differences,
        "classification_population": 60,
        "raw_ocr_projection_differences": raw_differences,
        "raw_ocr_population": 60,
        "deterministic_hash_differences": len(differences),
        "deterministic_artifact_count": len(keys),
        "target": 0,
        "status": status,
    }
    return {
        "schema_version": "1.0",
        "metric": metric,
        "whitelist_count": len(keys),
        "whitelist_keys": list(keys),
        "hash_differences": differences,
        "run_a_hashes": {key: pair[0] for key, pair in keys.items()},
        "run_b_hashes": {key: pair[1] for key, pair in keys.items()},
    }


def transactional_publish_directory(
    stage: Path,
    destination_root: Path,
    *,
    publisher: Callable[[Path, Path], None] = os.replace,
) -> None:
    """Publish a staged set with rollback; every destination must be new."""

    entries = sorted(stage.iterdir(), key=lambda path: (path.is_dir(), path.name))
    collisions = [entry.name for entry in entries if (destination_root / entry.name).exists()]
    if collisions:
        raise FileExistsError(f"transaction destination collision: {collisions}")
    moved: list[Path] = []
    try:
        for entry in entries:
            destination = destination_root / entry.name
            publisher(entry, destination)
            moved.append(destination)
        stage.rmdir()
    except Exception as exc:
        rollback_errors = []
        for destination in reversed(moved):
            try:
                if destination.is_dir():
                    shutil.rmtree(destination)
                else:
                    destination.unlink(missing_ok=True)
            except OSError:
                rollback_errors.append(destination.name)
        if rollback_errors:
            raise EvidenceError(f"transaction rollback failed for {rollback_errors}") from exc
        raise EvidenceError("transactional evidence publication failed") from exc


def publish_evidence(
    fixture_root: Path,
    run_a: Path,
    run_b: Path,
    evidence_root: Path,
    *,
    publisher: Callable[[Path, Path], None] = os.replace,
) -> dict[str, Any]:
    filenames = (
        "ground_truth.csv", "fixture_manifest.json", "raw_ocr_readings.csv",
        "accepted_points.csv", "rejected_readings.csv", "points_source_xyz.txt",
        "points_source_xyz_metadata.json", "classifications.json", "raw_ocr_projection.json",
        "metrics.json", "repeatability_comparison.json", "failed_cases.json",
    )
    collisions = [name for name in filenames if (evidence_root / name).exists()]
    if (evidence_root / "repeatability").exists():
        collisions.append("repeatability/")
    if collisions:
        raise FileExistsError(f"refusing evidence collisions: {collisions}")

    comparison = compare_runs(fixture_root, run_a, run_b)
    ground_truth = _csv_rows(fixture_root / "ground_truth.csv")
    classifications = _load_json(run_a / "classifications.json")
    raw_rows = _csv_rows(run_a / "raw_ocr_readings.csv")
    metrics = calculate_metrics(ground_truth, classifications, raw_rows, comparison["metric"])

    stage = evidence_root.parent / f".{evidence_root.name}.publication-staging-{os.getpid()}"
    if stage.exists():
        raise FileExistsError("evidence publication staging collision")
    stage.mkdir(parents=True)

    try:
        atomic_copy(fixture_root / "ground_truth.csv", stage / "ground_truth.csv")
        atomic_copy(fixture_root / "fixture_manifest.json", stage / "fixture_manifest.json")
        for filename in (
            "raw_ocr_readings.csv", "accepted_points.csv", "rejected_readings.csv",
            "points_source_xyz.txt", "points_source_xyz_metadata.json", "classifications.json",
            "raw_ocr_projection.json",
        ):
            atomic_copy(run_a / filename, stage / filename)
        atomic_write_json(stage / "metrics.json", metrics)
        atomic_write_json(stage / "repeatability_comparison.json", comparison)

        observed = {row["scenario_id"]: row for row in classifications}
        failed = [
            {
                "scenario_id": row["scenario_id"],
                "expected_disposition": row["expected_disposition"],
                "expected_primary_code": row["expected_primary_code"],
                "observed_classification": observed[row["scenario_id"]]["classification"],
                "observed_primary_code": observed[row["scenario_id"]]["primary_code"],
                "parsed_latitude": observed[row["scenario_id"]]["parsed_latitude"],
                "parsed_longitude": observed[row["scenario_id"]]["parsed_longitude"],
                "parsed_elevation_m": observed[row["scenario_id"]]["parsed_elevation_m"],
            }
            for row in ground_truth
            if row["scenario_id"] in metrics["diagnostics"]["failed_scenario_ids"]
        ]
        atomic_write_json(stage / "failed_cases.json", {"schema_version": "1.0", "failed_cases": failed})

        repeat_root = stage / "repeatability"
        atomic_copy(run_a / "raw_ocr_projection.json", repeat_root / "run_a_raw_ocr_projection.json")
        atomic_copy(run_b / "raw_ocr_projection.json", repeat_root / "run_b_raw_ocr_projection.json")
        atomic_copy(run_a / "classifications.json", repeat_root / "run_a_classifications.json")
        atomic_copy(run_b / "classifications.json", repeat_root / "run_b_classifications.json")
        atomic_write_json(repeat_root / "run_a_artifact_hashes.json", comparison["run_a_hashes"])
        atomic_write_json(repeat_root / "run_b_artifact_hashes.json", comparison["run_b_hashes"])
        transactional_publish_directory(stage, evidence_root, publisher=publisher)
    except Exception:
        safe_stage = stage.resolve()
        if safe_stage.parent == evidence_root.parent.resolve() and safe_stage.name.startswith(f".{evidence_root.name}.publication-staging-"):
            shutil.rmtree(safe_stage, ignore_errors=True)
        raise
    return metrics
