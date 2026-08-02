from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from screen2xyz_app.capture import AutoCaptureEngine, CapturePipeline, Reading
from screen2xyz_app.controller import CaptureSessionController
from screen2xyz_app.hotkeys import HOTKEYS
from screen2xyz_app.mapping import ChannelMapping, ChannelSource
from screen2xyz_app.operations import (
    DisplaySignature,
    SessionOptions,
    ZoneHealthMonitor,
)


def automatic_mapping() -> ChannelMapping:
    return ChannelMapping({
        "x": ChannelSource("screen_zone_ocr", (0, 0, 20, 20)),
        "y": ChannelSource("screen_zone_ocr", (20, 0, 20, 20)),
        "z": ChannelSource("clipboard"),
    })


class ContextReader:
    def __call__(self, column, source, context):
        del source
        return Reading(str(context[column]), 0.9)


class FailingReader:
    def __call__(self, column, source, context):
        del column, source, context
        raise ValueError("window moved")


class OperationsTests(unittest.TestCase):
    def test_session_policy_applies_xy_epsilon_and_numbering(self):
        mapping = ChannelMapping({
            "x": ChannelSource("manual"),
            "y": ChannelSource("manual"),
            "z": ChannelSource("manual"),
        })
        with tempfile.TemporaryDirectory() as temporary:
            controller = CaptureSessionController(
                Path(temporary),
                mapping,
                reader=ContextReader(),
                options=SessionOptions(min_xy_delta=1.0, point_prefix="TP-", point_start=20),
            )
            controller.capture_click({"x": 100, "y": 200, "z": 40})
            controller.capture_click({"x": 100.5, "y": 200.5, "z": 41})
            controller.capture_click({"x": 101, "y": 201, "z": 42})
            rows = controller.points()
            self.assertEqual(len(rows), 2)
            self.assertEqual([row["point_number"] for row in rows], ["TP-20", "TP-21"])
            controller.close()

    def test_mapping_test_does_not_retain_a_row(self):
        mapping = ChannelMapping({
            "x": ChannelSource("manual"),
            "y": ChannelSource("manual"),
            "z": ChannelSource("manual"),
        })
        with tempfile.TemporaryDirectory() as temporary:
            controller = CaptureSessionController(Path(temporary), mapping, reader=ContextReader())
            point = controller.test_mapping({"x": 1, "y": 2, "z": 3})
            self.assertEqual((point.x, point.y, point.z), (1, 2, 3))
            self.assertEqual(controller.points(), [])
            controller.close()

    def test_zone_failures_auto_pause_at_configured_limit(self):
        events = []
        monitor = ZoneHealthMonitor(
            2, signature_probe=lambda: DisplaySignature(1920, 1080, 96)
        )
        engine = AutoCaptureEngine(
            CapturePipeline(automatic_mapping(), FailingReader()),
            lambda _point: None,
            zone_failure_limit=2,
            on_health=events.append,
            health_monitor=monitor,
        )
        self.assertIsNone(engine.poll())
        self.assertFalse(engine.paused)
        self.assertIsNone(engine.poll())
        self.assertTrue(engine.paused)
        self.assertTrue(events[-1].paused)
        self.assertIn("re-pick", events[-1].message)

    def test_display_change_auto_pauses_before_reading(self):
        signature = [DisplaySignature(1920, 1080, 96)]
        monitor = ZoneHealthMonitor(3, signature_probe=lambda: signature[0])
        events = []
        engine = AutoCaptureEngine(
            CapturePipeline(automatic_mapping(), FailingReader()),
            lambda _point: None,
            on_health=events.append,
            health_monitor=monitor,
        )
        signature[0] = DisplaySignature(2560, 1440, 120)
        self.assertIsNone(engine.poll())
        self.assertTrue(engine.paused)
        self.assertIn("resolution or DPI", events[-1].message)

    def test_global_hotkey_contract_has_all_operator_actions(self):
        self.assertEqual(
            {value[2] for value in HOTKEYS.values()},
            {"start/pause", "stop", "force capture"},
        )


if __name__ == "__main__":
    unittest.main()
