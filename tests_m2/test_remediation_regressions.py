"""Regression tests for defects found in the M2-011 adversarial review.

Each test name references the review finding it locks down.
"""

from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from screen2xyz_m2 import contracts as C
from screen2xyz_m2.controller import LiveSessionController
from screen2xyz_m2.exports import long_csv, wide_csv, xyz_export
from screen2xyz_m2.journal import RunJournal, StorageFailure
from screen2xyz_m2.models import Observation, SourceConfig, new_source_id
from screen2xyz_m2.parsing import bound_raw, parse_auto, parse_for_source
from screen2xyz_m2.stability import StabilityEngine


def source(sid=None, **kw):
    return SourceConfig(source_id=sid or new_source_id(),
                        display_name=kw.pop("name", "S"),
                        rect=(0, 0, 100, 20), **kw)


def ok(sid, value, pixel="h", kind="number"):
    return Observation(source_id=sid, capture_status="OK", ocr_status="OK",
                       parse_status="OK", stability_status="NOT_EVALUATED",
                       value_status="OK", normalized_value=value,
                       value_kind=kind, pixel_sha256=pixel, ocr_executed=True)


def err(sid, vs):
    return Observation(source_id=sid, capture_status="OK", ocr_status="OK",
                       parse_status=vs if vs in C.PARSE_STATUSES else "OK",
                       stability_status="NOT_EVALUATED", value_status=vs)


def engine(sources, mode=C.RETENTION_CHANGED_AND_ERRORS, confirmations=1):
    return StabilityEngine(sources, confirmations=confirmations,
                           debounce_ms=0, min_change_threshold=None,
                           retention_mode=mode)


class StabilityRegressions(unittest.TestCase):
    def test_D1_changed_only_recovery_to_different_value_retained(self):
        a = source(name="A")
        eng = engine([a], mode=C.RETENTION_CHANGED_ONLY)
        eng.process_tick({a.source_id: ok(a.source_id, "10")}, "f1", 0, {})
        eng.process_tick({a.source_id: err(a.source_id, "NO_NUMBER")},
                         "f2", 1000, {})
        decision = eng.process_tick({a.source_id: ok(a.source_id, "20")},
                                    "f3", 2000, {})
        self.assertEqual(decision.event_status, "RETAINED_CHANGE")
        self.assertIn(a.source_id, decision.changed_source_ids)

    def test_D1_changed_only_recovery_to_same_value_not_retained(self):
        a = source(name="A")
        eng = engine([a], mode=C.RETENTION_CHANGED_ONLY)
        eng.process_tick({a.source_id: ok(a.source_id, "10")}, "f1", 0, {})
        eng.process_tick({a.source_id: err(a.source_id, "NO_NUMBER")},
                         "f2", 1000, {})
        decision = eng.process_tick({a.source_id: ok(a.source_id, "10")},
                                    "f3", 2000, {})
        self.assertIsNone(decision.event_status)

    def test_D2_evidence_bytes_released_on_same_value(self):
        a = source(name="A")
        eng = engine([a], confirmations=2)
        eng.process_tick({a.source_id: ok(a.source_id, "1", pixel="p1")},
                         "f1", 0, {a.source_id: b"PNGA"})
        # candidate owns bytes; a matching stable value must release them
        eng.process_tick({a.source_id: ok(a.source_id, "1", pixel="p1")},
                         "f2", 1000, {})  # confirms + seeds
        eng.process_tick({a.source_id: ok(a.source_id, "1", pixel="p1")},
                         "f3", 2000, {a.source_id: b"PNGB"})  # same_as_stable
        self.assertEqual(eng._evidence_bytes, 0)

    def test_D3_error_morph_to_different_type_retained(self):
        a = source(name="A")
        eng = engine([a])
        eng.process_tick({a.source_id: ok(a.source_id, "1")}, "f1", 0, {})
        first = eng.process_tick({a.source_id: err(a.source_id, "NO_NUMBER")},
                                 "f2", 1000, {})
        self.assertEqual(first.event_status, "RETAINED_ERROR")
        morph = eng.process_tick(
            {a.source_id: err(a.source_id, "MALFORMED_NUMBER")},
            "f3", 2000, {})
        self.assertEqual(morph.event_status, "RETAINED_ERROR")
        same = eng.process_tick(
            {a.source_id: err(a.source_id, "MALFORMED_NUMBER")},
            "f4", 3000, {})
        self.assertIsNone(same.event_status)

    def test_D4_replaced_candidate_marked_unstable(self):
        a = source(name="A")
        eng = engine([a], confirmations=2)
        eng.process_tick({a.source_id: ok(a.source_id, "1", pixel="p1")},
                         "f1", 0, {})   # pending
        obs = ok(a.source_id, "9", pixel="p2")
        eng.process_tick({a.source_id: obs}, "f2", 1000, {})  # replaces
        self.assertEqual(obs.stability_status, "REJECTED")
        self.assertEqual(obs.value_status, "UNSTABLE_READING")


