from __future__ import annotations

import csv
import json
import unittest

from screen2xyz_m1.session import APPROVED, PENDING, REJECTED, ReviewSession, SessionError

from .helpers_m1 import BASELINE_IMAGE, ROOT, failed_ocr, fake_ocr, fresh_run_root

VALID = "LAT: 49.100000 LON: -123.200000 ELEV: 12.50 m"
MALFORMED = "LAT: 4A.100000 LON: -123.200000 ELEV: 12.50 m"


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.run_root = fresh_run_root()
        self.texts: list[str] = []
        self.session = ReviewSession(
            ROOT,
            self.run_root,
            "run-a",
            ocr=lambda image: fake_ocr(self.texts.pop(0)),
        )

    def _process(self, text: str):
        self.texts.append(text)
        return self.session.process_image(BASELINE_IMAGE)

    def test_run_id_collision_refused(self):
        with self.assertRaises(SessionError):
            ReviewSession(ROOT, self.run_root, "run-a")

    def test_unsafe_run_id_refused(self):
        with self.assertRaises(SessionError):
            ReviewSession(ROOT, self.run_root, "bad/../id")

    def test_raw_ocr_immutable_and_preserved(self):
        candidate = self._process(VALID)
        raw_path = self.run_root / "run-a" / "raw" / f"{candidate.candidate_id}.json"
        recorded = json.loads(raw_path.read_text(encoding="utf-8"))
        self.assertEqual(recorded["raw_text"], VALID)
        # Correction must not touch the raw record or original parsed values.
        self.session.correct(candidate.candidate_id, "50.000000", "-120.000000", "1.00")
        updated = self.session.candidates()[0]
        self.assertEqual(updated.raw_text, VALID)
        self.assertEqual(updated.parsed_latitude, "49.100000")
        self.assertEqual(updated.corrected_latitude, "50.000000")
        self.assertEqual(json.loads(raw_path.read_text(encoding="utf-8")), recorded)

    def test_invalid_correction_rejected_with_codes(self):
        candidate = self._process(VALID)
        with self.assertRaises(SessionError):
            self.session.correct(candidate.candidate_id, "abc", "-120.0", "1.0")
        updated = self.session.candidates()[0]
        self.assertIn("MALFORMED_LAT", updated.correction_codes)
        self.assertEqual(updated.corrected_latitude, "")

    def test_out_of_range_correction_rejected(self):
        candidate = self._process(VALID)
        with self.assertRaises(SessionError):
            self.session.correct(candidate.candidate_id, "95.000000", "-120.000000", "1.00")

    def test_invalid_candidate_not_approvable_until_corrected(self):
        candidate = self._process(MALFORMED)
        self.assertEqual(candidate.classification, "REJECTED")
        with self.assertRaises(SessionError):
            self.session.approve(candidate.candidate_id)
        self.session.correct(candidate.candidate_id, "4.100000", "-123.200000", "12.50")
        approved = self.session.approve(candidate.candidate_id)
        self.assertEqual(approved.decision, APPROVED)
        self.assertTrue(approved.has_correction)

    def test_ocr_failure_yields_unapprovable_candidate(self):
        self.texts.append("ignored")
        candidate = ReviewSession(
            ROOT, self.run_root, "run-fail", ocr=lambda image: failed_ocr()
        ).process_image(BASELINE_IMAGE)
        self.assertEqual(candidate.classification, "REJECTED")
        self.assertIn("OCR_FAILURE", candidate.validation_codes)
        self.assertFalse(candidate.approvable())

    def test_export_contains_only_explicit_approvals(self):
        first = self._process(VALID)
        second = self._process("LAT: 1.000000 LON: 2.000000 ELEV: 3.00 m")
        third = self._process("LAT: 5.000000 LON: 6.000000 ELEV: 7.00 m")
        self.session.approve(third.candidate_id)  # approve out of order
        self.session.approve(first.candidate_id)
        self.session.reject(second.candidate_id)
        summary = self.session.export_approved()
        self.assertEqual(summary["approved_count"], 2)
        self.assertEqual(summary["rejected_count"], 1)
        with (self.run_root / "run-a" / "approved_points.csv").open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        # Deterministic sequence ordering regardless of approval order.
        self.assertEqual([row["candidate_id"] for row in rows], ["C001", "C003"])
        self.assertTrue(all(row["decision"] == APPROVED for row in rows))
        xyz = (self.run_root / "run-a" / "approved_points.xyz").read_text(encoding="utf-8")
        self.assertEqual(xyz.splitlines()[0], "-123.200000 49.100000 12.50")
        self.assertEqual(len(xyz.splitlines()), 2)

    def test_export_with_no_approvals_is_empty(self):
        self._process(VALID)
        summary = self.session.export_approved()
        self.assertEqual(summary["approved_count"], 0)
        self.assertEqual(
            (self.run_root / "run-a" / "approved_points.xyz").read_bytes(), b""
        )
        with (self.run_root / "run-a" / "approved_points.csv").open(newline="", encoding="utf-8") as handle:
            self.assertEqual(list(csv.DictReader(handle)), [])

    def test_no_automatic_approval_exists(self):
        candidate = self._process(VALID)
        self.assertEqual(candidate.decision, PENDING)
        self.assertEqual(self.session.candidates()[0].decision, PENDING)

    def test_rejected_candidate_never_exported(self):
        candidate = self._process(VALID)
        self.session.reject(candidate.candidate_id)
        self.session.export_approved()
        self.assertFalse(self.session.candidates()[0].exported)
        self.assertEqual(self.session.candidates()[0].decision, REJECTED)

    def test_formula_injection_neutralized_in_state(self):
        candidate = self._process("=cmd|' /C calc'!A0 LAT: 1.000000 LON: 2.000000 ELEV: 3.00 m")
        self.session.write_state()
        state = json.loads((self.run_root / "run-a" / "candidates.json").read_text(encoding="utf-8"))
        self.assertTrue(state[0]["raw_text_display"].startswith("'="))
        self.assertEqual(state[0]["raw_text"], candidate.raw_text)

    def test_manifest_covers_run_artifacts(self):
        candidate = self._process(VALID)
        self.session.approve(candidate.candidate_id)
        self.session.export_approved()
        manifest = (self.run_root / "run-a" / "evidence_manifest_sha256.txt").read_text(encoding="utf-8")
        for name in ("approved_points.csv", "approved_points.xyz", "candidates.json", "run_summary.json"):
            self.assertIn(name, manifest)

    def test_decisions_are_final(self):
        first = self._process(VALID)
        second = self._process("LAT: 1.000000 LON: 2.000000 ELEV: 3.00 m")
        self.session.reject(first.candidate_id)
        with self.assertRaises(SessionError):
            self.session.approve(first.candidate_id)  # cannot flip REJECTED
        self.session.approve(second.candidate_id)
        with self.assertRaises(SessionError):
            self.session.reject(second.candidate_id)  # cannot flip APPROVED
        self.assertEqual(self.session.candidates()[0].decision, REJECTED)
        self.assertEqual(self.session.candidates()[1].decision, APPROVED)

    def test_re_export_reflects_later_approvals(self):
        first = self._process(VALID)
        second = self._process("LAT: 1.000000 LON: 2.000000 ELEV: 3.00 m")
        self.session.approve(first.candidate_id)
        self.session.export_approved()
        self.session.approve(second.candidate_id)
        summary = self.session.export_approved()  # must not crash on overwrite
        self.assertEqual(summary["approved_count"], 2)
        xyz = (self.run_root / "run-a" / "approved_points.xyz").read_text(encoding="utf-8")
        self.assertEqual(len(xyz.splitlines()), 2)

    def test_summary_reports_external_ai_not_used(self):
        self._process(VALID)
        summary = self.session.write_state()
        self.assertFalse(summary["external_ai_used"])
