from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from screen2xyz_app.capture import AutoCaptureEngine, CapturePipeline, Reading
from screen2xyz_app.controller import CaptureSessionController
from screen2xyz_app.hotkeys import HOTKEYS, GlobalHotkeys
from screen2xyz_app.mapping import ChannelMapping, ChannelSource
from screen2xyz_app.operations import (
    DisplaySignature,
    SessionOptions,
    ZoneHealthMonitor,
    ZoneHealthSnapshot,
    review_rows,
    zone_indicator_states,
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

    def test_hotkey_registration_and_dispatch_are_headless_testable(self):
        class FakeUser32:
            def __init__(self):
                self.registered = []
                self.unregistered = []

            def RegisterHotKey(self, handle, hotkey_id, modifiers, virtual_key):
                self.registered.append((handle, hotkey_id, modifiers, virtual_key))
                return True

            def UnregisterHotKey(self, handle, hotkey_id):
                self.unregistered.append((handle, hotkey_id))

        actions = []
        hotkeys = GlobalHotkeys({name: lambda value=name: actions.append(value)
                                 for _mods, _key, name in HOTKEYS.values()})
        user32 = FakeUser32()
        ids = hotkeys.register_with(user32)
        self.assertEqual(ids, [1, 2, 3])
        self.assertEqual(len(user32.registered), 3)
        self.assertTrue(hotkeys.dispatch(1))
        self.assertTrue(hotkeys.dispatch(2))
        self.assertTrue(hotkeys.dispatch(3))
        self.assertFalse(hotkeys.dispatch(999))
        self.assertEqual(actions, ["start/pause", "stop", "force capture"])

    def test_overlay_indicator_state_is_per_zone(self):
        healthy = ZoneHealthSnapshot(
            True, False, "ok", 0, {"x": "1", "y": "2", "z": "3"}
        )
        self.assertEqual(zone_indicator_states(healthy)["x"], ("1", True))
        unhealthy = ZoneHealthSnapshot(False, True, "paused", 3, {"x": "1"})
        self.assertEqual(zone_indicator_states(unhealthy)["x"], ("1", False))
        self.assertEqual(zone_indicator_states(unhealthy)["y"], ("—", False))

    def test_review_filter_and_sort_logic(self):
        rows = [
            {"id": 1, "point_number": "TP-1", "x": 2.0, "y": 1.0, "z": 5.0,
             "description": "Existing", "created_utc": "b"},
            {"id": 2, "point_number": "TP-2", "x": 1.0, "y": 2.0, "z": 4.0,
             "description": "Design", "created_utc": "a"},
        ]
        filtered = review_rows(rows, filter_text="design", sort_by="x")
        self.assertEqual([row["id"] for row in filtered], [2])
        sorted_rows = review_rows(rows, sort_by="z", reverse=True)
        self.assertEqual([row["id"] for row in sorted_rows], [1, 2])

    def test_repick_reconfigures_same_session_and_preserves_numbering(self):
        first = automatic_mapping()
        second = ChannelMapping({
            "x": ChannelSource("screen_zone_ocr", (100, 0, 20, 20)),
            "y": ChannelSource("screen_zone_ocr", (120, 0, 20, 20)),
            "z": ChannelSource("clipboard"),
        })
        with tempfile.TemporaryDirectory() as temporary:
            controller = CaptureSessionController(
                Path(temporary), first, reader=ContextReader(),
                options=SessionOptions(point_prefix="P-", point_start=7),
            )
            session_id = controller.session_id
            controller.capture_click({"x": 1, "y": 2, "z": 3})
            controller.reconfigure(second)
            controller.capture_click({"x": 4, "y": 5, "z": 6})
            self.assertEqual(controller.session_id, session_id)
            self.assertEqual([row["point_number"] for row in controller.points()], ["P-7", "P-8"])
            self.assertEqual(len(controller.store.session_audit_events(session_id)), 1)
            controller.close()

    def test_stop_blocks_force_and_click_capture(self):
        mapping = ChannelMapping({
            "x": ChannelSource("manual"),
            "y": ChannelSource("manual"),
            "z": ChannelSource("manual"),
        })
        with tempfile.TemporaryDirectory() as temporary:
            controller = CaptureSessionController(Path(temporary), mapping, reader=ContextReader())
            controller.capture_click({"x": 1, "y": 2, "z": 3})
            controller.stop()
            with self.assertRaisesRegex(RuntimeError, "stopped"):
                controller.force_capture()
            with self.assertRaisesRegex(RuntimeError, "stopped"):
                controller.capture_click({"x": 4, "y": 5, "z": 6})
            self.assertEqual(len(controller.points()), 1)
            controller.close()


if __name__ == "__main__":
    unittest.main()
