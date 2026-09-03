from __future__ import annotations

import unittest

from screen2xyz_civil.symbols import SymbolError, _to_raw, circles_from_drawings


def _circle(cx, cy, r, *, color=(0.0, 0.0, 0.0), fill=None, curves=4):
    # The shape pymupdf's get_drawings() returns for a circle: four Bezier
    # arcs and a square bounding rect.
    return {
        "items": [("c", None, None, None, None)] * curves,
        "rect": (cx - r, cy - r, cx + r, cy + r),
        "color": color,
        "fill": fill,
    }


class CircleDetectionTests(unittest.TestCase):
    def test_a_filled_black_circle_of_the_manhole_size_is_found(self):
        # DEMO-001-12: three of these, labelled D1-D3, radius 4.24 pt.
        found = circles_from_drawings([_circle(100, 200, 4.24, fill=(0, 0, 0))], radius_pt=(3.5, 9.0))
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0]["filled"])
        self.assertEqual(found[0]["fill"], (0, 0, 0))
        self.assertAlmostEqual(found[0]["radius_pt"], 4.24, places=6)

    def test_a_heavily_stroked_open_circle_counts_as_solid(self):
        # The D1-D3 manholes on DEMO-001-12 are open paths whose stroke is wider
        # than their radius; they render as solid dots. A fill-only test
        # found none of them.
        heavy = _circle(0, 0, 4.24)
        heavy["width"] = 5.0
        found = circles_from_drawings([heavy], radius_pt=(3.5, 9.0))
        self.assertTrue(found[0]["filled"])
        self.assertEqual(found[0]["width_pt"], 5.0)

    def test_an_open_grey_circle_keeps_its_stroke_and_is_not_filled(self):
        found = circles_from_drawings([_circle(10, 10, 5.6, color=(0.502, 0.502, 0.502))], radius_pt=(3.5, 9.0))
        self.assertFalse(found[0]["filled"])
        self.assertEqual(found[0]["stroke"], (128, 128, 128))

    def test_size_outside_the_window_is_ignored(self):
        found = circles_from_drawings([_circle(0, 0, 2.0), _circle(0, 0, 30.0)], radius_pt=(3.5, 9.0))
        self.assertEqual(found, [])

    def test_a_non_round_curve_is_not_a_circle(self):
        oval = {"items": [("c",)] * 4, "rect": (0, 0, 20, 8), "color": (0, 0, 0), "fill": None}
        self.assertEqual(circles_from_drawings([oval], radius_pt=(3.5, 9.0)), [])

    def test_a_straight_line_path_is_not_a_circle(self):
        poly = {"items": [("l",)] * 4, "rect": (0, 0, 10, 10), "color": (0, 0, 0), "fill": None}
        self.assertEqual(circles_from_drawings([poly], radius_pt=(3.5, 9.0)), [])

    def test_a_rect_object_with_attributes_is_accepted(self):
        class R:
            x0, y0, x1, y1 = 0.0, 0.0, 10.0, 10.0
        found = circles_from_drawings([{"items": [("c",)] * 4, "rect": R(), "color": None, "fill": (1, 1, 1)}], radius_pt=(3.5, 9.0))
        self.assertEqual(found[0]["centre_gd"], (5.0, 5.0))


class FrameTests(unittest.TestCase):
    def test_rotation_180_flips_y_only_for_data(self):
        self.assertEqual(_to_raw(817.1, 694.2, rotation=180, width=2384.0, height=1684.0), (817.1, 1684.0 - 694.2))

    def test_rotation_0_is_identity(self):
        self.assertEqual(_to_raw(1.0, 2.0, rotation=0, width=100.0, height=100.0), (1.0, 2.0))

    def test_other_rotations_are_refused(self):
        with self.assertRaises(SymbolError):
            _to_raw(0.0, 0.0, rotation=90, width=1.0, height=1.0)


if __name__ == "__main__":
    unittest.main()
