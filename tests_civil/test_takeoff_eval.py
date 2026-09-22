from __future__ import annotations

import unittest

from screen2xyz_civil.takeoff import LINE, TakeoffGeometry, TakeoffVertex
from screen2xyz_civil.takeoff_eval import (
    REAL_BOARD,
    SYNTHETIC_BOARD,
    CoverageAccounting,
    EvalBox,
    MatchedTakeoff,
    TakeoffEvalError,
    bbox_iou,
    coverage_accounting,
    evaluate_matched_takeoffs,
    geometry_box,
)


class TakeoffEvalTests(unittest.TestCase):
    def test_bbox_iou_exact_match_is_one(self):
        box = EvalBox(0, 0, 10, 10)
        self.assertEqual(bbox_iou(box, box), 1.0)

    def test_bbox_iou_nonoverlap_is_zero(self):
        self.assertEqual(bbox_iou(EvalBox(0, 0, 5, 5), EvalBox(10, 10, 20, 20)), 0.0)

    def test_geometry_box_is_coordinate_frame_diagnostic(self):
        geometry = TakeoffGeometry(
            LINE,
            (TakeoffVertex(5, 10), TakeoffVertex(30, 20), TakeoffVertex(15, 40)),
        )
        self.assertEqual(geometry_box(geometry), EvalBox(5, 10, 30, 40))

    def test_coverage_distinguishes_withheld_from_silent_miss(self):
        coverage = coverage_accounting(
            expected_ids=["A", "B", "C", "D"],
            proposed_ids=["A", "B"],
            withheld_ids=["C"],
        )
        self.assertEqual(coverage.silent_miss_ids, frozenset({"D"}))
        self.assertEqual(coverage.accounted_rate, 0.75)
        self.assertEqual(coverage.silent_miss_rate, 0.25)

    def test_coverage_rejects_proposed_withheld_overlap(self):
        with self.assertRaises(TakeoffEvalError):
            CoverageAccounting(
                expected_ids=frozenset({"A"}),
                proposed_ids=frozenset({"A"}),
                withheld_ids=frozenset({"A"}),
            )

    def test_coverage_rejects_unknown_gold_ids(self):
        with self.assertRaises(TakeoffEvalError):
            coverage_accounting(
                expected_ids=["A"],
                proposed_ids=["A", "X"],
            )

    def test_evaluation_reports_rule_and_quantity_metrics(self):
        matches = [
            MatchedTakeoff(
                expected_id="A",
                expected_rule_id="DITCH_INFILL",
                actual_rule_id="DITCH_INFILL",
                expected_quantity=100.0,
                actual_quantity=102.0,
                unit="m2",
                expected_box=EvalBox(0, 0, 10, 10),
                actual_box=EvalBox(0, 0, 10, 10),
            ),
            MatchedTakeoff(
                expected_id="B",
                expected_rule_id="DRIVEWAY_CULVERT_300",
                actual_rule_id="DITCH_REGRADE",
                expected_quantity=10.0,
                actual_quantity=9.0,
                unit="m",
            ),
        ]
        result = evaluate_matched_takeoffs(
            matches,
            board=REAL_BOARD,
            dataset_id="REAL-PRIVATE-001",
            coverage=coverage_accounting(
                expected_ids=["A", "B"],
                proposed_ids=["A", "B"],
            ),
        )
        self.assertEqual(result.metrics["rule_accuracy"], 0.5)
        self.assertAlmostEqual(result.metrics["mean_absolute_percentage_error"], 0.06)
        self.assertEqual(result.metrics["mean_bbox_iou"], 1.0)

    def test_synthetic_board_cannot_be_claimed_as_real_accuracy(self):
        result = evaluate_matched_takeoffs(
            [],
            board=SYNTHETIC_BOARD,
            dataset_id="SYNTH-001",
            coverage=coverage_accounting(expected_ids=[], proposed_ids=[]),
        )
        self.assertFalse(result.is_real_accuracy_evidence)
        with self.assertRaises(TakeoffEvalError):
            result.assert_accuracy_claim_allowed()

    def test_real_board_allows_accuracy_claim_contract(self):
        result = evaluate_matched_takeoffs(
            [],
            board=REAL_BOARD,
            dataset_id="REAL-001",
            coverage=coverage_accounting(expected_ids=[], proposed_ids=[]),
        )
        result.assert_accuracy_claim_allowed()
        self.assertTrue(result.to_dict()["is_real_accuracy_evidence"])

    def test_zero_expected_quantity_is_excluded_from_percentage_error(self):
        result = evaluate_matched_takeoffs(
            [
                MatchedTakeoff(
                    expected_id="A",
                    expected_rule_id="DITCH_INFILL",
                    actual_rule_id="DITCH_INFILL",
                    expected_quantity=0.0,
                    actual_quantity=0.0,
                    unit="m2",
                )
            ],
            board=SYNTHETIC_BOARD,
            dataset_id="SYNTH-ZERO",
            coverage=coverage_accounting(expected_ids=["A"], proposed_ids=["A"]),
        )
        self.assertIsNone(result.metrics["mean_absolute_percentage_error"])
        self.assertIsNone(result.metrics["quantity_within_2pct_rate"])


if __name__ == "__main__":
    unittest.main()
