"""M1 controlled evaluation: varied synthetic intake fixture and scoring.

The M1 evaluation set (task ID ``S2XYZ-M1-001``) deliberately varies what
the sealed baseline fixture held constant — canvas size, contrast, glyph
softness, layout, and surrounding noise — so it challenges the intake and
review pipeline rather than re-encoding the parser's assumptions. All text
and values are generated from a fixed seed; nothing is derived from any
real drawing, project, or location.

Expected outcomes are defined from the *rendered truth* before any OCR
runs. Cases M015 (letter ``O`` inside digits) and M021 (numeric noise near
a valid reading) are intentional challenge cases whose real behaviour is
reported, not tuned for.
"""

from __future__ import annotations

import json
import random
import subprocess
from decimal import Decimal
from pathlib import Path
from typing import Any

from screen2xyz_lab.evidence import atomic_write_bytes, atomic_write_json, sha256_file
from screen2xyz_lab.exporters import csv_bytes

from .session import ReviewSession

EVAL_TASK_ID = "S2XYZ-M1-001"
EVAL_FIXTURE_VERSION = "m1_eval_v0.1"
EVAL_SEED = 20260718

GROUND_TRUTH_HEADER = (
    "scenario_id", "kind", "expected_disposition", "expected_primary_code",
    "expected_latitude", "expected_longitude", "expected_elevation_m",
    "reference_scenario_id",
)


def _triplet(rng: random.Random) -> tuple[str, str, str]:
    latitude = Decimal(rng.randint(-75_000_000, 75_000_000)) / Decimal(1_000_000)
    longitude = Decimal(rng.randint(-170_000_000, 170_000_000)) / Decimal(1_000_000)
    elevation = Decimal(rng.randint(-25_000, 250_000)) / Decimal(100)
    return (format(latitude, ".6f"), format(longitude, ".6f"), format(elevation, ".2f"))


def _line(text: str, x: int, y: int) -> dict[str, Any]:
    return {"text": text, "x": x, "y": y}


