import unittest

from screen2xyz_civil.host_frame import (
    HostFrameError,
    Rect,
    format_rect,
    parse_rect,
    raw_centre,
    raw_to_view,
    rect_from_centre,
    view_to_raw,
)

W, H = 2384.0, 1684.0


class ParseTests(unittest.TestCase):
    def test_parses_the_host_rect_string(self):
        self.assertEqual(parse_rect("1125 583 8 8"), Rect(1125.0, 583.0, 8.0, 8.0))

    def test_parses_decimals(self):
        self.assertEqual(parse_rect("813.1 985.8 8 8").x, 813.1)

    def test_refuses_the_wrong_arity(self):
        with self.assertRaises(HostFrameError):
            parse_rect("1125 583 8")

    def test_refuses_non_numeric(self):
        with self.assertRaises(HostFrameError):
            parse_rect("a b c d")

    def test_refuses_negative_extent(self):
        with self.assertRaises(HostFrameError):
            parse_rect("10 10 -8 8")

    def test_round_trips_through_format(self):
        self.assertEqual(format_rect(parse_rect("1114 405 8 8")), "1114 405 8 8")


class MeasuredHostValues(unittest.TestCase):
    """The two conversions, against numbers the host actually returned.

    Sheet 11 is /Rotate 0 and sheet 12 is /Rotate 180 in the Example Road set, so
    between them they pin both axes.
    """

    def test_rotate_0_page_flips_y(self):
        # get_markup_shape said "1125 583 8 8"; list_markups_in_pdf said y 1093
        view = raw_to_view(parse_rect("1125 583 8 8"), W, H, 0)
        self.assertAlmostEqual(view.y, 1093.0)
        self.assertAlmostEqual(view.x, 1125.0)

    def test_rotate_0_page_all_five_sheet_11_markers(self):
        stored = ["1125 583 8 8", "1359 583 8 8", "1670 583 8 8", "1114 405 8 8", "1700 401 8 8"]
        reported = [1093.0, 1093.0, 1093.0, 1271.0, 1275.0]
        got = [raw_to_view(parse_rect(s), W, H, 0).y for s in stored]
        self.assertEqual(got, reported)

    def test_rotate_180_page_flips_x(self):
        # get_markup_shape said "813.1 985.8 8 8"; list_markups_in_pdf said x 1562.9
        view = raw_to_view(parse_rect("813.1 985.8 8 8"), W, H, 180)
        self.assertAlmostEqual(view.x, 1562.9)
        self.assertAlmostEqual(view.y, 985.8)

    def test_the_conversion_is_its_own_inverse(self):
        raw = parse_rect("1670 583 8 8")
        for rotation in (0, 180):
            back = view_to_raw(raw_to_view(raw, W, H, rotation), W, H, rotation)
            self.assertEqual(back, raw)


class GuardTests(unittest.TestCase):
    def test_refuses_an_unmeasured_quarter_turn(self):
        # 90/270 swaps the page axes; guessing it is how the original bug happened
        for rotation in (90, 270):
            with self.assertRaises(HostFrameError):
                raw_to_view(Rect(0.0, 0.0, 8.0, 8.0), W, H, rotation)

    def test_refuses_a_nonsense_rotation(self):
        with self.assertRaises(HostFrameError):
            raw_to_view(Rect(0.0, 0.0, 8.0, 8.0), W, H, 45)

    def test_refuses_a_zero_page(self):
        with self.assertRaises(HostFrameError):
            raw_to_view(Rect(0.0, 0.0, 8.0, 8.0), 0.0, H, 0)


class MarkerTests(unittest.TestCase):
    def test_a_point_marker_is_centred(self):
        self.assertEqual(rect_from_centre(1129.0, 587.0), Rect(1125.0, 583.0, 8.0, 8.0))

    def test_centre_round_trips(self):
        self.assertEqual(raw_centre(rect_from_centre(1704.0, 405.0)), (1704.0, 405.0))

    def test_refuses_a_zero_size_marker(self):
        with self.assertRaises(HostFrameError):
            rect_from_centre(1.0, 1.0, size=0.0)


class RegressionTests(unittest.TestCase):
    def test_the_sheet_11_failure_is_reproduced(self):
        """Feeding a raw y to the view-frame writer lands 510 pt away.

        The intended HW1 marker centre was raw y 587, in the plan. Writing 583
        through the view-frame API stored raw y 1093, which renders in the
        profile - and reading it back through the same view-frame API returns
        583 again, so the mistake is invisible to a read-back check.
        """
        intended = rect_from_centre(1129.0, 587.0)
        stored_by_mistake = view_to_raw(intended, W, H, 0)
        self.assertAlmostEqual(stored_by_mistake.y, 1093.0)
        self.assertAlmostEqual(
            raw_to_view(stored_by_mistake, W, H, 0).y, intended.y
        )  # the circular read-back that hid it


if __name__ == "__main__":
    unittest.main()
