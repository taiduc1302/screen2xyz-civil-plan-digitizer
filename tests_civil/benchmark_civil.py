"""Reproducible synthetic benchmark for the Civil Plan Digitizer rules.

This benchmark does not use real drawings and must not be reported as
real-world OCR, symbol-detection, or downstream-import accuracy.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
import tracemalloc
from dataclasses import asdict, dataclass

from screen2xyz_civil import contracts as C
from screen2xyz_civil.detection import (
    Rect,
    SymbolCandidate,
    TextCandidate,
    classify_candidate,
    normalize_numeric,
)
from screen2xyz_civil.models import PixelPoint
from screen2xyz_civil.surface import build_project_surface
from screen2xyz_civil.transform import build_calibration, to_local, to_pixel

from helpers_civil import add_approved, clock, project_and_workflow


DATASET_ID = "CPD-SYNTH-BENCH-001"


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    text: str
    expected_type: str
    symbol_type: str | None = None
    context: str = ""


def _cases() -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    for index in range(25):
        cases.append(
            BenchmarkCase(
                f"EG-{index:03d}",
                f"{40 + index / 10:.2f}",
                C.EXISTING_GROUND,
                "EXISTING_CROSS",
            )
        )
        cases.append(
            BenchmarkCase(
                f"DG-{index:03d}",
                f"{50 + index / 10:.2f}",
                C.DESIGN_GRADE,
                "DESIGN_OVAL",
            )
        )
        cases.append(
            BenchmarkCase(
                f"RV-{index:03d}",
                f"{60 + index / 10:.2f}",
                C.REVIEW_REQUIRED_TYPE,
            )
        )
    for index in range(10):
        cases.append(
            BenchmarkCase(
                f"SL-{index:03d}",
                f"{index + 1}.0%",
                C.SLOPE_ANNOTATION,
            )
        )
        cases.append(
            BenchmarkCase(
                f"INV-{index:03d}",
                f"{30 + index / 10:.2f}",
                C.UTILITY_INVERT,
                context="INV",
            )
        )
        cases.append(
            BenchmarkCase(
                f"MD-{index:03d}",
                f"{70 + index / 10:.2f}",
                C.DRAWING_METADATA,
                context="SHEET",
            )
        )
    return cases


def _classify(cases: list[BenchmarkCase]) -> tuple[list[dict[str, object]], int]:
    rows: list[dict[str, object]] = []
    correct_associations = 0
    for index, case in enumerate(cases):
        text_box = Rect(100, index * 20, 135, index * 20 + 10)
        symbols: list[SymbolCandidate] = []
        expected_symbol_id = None
        if case.symbol_type:
            expected_symbol_id = f"target-{case.case_id}"
            symbols.append(
                SymbolCandidate(
                    expected_symbol_id,
                    case.symbol_type,
                    Rect(90, index * 20, 98, index * 20 + 8),
                    0.95,
                    C.PDF_VECTOR,
                    has_leader=True,
                )
            )
            symbols.append(
                SymbolCandidate(
                    f"distractor-{case.case_id}",
                    "DESIGN_OVAL"
                    if case.symbol_type == "EXISTING_CROSS"
                    else "EXISTING_CROSS",
                    Rect(35, index * 20, 43, index * 20 + 8),
                    0.95,
                    C.PDF_VECTOR,
                )
            )
        candidate = TextCandidate(
            case.case_id,
            case.text,
            text_box,
            0,
            C.PDF_TEXT,
            1.0,
            context=case.context,
        )
        result = classify_candidate(candidate, symbols)
        association_id = result.association.symbol_id if result.association else None
        if expected_symbol_id and association_id == expected_symbol_id:
            correct_associations += 1
        rows.append(
            {
                "id": case.case_id,
                "expected": case.expected_type,
                "predicted": result.point_type,
                "association": association_id,
            }
        )
    return rows, correct_associations


def _numeric_round_trip() -> dict[str, object]:
    values = [f"{index / 100:.2f}" for index in range(-5000, 5001, 125)]
    errors = [
        abs(normalize_numeric(value).value - float(value))
        for value in values
    ]
    return {
        "cases": len(values),
        "exact_count": sum(error == 0.0 for error in errors),
        "max_absolute_error": max(errors),
    }


def _transform_round_trip() -> dict[str, object]:
    calibration = build_calibration(
        revision=1,
        created_at=clock(),
        scale_point_1=PixelPoint(10, 180),
        scale_point_2=PixelPoint(210, 180),
        known_distance_m=50,
        origin_pixel=PixelPoint(110, 100),
        east_reference=PixelPoint(190, 40),
        origin_east_m=5000,
        origin_north_m=10000,
    )
    errors: list[float] = []
    for x in range(10, 211, 20):
        for y in range(0, 201, 20):
            source = PixelPoint(x, y)
            local = to_local(source, calibration)
            restored = to_pixel(*local, calibration)
            errors.append(math.hypot(restored.x - x, restored.y - y))
    return {
        "cases": len(errors),
        "max_round_trip_error_px": max(errors),
        "mean_round_trip_error_px": sum(errors) / len(errors),
    }


def _surface_digest() -> dict[str, object]:
    project, flow = project_and_workflow()
    for pixel, elevation in (
        (PixelPoint(20, 120), 40.0),
        (PixelPoint(180, 120), 41.0),
        (PixelPoint(180, 20), 42.0),
        (PixelPoint(20, 20), 43.0),
        (PixelPoint(100, 70), 44.0),
    ):
        add_approved(flow, pixel=pixel, elevation=elevation)
    surface = build_project_surface(project, C.EXISTING_GROUND)
    payload = json.dumps(
        [asdict(triangle) for triangle in surface.triangles],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "vertices": len(surface.vertices),
        "triangles": len(surface.triangles),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def run_benchmark(*, iterations: int = 100) -> dict[str, object]:
    cases = _cases()
    tracemalloc.start()
    start = time.perf_counter()
    first_rows, correct_associations = _classify(cases)
    for _ in range(iterations - 1):
        rows, _ = _classify(cases)
        if rows != first_rows:
            raise RuntimeError("classification output changed between iterations")
    elapsed = time.perf_counter() - start
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    exact = sum(row["expected"] == row["predicted"] for row in first_rows)
    terrain_rows = [
        row
        for row in first_rows
        if row["expected"] in {C.EXISTING_GROUND, C.DESIGN_GRADE}
    ]
    terrain_correct = sum(
        row["expected"] == row["predicted"] for row in terrain_rows
    )
    result = {
        "dataset_id": DATASET_ID,
        "scope": "synthetic rule-level benchmark; no OCR engine or real drawing",
        "classification": {
            "cases": len(first_rows),
            "exact_type_count": exact,
            "exact_type_accuracy": exact / len(first_rows),
            "terrain_cases": len(terrain_rows),
            "terrain_exact_count": terrain_correct,
            "terrain_exact_accuracy": terrain_correct / len(terrain_rows),
        },
        "association": {
            "cases": len(terrain_rows),
            "correct_count": correct_associations,
            "accuracy": correct_associations / len(terrain_rows),
        },
        "numeric": _numeric_round_trip(),
        "transform": _transform_round_trip(),
        "surface": _surface_digest(),
        "repeatability": {
            "iterations": iterations,
            "identical": True,
        },
        "performance": {
            "total_case_evaluations": len(cases) * iterations,
            "elapsed_seconds": elapsed,
            "mean_microseconds_per_case": elapsed / (len(cases) * iterations) * 1e6,
            "peak_traced_bytes": peak,
        },
        "not_measured": [
            "real-drawing OCR accuracy",
            "real-drawing vector-symbol precision or recall",
            "end-to-end estimator time savings",
            "AGTEK, Civil 3D, Kubla, or downstream LandXML acceptance",
            "survey or engineering accuracy",
        ],
    }
    deterministic_payload = {
        key: value
        for key, value in result.items()
        if key != "performance"
    }
    result["deterministic_sha256"] = hashlib.sha256(
        json.dumps(
            deterministic_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return result


if __name__ == "__main__":
    print(json.dumps(run_benchmark(), indent=2, sort_keys=True))
