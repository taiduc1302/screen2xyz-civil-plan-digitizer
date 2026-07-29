from __future__ import annotations

import unittest

from screen2xyz_m2.evaluation import (build_script, build_sources,
                                      run_evaluation)


class EvaluationTests(unittest.TestCase):
    def test_deterministic(self):
        first = run_evaluation()
        second = run_evaluation()
        self.assertEqual(first["outcomes"], second["outcomes"])

    def test_all_expectations_met(self):
        metrics = run_evaluation()
        self.assertTrue(metrics["all_expectations_met"])
        self.assertGreaterEqual(metrics["change_events"], 1)
        self.assertGreaterEqual(metrics["error_events"], 1)

    def test_unicode_minus_negative_preserved(self):
        metrics = run_evaluation()
        for outcome in metrics["outcomes"]:
            if outcome["frame"] == "unicode_minus":
                self.assertTrue(outcome["sign_normalized"])

    def test_ambiguous_not_resolved(self):
        metrics = run_evaluation()
        target = next(o for o in metrics["outcomes"]
                      if o["frame"] == "ambiguous_lat")
        self.assertEqual(target["value_status"]["src-lat"],
                         "AMBIGUOUS_MULTIPLE_NUMBERS")

    def test_script_covers_required_cases(self):
        labels = {frame.label for frame in build_script()}
        for required in ("constant", "unicode_minus", "ambiguous_lat",
                         "empty_lat", "recover_lat", "out_of_range"):
            self.assertIn(required, labels)
        self.assertEqual(len(build_sources()), 3)
