"""Regression tests for the autonomous-QA data-integrity fixes (journal
event_seq rollback, stability transactional restore, verify-from-disk,
skip-counter preservation, O(n) read_journal, broadened live-snapshot
exception boundary, and O(1) incremental live-CSV append). No worker, no
display - pure controller/journal/exports logic."""

from __future__ import annotations

import csv as _csv
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from screen2xyz_m2 import contracts as C
from screen2xyz_m2.exports import (long_csv, wide_csv, xyz_export)
from screen2xyz_m2.journal import (RunJournal, StorageFailure, read_journal)
from screen2xyz_m2.models import SourceConfig, new_source_id


def _sources():
    return [SourceConfig(source_id=new_source_id(), display_name=n,
                         semantic_role=r, rect=(0, 40 * i, 100, 20))
            for i, (n, r) in enumerate([("X", "x"), ("Y", "y"), ("Z", "z")])]


def _event(sources, seq, val, status="RETAINED_CHANGE"):
    obs = [{"source_id": s.source_id, "capture_status": "OK",
            "ocr_status": "OK", "parse_status": "OK",
            "stability_status": "IMMEDIATE", "value_status": "OK",
            "raw_text": f"{val + i}.5", "normalized_value": f"{val + i}.5",
            "value_kind": "number", "pixel_sha256": f"h{seq}{i}",
            "ocr_executed": True, "confirmation": "new_ocr"}
           for i, s in enumerate(sources)]
    return {"session_id": "s", "event_status": status, "worker_status": "OK",
            "event_seq": seq, "event_id": f"s-e{seq}",
            "frame": {"frame_id": f"f{seq}",
                      "capture_utc": "2026-07-19T00:00:00Z",
                      "monotonic_offset_ms": seq * 250, "cursor": None},
            "scheduler_context": None, "observations": obs, "crops_saved": {},
            "retention_mode": "changed_and_errors", "stable_signature": {},
            "changed_source_ids": [s.source_id for s in sources],
            "retention_reason_codes": ["STABLE_CHANGE"], "evidence": {},
            "skipped_ticks_since_last": 0}


class EventSeqRollbackTests(unittest.TestCase):
    """BLOCKER §1: a transient crop/journal failure must NOT advance the
    event_seq counter, so the retried event reuses the number and the
    journal stays contiguous and readable."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run_dir = Path(self._tmp.name) / "run"
        self.journal = RunJournal(self.run_dir)
        self.sources = _sources()

    def test_crop_failure_does_not_advance_seq_and_journal_stays_contiguous(
            self):
        for i, v in enumerate([1, 2, 3], 1):
            self.journal.append_event(_event(self.sources, i, v), {},
                                      C.RETENTION_CHANGED_AND_ERRORS)
        self.assertEqual(self.journal.event_seq, 3)
        # Event 4 with a crop that fails to write.
        with mock.patch.object(
                RunJournal, "_write_crop",
                side_effect=StorageFailure("CROP_WRITE_FAILURE", "boom")):
            with self.assertRaises(StorageFailure):
                self.journal.append_event(
                    _event(self.sources, 4, 4),
                    {self.sources[0].source_id: b"PNG"},
                    C.RETENTION_CHANGED_AND_ERRORS)
        # Counter unchanged - NOT advanced to 4.
        self.assertEqual(self.journal.event_seq, 3)
        # Resume: retried event reuses seq 4.
        self.journal.append_event(_event(self.sources, 4, 4), {},
                                  C.RETENTION_CHANGED_AND_ERRORS)
        self.assertEqual(self.journal.event_seq, 4)
        events, warnings = read_journal(self.run_dir)
        self.assertEqual([e["event_seq"] for e in events], [1, 2, 3, 4])
        self.assertEqual(warnings, [])

    def test_journal_append_failure_does_not_advance_seq(self):
        self.journal.append_event(_event(self.sources, 1, 1), {},
                                  C.RETENTION_CHANGED_AND_ERRORS)
        real_open = Path.open

        def flaky_open(self_path, *a, **k):
            if self_path.name == "events.jsonl" and "a" in (a[0] if a else ""):
                raise OSError("append blocked")
            return real_open(self_path, *a, **k)

        with mock.patch.object(Path, "open", flaky_open):
            with self.assertRaises(StorageFailure):
                self.journal.append_event(_event(self.sources, 2, 2), {},
                                          C.RETENTION_CHANGED_AND_ERRORS)
        self.assertEqual(self.journal.event_seq, 1)  # not advanced to 2
        self.journal.append_event(_event(self.sources, 2, 2), {},
                                  C.RETENTION_CHANGED_AND_ERRORS)
        events, _ = read_journal(self.run_dir)
        self.assertEqual([e["event_seq"] for e in events], [1, 2])


class VerifyFromDiskTests(unittest.TestCase):
    """§23: finalize's row-count verification must read the on-disk file,
    not the in-memory buffer, so a truncated/corrupt CSV is caught."""

    def test_truncated_on_disk_csv_is_detected_as_mismatch(self):
        from screen2xyz_m2.exports import finalize_exports
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            sources = _sources()
            events = [_event(sources, i, i) for i in range(1, 4)]
            session = {"session_id": "s", "cursor_metadata": False,
                       "retention_mode": "changed_and_errors",
                       "locked_backend": {"name": "printwindow_clientonly"},
                       "scope": {"type": "window"},
                       "environment_snapshot": {"window": {}, "monitors": [],
                                                "virtual_screen": {}},
                       "sources": [s.to_json() for s in sources]}
            # Corrupt the file on disk immediately after finalize writes it,
            # by making the read-back see a truncated file.
            orig_read = Path.read_bytes

            def truncated(self_path):
                data = orig_read(self_path)
                if self_path.name == "events_wide.csv":
                    lines = data.split(b"\r\n")
                    return b"\r\n".join(lines[:2])  # header + 1 row only
                return data

            with mock.patch.object(Path, "read_bytes", truncated):
                summary = finalize_exports(run_dir, session, events, sources,
                                          {"events": len(events)})
            self.assertEqual(summary["final_csv_row_count"], 1)
            self.assertFalse(summary["final_csv_row_count_verified"])
            self.assertTrue(any(w.startswith("FINAL_CSV_ROW_COUNT_MISMATCH")
                                for w in summary["warnings"]))


class LiveSnapshotExceptionBoundaryTests(unittest.TestCase):
    """§26: write_live_snapshot / append_live_row must never raise for an
    EXPECTED export failure (not just OSError) - a malformed event must be
    reported as {ok: False}, never crash the tick."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.journal = RunJournal(Path(self._tmp.name) / "run")
        self.sources = _sources()

    def test_full_snapshot_catches_non_oserror(self):
        self.journal.live_events = [_event(self.sources, 1, 1)]
        with mock.patch("screen2xyz_m2.exports.wide_csv",
                        side_effect=TypeError("bad shape")):
            res = self.journal.write_live_snapshot(self.sources, False)
        self.assertFalse(res["ok"])
        self.assertIn("TypeError", res["error"])

    def test_append_catches_non_oserror(self):
        with mock.patch("screen2xyz_m2.exports.wide_csv_row",
                        side_effect=ValueError("bad row")):
            res = self.journal.append_live_row(
                _event(self.sources, 1, 1), self.sources, False)
        self.assertFalse(res["ok"])
        self.assertIn("ValueError", res["error"])

    def test_append_oserror_still_caught(self):
        with mock.patch.object(RunJournal, "_append_bytes",
                              side_effect=OSError("disk full")):
            res = self.journal.append_live_row(
                _event(self.sources, 1, 1), self.sources, False)
        self.assertFalse(res["ok"])
        self.assertIn("disk full", res["error"])

    def test_unexpected_exception_still_propagates(self):
        # An AttributeError (a genuine programmer defect) must NOT be
        # swallowed - the boundary is deliberately not bare Exception.
        with mock.patch("screen2xyz_m2.exports.wide_csv",
                        side_effect=AttributeError("real bug")):
            self.journal.live_events = [_event(self.sources, 1, 1)]
            with self.assertRaises(AttributeError):
                self.journal.write_live_snapshot(self.sources, False)


