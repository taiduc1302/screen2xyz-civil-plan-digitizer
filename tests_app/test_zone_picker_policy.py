from __future__ import annotations

import unittest

from PIL import Image, ImageDraw

from screen2xyz_app.backends import ScreenOcrBackend
from screen2xyz_app.capture import Reading
from screen2xyz_app.operations import (
    VirtualDesktopBounds,
    format_virtual_geometry,
    preview_without_overlay,
    screen_zone_from_drag,
    zone_preview_assessment,
)


class ZonePickerPolicyTests(unittest.TestCase):
    def test_virtual_desktop_geometry_spans_two_monitors(self):
        bounds = VirtualDesktopBounds(-1920, 0, 3840, 1080)
        self.assertEqual(format_virtual_geometry(bounds), "3840x1080-1920+0")
        self.assertEqual(
            screen_zone_from_drag((-582, 1009), (-470, 1038)),
            (-582, 1009, 112, 29),
        )
        self.assertEqual(
            screen_zone_from_drag((-348, 1030), (-452, 1011)),
            (-452, 1011, 104, 19),
        )

    def test_zone_capture_preserves_negative_screen_coordinates(self):
        grabbed = []
        backend = ScreenOcrBackend(
            capture_provider=lambda zone: grabbed.append(zone)
            or Image.new("RGB", (zone[2], zone[3]), "white")
        )
        backend.read_image = lambda *_args, **_kwargs: Reading("2,768.313", 0.95)
        reading = backend.read_zone((-582, 1009, 112, 29))
        self.assertEqual(grabbed, [(-582, 1009, 112, 29)])
        self.assertEqual(reading.raw_text, "2,768.313")

    def test_zone_heights_18_through_30_warn_only_when_tight(self):
        for height in range(18, 31):
            with self.subTest(height=height):
                assessment = zone_preview_assessment(
                    (-452, 1011, 104, height), "2,768.313"
                )
                self.assertFalse(assessment.blocking)
                warning = " ".join(assessment.warnings)
                self.assertEqual("may clip" in warning, height < 24)

    def test_preview_hides_overlay_before_capture_and_restores_after(self):
        calls = []
        value = preview_without_overlay(
            hide=lambda: calls.append("hide"),
            flush=lambda: calls.append("flush"),
            preview=lambda: calls.append("preview") or "North: 2,380,658",
            restore=lambda: calls.append("restore"),
        )
        self.assertEqual(value, "North: 2,380,658")
        self.assertEqual(calls, ["hide", "flush", "preview", "restore"])

    def test_label_text_and_two_numbers_produce_actionable_warnings(self):
        label = zone_preview_assessment((0, 0, 300, 28), "North: 2,380,658")
        self.assertIn("includes label text", " ".join(label.warnings))
        two = zone_preview_assessment(
            (0, 0, 500, 28), "2,380,658  1,328,135"
        )
        self.assertIn("more than one number", " ".join(two.warnings))

    def test_rendered_multiline_tall_zone_is_rejected_at_pick_time(self):
        image = Image.new("RGB", (87, 72), "white")
        draw = ImageDraw.Draw(image)
        draw.text((4, 5), "49.78", fill="black")
        draw.text((4, 42), "49.47", fill="black")
        assessment = zone_preview_assessment(
            (0, 0, image.width, image.height), "49.78\n49.47"
        )
        self.assertTrue(assessment.blocking)
        self.assertIn("72 px tall", " ".join(assessment.warnings))
        self.assertIn("48 px", " ".join(assessment.warnings))


if __name__ == "__main__":
    unittest.main()
