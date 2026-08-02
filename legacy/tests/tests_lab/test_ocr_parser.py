from __future__ import annotations

import base64
import hashlib
import subprocess
import unittest

from screen2xyz_lab.config import LIVE_CAPTURE_STATUS
from screen2xyz_lab.exporters import RAW_HEADER, formula_safe_display
from screen2xyz_lab.parser import known_clean_result, parse_reading
from screen2xyz_lab.pipeline import RunTimeoutError, evaluate_fixture, run_ocr

from helpers import EVIDENCE, FIXTURE, ROOT, csv_rows


class OcrParserTests(unittest.TestCase):
    def test_T_LIVE_001_status(self):
        self.assertEqual(LIVE_CAPTURE_STATUS, "Not executed")

    def test_T_OCR_001_actual_pixels(self):
        for scenario_id in ("S001", "S021", "S041"):
            with self.subTest(scenario_id=scenario_id):
                image = FIXTURE / f"images/{scenario_id}.png"
                observed = run_ocr(ROOT, image, timeout_seconds=30)
                self.assertEqual(observed.status, "SUCCESS")
                self.assertIn("LAT", observed.raw_text)
                self.assertEqual(observed.engine, "Windows.Media.Ocr")
        rows = csv_rows(EVIDENCE / "raw_ocr_readings.csv")
        self.assertEqual(len(rows), 60)
        self.assertEqual(len({row["scenario_id"] for row in rows}), 60)
        self.assertEqual({condition: sum(row["condition_id"] == condition for row in rows) for condition in ("baseline", "scale_125", "scale_150")}, {"baseline": 20, "scale_125": 20, "scale_150": 20})
        for row in rows:
            self.assertIn(row["ocr_status"], {"SUCCESS", "FAILURE", "TIMEOUT", "NOT_INVOKED"})
            self.assertNotEqual(row["ocr_status"], "NOT_INVOKED")
            self.assertNotEqual(row["ocr_engine"], "not_invoked")
            self.assertEqual(len(row["image_sha256"]), 64)
            self.assertNotIn("expected", " ".join(row).lower())

    def test_T_OCR_002_reversible_raw(self):
        rows = csv_rows(EVIDENCE / "raw_ocr_readings.csv")
        self.assertEqual(len(rows), 60)
        self.assertEqual(tuple(rows[0]), RAW_HEADER)
        for row in rows:
            self.assertIn(row["ocr_status"], {"SUCCESS", "FAILURE", "TIMEOUT", "NOT_INVOKED"})
            if row["raw_text_utf8_b64"]:
                raw = base64.b64decode(row["raw_text_utf8_b64"], validate=True)
                self.assertEqual(hashlib.sha256(raw).hexdigest(), row["raw_text_sha256"])
            else:
                self.assertEqual(row["raw_text_sha256"], "")
            if row["ocr_status"] == "SUCCESS":
                self.assertEqual(row["ocr_error_code"], "")
            else:
                self.assertIn(row["ocr_error_code"], {"OCR_FAILURE", "OCR_TIMEOUT", "INPUT_BOUNDARY_FAILURE"})
        self.assertEqual(formula_safe_display("=1"), "'=1")

    def test_T_OCR_003_timeouts_and_local_host(self):
        image = FIXTURE / "images/S001.png"
        timed = run_ocr(ROOT, image, timeout_seconds=0.05, delay_milliseconds=1000)
        self.assertEqual((timed.status, timed.error_code), ("TIMEOUT", "OCR_TIMEOUT"))
        script = ROOT / "src/screen2xyz_lab/adapters/ocr_windows.ps1"
        missing = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(script), "-ImagePath", str(FIXTURE / "missing.png")],
            capture_output=True, timeout=10, check=False,
        )
        self.assertEqual(missing.returncode, 20)
        boundary = run_ocr(ROOT, FIXTURE / "missing.png", timeout_seconds=10)
        self.assertEqual(
            (boundary.status, boundary.engine, boundary.engine_version, boundary.error_code),
            ("NOT_INVOKED", "not_invoked", "not_applicable", "INPUT_BOUNDARY_FAILURE"),
        )
        with self.assertRaises(RunTimeoutError):
            evaluate_fixture(ROOT, FIXTURE, ROOT / ".lab_work/timeout-test-output", run_timeout_seconds=0.000001)

    def test_T_PAR_001_labels_variants_and_order(self):
        passed, total = known_clean_result()
        self.assertEqual((passed, total), (13, 13))
        ambiguous = parse_reading("49.1 -123.2 10")
        self.assertIn("AMBIGUOUS_ORDER", ambiguous.codes)
        duplicate = parse_reading("LAT: 1 LAT: 2 LON: 3 ELEV: 4")
        self.assertIn("AMBIGUOUS_ORDER", duplicate.codes)

    def test_T_PAR_002_precision_signs_and_controls(self):
        self.assertIn("EXCESS_PRECISION_LAT", parse_reading("LAT: 1.0000001 LON: 2 ELEV: 3").codes)
        self.assertIn("MALFORMED_LAT", parse_reading("LAT: 1A.2 LON: 2 ELEV: 3").codes)
        self.assertIn("CONTROL_CHARACTER", parse_reading("LAT: 1\x00 LON: 2 ELEV: 3").codes)
        normalized = parse_reading("LAT = 1 LON = — 2 ELEV = -0.00")
        self.assertEqual(str(normalized.longitude), "-2.000000")
        self.assertEqual(str(normalized.elevation_m), "0.00")

    def test_T_PAR_003_raw_immutability(self):
        raw = "LAT = 1 LON = — 2 ELEV = 3"
        identity = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        parse_reading(raw)
        self.assertEqual(hashlib.sha256(raw.encode("utf-8")).hexdigest(), identity)
