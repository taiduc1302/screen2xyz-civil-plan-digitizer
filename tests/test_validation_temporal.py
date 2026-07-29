from __future__ import annotations

import unittest
from decimal import Decimal

from screen2xyz_lab.config import ConfigError, canonical_config
from screen2xyz_lab.models import ParseResult
from screen2xyz_lab.temporal import TemporalClassifier
from screen2xyz_lab.validator import validate_metadata, validate_reading

from helpers import EVIDENCE, csv_rows, load_json


TRIPLET_A = (Decimal("1.000000"), Decimal("2.000000"), Decimal("3.00"))
TRIPLET_B = (Decimal("4.000000"), Decimal("5.000000"), Decimal("6.00"))


class ValidationTemporalTests(unittest.TestCase):
    def test_T_VAL_001_ranges_and_metadata(self):
        config = canonical_config()
        validate_metadata(config)
        valid = ParseResult(Decimal("90"), Decimal("-180"), Decimal("9000"), ())
        self.assertEqual(validate_reading(valid, config), ())
        invalid = ParseResult(Decimal("90.1"), Decimal("180.1"), Decimal("9000.01"), ())
        self.assertEqual(validate_reading(invalid, config), ("OUT_OF_RANGE_ELEV", "OUT_OF_RANGE_LAT", "OUT_OF_RANGE_LON"))
        config["source_crs"] = ""
        with self.assertRaises(ConfigError):
            validate_metadata(config)

    def test_T_VAL_002_complete_retention_logic(self):
        classifications = load_json(EVIDENCE / "classifications.json")
        accepted = csv_rows(EVIDENCE / "accepted_points.csv")
        rejected = csv_rows(EVIDENCE / "rejected_readings.csv")
        ids = [row["scenario_id"] for row in classifications]
        self.assertEqual(ids, [f"S{i:03d}" for i in range(1, 61)])
        self.assertEqual(len(set(ids)), 60)
        self.assertEqual(len(accepted) + len(rejected), 60)
        self.assertEqual({row["scenario_id"] for row in accepted}.intersection(row["scenario_id"] for row in rejected), set())

    def test_T_VAL_003_vocabularies(self):
        scenario_codes = {
            "INPUT_BOUNDARY_FAILURE", "OCR_FAILURE", "OCR_TIMEOUT", "MISSING_LAT", "MISSING_LON", "MISSING_ELEV",
            "MALFORMED_LAT", "MALFORMED_LON", "MALFORMED_ELEV", "EXCESS_PRECISION_LAT", "EXCESS_PRECISION_LON",
            "EXCESS_PRECISION_ELEV", "AMBIGUOUS_ORDER", "EXTRA_NUMERIC_FIELD", "CONTROL_CHARACTER",
            "OUT_OF_RANGE_LAT", "OUT_OF_RANGE_LON", "OUT_OF_RANGE_ELEV", "STALE_READING", "DUPLICATE_READING",
        }
        run_codes = {"RUN_CONFIG_INVALID", "RUN_OUTPUT_WRITE_FAILURE", "RUN_MANIFEST_WRITE_FAILURE", "RUN_TIMEOUT"}
        self.assertTrue(scenario_codes.isdisjoint(run_codes))
        self.assertEqual(len(scenario_codes), 20)
        actual = load_json(EVIDENCE / "classifications.json")
        actual_codes = {row["primary_code"] for row in actual if row["primary_code"]}
        self.assertEqual(actual_codes, {"MALFORMED_LAT", "MISSING_ELEV", "STALE_READING", "DUPLICATE_READING"})

    def test_T_VAL_004_short_circuit_and_precedence(self):
        classifier = TemporalClassifier()
        outcome = classifier.classify("S001", None, ("OCR_FAILURE",))
        self.assertEqual(outcome.all_codes, ("OCR_FAILURE",))
        parsed = ParseResult(None, Decimal("181"), None, ("MISSING_LAT", "MISSING_ELEV"))
        self.assertEqual(validate_reading(parsed, canonical_config()), ("MISSING_ELEV", "MISSING_LAT", "OUT_OF_RANGE_LON"))

    def test_T_DED_001_stale_sequences(self):
        classifier = TemporalClassifier()
        self.assertEqual(classifier.classify("A1", TRIPLET_A, ()).classification, "ACCEPTED")
        stale = classifier.classify("A2", TRIPLET_A, ())
        self.assertEqual((stale.primary_code, stale.reference_scenario_id), ("STALE_READING", "A1"))
        repeated = classifier.classify("A3", TRIPLET_A, ())
        self.assertEqual(repeated.primary_code, "DUPLICATE_READING")

    def test_T_DED_002_duplicate_sequences(self):
        classifier = TemporalClassifier()
        classifier.classify("A", TRIPLET_A, ())
        classifier.classify("B", TRIPLET_B, ())
        duplicate = classifier.classify("A2", TRIPLET_A, ())
        self.assertEqual((duplicate.primary_code, duplicate.reference_scenario_id), ("DUPLICATE_READING", "A"))
        classifier = TemporalClassifier()
        classifier.classify("A", TRIPLET_A, ())
        classifier.classify("X", None, ("MALFORMED_LAT",))
        self.assertEqual(classifier.classify("A2", TRIPLET_A, ()).primary_code, "DUPLICATE_READING")
