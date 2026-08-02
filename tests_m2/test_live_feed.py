"""Deterministic tests for the live-feed row classification (ui/layout.py)
and the wide_csv_row/wide_csv_header <-> wide_csv equivalence
(exports.py) - no Tk, no worker."""

from __future__ import annotations

import unittest

from screen2xyz_m2.exports import wide_csv, wide_csv_header, wide_csv_row
from screen2xyz_m2.models import SourceConfig, new_source_id
from screen2xyz_m2.ui.layout import (feed_row_color, persistence_state,
                                     PERSISTENCE_FINAL_CSV,
                                     PERSISTENCE_JOURNAL,
                                     PERSISTENCE_LIVE_CSV,
                                     PERSISTENCE_OBSERVED_LIVE, value_changed)


class ValueChangedTests(unittest.TestCase):
    def test_seeding_is_not_a_change(self):
        # Nothing to compare against yet - the first observation is never
        # "changed", matching the stability engine's own seeding rule.
        self.assertFalse(value_changed(None, "1.0"))

    def test_same_value_is_not_changed(self):
        self.assertFalse(value_changed("1.0", "1.0"))

    def test_different_value_is_changed(self):
        self.assertTrue(value_changed("1.0", "2.0"))

    def test_none_to_none_is_not_changed(self):
        self.assertFalse(value_changed(None, None))


class FeedRowColorTests(unittest.TestCase):
    def test_retained_error_is_red_regardless_of_other_flags(self):
        color = feed_row_color(value_status="CAPTURE_FAILURE",
                               ocr_status="NOT_RUN_CAPTURE_FAILED",
                               capture_status="BACKEND_FAILURE",
                               stability_status="NOT_EVALUATED",
                               journal_persisted=True, is_retained_error=True)
        self.assertEqual(color, "red")

    def test_persisted_and_live_csv_ok_is_green(self):
        color = feed_row_color(value_status="OK", ocr_status="OK",
                               capture_status="OK",
                               stability_status="CONFIRMED",
                               journal_persisted=True,
                               is_retained_error=False, live_csv_ok=True)
        self.assertEqual(color, "green")

    def test_persisted_but_live_csv_failed_is_orange(self):
        # §2/§3: journal persistence and the live CSV snapshot are separate
        # truths - a snapshot write failure must be visibly distinct from a
        # fully successful row, never silently shown as green.
        color = feed_row_color(value_status="OK", ocr_status="OK",
                               capture_status="OK",
                               stability_status="CONFIRMED",
                               journal_persisted=True,
                               is_retained_error=False, live_csv_ok=False)
        self.assertEqual(color, "orange")

    def test_persisted_with_unknown_live_csv_status_is_green(self):
        # live_csv_ok defaults to None (e.g. a caller that doesn't track it
        # separately) - must not be misread as a failure.
        color = feed_row_color(value_status="OK", ocr_status="OK",
                               capture_status="OK",
                               stability_status="CONFIRMED",
                               journal_persisted=True, is_retained_error=False)
        self.assertEqual(color, "green")

    def test_warning_status_not_persisted_is_yellow(self):
        color = feed_row_color(value_status="AMBIGUOUS_MULTIPLE_NUMBERS",
                               ocr_status="OK", capture_status="OK",
                               stability_status="NOT_EVALUATED",
                               journal_persisted=False,
                               is_retained_error=False)
        self.assertEqual(color, "yellow")

    def test_empty_ocr_not_persisted_is_yellow(self):
        color = feed_row_color(value_status="MISSING_SOURCE_VALUE",
                               ocr_status="EMPTY_TEXT",
                               capture_status="OK",
                               stability_status="NOT_EVALUATED",
                               journal_persisted=False,
                               is_retained_error=False)
        self.assertEqual(color, "yellow")

    def test_pending_confirmation_is_blue(self):
        color = feed_row_color(value_status="OK", ocr_status="OK",
                               capture_status="OK",
                               stability_status="PENDING_CONFIRMATION",
                               journal_persisted=False,
                               is_retained_error=False)
        self.assertEqual(color, "blue")

    def test_plain_observation_is_gray(self):
        color = feed_row_color(value_status="OK", ocr_status="OK",
                               capture_status="OK",
                               stability_status="CONFIRMED",
                               journal_persisted=False,
                               is_retained_error=False)
        self.assertEqual(color, "gray")

    def test_persisted_wins_over_warning(self):
        # A value that was retained AND happens to carry a warning-ish
        # status (e.g. a RETAINED_CHANGE tick where a co-field warns) still
        # shows green - journal persistence is the definitive signal.
        color = feed_row_color(value_status="OUT_OF_RANGE",
                               ocr_status="OK", capture_status="OK",
                               stability_status="CONFIRMED",
                               journal_persisted=True, is_retained_error=False,
                               live_csv_ok=True)
        self.assertEqual(color, "green")


