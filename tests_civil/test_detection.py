from __future__ import annotations

import unittest

from screen2xyz_civil import contracts as C
from screen2xyz_civil.detection import (
    Rect,
    SymbolCandidate,
    TextCandidate,
    VectorShape,
    associate_candidate,
    candidate_to_point,
    classify_candidate,
    detect_symbols,
    in_exclusion_zone,
    normalize_numeric,
)
from screen2xyz_civil.models import PixelPoint

from .helpers_civil import FIXED_NOW


class DetectionTests(unittest.TestCase):
    def candidate(self, text: str, **overrides):
        values = {
            "id": "T1",
            "text": text,
            "bbox": Rect(20, 20, 50, 32),
            "page_index": 0,
            "source_method": C.PDF_TEXT,
            "confidence": 0.99,
        }
        values.update(overrides)
        return TextCandidate(**values)

    def test_plain_decimal_normalization(self):
        result = normalize_numeric("49.06")
        self.assertEqual(result.value, 49.06)
        self.assertFalse(result.ambiguous)

    def test_decimal_comma_normalization(self):
        result = normalize_numeric("49,06")
        self.assertEqual(result.normalized_text, "49.06")
        self.assertIn("decimal comma normalized", result.reasons)

    def test_ocr_o_normalization_is_ambiguous(self):
        result = normalize_numeric("49.O6")
        self.assertEqual(result.value, 49.06)
        self.assertTrue(result.ambiguous)

    def test_percent_date_scale_and_station_rejected(self):
        for text in ("2.9%", "07/28/2026", "1:500", "10+250.5"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                normalize_numeric(text)

    def test_context_classifies_utility_and_slab(self):
        cases = (
            ("49.06", "INV 49.06", C.UTILITY_INVERT),
            ("49.06", "RIM 49.06", C.UTILITY_RIM),
            ("49.06", "SLAB 49.06", C.SLAB_ELEVATION),
        )
        for text, context, expected in cases:
            with self.subTest(expected=expected):
                result = classify_candidate(
                    self.candidate(text, context=context)
                )
                self.assertEqual(result.point_type, expected)

    def test_percent_is_slope_annotation(self):
        result = classify_candidate(self.candidate("3.7%"))
        self.assertEqual(result.point_type, C.SLOPE_ANNOTATION)

    def test_exclusion_is_metadata(self):
        result = classify_candidate(
            self.candidate("49.06", in_exclusion_zone=True)
        )
        self.assertEqual(result.point_type, C.DRAWING_METADATA)

    def test_symbol_detector_distinguishes_cross_and_oval(self):
        symbols = detect_symbols(
            [
                VectorShape("S1", Rect(0, 0, 10, 10), "cross", line_segments=2),
                VectorShape("S2", Rect(20, 0, 40, 10), "ellipse", closed=True),
            ]
        )
        self.assertEqual(
            [symbol.symbol_type for symbol in symbols],
            ["EXISTING_CROSS", "DESIGN_OVAL"],
        )

    def test_perpendicular_vector_lines_propose_cross(self):
        symbols = detect_symbols(
            [
                VectorShape("L1", Rect(0, 5, 10, 5), "line", line_segments=1),
                VectorShape("L2", Rect(5, 0, 5, 10), "line", line_segments=1),
            ]
        )
        self.assertIn("EXISTING_CROSS", [item.symbol_type for item in symbols])

    def test_association_uses_multiple_signals_and_alternatives(self):
        symbols = [
            SymbolCandidate(
                "S1", "EXISTING_CROSS", Rect(10, 20, 18, 28), 0.9, C.PDF_VECTOR
            ),
            SymbolCandidate(
                "S2",
                "DESIGN_OVAL",
                Rect(15, 18, 55, 34),
                0.9,
                C.PDF_VECTOR,
                has_leader=True,
            ),
        ]
        associations = associate_candidate(self.candidate("49.06"), symbols)
        self.assertEqual(len(associations), 2)
        self.assertGreater(associations[0].score, associations[1].score)
        self.assertGreaterEqual(len(associations[0].reasons), 3)

    def test_cross_classifies_existing(self):
        symbol = SymbolCandidate(
            "S1", "EXISTING_CROSS", Rect(10, 20, 18, 28), 0.9, C.PDF_VECTOR
        )
        result = classify_candidate(self.candidate("49.06"), [symbol])
        self.assertEqual(result.point_type, C.EXISTING_GROUND)

    def test_oval_classifies_design(self):
        symbol = SymbolCandidate(
            "S1", "DESIGN_OVAL", Rect(15, 18, 55, 34), 0.9, C.PDF_VECTOR
        )
        result = classify_candidate(self.candidate("49.06"), [symbol])
        self.assertEqual(result.point_type, C.DESIGN_GRADE)

    def test_unassociated_decimal_requires_review(self):
        result = classify_candidate(self.candidate("49.06"))
        self.assertEqual(result.point_type, C.REVIEW_REQUIRED_TYPE)

    def test_ambiguous_numeric_never_high_confidence(self):
        symbol = SymbolCandidate(
            "S1", "DESIGN_OVAL", Rect(15, 18, 55, 34), 1.0, C.PDF_VECTOR
        )
        result = classify_candidate(self.candidate("49.O6"), [symbol])
        self.assertLess(result.confidence, 0.6)

    def test_candidate_to_point_is_never_approved(self):
        symbol = SymbolCandidate(
            "S1", "DESIGN_OVAL", Rect(15, 18, 55, 34), 1.0, C.PDF_VECTOR
        )
        candidate = self.candidate("49.06")
        classification = classify_candidate(candidate, [symbol])
        point = candidate_to_point(
            candidate,
            classification,
            point_id="PT-0001",
            source_file="synthetic.pdf",
            source_sha256="a" * 64,
            now=FIXED_NOW,
        )
        self.assertNotIn(point.review_status, C.APPROVED_STATUSES)
        self.assertEqual(point.symbol_type, "DESIGN_OVAL")

    def test_polygon_exclusion_filter(self):
        zone = [
            PixelPoint(0, 0),
            PixelPoint(100, 0),
            PixelPoint(100, 100),
            PixelPoint(0, 100),
        ]
        self.assertTrue(in_exclusion_zone(Rect(20, 20, 30, 30), [zone]))
        self.assertFalse(in_exclusion_zone(Rect(120, 20, 130, 30), [zone]))
