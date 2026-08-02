from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from screen2xyz_app.backends import OcrPolicy, ScreenOcrBackend
from screen2xyz_civil.ocr import TesseractOcrAdapter
from tests_app.harness.renderers import (
    STATUS_STYLES,
    render_plan,
    render_status_frame,
    scripted_coordinates,
)


class HarnessContractTests(unittest.TestCase):
    def test_ocr_policy_rejects_invalid_consensus(self):
        with self.assertRaisesRegex(ValueError, "consensus"):
            OcrPolicy(consensus_min=0)

    def test_script_contains_at_least_200_unique_pairs_and_required_styles(self):
        scenarios = scripted_coordinates()
        rows = [point for _style, _primer, values in scenarios for point in values]
        self.assertGreaterEqual(len(rows), 200)
        self.assertEqual(len(rows), len(set(rows)))
        self.assertEqual({style.decimal_separator for style in STATUS_STYLES}, {"point", "comma"})
        self.assertTrue(any(style.grouped for style in STATUS_STYLES))
        self.assertTrue(any(point[0] < 0 or point[1] < 0 for point in rows))

    def test_plan_has_40_plus_labels_rotations_and_both_markers(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "plan.png"
            labels = render_plan(path)
            self.assertGreaterEqual(len(labels), 40)
            self.assertTrue(any(label.angle != 0 for label in labels))
            self.assertEqual({label.marker for label in labels}, {"existing_cross", "design_oval"})
            self.assertTrue(path.is_file())

    def test_dark_status_surfaces_are_normalized_before_ocr(self):
        image = Image.new("RGB", (20, 20), (50, 55, 60))
        variants = ScreenOcrBackend._prepare_variants(image, OcrPolicy())
        self.assertGreater(sum(variants[0][1].getpixel((0, 0))) / 3, 128)

    @unittest.skipUnless(TesseractOcrAdapter.find_executable(), "Tesseract unavailable")
    def test_real_backend_reads_small_status_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "frame.png"
            style = STATUS_STYLES[0]
            frame = render_status_frame(path, sequence=1, style=style, x=512.25, y=-120.75)
            backend = ScreenOcrBackend()
            reading = backend.read_image_region(
                path, frame.x_zone,
                policy=OcrPolicy(separator_mode="point", confidence_min=0.35),
            )
            self.assertEqual(reading.raw_text, "512.25")


if __name__ == "__main__":
    unittest.main()
