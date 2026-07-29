"""Deterministic tests for the §5 real-target validator's pure verdict/
report logic (no Tk, no worker) - proving PASS cannot be reached without
every named technical check and every named owner confirmation, and that
BLOCKED/FAIL are otherwise the only alternatives."""

from __future__ import annotations

import unittest

from screen2xyz_m2.validate_real_target import (build_report,
                                                 compute_verdict,
                                                 observation_is_meaningful,
                                                 REQUIRED_OWNER_CONFIRMATIONS,
                                                 REQUIRED_TECHNICAL_CHECKS)


class ObservationMeaningfulTests(unittest.TestCase):
    """§12: garbage OCR must never satisfy ocr_meaningful. Meaningful means
    OCR actually succeeded AND the parsed value is acceptable."""

    def test_valid_number_is_meaningful(self):
        self.assertTrue(observation_is_meaningful(
            data_type="number", ocr_status="OK", value_status="OK",
            normalized_value="49.123456", raw_text="49.123456"))

    def test_nonempty_ocr_that_did_not_parse_is_not_meaningful(self):
        # A blank/wrong region OCR'd to noise ('::', '|') parses to NO_NUMBER
        # / MALFORMED (value_status != OK) - non-empty text is NOT enough.
        self.assertFalse(observation_is_meaningful(
            data_type="number", ocr_status="OK", value_status="NO_NUMBER",
            normalized_value=None, raw_text="::"))
        self.assertFalse(observation_is_meaningful(
            data_type="number", ocr_status="OK",
            value_status="MALFORMED_NUMBER", normalized_value=None,
            raw_text="1.2.3"))

    def test_failed_ocr_is_not_meaningful_even_with_a_value(self):
        self.assertFalse(observation_is_meaningful(
            data_type="number", ocr_status="ENGINE_FAILURE",
            value_status="OK", normalized_value="5", raw_text=""))

    def test_empty_text_source_is_not_meaningful(self):
        self.assertFalse(observation_is_meaningful(
            data_type="text", ocr_status="OK", value_status="OK",
            normalized_value="", raw_text=""))

    def test_nonempty_text_source_is_meaningful(self):
        self.assertTrue(observation_is_meaningful(
            data_type="text", ocr_status="OK", value_status="OK",
            normalized_value="READY", raw_text="READY"))

    def test_capture_failure_is_not_meaningful(self):
        self.assertFalse(observation_is_meaningful(
            data_type="number", ocr_status="NOT_RUN_CAPTURE_FAILED",
            value_status="CAPTURE_FAILURE", normalized_value=None,
            raw_text=""))


def _all_true(keys) -> dict[str, bool]:
    return {key: True for key in keys}