def build_m1_scenarios() -> list[dict[str, Any]]:
    """Build the 24 deterministic M1 evaluation scenarios."""

    rng = random.Random(EVAL_SEED)
    values = [_triplet(rng) for _ in range(20)]
    base = {
        "width_px": 1600, "height_px": 260, "font_size_px": 32,
        "foreground_gray": 0, "background_gray": 255, "softness_scale": 1.0,
    }

    def scenario(
        sid: str, kind: str, lines: list[dict[str, Any]],
        disposition: str, primary: str = "",
        expected: tuple[str, str, str] | None = None,
        reference: str = "", **render: Any,
    ) -> dict[str, Any]:
        lat, lon, elev = expected if expected else ("", "", "")
        return {
            "scenario_id": sid, "kind": kind, "lines": lines,
            "expected_disposition": disposition, "expected_primary_code": primary,
            "expected_latitude": lat, "expected_longitude": lon,
            "expected_elevation_m": elev, "reference_scenario_id": reference,
            **{**base, **render},
        }

    def v1(t: tuple[str, str, str]) -> str:
        return f"LAT: {t[0]}   LON: {t[1]}   ELEV: {t[2]} m"

    scenarios = [
        scenario("M001", "valid_baseline", [_line(v1(values[0]), 30, 80)], "ACCEPT", expected=values[0]),
        scenario("M002", "valid_large_canvas", [_line(v1(values[1]), 60, 150)], "ACCEPT", expected=values[1], width_px=2400, height_px=420, font_size_px=48),
        scenario("M003", "valid_small_canvas", [_line(v1(values[2]), 15, 60)], "ACCEPT", expected=values[2], width_px=1100, height_px=170, font_size_px=22),
        scenario("M004", "valid_low_contrast", [_line(v1(values[3]), 30, 80)], "ACCEPT", expected=values[3], foreground_gray=110, background_gray=225),
        scenario("M005", "valid_soft_glyphs", [_line(v1(values[4]), 30, 80)], "ACCEPT", expected=values[4], softness_scale=0.6),
        scenario("M006", "valid_numberless_noise", [
            _line("Site survey working view", 30, 20),
            _line(v1(values[5]), 30, 100),
            _line("Preliminary review only", 30, 190),
        ], "ACCEPT", expected=values[5], height_px=260),
        scenario("M007", "valid_all_negative", [_line(f"LAT: -{values[6][0].lstrip('-')}   LON: -{values[6][1].lstrip('-')}   ELEV: -120.55 m", 30, 80)], "ACCEPT",
                 expected=(f"-{values[6][0].lstrip('-')}", f"-{values[6][1].lstrip('-')}", "-120.55")),
        scenario("M008", "valid_max_precision", [_line("LAT: 49.123456   LON: -123.987654   ELEV: 87.05 m", 30, 80)], "ACCEPT",
                 expected=("49.123456", "-123.987654", "87.05")),
        scenario("M009", "valid_equals_format", [_line(f"LAT = {values[7][0]}    LON = {values[7][1]}    ELEV = {values[7][2]} m", 30, 80)], "ACCEPT", expected=values[7]),
        scenario("M010", "valid_deg_pipe_format", [_line(f"LAT {values[8][0]} deg     |     LON {values[8][1]} deg     |     ELEV {values[8][2]} m", 20, 80)], "ACCEPT", expected=values[8], width_px=2200),
        scenario("M011", "valid_multiline", [
            _line(f"LAT: {values[9][0]}", 30, 30),
            _line(f"LON: {values[9][1]}", 30, 110),
            _line(f"ELEV: {values[9][2]} m", 30, 190),
        ], "ACCEPT", expected=values[9], height_px=300),
        scenario("M012", "valid_integers", [_line("LAT: 49   LON: -123   ELEV: 10 m", 30, 80)], "ACCEPT",
                 expected=("49.000000", "-123.000000", "10.00")),
        scenario("M013", "stale_repeat_of_M012", [_line("LAT: 49   LON: -123   ELEV: 10 m", 40, 90)], "REJECT", "STALE_READING", reference="M012", width_px=1800),
        scenario("M014", "duplicate_of_M001", [_line(v1(values[0]), 30, 80)], "REJECT", "DUPLICATE_READING", reference="M001", width_px=2000, font_size_px=40, height_px=320),
        scenario("M015", "challenge_letter_O_digit", [_line("LAT: 49.1O2345   LON: -122.334455   ELEV: 55.10 m", 30, 80)], "REJECT", "MALFORMED_LAT"),
        scenario("M016", "malformed_letter_in_lat", [_line("LAT: 4A.123456   LON: -121.222333   ELEV: 12.30 m", 30, 80)], "REJECT", "MALFORMED_LAT"),
        scenario("M017", "missing_elevation", [_line(f"LAT: {values[10][0]}   LON: {values[10][1]}", 30, 80)], "REJECT", "MISSING_ELEV"),
        scenario("M018", "out_of_range_latitude", [_line("LAT: 95.100000   LON: 12.345678   ELEV: 100.00 m", 30, 80)], "REJECT", "OUT_OF_RANGE_LAT"),
        scenario("M019", "excess_precision_latitude", [_line("LAT: 49.1234567   LON: -123.111222   ELEV: 44.00 m", 30, 80)], "REJECT", "EXCESS_PRECISION_LAT"),
        scenario("M020", "no_coordinates", [
            _line("General arrangement notes", 30, 60),
            _line("Issued for internal review", 30, 140),
        ], "REJECT", "MISSING_ELEV"),
        scenario("M021", "challenge_numeric_noise", [
            _line("Sheet 4 of 12", 30, 20),
            _line(v1(values[11]), 30, 100),
        ], "REJECT", "EXTRA_NUMERIC_FIELD"),
        scenario("M022", "valid_recovery", [_line(v1(values[12]), 30, 80)], "ACCEPT", expected=values[12]),
        scenario("M023", "valid_low_contrast_soft", [_line(v1(values[13]), 30, 80)], "ACCEPT", expected=values[13], foreground_gray=90, background_gray=210, softness_scale=0.7),
        scenario("M024", "valid_wide_canvas", [_line(v1(values[14]), 50, 100)], "ACCEPT", expected=values[14], width_px=3200, height_px=300, font_size_px=36),
    ]
    return scenarios


