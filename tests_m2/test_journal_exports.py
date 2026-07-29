from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from screen2xyz_m2 import contracts as C
from screen2xyz_m2.exports import finalize_exports, xyz_export
from screen2xyz_m2.journal import (DiskLimit, RunJournal, StorageFailure,
                                   read_journal, verify_crops)
from screen2xyz_m2.models import SourceConfig, new_source_id
from screen2xyz_m2.recovery import recover_run


def sources_xyz() -> list[SourceConfig]:
    return [SourceConfig(source_id=new_source_id(), display_name=name,
                         semantic_role=role, rect=(0, 40 * i, 100, 20))
            for i, (name, role) in enumerate(
                (("X", "x"), ("Y", "y"), ("Z", "z")))]


def event(seq_sources, session="s", status="RETAINED_CHANGE",
          values=("1.0", "2.0", "3.0"), value_status="OK"):
    return {
        "session_id": session,
        "event_status": status,
        "worker_status": "OK",
        "frame": {"frame_id": "f1", "capture_utc": "2026-07-18T00:00:00Z",
                  "monotonic_offset_ms": 1000, "cursor": None},
        "scheduler_context": None,
        "observations": [
            {"source_id": src.source_id, "capture_status": "OK",
             "ocr_status": "OK", "parse_status": "OK",
             "stability_status": "IMMEDIATE", "value_status": value_status,
             "raw_text": values[i], "normalized_value": values[i],
             "value_kind": "number", "pixel_sha256": f"h{i}",
             "ocr_executed": True, "confirmation": "new_ocr"}
            for i, src in enumerate(seq_sources)],
        "stable_signature": {src.source_id:
                             {"value_kind": "number",
                              "normalized_value": values[i]}
                             for i, src in enumerate(seq_sources)},
        "changed_source_ids": [src.source_id for src in seq_sources],
        "retention_reason_codes": ["STABLE_CHANGE"],
        "evidence": {},
        "skipped_ticks_since_last": 0,
    }


class JournalTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run_dir = Path(self._tmp.name) / "run"
        self.journal = RunJournal(self.run_dir)
        self.sources = sources_xyz()

    def test_crop_before_journal_and_hashes(self):
        crops = {self.sources[0].source_id: b"PNGDATA"}
        written = self.journal.append_event(event(self.sources), crops,
                                            C.RETENTION_CHANGED_AND_ERRORS)
        ref = written["crops_saved"][self.sources[0].source_id]
        crop_path = self.run_dir / ref["path"]
        self.assertTrue(crop_path.is_file())
        self.assertEqual(len(ref["crop_artifact_sha256"]), 64)
        events, warnings = read_journal(self.run_dir)
        self.assertEqual(len(events), 1)
        self.assertEqual(warnings, [])
        self.assertEqual(verify_crops(self.run_dir, events), [])

    def test_values_only_writes_no_pngs(self):
        crops = {self.sources[0].source_id: b"PNGDATA"}
        written = self.journal.append_event(event(self.sources), crops,
                                            C.RETENTION_VALUES_ONLY)
        self.assertIsNone(
            written["crops_saved"][self.sources[0].source_id])
        self.assertFalse((self.run_dir / "crops").exists())

    def test_diagnostic_same_hash_references_prior_artifact(self):
        sid = self.sources[0].source_id
        self.journal.append_event(event(self.sources), {sid: b"PNG1"},
                                  C.RETENTION_EVERY_TICK)
        second = self.journal.append_event(
            event(self.sources, status="RETAINED_DIAGNOSTIC"),
            {sid: b"PNG1"}, C.RETENTION_EVERY_TICK)
        ref = second["crops_saved"][sid]
        self.assertTrue(ref["reference"])
        self.assertEqual(ref["path"], f"crops/1/{sid}.png")

    def test_partial_final_line_tolerated(self):
        self.journal.append_event(event(self.sources), {},
                                  C.RETENTION_CHANGED_AND_ERRORS)
        with (self.run_dir / "events.jsonl").open("a",
                                                  encoding="utf-8") as fh:
            fh.write('{"event_seq": 2, "truncat')
        events, warnings = read_journal(self.run_dir)
        self.assertEqual(len(events), 1)
        self.assertIn("PARTIAL_FINAL_LINE", warnings)

    def test_malformed_complete_line_fails_closed(self):
        self.journal.append_event(event(self.sources), {},
                                  C.RETENTION_CHANGED_AND_ERRORS)
        with (self.run_dir / "events.jsonl").open("a",
                                                  encoding="utf-8") as fh:
            fh.write("not json at all\n")
            fh.write(json.dumps({"event_seq": 3}) + "\n")
        with self.assertRaises(StorageFailure):
            read_journal(self.run_dir)

    def test_sequence_break_fails_closed(self):
        self.journal.append_event(event(self.sources), {},
                                  C.RETENTION_CHANGED_AND_ERRORS)
        with (self.run_dir / "events.jsonl").open("a",
                                                  encoding="utf-8") as fh:
            fh.write(json.dumps({"event_seq": 7}) + "\n")
        with self.assertRaises(StorageFailure):
            read_journal(self.run_dir)

    def test_missing_and_mismatched_crops_warn_and_null(self):
        sid = self.sources[0].source_id
        self.journal.append_event(event(self.sources), {sid: b"PNG1"},
                                  C.RETENTION_CHANGED_AND_ERRORS)
        other = self.sources[1].source_id
        self.journal.append_event(
            event(self.sources), {other: b"PNG2"},
            C.RETENTION_CHANGED_AND_ERRORS)
        (self.run_dir / f"crops/1/{sid}.png").unlink()
        (self.run_dir / f"crops/2/{other}.png").write_bytes(b"TAMPERED")
        events, _ = read_journal(self.run_dir)
        warnings = verify_crops(self.run_dir, events)
        self.assertTrue(any(w.startswith("MISSING_CROP") for w in warnings))
        self.assertTrue(any(w.startswith("CROP_HASH_MISMATCH")
                            for w in warnings))
        self.assertIsNone(events[0]["crops_saved"][sid])
        self.assertIsNone(events[1]["crops_saved"][other])

    def test_orphan_crop_reported_not_deleted(self):
        self.journal.append_event(event(self.sources), {},
                                  C.RETENTION_CHANGED_AND_ERRORS)
        orphan = self.run_dir / "crops/9/orphan.png"
        orphan.parent.mkdir(parents=True)
        orphan.write_bytes(b"X")
        events, _ = read_journal(self.run_dir)
        warnings = verify_crops(self.run_dir, events)
        self.assertTrue(any(w.startswith("ORPHAN_CROP") for w in warnings))
        self.assertTrue(orphan.exists())

    def test_disk_hard_stop(self):
        self.journal.disk_bytes = C.DISK_STOP_BYTES
        with self.assertRaises(DiskLimit):
            self.journal.append_event(event(self.sources), {},
                                      C.RETENTION_CHANGED_AND_ERRORS)

    def test_checkpoint_follows_journal(self):
        self.journal.append_event(event(self.sources), {},
                                  C.RETENTION_CHANGED_AND_ERRORS)
        self.journal.maybe_checkpoint({"a": 1}, force=True)
        checkpoint = json.loads(
            (self.run_dir / "state_checkpoint.json")
            .read_text(encoding="utf-8"))
        self.assertEqual(checkpoint["last_event_seq"], 1)


