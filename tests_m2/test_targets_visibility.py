"""Pure-function tests for targets.window_visibility (off-screen detection).

No Windows API calls involved - these exercise only the geometry math.
"""

from __future__ import annotations

import unittest

from screen2xyz_m2.targets import window_visibility

VIRTUAL = {"x": 0, "y": 0, "w": 1920, "h": 1080}


class WindowVisibilityTests(unittest.TestCase):
    def test_fully_on_screen(self):
        result = window_visibility(800, 600, 100, 100, VIRTUAL)
        self.assertTrue(result["fully_visible"])
        self.assertEqual(result["off_screen_px"],
                         {"left": 0, "top": 0, "right": 0, "bottom": 0})

    def test_partially_off_left_and_top(self):
        result = window_visibility(800, 600, -50, -30, VIRTUAL)
        self.assertFalse(result["fully_visible"])
        self.assertEqual(result["off_screen_px"]["left"], 50)
        self.assertEqual(result["off_screen_px"]["top"], 30)
        self.assertEqual(result["off_screen_px"]["right"], 0)
        self.assertEqual(result["off_screen_px"]["bottom"], 0)

    def test_partially_off_right_and_bottom(self):
        # window right/bottom edge = 1920+50=1970, 1080+40=1120 -> overhangs
        result = window_visibility(800, 600, 1170, 520, VIRTUAL)
        self.assertFalse(result["fully_visible"])
        self.assertEqual(result["off_screen_px"]["right"], 50)
        self.assertEqual(result["off_screen_px"]["bottom"], 40)

    def test_larger_than_desktop_is_off_screen_on_all_sides_it_exceeds(self):
        result = window_visibility(3000, 2000, 0, 0, VIRTUAL)
        self.assertFalse(result["fully_visible"])
        self.assertEqual(result["off_screen_px"]["right"], 3000 - 1920)
        self.assertEqual(result["off_screen_px"]["bottom"], 2000 - 1080)

    def test_multi_monitor_negative_origin_virtual_screen(self):
        # A virtual screen starting at a negative x (secondary monitor to
        # the left of the primary) must not be misread as "off-screen".
        virtual = {"x": -1920, "y": 0, "w": 3840, "h": 1080}
        result = window_visibility(800, 600, -1000, 100, virtual)
        self.assertTrue(result["fully_visible"])

    def test_exactly_at_edge_is_fully_visible(self):
        result = window_visibility(1920, 1080, 0, 0, VIRTUAL)
        self.assertTrue(result["fully_visible"])
