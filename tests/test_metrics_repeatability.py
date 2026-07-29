from __future__ import annotations

import unittest
from decimal import Decimal

from screen2xyz_lab.metrics import _rate, calculate_metrics

from helpers import EVIDENCE, FIXTURE, csv_rows, load_json


def perfect_inputs():
    ground = csv_rows(FIXTURE / "ground_truth.csv")
    classifications = []
    raw = []
    for row in ground:
        accepted = row["expected_disposition"] == "ACCEPT"
        classifications.append(
            {
                "scenario_id": row["scenario_id"],
                "classification": "ACCEPTED" if accepted else "REJECTED",
                "primary_code": row["expected_primary_code"],
                "parsed_latitude": row["expected_latitude"],
                "parsed_longitude": row["expected_longitude"],
                "parsed_elevation_m": row["expected_elevation_m"],
            }
        )
        raw.append({"ocr_status": "SUCCESS", "duration_ms": "10"})
    repeat = {
        "classification_differences": 0,
        "classification_population": 60,
        "raw_ocr_projection_differences": 0,
        "raw_ocr_population": 60,
        "deterministic_hash_differences": 0,
        "deterministic_artifact_count": 69,
        "target": 0,
        "status": "met",
    }
    return ground, classifications, raw, repeat


class MetricsRepeatabilityTests(unittest.TestCase):
    def test_T_MET_001_sixteen_formulas(self):
        result = calculate_metrics(*perfect_inputs())
        metrics = result["metrics"]
        self.assertEqual(len(metrics), 16)
        report_42 = {"numerator": 42, "denominator": 42, "rate": 1.0, "target_operator": None, "target_value": None, "status": "report_only"}
        for name in ("latitude_field_exact_match", "longitude_field_exact_match", "elevation_field_exact_match", "end_to_end_accepted_reading_correctness"):
            self.assertEqual(metrics[name], report_42)
        self.assertEqual(metrics["complete_three_field_exact_match"]["baseline"], {"numerator": 14, "denominator": 14, "rate": 1.0, "target_operator": "gte", "target_value": 0.95, "status": "met"})
        self.assertEqual(metrics["complete_three_field_exact_match"]["all_valid"], {"numerator": 42, "denominator": 42, "rate": 1.0, "target_operator": "gte", "target_value": 0.9, "status": "met"})
        self.assertEqual(metrics["parser_success_known_clean"], {"numerator": 13, "denominator": 13, "rate": 1.0, "target_operator": "eq", "target_value": 1.0, "status": "met"})
        self.assertEqual(metrics["rejected_reading_rate"], {"numerator": 18, "denominator": 60, "rate": 0.3, "target_operator": None, "target_value": None, "status": "report_only"})
        self.assertEqual(metrics["expected_invalid_rejection"], {"numerator": 18, "denominator": 18, "rate": 1.0, "target_operator": "gte", "target_value": 0.95, "status": "met"})
        self.assertEqual(metrics["false_accept_count"], {"count": 0, "population": 18, "target_operator": "eq", "target_value": 0, "status": "met"})
        self.assertEqual(metrics["false_reject_count"], {"count": 0, "population": 42, "target_operator": None, "target_value": None, "status": "report_only"})
        for name in ("duplicate_detection", "stale_detection"):
            self.assertEqual(metrics[name], {"numerator": 6, "denominator": 6, "rate": 1.0, "target_operator": "eq", "target_value": 1.0, "status": "met"})
        self.assertEqual(metrics["coordinate_error_accepted"], {
            "eligible_count": 42,
            "latitude_degrees": {"count": 42, "mean": 0.0, "max": 0.0},
            "longitude_degrees": {"count": 42, "mean": 0.0, "max": 0.0},
        })
        self.assertEqual(metrics["elevation_error_accepted"], {"eligible_count": 42, "metres": {"count": 42, "mean": 0.0, "max": 0.0}})
        self.assertEqual(metrics["processing_time"], {"unit": "ms", "total_ms": 600, "per_reading": {"count": 60, "mean": 10, "p50_nearest_rank": 10, "p95_nearest_rank": 10, "max": 10}})
        self.assertEqual(metrics["repeatability_difference"], perfect_inputs()[3])
        self.assertEqual(result["diagnostics"], {"ocr_failure_count": 0, "ocr_timeout_count": 0, "failed_scenario_ids": []})

        ground, imperfect_classifications, imperfect_raw, imperfect_repeatability = perfect_inputs()
        by_id = {row["scenario_id"]: row for row in imperfect_classifications}
        by_id["S001"].update({
            "classification": "REJECTED", "primary_code": "OCR_FAILURE",
            "parsed_latitude": "", "parsed_longitude": "", "parsed_elevation_m": "",
        })
        expected = {row["scenario_id"]: row for row in ground}
        for scenario_id in ("S005", "S006", "S007", "S008", "S009"):
            row = by_id[scenario_id]
            truth = expected[scenario_id]
            row["parsed_latitude"] = format(Decimal(truth["expected_latitude"]) + Decimal("0.000001"), ".6f")
            row["parsed_longitude"] = format(Decimal(truth["expected_longitude"]) + Decimal("0.000002"), ".6f")
            row["parsed_elevation_m"] = format(Decimal(truth["expected_elevation_m"]) + Decimal("0.01"), ".2f")
        by_id["S002"]["primary_code"] = "DUPLICATE_READING"
        by_id["S017"].update({"classification": "ACCEPTED", "primary_code": ""})
        by_id["S019"]["primary_code"] = "MALFORMED_LAT"
        for index, row in enumerate(imperfect_raw, start=1):
            row["duration_ms"] = str(index)
        imperfect_raw[0]["ocr_status"] = "FAILURE"
        imperfect_raw[1]["ocr_status"] = "TIMEOUT"
        imperfect_repeatability.update({
            "classification_differences": 1,
            "raw_ocr_projection_differences": 2,
            "deterministic_hash_differences": 3,
            "status": "missed",
        })

        imperfect = calculate_metrics(ground, imperfect_classifications, imperfect_raw, imperfect_repeatability)
        changed = imperfect["metrics"]
        for name in ("latitude_field_exact_match", "longitude_field_exact_match", "elevation_field_exact_match", "end_to_end_accepted_reading_correctness"):
            self.assertEqual((changed[name]["numerator"], changed[name]["denominator"], changed[name]["rate"]), (36, 42, 0.857143))
        self.assertEqual((changed["complete_three_field_exact_match"]["baseline"]["numerator"], changed["complete_three_field_exact_match"]["baseline"]["status"]), (8, "missed"))
        self.assertEqual((changed["complete_three_field_exact_match"]["all_valid"]["numerator"], changed["complete_three_field_exact_match"]["all_valid"]["status"]), (36, "missed"))
        self.assertEqual(changed["expected_invalid_rejection"], {"numerator": 17, "denominator": 18, "rate": 0.944444, "target_operator": "gte", "target_value": 0.95, "status": "missed"})
        self.assertEqual(changed["false_accept_count"], {"count": 1, "population": 18, "target_operator": "eq", "target_value": 0, "status": "missed"})
        self.assertEqual(changed["false_reject_count"]["count"], 1)
        self.assertEqual((changed["duplicate_detection"]["numerator"], changed["duplicate_detection"]["status"]), (5, "missed"))
        self.assertEqual((changed["stale_detection"]["numerator"], changed["stale_detection"]["status"]), (5, "missed"))
        coordinate = changed["coordinate_error_accepted"]
        self.assertEqual(coordinate["eligible_count"], 41)
        self.assertEqual((coordinate["latitude_degrees"]["count"], coordinate["latitude_degrees"]["max"]), (41, 0.000001))
        self.assertEqual((coordinate["longitude_degrees"]["count"], coordinate["longitude_degrees"]["max"]), (41, 0.000002))
        self.assertAlmostEqual(coordinate["latitude_degrees"]["mean"], float(Decimal("0.000005") / Decimal(41)))
        self.assertAlmostEqual(coordinate["longitude_degrees"]["mean"], float(Decimal("0.000010") / Decimal(41)))
        elevation = changed["elevation_error_accepted"]
        self.assertEqual((elevation["eligible_count"], elevation["metres"]["count"], elevation["metres"]["max"]), (41, 41, 0.01))
        self.assertAlmostEqual(elevation["metres"]["mean"], float(Decimal("0.05") / Decimal(41)))
        self.assertEqual(changed["processing_time"], {"unit": "ms", "total_ms": 1830, "per_reading": {"count": 60, "mean": 30.5, "p50_nearest_rank": 30, "p95_nearest_rank": 57, "max": 60}})
        self.assertEqual(changed["repeatability_difference"]["status"], "missed")
        self.assertEqual(imperfect["diagnostics"], {
            "ocr_failure_count": 1,
            "ocr_timeout_count": 1,
            "failed_scenario_ids": ["S001", "S002", "S005", "S006", "S007", "S008", "S009", "S017", "S019"],
        })

    def test_T_MET_002_schema_and_zero_denominator(self):
        empty = _rate(0, 0, "gte", 0.9)
        self.assertEqual(empty["status"], "not_applicable")
        self.assertIsNone(empty["rate"])
        metrics = calculate_metrics(*perfect_inputs())
        self.assertEqual(set(metrics), {"schema_version", "scenario_count", "expected_valid_count", "expected_invalid_count", "metrics", "diagnostics"})
        self.assertEqual((metrics["scenario_count"], metrics["expected_valid_count"], metrics["expected_invalid_count"]), (60, 42, 18))
        rate_keys = {"numerator", "denominator", "rate", "target_operator", "target_value", "status"}
        count_keys = {"count", "population", "target_operator", "target_value", "status"}
        rate_objects = [
            metrics["metrics"][name]
            for name in (
                "latitude_field_exact_match", "longitude_field_exact_match", "elevation_field_exact_match",
                "parser_success_known_clean", "end_to_end_accepted_reading_correctness", "rejected_reading_rate",
                "expected_invalid_rejection", "duplicate_detection", "stale_detection",
            )
        ] + list(metrics["metrics"]["complete_three_field_exact_match"].values())
        self.assertTrue(all(set(value) == rate_keys for value in rate_objects))
        self.assertEqual(set(metrics["metrics"]["false_accept_count"]), count_keys)
        self.assertEqual(set(metrics["metrics"]["false_reject_count"]), count_keys)
        self.assertEqual(set(metrics["metrics"]["coordinate_error_accepted"]), {"eligible_count", "latitude_degrees", "longitude_degrees"})
        self.assertEqual(set(metrics["metrics"]["elevation_error_accepted"]), {"eligible_count", "metres"})
        for stats in (
            metrics["metrics"]["coordinate_error_accepted"]["latitude_degrees"],
            metrics["metrics"]["coordinate_error_accepted"]["longitude_degrees"],
            metrics["metrics"]["elevation_error_accepted"]["metres"],
        ):
            self.assertEqual(set(stats), {"count", "mean", "max"})
        self.assertEqual(set(metrics["metrics"]["processing_time"]), {"unit", "total_ms", "per_reading"})
        self.assertEqual(set(metrics["metrics"]["processing_time"]["per_reading"]), {"count", "mean", "p50_nearest_rank", "p95_nearest_rank", "max"})
        self.assertEqual(set(metrics["metrics"]["repeatability_difference"]), {
            "classification_differences", "classification_population", "raw_ocr_projection_differences",
            "raw_ocr_population", "deterministic_hash_differences", "deterministic_artifact_count",
            "target", "status",
        })

    def test_T_REP_001_two_run_comparison(self):
        comparison = load_json(EVIDENCE / "repeatability_comparison.json")
        metric = comparison["metric"]
        self.assertEqual(comparison["whitelist_count"], 69)
        expected_keys = {
            "fixture_config.json", "ground_truth.csv", "fixture_manifest.json",
            *(f"image:S{index:03d}" for index in range(1, 61)),
            "raw_ocr_projection.json", "classifications.json", "accepted_points.csv",
            "rejected_readings.csv", "points_source_xyz.txt",
            "points_source_xyz_metadata.json:deterministic_projection",
        }
        self.assertEqual(set(comparison["whitelist_keys"]), expected_keys)
        self.assertEqual(metric["classification_differences"], 0)
        self.assertEqual(metric["classification_population"], 60)
        self.assertEqual(metric["raw_ocr_projection_differences"], 0)
        self.assertEqual(metric["raw_ocr_population"], 60)
        self.assertEqual(metric["deterministic_hash_differences"], 0)
        self.assertEqual(metric["deterministic_artifact_count"], 69)
        self.assertEqual(metric["status"], "met")