class LiveCsvSnapshotTests(unittest.TestCase):
    """§2: the live CSV snapshot is a best-effort, atomically-replaced
    convenience view of the canonical journal - it must never lose or
    corrupt the journal's own record, even when the snapshot write fails."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run_dir = Path(self._tmp.name) / "run"
        self.journal = RunJournal(self.run_dir)
        self.sources = sources_xyz()

    def test_snapshot_reflects_every_journaled_event(self):
        self.journal.append_event(event(self.sources), {},
                                  C.RETENTION_CHANGED_AND_ERRORS)
        self.journal.append_event(
            event(self.sources, values=("4.0", "5.0", "6.0")), {},
            C.RETENTION_CHANGED_AND_ERRORS)
        result = self.journal.write_live_snapshot(self.sources, False)
        self.assertTrue(result["ok"])
        self.assertEqual(result["row_count"], 2)
        self.assertEqual(self.journal.live_snapshot_row_count, 2)
        self.assertIsNone(self.journal.last_live_snapshot_error)
        wide = (self.run_dir / "events_wide.live.csv").read_bytes()
        self.assertEqual(wide.count(b"\r\n"), 3)  # header + 2 rows
        self.assertTrue((self.run_dir / "observations_long.live.csv")
                        .is_file())
        # A real XYZ-eligible session also gets a live XYZ file.
        self.assertTrue((self.run_dir / "points.live.xyz").is_file())

    def test_snapshot_is_atomic_replace_not_partial_write(self):
        self.journal.append_event(event(self.sources), {},
                                  C.RETENTION_CHANGED_AND_ERRORS)
        self.journal.write_live_snapshot(self.sources, False)
        self.assertFalse(
            (self.run_dir / "events_wide.live.csv.tmp").exists())

    def test_snapshot_failure_never_loses_the_journal_event(self):
        self.journal.append_event(event(self.sources), {},
                                  C.RETENTION_CHANGED_AND_ERRORS)
        events_before, _ = read_journal(self.run_dir)
        with mock.patch.object(RunJournal, "_atomic_replace",
                              side_effect=OSError("disk full")):
            result = self.journal.write_live_snapshot(self.sources, False)
        self.assertFalse(result["ok"])
        self.assertIn("disk full", result["error"])
        self.assertIn("disk full", self.journal.last_live_snapshot_error)
        events_after, _ = read_journal(self.run_dir)
        self.assertEqual(events_before, events_after)
        self.assertEqual(self.journal.counters["events"], 1)

    def test_snapshot_row_count_freezes_at_last_success_after_a_failure(self):
        self.journal.append_event(event(self.sources), {},
                                  C.RETENTION_CHANGED_AND_ERRORS)
        self.journal.write_live_snapshot(self.sources, False)
        self.assertEqual(self.journal.live_snapshot_row_count, 1)
        self.journal.append_event(
            event(self.sources, values=("4.0", "5.0", "6.0")), {},
            C.RETENTION_CHANGED_AND_ERRORS)
        with mock.patch.object(RunJournal, "_atomic_replace",
                              side_effect=OSError("transient")):
            self.journal.write_live_snapshot(self.sources, False)
        # The failed attempt must not claim a row count it never wrote.
        self.assertEqual(self.journal.live_snapshot_row_count, 1)


class ExportTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.run_dir = Path(self._tmp.name) / "run"
        self.sources = sources_xyz()

    def _finalize(self, events, sources=None, cursor=False):
        self.run_dir.mkdir(parents=True, exist_ok=True)
        session = {"session_id": "s", "retention_mode": "changed_and_errors",
                   "interval_ms": 1000, "cursor_metadata": cursor,
                   "locked_backend": {"name": "printwindow_clientonly"},
                   "scope": {"type": "window"},
                   "environment_snapshot": {
                       "window": {"title": "SECRET", "client_w": 900,
                                  "client_h": 300, "dpi": 96},
                       "monitors": [], "virtual_screen": {}},
                   "sources": [s.to_json() for s in (sources
                                                     or self.sources)]}
        for i, e in enumerate(events):
            e["event_seq"] = i + 1
            e["event_id"] = f"s-e{i + 1}"
            e.setdefault("crops_saved", {})
            e.setdefault("retention_mode", "changed_and_errors")
        return finalize_exports(self.run_dir, session, events,
                                sources or self.sources, {"events":
                                                          len(events)})

    def test_deterministic_and_formula_safe(self):
        text_source = SourceConfig(source_id=new_source_id(),
                                   display_name="Note", data_type="text",
                                   rect=(0, 0, 100, 20))
        srcs = self.sources + [text_source]
        ev = event(srcs, values=("1.0", "2.0", "3.0", "=cmd()"))
        ev["observations"][3]["value_kind"] = "text"
        self._finalize([ev], sources=srcs)
        wide1 = (self.run_dir / "events_wide.csv").read_bytes()
        self.assertIn(b"'=cmd()", wide1)
        long_data = (self.run_dir / "observations_long.csv").read_bytes()
        self.assertIn(b"'=cmd()", long_data)
        ev2 = event(srcs, values=("1.0", "2.0", "3.0", "=cmd()"))
        ev2["observations"][3]["value_kind"] = "text"
        self._finalize([ev2], sources=srcs)
        self.assertEqual(wide1,
                         (self.run_dir / "events_wide.csv").read_bytes())

    def test_warning_codes_survive_into_the_long_csv_export(self):
        # Adversarial review finding (2026-07-21): a DEGREE_GLYPH_RECOVERED
        # -labelled coordinate value (or any other warned value) used to be
        # indistinguishable from a cleanly-read one in every export - the
        # warning was present on the journal's own Observation but no
        # exporter surfaced it. long CSV (the audit-trail export) is the
        # one place it must now appear.
        ev = event(self.sources)
        ev["observations"][0]["warning_codes"] = ["DEGREE_GLYPH_RECOVERED"]
        self._finalize([ev])
        header, *rows = (self.run_dir / "observations_long.csv") \
            .read_text(encoding="utf-8").splitlines()
        self.assertIn("warning_codes", header)
        col = header.split(",").index("warning_codes")
        self.assertIn("DEGREE_GLYPH_RECOVERED", rows[0].split(",")[col])
        # An unwarned observation's column stays empty, not "None"/"[]".
        self.assertEqual(rows[1].split(",")[col], "")

    def test_summary_sanitized(self):
        self._finalize([event(self.sources)])
        summary = json.loads((self.run_dir / "run_summary.json")
                             .read_text(encoding="utf-8"))
        text = json.dumps(summary)
        self.assertNotIn("SECRET", text)
        self.assertNotIn("hwnd", text.lower())
        self.assertEqual(summary["session_label"], "Selected target")

    def test_xyz_gate_positive_and_filter(self):
        good = event(self.sources)
        bad = event(self.sources, values=("9.0", "8.0", "7.0"))
        bad["observations"][2]["value_status"] = "OCR_FAILURE"
        bad["observations"][2]["normalized_value"] = None
        diag = event(self.sources, status="RETAINED_DIAGNOSTIC")
        payload, meta = xyz_export([good, bad, diag], self.sources)
        self.assertEqual(meta["row_count"], 1)
        self.assertEqual(meta["excluded_event_count"], 1)
        self.assertEqual(payload.decode(), "1.0 2.0 3.0\n")
        self.assertEqual(meta["coordinate_reference"], "UNSPECIFIED_LOCAL")

    def test_xyz_gate_negative_missing_role(self):
        two = self.sources[:2]
        payload, meta = xyz_export([event(two)], two)
        self.assertIsNone(payload)
        self.assertFalse(meta["eligible"])

    def test_finalize_records_verified_row_count_on_success(self):
        summary = self._finalize([event(self.sources),
                                  event(self.sources,
                                       values=("4.0", "5.0", "6.0"))])
        self.assertEqual(summary["final_csv_row_count"], 2)
        self.assertTrue(summary["final_csv_row_count_verified"])
        self.assertNotIn("FINAL_CSV_ROW_COUNT_MISMATCH", summary["warnings"])

    def test_finalize_detects_and_warns_on_row_count_mismatch(self):
        # Corrupt what wide_csv would have written (simulating a hypothetical
        # future bug) and prove finalize_exports catches it rather than
        # silently reporting success (§5/§12 "no false PASS").
        with mock.patch("screen2xyz_m2.exports.wide_csv",
                        return_value=b"only,a,header\r\n"):
            summary = self._finalize([event(self.sources)])
        self.assertEqual(summary["final_csv_row_count"], 0)
        self.assertFalse(summary["final_csv_row_count_verified"])
        self.assertTrue(any(w.startswith("FINAL_CSV_ROW_COUNT_MISMATCH")
                            for w in summary["warnings"]))

    def test_finalize_writes_via_atomic_replace(self):
        self._finalize([event(self.sources)])
        self.assertFalse((self.run_dir / "events_wide.csv.tmp").exists())
        self.assertTrue((self.run_dir / "events_wide.csv").is_file())

    def test_cursor_columns_toggle(self):
        ev = event(self.sources)
        ev["frame"]["cursor"] = {"screen_x": 10, "screen_y": 20}
        self._finalize([ev], cursor=True)
        header = (self.run_dir / "events_wide.csv").read_bytes() \
            .split(b"\r\n")[0]
        self.assertIn(b"cursor_screen_x", header)
        self._finalize([event(self.sources)], cursor=False)
        header2 = (self.run_dir / "events_wide.csv").read_bytes() \
            .split(b"\r\n")[0]
        self.assertNotIn(b"cursor_screen_x", header2)


class RecoveryTests(unittest.TestCase):
    def test_recover_rebuilds_from_partial_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            journal = RunJournal(run_dir)
            srcs = sources_xyz()
            session = {"session_id": "s", "sources":
                       [s.to_json() for s in srcs],
                       "retention_mode": "changed_and_errors",
                       "cursor_metadata": False,
                       "environment_snapshot": {}}
            journal.write_session(session)
            journal.append_event(event(srcs), {srcs[0].source_id: b"P"},
                                 C.RETENTION_CHANGED_AND_ERRORS)
            journal.append_event(event(srcs, values=("4.0", "5.0", "6.0")),
                                 {}, C.RETENTION_CHANGED_AND_ERRORS)
            with (run_dir / "events.jsonl").open("a",
                                                 encoding="utf-8") as fh:
                fh.write('{"event_seq": 3, "cut')
            (run_dir / f"crops/1/{srcs[0].source_id}.png").unlink()
            result = recover_run(run_dir)
            self.assertEqual(result["events"], 2)
            self.assertIn("PARTIAL_FINAL_LINE", result["warnings"])
            self.assertTrue(any(w.startswith("MISSING_CROP")
                                for w in result["warnings"]))
            summary = json.loads((run_dir / "run_summary.json")
                                 .read_text(encoding="utf-8"))
            self.assertTrue(summary["recovered"])
            self.assertTrue((run_dir / "points.xyz").is_file())
            self.assertTrue(
                (run_dir / "evidence_manifest_sha256.txt").is_file())
