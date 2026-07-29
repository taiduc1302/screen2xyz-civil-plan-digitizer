from __future__ import annotations

import copy
import hashlib
import os
import shutil
import unittest
import uuid
from pathlib import Path
from unittest import mock

from screen2xyz_lab.config import ConfigError, canonical_config, config_sha256, validate_config
from screen2xyz_lab.fixture import build_scenarios, validate_fixture, validate_runtime_fixture
from screen2xyz_lab.pipeline import evaluate_fixture, validate_image
from screen2xyz_lab.models import OcrObservation

from helpers import FIXTURE, ROOT, load_json


def fresh_work(prefix: str) -> Path:
    path = ROOT / ".lab_work" / f"{prefix}-{os.getpid()}-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    return path


class ConfigFixtureTests(unittest.TestCase):
    def test_T_CFG_001_canonical_config(self):
        config = canonical_config()
        validate_config(config)
        self.assertEqual([item["condition_id"] for item in config["conditions"]], ["baseline", "scale_125", "scale_150"])
        self.assertEqual(config_sha256(config), config_sha256(copy.deepcopy(config)))

    def test_T_CFG_002_fail_closed_config(self):
        for key in canonical_config():
            invalid = canonical_config()
            invalid.pop(key)
            with self.subTest(key=key), self.assertRaises(ConfigError):
                validate_config(invalid)
        invalid = canonical_config()
        invalid["source_crs"] = "missing"
        with self.assertRaises(ConfigError):
            validate_config(invalid)

    def test_T_FIX_001_exact_allocation(self):
        rows = build_scenarios()
        self.assertEqual(len(rows), 60)
        self.assertEqual([row["scenario_id"] for row in rows], [f"S{i:03d}" for i in range(1, 61)])
        self.assertEqual(sum(row["expected_disposition"] == "ACCEPT" for row in rows), 42)
        self.assertEqual(sum(row["expected_disposition"] != "ACCEPT" for row in rows), 18)
        for condition in ("baseline", "scale_125", "scale_150"):
            self.assertEqual(sum(row["condition_id"] == condition for row in rows), 20)

    def test_T_FIX_002_runtime_separation(self):
        manifest = load_json(FIXTURE / "fixture_manifest.json")
        forbidden = {"visible_text", "expected_disposition", "expected_primary_code", "reference_scenario_id", "scenario_class"}
        for row in manifest["scenarios"]:
            self.assertFalse(forbidden.intersection(row))
            self.assertFalse(any(key.startswith("expected_") for key in row))
        temporary = fresh_work("runtime-only")
        runtime_fixture = temporary / "fixture"
        runtime_fixture.mkdir()
        shutil.copy2(FIXTURE / "fixture_config.json", runtime_fixture / "fixture_config.json")
        shutil.copy2(FIXTURE / "fixture_manifest.json", runtime_fixture / "fixture_manifest.json")
        shutil.copytree(FIXTURE / "images", runtime_fixture / "images")
        self.assertEqual(validate_runtime_fixture(runtime_fixture)["scenario_count"], 60)
        output = temporary / "evaluation"
        observed = OcrObservation("SUCCESS", "LAT: 1 LON: 2 ELEV: 3 m", 1, "")
        with mock.patch("screen2xyz_lab.pipeline.run_ocr", return_value=observed):
            result = evaluate_fixture(ROOT, runtime_fixture, output)
        self.assertEqual(result["scenario_count"], 60)
        self.assertTrue((output / "raw_ocr_readings.csv").is_file())
        self.assertFalse((runtime_fixture / "ground_truth.csv").exists())
        self.assertFalse((runtime_fixture / "render_jobs.json").exists())

    def test_T_FIX_003_coverage_and_hashes(self):
        manifest = validate_fixture(FIXTURE)
        scenarios = build_scenarios()
        text = "\n".join(row["visible_text"] for row in scenarios)
        self.assertIn("LAT = ", text)
        self.assertIn(" deg", text)
        self.assertIn("\n", text)
        self.assertTrue(any(row["expected_longitude"].startswith("-") for row in scenarios))
        self.assertTrue(any(row["expected_longitude"] and not row["expected_longitude"].startswith("-") for row in scenarios))
        self.assertEqual(sum(row["scenario_class"] == "valid_negative_elevation" for row in scenarios), 6)
        self.assertEqual(manifest["scenario_count"], 60)
        self.assertTrue(all(row["image_bytes"] > 0 for row in manifest["scenarios"]))

    def test_T_INP_001_image_boundaries(self):
        config = canonical_config()
        manifest = load_json(FIXTURE / "fixture_manifest.json")
        source_row = manifest["scenarios"][0]
        self.assertTrue(validate_image(FIXTURE, source_row, config).is_file())
        not_invoked = OcrObservation(
            "NOT_INVOKED", "", 0, "INPUT_BOUNDARY_FAILURE",
            engine="not_invoked", engine_version="not_applicable",
        )
        self.assertEqual((not_invoked.status, not_invoked.engine, not_invoked.error_code), ("NOT_INVOKED", "not_invoked", "INPUT_BOUNDARY_FAILURE"))
        invalid_rows = []
        invalid = dict(source_row)
        invalid["image_sha256"] = "0" * 64
        invalid_rows.append((FIXTURE, invalid, config))
        invalid = dict(source_row)
        invalid["image_relpath"] = "../escape.png"
        invalid_rows.append((FIXTURE, invalid, config))
        invalid = dict(source_row)
        invalid["image_relpath"] = "images/S001.jpg"
        invalid_rows.append((FIXTURE, invalid, config))
        for root, candidate, candidate_config in invalid_rows:
            with self.subTest(path=candidate["image_relpath"]), self.assertRaisesRegex(ValueError, "INPUT_BOUNDARY_FAILURE"):
                validate_image(root, candidate, candidate_config)

        fixture = fresh_work("input-boundary")
        (fixture / "images").mkdir()
        image = fixture / "images/S001.png"
        shutil.copy2(FIXTURE / "images/S001.png", image)
        row = dict(source_row)
        small_limit = copy.deepcopy(config)
        small_limit["max_image_bytes"] = image.stat().st_size - 1
        with self.assertRaisesRegex(ValueError, "INPUT_BOUNDARY_FAILURE"):
            validate_image(fixture, row, small_limit)

        dimension_data = bytearray(image.read_bytes())
        dimension_data[16:20] = (1599).to_bytes(4, "big")
        image.write_bytes(dimension_data)
        dimension_row = dict(row)
        dimension_row["image_bytes"] = len(dimension_data)
        dimension_row["image_sha256"] = hashlib.sha256(dimension_data).hexdigest()
        with self.assertRaisesRegex(ValueError, "INPUT_BOUNDARY_FAILURE"):
            validate_image(fixture, dimension_row, config)

        corrupt = b"not-a-valid-png"
        image.write_bytes(corrupt)
        corrupt_row = dict(row)
        corrupt_row["image_bytes"] = len(corrupt)
        corrupt_row["image_sha256"] = hashlib.sha256(corrupt).hexdigest()
        with self.assertRaisesRegex(ValueError, "INPUT_BOUNDARY_FAILURE"):
            validate_image(fixture, corrupt_row, config)