class ParsingRegressions(unittest.TestCase):
    def test_D6_bound_raw_keeps_char_ending_on_boundary(self):
        # 'é' is 2 bytes; 2048 of them = 4096 bytes exactly ending on a
        # code-point boundary — nothing should be truncated.
        raw = bound_raw("é" * 2048)
        self.assertFalse(raw.raw_truncated)
        self.assertEqual(len(raw.raw_text), 2048)

    def test_D6_bound_raw_truncates_straddling_char(self):
        raw = bound_raw("a" * 4095 + "é")   # 4097 bytes, é straddles 4096
        self.assertTrue(raw.raw_truncated)
        self.assertEqual(raw.raw_text, "a" * 4095)

    def test_D7_auto_surfaces_out_of_range(self):
        outcome = parse_auto("181.0", numeric_range=(-180.0, 180.0))
        self.assertEqual(outcome.parse_status, "OUT_OF_RANGE")

    def test_D7_auto_surfaces_precision_error(self):
        outcome = parse_auto("1.1234567", precision_max=6)
        self.assertEqual(outcome.parse_status, "MALFORMED_NUMBER")


class ExportRegressions(unittest.TestCase):
    def _event(self, sources, values, kinds=None, stability="IMMEDIATE",
               statuses=None):
        kinds = kinds or ["number"] * len(sources)
        statuses = statuses or ["OK"] * len(sources)
        return {
            "event_seq": 1, "event_id": "s-e1",
            "event_status": "RETAINED_CHANGE",
            "worker_status": "OK",
            "frame": {"capture_utc": "t", "monotonic_offset_ms": 0,
                      "cursor": None},
            "observations": [
                {"source_id": s.source_id, "value_status": st,
                 "value_kind": k, "normalized_value": v,
                 "stability_status": stability, "capture_status": "OK",
                 "ocr_status": "OK", "parse_status": "OK",
                 "raw_text": v, "ocr_executed": True,
                 "confirmation": "new_ocr"}
                for s, v, k, st in zip(sources, values, kinds, statuses)],
            "crops_saved": {}, "stable_signature": {},
        }

    def test_P1_display_name_formula_escaped_in_headers(self):
        evil = source(name="=cmd()", semantic_role="none")
        header = wide_csv([self._event([evil], ["1"])], [evil], False) \
            .split(b"\r\n")[0]
        self.assertIn(b"'=cmd()", header)

    def test_P1_text_value_formula_escaped_in_long_csv(self):
        note = source(name="Note", data_type="text")
        data = long_csv([self._event([note], ["=danger()"],
                                     kinds=["text"])], [note])
        self.assertIn(b"'=danger()", data)
        self.assertNotIn(b",=danger()", data)

    def test_P1_long_csv_display_name_escaped(self):
        evil = source(name="=evil")
        data = long_csv([self._event([evil], ["1"])], [evil])
        self.assertIn(b"'=evil", data)

    def test_D5_xyz_excludes_pending_axis_value(self):
        srcs = [source(name=n, semantic_role=r)
                for n, r in (("X", "x"), ("Y", "y"), ("Z", "z"))]
        pending = self._event(srcs, ["1", "2", "3"],
                              stability="PENDING_CONFIRMATION")
        payload, meta = xyz_export([pending], srcs)
        self.assertEqual(meta["row_count"], 0)
        self.assertEqual(meta["excluded_event_count"], 1)


class JournalSecurityRegressions(unittest.TestCase):
    def test_P3_crop_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = RunJournal(Path(tmp) / "run")
            with self.assertRaises(StorageFailure):
                journal._write_crop(1, "../../evil", b"PNG")


class SkipCounterConcurrencyRegression(unittest.TestCase):
    """W1: the dedicated per-tick thread means note_skipped_tick (loop thread)
    now races the peek/consume of the skip counter (tick thread). The lock
    must conserve every skip across concurrent drains so no event under-
    reports skips. (§24: consume subtracts the exact peeked count rather than
    resetting to 0, so a concurrent increment between peek and consume is
    never lost either.)"""

    def test_skip_increments_not_lost_across_concurrent_resets(self):
        # A minimal holder exposing exactly the state the real controller
        # counter methods touch, so we exercise the actual implementations
        # under contention without spawning a worker or run directory.
        holder = type("_H", (), {})()
        holder._skip_lock = threading.Lock()
        holder.skipped_since_last_event = 0
        holder.diagnostics = {"skipped_ticks": 0}
        holder.journal = None
        note = LiveSessionController.note_skipped_tick.__get__(holder)
        peek = LiveSessionController._peek_skipped_since_last.__get__(holder)
        consume = LiveSessionController._consume_skipped_since_last.__get__(
            holder)

        def drain() -> int:
            # A durable event consumes exactly what it embedded (the peeked
            # value), never resetting - this is the real §24 sequence.
            count = peek()
            consume(count)
            return count

        total = 200_000
        taken = [0]
        stop = threading.Event()

        def reader() -> None:
            while not stop.is_set():
                taken[0] += drain()

        thread = threading.Thread(target=reader)
        thread.start()
        for _ in range(total):
            note()
        stop.set()
        thread.join()
        taken[0] += drain()  # drain whatever remained after the last consume
        self.assertEqual(taken[0], total)  # no skip lost to a racing drain
        self.assertEqual(holder.diagnostics["skipped_ticks"], total)
        self.assertEqual(holder.skipped_since_last_event, 0)
