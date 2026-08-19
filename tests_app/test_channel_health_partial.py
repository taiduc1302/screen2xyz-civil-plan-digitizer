from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from openpyxl import load_workbook

from screen2xyz_app.capture import AutoCaptureEngine, CapturePipeline, Reading
from screen2xyz_app.controller import CaptureSessionController
from screen2xyz_app.mapping import ChannelMapping, ChannelSource
from screen2xyz_app.operations import SessionOptions, ZoneHealthMonitor


def mapping() -> ChannelMapping:
    return ChannelMapping({
        "x": ChannelSource("screen_zone_ocr", (0, 0, 20, 20)),
        "y": ChannelSource("screen_zone_ocr", (20, 0, 20, 20)),
        "z": ChannelSource("screen_cursor_ocr"),
    })


class ZFailingReader:
    def __call__(self, column, source, context):
        del source, context
        if column == "z":
            raise ValueError("OCR found no numeric candidate near the cursor")
        return Reading("100.25" if column == "x" else "200.50", 0.95)


class AlternatingReader:
    def __init__(self, rows):
        self.rows = rows
        self.index = 0

    def __call__(self, column, source, context):
        del source, context
        row = self.rows[self.index]
        if column == "z" and row["z"] is None:
            raise ValueError("Z unavailable")
        return Reading(str(row[column]), 0.95)


class BlockingReader:
    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()

    def __call__(self, column, source, context):
        del source, context
        if column == "z":
            self.entered.set()
            self.release.wait(timeout=5)
        return Reading({"x": "100.25", "y": "200.50", "z": "49.50"}[column], 0.95)


class ChannelHealthAndPartialTests(unittest.TestCase):
    def test_health_counts_each_channel_and_never_reports_normal_while_z_fails(self):
        events = []
        monitor = ZoneHealthMonitor(10, signature_probe=lambda: (1920, 1080, 96))
        engine = AutoCaptureEngine(
            CapturePipeline(mapping(), ZFailingReader()),
            lambda _point: None,
            zone_failure_limit=10,
            on_health=events.append,
            health_monitor=monitor,
        )
        self.assertIsNone(engine.poll())
        self.assertIsNone(engine.poll())
        snapshot = events[-1]
        self.assertEqual(snapshot.channels["x"].success_count, 2)
        self.assertEqual(snapshot.channels["x"].failure_count, 0)
        self.assertEqual(snapshot.channels["x"].last_success, "100.25")
        self.assertEqual(snapshot.channels["z"].success_count, 0)
        self.assertEqual(snapshot.channels["z"].failure_count, 2)
        self.assertIn("OCR found no numeric candidate", snapshot.channels["z"].last_failure)
        self.assertIn("Z ok 0 / fail 2", snapshot.message)
        self.assertNotIn("reading normally", snapshot.message)

    def test_channel_that_never_succeeds_pauses_at_default_ten_attempts(self):
        events = []
        engine = AutoCaptureEngine(
            CapturePipeline(mapping(), ZFailingReader()),
            lambda _point: None,
            on_health=events.append,
        )
        for _ in range(10):
            engine.poll()
        self.assertTrue(engine.paused)
        self.assertTrue(events[-1].paused)
        self.assertIn("Z has never produced a successful read after 10 attempts", events[-1].message)
        self.assertIn("OCR found no numeric candidate", events[-1].message)

    def test_headless_engine_enforces_channel_pause_without_ui_callback(self):
        engine = AutoCaptureEngine(
            CapturePipeline(mapping(), ZFailingReader()),
            lambda _point: None,
            zone_failure_limit=2,
        )
        self.assertIsNone(engine.poll())
        self.assertIsNone(engine.poll())
        self.assertTrue(engine.paused)
        self.assertEqual(engine.health._channels["z"].failure_count, 2)

    def test_limit_triggering_partial_tick_is_not_retained(self):
        retained = []
        engine = AutoCaptureEngine(
            CapturePipeline(mapping(), ZFailingReader(), allow_partial_z=True),
            retained.append,
            confirmations=1,
            zone_failure_limit=2,
        )
        self.assertIsNotNone(engine.poll())
        self.assertIsNone(engine.poll())
        self.assertTrue(engine.paused)
        self.assertEqual(len(retained), 1)

    def test_partial_z_requires_opt_in_and_exports_empty_z_with_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            strict = CaptureSessionController(root / "strict", mapping(), reader=ZFailingReader())
            try:
                with self.assertRaisesRegex(ValueError, "z"):
                    strict.capture_click()
                self.assertEqual(strict.points(), [])
            finally:
                strict.close()

            partial = CaptureSessionController(
                root / "partial",
                mapping(),
                reader=ZFailingReader(),
                options=SessionOptions(allow_partial_z=True),
            )
            try:
                point = partial.capture_click()
                self.assertIsNone(point.z)
                row = partial.points()[0]
                self.assertIsNone(row["z"])
                self.assertEqual(row["capture_status"], "PARTIAL_MISSING_Z")
                output = partial.export_xlsx(root / "partial.xlsx")
                sheet = load_workbook(output, data_only=True)["Points"]
                headers = [cell.value for cell in sheet[1]]
                values = [cell.value for cell in sheet[2]]
                self.assertIsNone(values[headers.index("Z")])
                self.assertEqual(values[headers.index("Status")], "PARTIAL_MISSING_Z")
                partial.edit_point(row["id"], {"z": 49.78})
                reviewed = partial.points()[0]
                self.assertEqual(reviewed["z"], 49.78)
                self.assertEqual(reviewed["capture_status"], "COMPLETE")
            finally:
                partial.close()

    def test_partial_auto_capture_still_requires_stability_and_change(self):
        retained = []
        engine = AutoCaptureEngine(
            CapturePipeline(mapping(), ZFailingReader(), allow_partial_z=True),
            retained.append,
            confirmations=2,
            on_health=lambda _snapshot: None,
        )
        self.assertIsNone(engine.poll())
        self.assertIsNotNone(engine.poll())
        self.assertIsNone(engine.poll())
        self.assertEqual(len(retained), 1)
        self.assertEqual(retained[0].capture_status, "PARTIAL_MISSING_Z")

    def test_complete_point_resets_partial_deduplication_state(self):
        reader = AlternatingReader([
            {"x": 100.25, "y": 200.50, "z": None},
            {"x": 100.25, "y": 200.50, "z": 49.50},
            {"x": 101.25, "y": 201.50, "z": 49.50},
            {"x": 100.25, "y": 200.50, "z": None},
        ])
        retained = []
        engine = AutoCaptureEngine(
            CapturePipeline(mapping(), reader, allow_partial_z=True),
            retained.append,
            confirmations=1,
        )
        self.assertIsNotNone(engine.poll())
        reader.index = 1
        engine.poll()
        reader.index = 2
        self.assertIsNotNone(engine.poll())
        reader.index = 3
        self.assertIsNotNone(engine.poll())
        self.assertEqual(
            [point.capture_status for point in retained],
            ["PARTIAL_MISSING_Z", "COMPLETE", "PARTIAL_MISSING_Z"],
        )

    def test_pause_discards_an_inflight_ocr_result(self):
        reader = BlockingReader()
        retained = []
        engine = AutoCaptureEngine(
            CapturePipeline(mapping(), reader), retained.append, confirmations=1,
        )
        poller = threading.Thread(target=engine.poll)
        poller.start()
        self.assertTrue(reader.entered.wait(timeout=2))
        engine.pause()
        reader.release.set()
        poller.join(timeout=2)
        self.assertFalse(poller.is_alive())
        self.assertEqual(retained, [])


if __name__ == "__main__":
    unittest.main()