class PersistenceStateTests(unittest.TestCase):
    def test_nothing_retained_is_observed_live(self):
        self.assertEqual(
            persistence_state(retained=False, journal_ok=False,
                              live_csv_ok=None),
            PERSISTENCE_OBSERVED_LIVE)

    def test_retained_but_journal_write_pending_is_observed_live(self):
        self.assertEqual(
            persistence_state(retained=True, journal_ok=False,
                              live_csv_ok=None),
            PERSISTENCE_OBSERVED_LIVE)

    def test_journal_ok_but_live_csv_not_yet_is_persisted_to_journal(self):
        self.assertEqual(
            persistence_state(retained=True, journal_ok=True,
                              live_csv_ok=False),
            PERSISTENCE_JOURNAL)

    def test_journal_and_live_csv_ok_is_live_csv_snapshot_updated(self):
        self.assertEqual(
            persistence_state(retained=True, journal_ok=True,
                              live_csv_ok=True),
            PERSISTENCE_LIVE_CSV)

    def test_finalized_wins_over_everything(self):
        self.assertEqual(
            persistence_state(retained=True, journal_ok=True,
                              live_csv_ok=True, finalized=True),
            PERSISTENCE_FINAL_CSV)


def _event(sources, values, event_seq=1):
    observations = [{"source_id": s.source_id, "normalized_value": v,
                     "value_status": "OK", "value_kind": "number"}
                    for s, v in zip(sources, values)]
    return {"event_seq": event_seq, "event_id": f"run-e{event_seq}",
           "event_status": "RETAINED_CHANGE",
           "frame": {"capture_utc": "2026-07-19T00:00:00Z",
                    "monotonic_offset_ms": 100},
           "scheduler_context": None, "observations": observations}


class WideCsvRowEquivalenceTests(unittest.TestCase):
    def setUp(self):
        self.sources = [SourceConfig(source_id=new_source_id(),
                                     display_name=n, rect=(0, 0, 10, 10))
                        for n in ("Lon", "Lat")]

    def test_row_by_row_matches_full_csv(self):
        events = [self._e(1, ["1.5", "2.5"]), self._e(2, ["1.6", "2.6"])]
        full = wide_csv(events, self.sources, False)
        header = wide_csv_header(self.sources, False)
        rows = [wide_csv_row(e, self.sources, False) for e in events]
        from screen2xyz_m2.io_utils import csv_bytes
        rebuilt = csv_bytes(rows, header)
        self.assertEqual(full, rebuilt)

    def test_header_matches_full_csv_header_line(self):
        header = wide_csv_header(self.sources, cursor_metadata=True)
        full = wide_csv([], self.sources, True)
        first_line = full.split(b"\r\n")[0].decode("utf-8")
        self.assertEqual(first_line, ",".join(header))

    def test_single_row_reflects_real_values(self):
        event = self._e(5, ["49.123456", "-123.654321"])
        row = wide_csv_row(event, self.sources, False)
        self.assertEqual(row["event_seq"], 5)
        self.assertEqual(row[f"{self.sources[0].display_name} [value]"],
                         "49.123456")
        self.assertEqual(row[f"{self.sources[1].display_name} [value]"],
                         "-123.654321")

    def _e(self, seq, values):
        return _event(self.sources, values, event_seq=seq)