def _render_jobs(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "fixture_version": EVAL_FIXTURE_VERSION,
        "jobs": [
            {
                "scenario_id": row["scenario_id"],
                "image_relpath": f"images/{row['scenario_id']}.png",
                "width_px": row["width_px"],
                "height_px": row["height_px"],
                "font_size_px": row["font_size_px"],
                "foreground_gray": row["foreground_gray"],
                "background_gray": row["background_gray"],
                "softness_scale": row["softness_scale"],
                "lines": row["lines"],
            }
            for row in scenarios
        ],
    }


def _ground_truth_bytes(scenarios: list[dict[str, Any]]) -> bytes:
    rows = [{key: row[key] for key in GROUND_TRUTH_HEADER} for row in scenarios]
    return csv_bytes(rows, GROUND_TRUTH_HEADER)


def generate_eval_fixture(repository_root: Path, fixture_root: Path) -> dict[str, Any]:
    """Generate (or verify) the deterministic M1 evaluation fixture."""

    scenarios = build_m1_scenarios()
    if fixture_root.exists():
        manifest = json.loads((fixture_root / "eval_manifest.json").read_text(encoding="utf-8"))
        if (fixture_root / "ground_truth.csv").read_bytes() != _ground_truth_bytes(scenarios):
            raise ValueError("m1 eval ground truth differs from deterministic generation")
        for row in manifest["images"]:
            if sha256_file(fixture_root / row["image_relpath"]) != row["sha256"]:
                raise ValueError(f"m1 eval image hash mismatch: {row['image_relpath']}")
        return {"status": "VERIFIED_EXISTING", "scenario_count": len(scenarios)}

    stage = fixture_root.with_name(f".{fixture_root.name}.staging")
    if stage.exists():
        raise RuntimeError("m1 eval fixture staging collision")
    stage.mkdir(parents=True)
    try:
        atomic_write_json(stage / "render_jobs.json", _render_jobs(scenarios))
        atomic_write_bytes(stage / "ground_truth.csv", _ground_truth_bytes(scenarios))
        adapter = repository_root / "src/screen2xyz_m1/adapters/render_m1_windows.ps1"
        completed = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(adapter),
                "-RenderJobsPath", str(stage / "render_jobs.json"), "-OutputRoot", str(stage),
            ],
            capture_output=True, text=True, timeout=180, check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"m1 renderer failed with exit {completed.returncode}")
        result = json.loads(completed.stdout.strip())
        if result.get("status") != "SUCCESS" or result.get("rendered_count") != len(scenarios):
            raise RuntimeError("m1 renderer returned an invalid result")
        manifest = {
            "schema_version": "1.0",
            "task_id": EVAL_TASK_ID,
            "fixture_version": EVAL_FIXTURE_VERSION,
            "seed": EVAL_SEED,
            "scenario_count": len(scenarios),
            "images": [
                {
                    "scenario_id": row["scenario_id"],
                    "image_relpath": f"images/{row['scenario_id']}.png",
                    "sha256": sha256_file(stage / "images" / f"{row['scenario_id']}.png"),
                    "bytes": (stage / "images" / f"{row['scenario_id']}.png").stat().st_size,
                }
                for row in scenarios
            ],
        }
        atomic_write_json(stage / "eval_manifest.json", manifest)
        fixture_root.parent.mkdir(parents=True, exist_ok=True)
        stage.replace(fixture_root)
        return {"status": "GENERATED", "scenario_count": len(scenarios)}
    except Exception:
        import shutil

        shutil.rmtree(stage, ignore_errors=True)
        raise


