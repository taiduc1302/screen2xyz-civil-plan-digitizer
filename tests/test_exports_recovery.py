from __future__ import annotations

import csv
import io
import json
import os
import shutil
import unittest
import uuid
from decimal import Decimal
from unittest import mock

from screen2xyz_lab.config import ConfigError, OUTPUT_CLASSIFICATION, canonical_config, validate_config
from screen2xyz_lab.evidence import EvidenceError, atomic_write_bytes, sha256_file, write_manifest
from screen2xyz_lab.exporters import (
    ACCEPTED_HEADER,
    RAW_HEADER,
    REJECTED_HEADER,
    csv_bytes,
    sidecar_value,
    xyz_bytes,
)
from screen2xyz_lab.fixture import GROUND_TRUTH_HEADER
from screen2xyz_lab.models import OcrObservation
from screen2xyz_lab.pipeline import RunTimeoutError, evaluate_fixture, publish_evidence, transactional_publish_directory
from screen2xyz_lab.evidence import ManifestEvidenceError
from screen2xyz_lab import cli

from helpers import EVIDENCE, FIXTURE, ROOT


class ExportRecoveryTests(unittest.TestCase):
    def test_T_EXP_001_csv_dialect(self):
        data = csv_bytes([{"a": "plain", "b": "x,\"y\n", "c": ""}], ("a", "b", "c"))
        self.assertFalse(data.startswith(b"\xef\xbb\xbf"))
        self.assertTrue(data.endswith(b"\r\n"))
        self.assertTrue(data.startswith(b"a,b,c\r\n"))
        self.assertIn(b'"x,""y\n"', data)
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"), newline="")))
        self.assertEqual(rows[0]["b"], "x,\"y\n")

    def test_T_EXP_002_exact_csv_schemas(self):
        paths_and_headers = (
            (EVIDENCE / "ground_truth.csv", GROUND_TRUTH_HEADER),
            (EVIDENCE / "raw_ocr_readings.csv", RAW_HEADER),
            (EVIDENCE / "accepted_points.csv", ACCEPTED_HEADER),
            (EVIDENCE / "rejected_readings.csv", REJECTED_HEADER),
        )
        loaded = {}
        for path, expected_header in paths_and_headers:
            with path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(tuple(reader.fieldnames or ()), expected_header)
                loaded[path.name] = list(reader)
        self.assertEqual(len(loaded["ground_truth.csv"]), 60)
        self.assertEqual(len(loaded["raw_ocr_readings.csv"]), 60)
        self.assertEqual(len(loaded["accepted_points.csv"]) + len(loaded["rejected_readings.csv"]), 60)
        expected_ids = [f"S{index:03d}" for index in range(1, 61)]
        self.assertEqual([row["scenario_id"] for row in loaded["ground_truth.csv"]], expected_ids)
        self.assertEqual([row["scenario_id"] for row in loaded["raw_ocr_readings.csv"]], expected_ids)
        partition_ids = [row["scenario_id"] for row in loaded["accepted_points.csv"]] + [row["scenario_id"] for row in loaded["rejected_readings.csv"]]
        self.assertEqual(set(partition_ids), set(expected_ids))
        self.assertEqual(len(partition_ids), len(set(partition_ids)))
        for name in ("accepted_points.csv", "rejected_readings.csv"):
            sequences = [int(row["sequence"]) for row in loaded[name]]
            self.assertEqual(sequences, sorted(sequences))
        self.assertTrue(all(row["sequence"].isdigit() for rows in loaded.values() for row in rows))
        self.assertTrue(all(len(row["image_sha256"]) == 64 for name, rows in loaded.items() if name != "ground_truth.csv" for row in rows))
        self.assertTrue(all(row["duration_ms"].isdigit() for row in loaded["raw_ocr_readings.csv"]))
        self.assertTrue(all(row["classification"] == "ACCEPTED" for row in loaded["accepted_points.csv"]))
        self.assertTrue(all(row["classification"] == "REJECTED" and row["primary_code"] for row in loaded["rejected_readings.csv"]))
        for row in loaded["accepted_points.csv"]:
            Decimal(row["longitude"]); Decimal(row["latitude"]); Decimal(row["elevation_m"])
        self.assertFalse(any(name.startswith("expected_") or name == "visible_text" for name in RAW_HEADER))

    def test_T_EXP_003_xyz_schema(self):
        rows = [{"longitude": "-123.000001", "latitude": "49.000001", "elevation_m": "10.20"}]
        self.assertEqual(xyz_bytes(rows), b"-123.000001 49.000001 10.20\n")

    def test_T_EXP_004_sidecar_schema(self):
        sidecar = sidecar_value(config_hash="a" * 64, accepted_count=1, rejected_count=2, xyz_hash="b" * 64)
        required = {
            "schema_version", "task_id", "fixture_version", "config_sha256", "source_crs", "axis_order",
            "x_field", "y_field", "z_field", "elevation_unit", "vertical_reference", "coordinate_precision",
            "elevation_precision", "ocr_engine", "ocr_engine_version", "ocr_language", "accepted_count",
            "rejected_count", "artifact_sha256", "output_classification", "limitations", "deterministic_projection",
        }
        self.assertEqual(set(sidecar), required)
        self.assertEqual(sidecar["artifact_sha256"], {"points_source_xyz.txt": "b" * 64})
        self.assertEqual(sidecar["output_classification"], OUTPUT_CLASSIFICATION)
        self.assertIn("not tested", " ".join(sidecar["limitations"]).lower())
        projection_keys = {
            "schema_version", "fixture_version", "config_sha256", "source_crs", "axis_order",
            "x_field", "y_field", "z_field", "elevation_unit", "vertical_reference",
            "coordinate_precision", "elevation_precision", "ocr_engine", "ocr_engine_version",
            "ocr_language", "accepted_count", "rejected_count", "points_source_xyz_sha256",
            "output_classification", "limitations",
        }
        self.assertEqual(set(sidecar["deterministic_projection"]), projection_keys)
        self.assertEqual(sidecar["deterministic_projection"]["points_source_xyz_sha256"], "b" * 64)
        self.assertEqual(sidecar["deterministic_projection"]["x_field"], "longitude")
        self.assertEqual(sidecar["deterministic_projection"]["y_field"], "latitude")
        self.assertEqual(sidecar["deterministic_projection"]["z_field"], "elevation_m")

    def test_T_REC_001_atomic_write_failure(self):
        directory = ROOT / ".lab_work" / f"rec001-{os.getpid()}-{uuid.uuid4().hex}"
        directory.mkdir(parents=True)
        target = directory / "artifact.txt"
        with mock.patch("screen2xyz_lab.evidence.os.replace", side_effect=OSError("injected")):
            with self.assertRaises(EvidenceError):
                atomic_write_bytes(target, b"value")
        self.assertFalse(target.exists())
        self.assertEqual(list(directory.iterdir()), [])
        stage = ROOT / ".lab_work" / f"publish-stage-{os.getpid()}-{uuid.uuid4().hex}"
        destination = ROOT / ".lab_work" / f"publish-destination-{os.getpid()}-{uuid.uuid4().hex}"
        stage.mkdir(parents=True)
        destination.mkdir(parents=True)
        atomic_write_bytes(stage / "a.txt", b"a")
        atomic_write_bytes(stage / "b.txt", b"b")
        calls = 0

        def injected(source, target):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected publication failure")
            os.replace(source, target)

        with self.assertRaises(EvidenceError):
            transactional_publish_directory(stage, destination, publisher=injected)
        self.assertEqual(list(destination.iterdir()), [])

    def test_T_REC_002_config_corruption_and_idempotency(self):
        invalid = canonical_config()
        invalid["axis_order"] = "ambiguous"
        with self.assertRaises(ConfigError):
            validate_config(invalid)
        directory = ROOT / ".lab_work" / f"rec002-{os.getpid()}-{uuid.uuid4().hex}"
        directory.mkdir(parents=True)
        target = directory / "retained.txt"
        atomic_write_bytes(target, b"first")
        original_hash = sha256_file(target)
        with self.assertRaises(EvidenceError):
            atomic_write_bytes(target, b"second")
        self.assertEqual(sha256_file(target), original_hash)
        temporary_root = ROOT / ".lab_work" / f"rec002-runtime-{os.getpid()}-{uuid.uuid4().hex}"
        temporary_root.mkdir(parents=True)
        fixture = temporary_root / "fixture"
        fixture.mkdir()
        shutil.copy2(FIXTURE / "fixture_config.json", fixture / "fixture_config.json")
        shutil.copy2(FIXTURE / "fixture_manifest.json", fixture / "fixture_manifest.json")
        shutil.copytree(FIXTURE / "images", fixture / "images")
        (fixture / "images/S001.png").write_bytes(b"corrupt-png")
        observed = OcrObservation("SUCCESS", "LAT: 1 LON: 2 ELEV: 3 m", 1, "")
        run_a = temporary_root / "run-a"
        run_b = temporary_root / "run-b"
        with mock.patch("screen2xyz_lab.pipeline.run_ocr", return_value=observed):
            evaluate_fixture(ROOT, fixture, run_a)
            evaluate_fixture(ROOT, fixture, run_b)
        with (run_a / "rejected_readings.csv").open("r", encoding="utf-8", newline="") as handle:
            rejected = {row["scenario_id"]: row for row in csv.DictReader(handle)}
        self.assertEqual(rejected["S001"]["primary_code"], "INPUT_BOUNDARY_FAILURE")
        self.assertEqual(
            {path.name: sha256_file(path) for path in run_a.iterdir()},
            {path.name: sha256_file(path) for path in run_b.iterdir()},
        )

        interrupted = temporary_root / "interrupted"
        with mock.patch("screen2xyz_lab.pipeline.run_ocr", return_value=observed), mock.patch(
            "screen2xyz_lab.exporters.atomic_write_json", side_effect=EvidenceError("injected")
        ):
            with self.assertRaises(EvidenceError):
                evaluate_fixture(ROOT, fixture, interrupted)
        self.assertFalse(interrupted.exists())
        self.assertEqual(list(temporary_root.glob(".interrupted.staging-*")), [])
        with mock.patch("screen2xyz_lab.pipeline.run_ocr", return_value=observed):
            evaluate_fixture(ROOT, fixture, interrupted)
        self.assertTrue((interrupted / "raw_ocr_readings.csv").is_file())

        shutil.copy2(FIXTURE / "ground_truth.csv", fixture / "ground_truth.csv")
        retained = temporary_root / "retained"
        retained.mkdir()
        with mock.patch("screen2xyz_lab.pipeline.atomic_copy", side_effect=EvidenceError("injected")):
            with self.assertRaises(EvidenceError):
                publish_evidence(fixture, run_a, run_b, retained)
        self.assertEqual(list(retained.iterdir()), [])
        self.assertEqual(list(temporary_root.glob(".retained.publication-staging-*")), [])
        publish_evidence(fixture, run_a, run_b, retained)
        self.assertTrue((retained / "metrics.json").is_file())

    def test_T_REC_003_run_fatal_separation(self):
        self.assertEqual(ConfigError.code, "RUN_CONFIG_INVALID")
        self.assertEqual(EvidenceError.code, "RUN_OUTPUT_WRITE_FAILURE")
        self.assertEqual(RunTimeoutError.code, "RUN_TIMEOUT")
        self.assertEqual(ManifestEvidenceError.code, "RUN_MANIFEST_WRITE_FAILURE")
        run_fatal = {"RUN_CONFIG_INVALID", "RUN_OUTPUT_WRITE_FAILURE", "RUN_MANIFEST_WRITE_FAILURE", "RUN_TIMEOUT"}
        self.assertFalse(run_fatal.intersection({"OCR_FAILURE", "MISSING_ELEV", "DUPLICATE_READING"}))
        with mock.patch("screen2xyz_lab.cli.generate_fixture", side_effect=ConfigError("injected")):
            self.assertEqual(cli.main(["generate"]), 30)
        with mock.patch("screen2xyz_lab.cli._environment_evidence", side_effect=EvidenceError("injected")):
            self.assertEqual(cli.main(["environment"]), 31)
        with mock.patch("screen2xyz_lab.cli.evaluate_fixture", side_effect=RunTimeoutError("injected")):
            self.assertEqual(cli.main(["evaluate", "--output", ".lab_work/rec003-timeout"]), 32)
        with mock.patch("screen2xyz_lab.cli.evaluate_fixture", side_effect=EvidenceError("injected")):
            self.assertEqual(cli.main(["evaluate", "--output", ".lab_work/rec003-output"]), 31)
        with mock.patch("screen2xyz_lab.cli.finalize_evidence", side_effect=ManifestEvidenceError("injected")):
            self.assertEqual(cli.main(["finalize-evidence", "--test-results", ".lab_work/fake.txt"]), 33)
        manifest_root = ROOT / ".lab_work" / f"manifest-failure-{os.getpid()}-{uuid.uuid4().hex}"
        (manifest_root / "evidence").mkdir(parents=True)
        with mock.patch("screen2xyz_lab.evidence.atomic_write_bytes", side_effect=EvidenceError("injected")):
            with self.assertRaises(ManifestEvidenceError):
                write_manifest(manifest_root / "evidence", manifest_root)
        atomic_write_bytes(manifest_root / "evidence/a.txt", b"a")
        with mock.patch("screen2xyz_lab.evidence.sha256_file", side_effect=OSError("injected")):
            with self.assertRaises(ManifestEvidenceError):
                write_manifest(manifest_root / "evidence", manifest_root)
        self.assertFalse(any(code in REJECTED_HEADER for code in run_fatal))
        retained_rejected = EVIDENCE / "rejected_readings.csv"
        if retained_rejected.is_file():
            with retained_rejected.open("r", encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    self.assertFalse(any(value.startswith("RUN_") for value in row.values()))
