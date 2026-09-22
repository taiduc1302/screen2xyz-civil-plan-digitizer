from __future__ import annotations

import unittest

from screen2xyz_civil.markup_view import (
    MarkupViewError,
    clip_around,
    parse_path,
    parse_rect,
    rect_corners,
    to_clip,
    to_page,
)

W, H = 2384.0, 1684.0


class PathParsingTests(unittest.TestCase):
    def test_a_closed_polygon_path_parses_to_its_points(self):
        pts = parse_path("M 409.9 1148.3 L 1049.9 1156 L 1051.9 1166 H")
        self.assertEqual(pts, [(409.9, 1148.3), (1049.9, 1156.0), (1051.9, 1166.0)])

    def test_an_open_polyline_parses(self):
        self.assertEqual(len(parse_path("M 1118.8 677.9 L 1221.5 677.9")), 2)

    def test_an_odd_coordinate_count_is_refused(self):
        with self.assertRaises(MarkupViewError):
            parse_path("M 1 2 L 3")

    def test_a_square_rect_parses_to_x_y_w_h_and_four_corners(self):
        self.assertEqual(parse_rect("1741 1545 8 8"), (1741.0, 1545.0, 8.0, 8.0))
        self.assertEqual(
            rect_corners("10 20 4 6"),
            [(10.0, 20.0), (14.0, 20.0), (14.0, 26.0), (10.0, 26.0)],
        )

    def test_a_malformed_rect_is_refused(self):
        with self.assertRaises(MarkupViewError):
            parse_rect("1 2 3")


class FrameTests(unittest.TestCase):
    # The trap: drawing and clipping do not share a frame on a rotated page.
    # Using one for both puts the render window in the profile while the
    # geometry is in the plan, which reads as a misplaced markup when nothing
    # is wrong with it. It has cost two sessions a wrong first attempt.
    POINT = (817.9, 1145.7)

    def test_drawing_flips_y_on_a_rotated_page(self):
        self.assertEqual(to_page(self.POINT, rotation=180, height=H), (817.9, H - 1145.7))

    def test_drawing_flips_y_on_an_unrotated_page_too(self):
        # The raw frame measures y from the bottom, pymupdf from the top. That
        # is a convention difference, not a rotation effect. Returning y
        # unchanged here put every symbol on DEMO-001-11, the set's only
        # rotation-0 sheet, 1684 - y away from the truth, and two markers were
        # written from those coordinates onto blank paper.
        self.assertEqual(to_page(self.POINT, rotation=0, height=H), (817.9, H - 1145.7))

    def test_clipping_mirrors_x_and_keeps_y_on_a_rotated_page(self):
        self.assertEqual(to_clip(self.POINT, rotation=180, width=W, height=H), (W - 817.9, 1145.7))

    def test_clipping_only_flips_y_on_an_unrotated_page(self):
        self.assertEqual(to_clip(self.POINT, rotation=0, width=W, height=H), (817.9, H - 1145.7))

    def test_the_two_frames_differ_on_a_rotated_page(self):
        self.assertNotEqual(
            to_page(self.POINT, rotation=180, height=H),
            to_clip(self.POINT, rotation=180, width=W, height=H),
        )

    def test_the_two_frames_agree_on_an_unrotated_page(self):
        self.assertEqual(
            to_page(self.POINT, rotation=0, height=H),
            to_clip(self.POINT, rotation=0, width=W, height=H),
        )

    def test_neither_frame_is_ever_the_identity(self):
        for rotation in (0, 180):
            self.assertNotEqual(to_page(self.POINT, rotation=rotation, height=H), self.POINT)

    def test_an_unhandled_rotation_is_refused(self):
        with self.assertRaises(MarkupViewError):
            to_page(self.POINT, rotation=90, height=H)
        with self.assertRaises(MarkupViewError):
            to_clip(self.POINT, rotation=90, width=W, height=H)

    def test_a_clip_box_is_built_in_displayed_coordinates_with_margin(self):
        box = clip_around([(100.0, 200.0), (300.0, 260.0)],
                          rotation=180, width=W, height=H, margin=10.0)
        self.assertAlmostEqual(box[0], W - 300.0 - 10.0)
        self.assertAlmostEqual(box[2], W - 100.0 + 10.0)
        self.assertAlmostEqual(box[1], 190.0)
        self.assertAlmostEqual(box[3], 270.0)


class DelegationTests(unittest.TestCase):
    # to_clip and host_frame.raw_to_view are one rule. Two implementations of
    # one rule is how the two sessions ended up disagreeing about where five
    # markers were, so this pins them together.

    def test_to_clip_agrees_with_host_frame_on_both_rotations(self):
        from screen2xyz_civil import host_frame

        for rotation in (0, 180):
            for point in ((817.9, 1145.7), (1125.0, 583.0), (10.0, 20.0)):
                rect = host_frame.raw_to_view(
                    host_frame.Rect(point[0], point[1], 0.0, 0.0), W, H, rotation
                )
                self.assertEqual(
                    to_clip(point, rotation=rotation, width=W, height=H),
                    (rect.x, rect.y),
                    (rotation, point),
                )

    def test_a_rotation_host_frame_refuses_is_refused_here_too(self):
        for rotation in (90, 270):
            with self.assertRaises(MarkupViewError):
                to_clip((1.0, 2.0), rotation=rotation, width=W, height=H)


if __name__ == "__main__":
    unittest.main()