def evaluate(repository_root: Path, fixture_root: Path, run_root: Path, run_id: str) -> dict[str, Any]:
    """Run the intake→review pipeline over the M1 fixture and score it.

    No human review actions are simulated here; this scores only the
    automatic classify stage. Review, correction, and approval behaviour is
    covered by the deterministic unit tests.
    """

    scenarios = build_m1_scenarios()
    generate_eval_fixture(repository_root, fixture_root)
    session = ReviewSession(repository_root, run_root, run_id)
    outcomes: list[dict[str, Any]] = []
    for row in scenarios:
        candidate = session.process_image(fixture_root / "images" / f"{row['scenario_id']}.png")
        observed_disposition = "ACCEPT" if candidate.classification == "ACCEPTED" else "REJECT"
        exact = (
            row["expected_disposition"] == "ACCEPT"
            and observed_disposition == "ACCEPT"
            and candidate.parsed_latitude == row["expected_latitude"]
            and candidate.parsed_longitude == row["expected_longitude"]
            and candidate.parsed_elevation_m == row["expected_elevation_m"]
        )
        outcomes.append(
            {
                "scenario_id": row["scenario_id"],
                "kind": row["kind"],
                "expected_disposition": row["expected_disposition"],
                "expected_primary_code": row["expected_primary_code"],
                "observed_disposition": observed_disposition,
                "observed_primary_code": candidate.primary_code,
                "observed_codes": list(candidate.validation_codes),
                "parsed_latitude": candidate.parsed_latitude,
                "parsed_longitude": candidate.parsed_longitude,
                "parsed_elevation_m": candidate.parsed_elevation_m,
                "expected_latitude": row["expected_latitude"],
                "expected_longitude": row["expected_longitude"],
                "expected_elevation_m": row["expected_elevation_m"],
                "exact_triplet": exact,
                "raw_text_sha256_present": bool(candidate.raw_text),
            }
        )
    session.write_state()

    expected_valid = [o for o in outcomes if o["expected_disposition"] == "ACCEPT"]
    expected_invalid = [o for o in outcomes if o["expected_disposition"] == "REJECT"]
    exact_count = sum(o["exact_triplet"] for o in expected_valid)
    false_accepts = [o["scenario_id"] for o in expected_invalid if o["observed_disposition"] == "ACCEPT"]
    false_rejects = [o["scenario_id"] for o in expected_valid if o["observed_disposition"] == "REJECT"]
    code_mismatches = [
        o["scenario_id"]
        for o in expected_invalid
        if o["observed_disposition"] == "REJECT"
        and o["expected_primary_code"]
        and o["observed_primary_code"] != o["expected_primary_code"]
    ]
    metrics = {
        "schema_version": "1.0",
        "task_id": EVAL_TASK_ID,
        "fixture_version": EVAL_FIXTURE_VERSION,
        "seed": EVAL_SEED,
        "scenario_count": len(scenarios),
        "expected_valid_count": len(expected_valid),
        "expected_invalid_count": len(expected_invalid),
        "exact_triplet_count": exact_count,
        "exact_triplet_rate": round(exact_count / len(expected_valid), 6),
        "target_exact_triplet_rate": 0.9,
        "target_met": exact_count / len(expected_valid) >= 0.9,
        "false_accept_scenarios": false_accepts,
        "false_reject_scenarios": false_rejects,
        "rejected_primary_code_mismatches": code_mismatches,
        "automatic_approvals": 0,
        "exports_without_approval": 0,
        "note": (
            "Synthetic controlled evaluation of the automatic classify stage "
            "only; human review/approval behaviour is covered by unit tests. "
            "Not real-world accuracy."
        ),
        "outcomes": outcomes,
    }
    atomic_write_json(session.run_dir / "m1_eval_metrics.json", metrics)
    return metrics
