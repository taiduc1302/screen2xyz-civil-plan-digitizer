from __future__ import annotations

import math
import unittest

from screen2xyz_civil.models import CivilModelError, PixelPoint
from screen2xyz_civil.transform import (
    build_calibration,
    east_basis,
    metres_per_pixel,
    to_local,
    to_pixel,
    verify_scale,
)

from .helpers_civil import FIXED_NOW


class TransformTests(unittest.TestCase):
    def calibration(self, **overrides):
        values = {
            "revision": 1,
            "created_at": FIXED_NOW,
            "scale_point_1": PixelPoint(0, 100),
            "scale_point_2": PixelPoint(100, 100),
            "known_distance_m": 10.0,
            "origin_pixel": PixelPoint(50, 50),
            "east_reference": PixelPoint(60, 50),
            "origin_east_m": 500.0,
            "origin_north_m": 1000.0,
        }
        values.update(overrides)
        return build_calibration(**values)

    def test_scale_calibration(self):
        self.assertAlmostEqual(
            metres_per_pixel(PixelPoint(0, 0), PixelPoint(30, 40), 10), 0.2
        )

    def test_zero_scale_span_rejected(self):
        with self.assertRaises(CivilModelError):
            metres_per_pixel(PixelPoint(1, 1), PixelPoint(1, 1), 10)

    def test_screen_y_is_inverted(self):
        east, north = to_local(PixelPoint(50, 40), self.calibration())
        self.assertAlmostEqual(east, 500.0)
        self.assertAlmostEqual(north, 1001.0)

    def test_local_origin_offset(self):
        east, north = to_local(PixelPoint(50, 50), self.calibration())
        self.assertEqual((east, north), (500.0, 1000.0))

    def test_rotated_east_axis(self):
        calibration = self.calibration(
            origin_pixel=PixelPoint(50, 50),
            east_reference=PixelPoint(50, 40),
        )
        east, north = to_local(PixelPoint(60, 50), calibration)
        self.assertAlmostEqual(east, 500.0)
        self.assertAlmostEqual(north, 999.0)

    def test_round_trip(self):
        calibration = self.calibration(east_reference=PixelPoint(60, 40))
        source = PixelPoint(74.25, 19.75)
        east, north = to_local(source, calibration)
        restored = to_pixel(east, north, calibration)
        self.assertAlmostEqual(restored.x, source.x, places=9)
        self.assertAlmostEqual(restored.y, source.y, places=9)

    def test_second_distance_verification_pass_and_warning(self):
        passed = verify_scale(
            PixelPoint(0, 0), PixelPoint(100, 0), 10.0, 0.1
        )
        warned = verify_scale(
            PixelPoint(0, 0), PixelPoint(98, 0), 10.0, 0.1
        )
        self.assertTrue(passed.passed)
        self.assertFalse(warned.passed)
        self.assertAlmostEqual(warned.error_percent, 2.0)

    def test_basis_is_normalized(self):
        x, y = east_basis(PixelPoint(0, 0), PixelPoint(3, -4))
        self.assertAlmostEqual(math.hypot(x, y), 1.0)

    def test_partial_second_check_rejected(self):
        with self.assertRaises(CivilModelError):
            self.calibration(check_point_1=PixelPoint(0, 0))
