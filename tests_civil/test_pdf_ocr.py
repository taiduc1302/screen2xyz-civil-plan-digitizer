from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from unittest import mock

from screen2xyz_civil.detection import Rect
from screen2xyz_civil.ocr import (
    MockOcrAdapter,
    OcrAdapterError,
    OcrLine,
    OcrResult,
    OcrWord,
    WindowsOcrAdapter,
)
from screen2xyz_civil.pdf import (
    PdfAdapterError,
    PdfPageInfo,
    extract_pdf_text_candidates,
    extract_pdf_vector_shapes,
    inspect_pdf,
    pdf_rect_to_render_pixels,
    render_pdf_page,
)

from .helpers_civil import ROOT, fresh_dir, make_png, make_vector_pdf


class PdfOcrTests(unittest.TestCase):
    def test_pdf_inspection_reports_vector_text_and_dimensions(self):
        path = make_vector_pdf(fresh_dir() / "plan.pdf")
        info = inspect_pdf(path)
        self.assertEqual(info.page_count, 1)
        self.assertEqual(
            (info.pages[0].width_points, info.pages[0].height_points),
            (612.0, 792.0),
        )
        self.assertTrue(info.pages[0].has_vector_text)

    def test_pdf_text_extraction_preserves_pdf_and_pixel_boxes(self):
        path = make_vector_pdf(fresh_dir() / "plan.pdf", "49.06")
        candidates = extract_pdf_text_candidates(path, 0, dpi=144)
        candidate = next(item for item in candidates if item.text == "49.06")
        self.assertIsNotNone(candidate.pdf_bbox)
        self.assertAlmostEqual(candidate.bbox.x0, candidate.pdf_bbox.x0 * 2)
        self.assertEqual(candidate.source_method, "PDF_TEXT")

    def test_pdf_vector_path_extraction_finds_lines_and_ellipse(self):
        path = make_vector_pdf(
            fresh_dir() / "plan.pdf", "49.06", with_shapes=True
        )
        shapes = extract_pdf_vector_shapes(path, 0, dpi=72)
        self.assertGreaterEqual(
            sum(shape.kind == "line" for shape in shapes), 2
        )
        self.assertIn("ellipse", [shape.kind for shape in shapes])

    def test_pdf_rotation_mapping(self):
        page = PdfPageInfo(0, 612, 792, 90, True)
        mapped = pdf_rect_to_render_pixels(Rect(10, 20, 30, 40), page, 72)
        self.assertEqual(mapped.to_dict(), {"x0": 752, "y0": 10, "x1": 772, "y1": 30})

    def test_pdf_renderer_unavailable_is_actionable(self):
        path = make_vector_pdf(fresh_dir() / "plan.pdf")
        with self.assertRaises(PdfAdapterError):
            render_pdf_page(path, 0, fresh_dir(), renderer="missing-renderer.exe")

    @unittest.skipUnless(shutil.which("pdftoppm"), "local Poppler renderer unavailable")
    def test_local_pdf_renderer_creates_png(self):
        root = fresh_dir()
        path = make_vector_pdf(root / "plan.pdf")
        rendered = render_pdf_page(path, 0, root / "rendered", dpi=72)
        self.assertTrue(rendered.is_file())
        self.assertGreater(rendered.stat().st_size, 100)

    def test_ocr_result_maps_word_boxes_with_crop_offset(self):
        result = OcrResult(
            "SUCCESS",
            "49.06",
            "mock",
            "en-US",
            1,
            (OcrLine("49.06", (OcrWord("49.06", Rect(1, 2, 11, 12), 0.9),)),),
        )
        candidate = result.text_candidates(page_index=2, offset_x=100, offset_y=200)[0]
        self.assertEqual(candidate.bbox.to_dict(), {"x0": 101, "y0": 202, "x1": 111, "y1": 212})
        self.assertEqual(candidate.page_index, 2)

    def test_mock_ocr_adapter_is_swappable(self):
        expected = OcrResult("SUCCESS", "", "mock", "en-US", 0, ())
        adapter = MockOcrAdapter(expected)
        self.assertIs(adapter.extract(fresh_dir() / "unused.png"), expected)

    def test_windows_ocr_rejects_non_png_before_invocation(self):
        path = fresh_dir() / "bad.txt"
        path.write_text("not an image", encoding="utf-8")
        with self.assertRaises(OcrAdapterError):
            WindowsOcrAdapter(ROOT).extract(path)

    def test_windows_ocr_schema_parsing(self):
        image = make_png(fresh_dir() / "crop.png", 20, 20)
        payload = {
            "schema_version": "1.0",
            "status": "SUCCESS",
            "raw_text": "49.06",
            "engine": "Windows.Media.Ocr",
            "language": "en-US",
            "duration_ms": 3,
            "lines": [
                {
                    "text": "49.06",
                    "words": [
                        {"text": "49.06", "x": 1, "y": 2, "width": 10, "height": 8}
                    ],
                }
            ],
        }
        completed = subprocess.CompletedProcess([], 0, json.dumps(payload), "")
        with mock.patch("screen2xyz_civil.ocr.subprocess.run", return_value=completed):
            result = WindowsOcrAdapter(ROOT).extract(image)
        self.assertEqual(result.lines[0].words[0].text, "49.06")
        self.assertEqual(result.lines[0].words[0].bbox.x1, 11)