class IncrementalAppendEquivalenceTests(unittest.TestCase):
    """§10: incremental per-event append must be byte-identical to a full
    regeneration of every live export - the O(n^2) full-regen replaced by
    O(1) appends with no change in output."""

    def test_append_byte_identical_to_full_regen(self):
        with tempfile.TemporaryDirectory() as tmp:
            j = RunJournal(Path(tmp) / "run")
            sources = _sources()
            events = [_event(sources, i, i) for i in range(1, 26)]
            # a non-eligible event (RETAINED_ERROR) must be skipped in xyz
            events.append(_event(sources, 26, 99, status="RETAINED_ERROR"))
            for e in events:
                j.append_live_row(e, sources, False)
            run = Path(tmp) / "run"
            self.assertEqual(
                (run / "events_wide.live.csv").read_bytes(),
                wide_csv(events, sources, False))
            self.assertEqual(
                (run / "observations_long.live.csv").read_bytes(),
                long_csv(events, sources))
            full_xyz, _ = xyz_export(events, sources)
            self.assertEqual((run / "points.live.xyz").read_bytes(),
                             full_xyz)
            self.assertEqual(j.live_snapshot_row_count, 26)

    def test_row_count_tracks_appends(self):
        with tempfile.TemporaryDirectory() as tmp:
            j = RunJournal(Path(tmp) / "run")
            sources = _sources()
            for i in range(1, 6):
                res = j.append_live_row(_event(sources, i, i), sources, False)
                self.assertTrue(res["ok"])
                self.assertEqual(res["row_count"], i)


class ReadJournalLinearTests(unittest.TestCase):
    """§25: read_journal must not rebuild the non-empty-line list per
    iteration. Behaviour (partial-final-line detection) must be preserved."""

    def test_partial_final_line_still_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            j = RunJournal(Path(tmp) / "run")
            sources = _sources()
            j.append_event(_event(sources, 1, 1), {},
                          C.RETENTION_CHANGED_AND_ERRORS)
            with (Path(tmp) / "run" / "events.jsonl").open(
                    "a", encoding="utf-8") as fh:
                fh.write('{"event_seq": 2, "trunc')
            events, warnings = read_journal(Path(tmp) / "run")
            self.assertEqual(len(events), 1)
            self.assertIn("PARTIAL_FINAL_LINE", warnings)

    def test_many_lines_read_correctly(self):
        with tempfile.TemporaryDirectory() as tmp:
            j = RunJournal(Path(tmp) / "run")
            sources = _sources()
            for i in range(1, 501):
                j.append_event(_event(sources, i, i), {},
                              C.RETENTION_CHANGED_AND_ERRORS)
            events, warnings = read_journal(Path(tmp) / "run")
            self.assertEqual(len(events), 500)
            self.assertEqual(warnings, [])
            self.assertEqual([e["event_seq"] for e in events],
                             list(range(1, 501)))


if __name__ == "__main__":
    unittest.main()
