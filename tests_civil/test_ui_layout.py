from __future__ import annotations

import importlib
import unittest

from screen2xyz_civil.ui.layout import (
    canvas_to_source,
    manual_type,
    next_zoom,
    point_color,
    source_to_canvas,
    zoom_operation,
)


class UiLayoutTests(unittest.TestCase):
    def test_canvas_source_round_trip(self):
        source = 123.456
        canvas = source_to_canvas(source, 2.0)
        self.assertAlmostEqual(canvas_to_source(canvas, 2.0), source)

    def test_zoom_operations(self):
        self.assertEqual(zoom_operation(2.0), ("zoom", 2))
        self.assertEqual(zoom_operation(0.25), ("subsample", 4))

    def test_next_zoom_clamps(self):
        self.assertEqual(next_zoom(0.25, -1), 0.25)
        self.assertEqual(next_zoom(4.0, 1), 4.0)
        self.assertEqual(next_zoom(1.0, 1), 2.0)

    def test_point_review_color_overrides_type(self):
        self.assertEqual(
            point_color("EXISTING_GROUND", "REVIEW_REQUIRED"), "#dc2626"
        )
        self.assertEqual(point_color("DESIGN_GRADE", "APPROVED"), "#d97706")

    def test_manual_type_aliases(self):
        self.assertEqual(manual_type("e"), "EXISTING_GROUND")
        self.assertEqual(manual_type("Design"), "DESIGN_GRADE")
        self.assertEqual(manual_type("C"), "CONTOUR_ELEVATION")

    def test_manual_type_rejects_ambiguous_input(self):
        with self.assertRaises(ValueError):
            manual_type("utility")

    def test_ui_module_imports_without_creating_window(self):
        module = importlib.import_module("screen2xyz_civil.ui.app")
        self.assertTrue(hasattr(module, "CivilPlanDigitizerApp"))