class ComputeVerdictTests(unittest.TestCase):
    def test_all_true_is_pass(self):
        verdict = compute_verdict(
            _all_true(REQUIRED_TECHNICAL_CHECKS),
            _all_true(REQUIRED_OWNER_CONFIRMATIONS))
        self.assertEqual(verdict, "PASS")

    def test_blocked_reason_wins_even_if_everything_else_true(self):
        verdict = compute_verdict(
            _all_true(REQUIRED_TECHNICAL_CHECKS),
            _all_true(REQUIRED_OWNER_CONFIRMATIONS),
            blocked_reason="protected content")
        self.assertEqual(verdict, "BLOCKED")

    def test_any_single_technical_check_false_is_fail(self):
        for key in REQUIRED_TECHNICAL_CHECKS:
            technical = _all_true(REQUIRED_TECHNICAL_CHECKS)
            technical[key] = False
            verdict = compute_verdict(
                technical, _all_true(REQUIRED_OWNER_CONFIRMATIONS))
            self.assertEqual(verdict, "FAIL", f"expected FAIL when {key} "
                                              f"is False")

    def test_any_single_owner_confirmation_false_is_fail(self):
        for key in REQUIRED_OWNER_CONFIRMATIONS:
            confirmations = _all_true(REQUIRED_OWNER_CONFIRMATIONS)
            confirmations[key] = False
            verdict = compute_verdict(
                _all_true(REQUIRED_TECHNICAL_CHECKS), confirmations)
            self.assertEqual(verdict, "FAIL", f"expected FAIL when {key} "
                                              f"is False")

    def test_zero_events_and_zero_changes_never_pass(self):
        # The exact false-PASS scenario the old validator was vulnerable to:
        # zero events, zero OCR, zero changes - must be FAIL, never PASS or
        # a fabricated "COMPLETED".
        technical = {
            "captures_occurred": False, "ocr_meaningful": False,
            "every_enabled_source_meaningful": False,
            "change_detected": False, "journal_event_persisted": False,
            "live_csv_snapshot_updated": False, "final_csv_generated": False,
            "final_csv_row_count_matches_journal": True,
            "crop_artifacts_match_policy": True, "no_orphan_worker": True,
        }
        verdict = compute_verdict(
            technical, _all_true(REQUIRED_OWNER_CONFIRMATIONS))
        self.assertEqual(verdict, "FAIL")

    def test_missing_technical_key_raises(self):
        incomplete = _all_true(REQUIRED_TECHNICAL_CHECKS)
        del incomplete[REQUIRED_TECHNICAL_CHECKS[0]]
        with self.assertRaises(ValueError):
            compute_verdict(incomplete, _all_true(REQUIRED_OWNER_CONFIRMATIONS))

    def test_missing_owner_confirmation_key_raises(self):
        incomplete = _all_true(REQUIRED_OWNER_CONFIRMATIONS)
        del incomplete[REQUIRED_OWNER_CONFIRMATIONS[0]]
        with self.assertRaises(ValueError):
            compute_verdict(_all_true(REQUIRED_TECHNICAL_CHECKS), incomplete)

    def test_final_csv_row_mismatch_alone_fails_even_with_events(self):
        technical = _all_true(REQUIRED_TECHNICAL_CHECKS)
        technical["final_csv_row_count_matches_journal"] = False
        verdict = compute_verdict(
            technical, _all_true(REQUIRED_OWNER_CONFIRMATIONS))
        self.assertEqual(verdict, "FAIL")

    def test_orphan_worker_alone_fails(self):
        technical = _all_true(REQUIRED_TECHNICAL_CHECKS)
        technical["no_orphan_worker"] = False
        verdict = compute_verdict(
            technical, _all_true(REQUIRED_OWNER_CONFIRMATIONS))
        self.assertEqual(verdict, "FAIL")


class BuildReportTests(unittest.TestCase):
    def test_report_never_includes_title_or_screenshot_fields(self):
        report = build_report(
            attempted_backends=["printwindow_clientonly"],
            selected_backend="printwindow_clientonly", target_w=900,
            target_h=320, target_dpi=96, source_count=3,
            per_source_status={"src-1": "region_confirmed"},
            capture_counts={"total": 10}, ocr_counts={"nonempty": 9},
            journal_event_count=4, live_csv_row_count=4,
            final_csv_row_count=4,
            owner_confirmations=_all_true(REQUIRED_OWNER_CONFIRMATIONS),
            controls_exercised=["pause", "resume", "stop"],
            pause_resume_stop_results={"pause_used": True},
            orphan_process_check="none_found", limitations=[],
            final_result="PASS")
        self.assertNotIn("title", report)
        self.assertNotIn("screenshot", str(report).lower())
        self.assertFalse(report["target_identity_included"])
        self.assertEqual(report["final_result"], "PASS")
        self.assertEqual(report["gate"], "G-E-REAL")

    def test_blocked_report_has_no_evidence_fields_populated(self):
        report = build_report(
            attempted_backends=[], selected_backend=None, target_w=None,
            target_h=None, target_dpi=None, source_count=0,
            per_source_status={}, capture_counts={}, ocr_counts={},
            journal_event_count=0, live_csv_row_count=0,
            final_csv_row_count=0, owner_confirmations={},
            controls_exercised=[], pause_resume_stop_results={},
            orphan_process_check="not_applicable",
            limitations=["owner did not confirm content"],
            final_result="BLOCKED")
        self.assertEqual(report["final_result"], "BLOCKED")
        self.assertEqual(report["source_count"], 0)
