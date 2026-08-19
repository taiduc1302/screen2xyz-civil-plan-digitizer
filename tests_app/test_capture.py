from __future__ import annotations

import unittest

from screen2xyz_app.capture import AutoCaptureEngine, CapturePipeline, Reading
from screen2xyz_app.mapping import ChannelMapping, ChannelSource
from screen2xyz_app.plan import plan_click_xy
from screen2xyz_civil.models import PixelPoint
from screen2xyz_civil.transform import build_calibration


class SequenceReader:
    def __init__(self, rows):
        self.rows = rows
        self.index = 0

    def __call__(self, column, source, context):
        del source, context
        return Reading(str(self.rows[self.index][column]), 0.9)


class CaptureTests(unittest.TestCase):
    def mapping(self):
        return ChannelMapping({
            "x": ChannelSource("screen_zone_ocr", (0, 0, 20, 20)),
            "y": ChannelSource("screen_zone_ocr", (20, 0, 20, 20)),
            "z": ChannelSource("clipboard"),
        })

    def test_stable_combined_change_emits_once(self):
        reader = SequenceReader([
            {"x": 1, "y": 2, "z": 3},
            {"x": 1, "y": 2, "z": 3},
            {"x": 4, "y": 5, "z": 6},
            {"x": 4, "y": 5, "z": 6},
        ])
        captured = []
        engine = AutoCaptureEngine(CapturePipeline(self.mapping(), reader), captured.append)
        for index in range(4):
            reader.index = index
            engine.poll()
        self.assertEqual(len(captured), 1)
        self.assertEqual((captured[0].x, captured[0].y, captured[0].z), (4, 5, 6))

    def test_click_pipeline_supports_mixed_sources(self):
        mapping = ChannelMapping({
            "x": ChannelSource("screen_zone_ocr", (0, 0, 20, 20)),
            "y": ChannelSource("screen_zone_ocr", (20, 0, 20, 20)),
            "z": ChannelSource("plan_label_ocr"),
        })
        values = {"x": "100.5", "y": "200.5", "z": "49.78"}
        point, _, _ = CapturePipeline(
            mapping, lambda column, source, context: Reading(values[column], 0.8)
        ).read()
        self.assertEqual((point.x, point.y, point.z), (100.5, 200.5, 49.78))

    def test_plan_click_reuses_civil_transform(self):
        calibration = build_calibration(
            revision=1,
            created_at="2026-01-01T00:00:00Z",
            scale_point_1=PixelPoint(0, 0),
            scale_point_2=PixelPoint(10, 0),
            known_distance_m=100,
            origin_pixel=PixelPoint(0, 0),
            east_reference=PixelPoint(10, 0),
        )
        self.assertEqual(plan_click_xy(PixelPoint(2, -3), calibration), (20, 30))

    def test_automatic_ocr_without_confidence_cannot_be_retained(self):
        captured = []

        def reader(column, source, context):
            del column, source, context
            return Reading("1.0", None, ocr_executed=True)

        engine = AutoCaptureEngine(
            CapturePipeline(self.mapping(), reader), captured.append,
            confirmations=1,
        )
        with self.assertRaisesRegex(ValueError, "confidence"):
            engine.force_capture()
        self.assertEqual(captured, [])

    def test_explicit_single_confirmation_is_honored_by_stability(self):
        reader = SequenceReader([
            {"x": 1, "y": 2, "z": 3},
            {"x": 4, "y": 5, "z": 6},
        ])
        captured = []
        engine = AutoCaptureEngine(
            CapturePipeline(self.mapping(), reader), captured.append,
            confirmations=1,
        )
        engine.poll()  # establish the initial stable values
        reader.index = 1
        engine.poll()
        self.assertEqual([(point.x, point.y, point.z) for point in captured], [
            (4, 5, 6),
        ])


if __name__ == "__main__":
    unittest.main()
