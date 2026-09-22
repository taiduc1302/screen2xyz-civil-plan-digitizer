"""Tests for ``screen2xyz_civil.sheet_geometry``.

All fixtures are synthetic and generated in-process. The pure-geometry cases run
everywhere; the page-level cases are skipped when the optional ``pymupdf`` and
``shapely`` dependencies are absent, because the rest of the application does not
require them.
"""

from __future__ import annotations

import unittest

from screen2xyz_civil.sheet_geometry import (
    boundary_offset,
    flatten_cubic,
    flip_y,
    group_offsets,
)

try:  # optional dependencies
    import fitz  # type: ignore
    import shapely  # noqa: F401  # type: ignore

    HAVE_PAGE_DEPS = True
except Exception:  # pragma: no cover - environment dependent
    HAVE_PAGE_DEPS = False


PAGE_H = 1584.0


class FlipYTests(unittest.TestCase):
    def test_flip_is_its_own_inverse(self) -> None:
        for y in (0.0, 1.0, 791.9, 792.0, 1583.0, PAGE_H):
            self.assertAlmostEqual(flip_y(flip_y(y, PAGE_H), PAGE_H), y, places=9)

    def test_midpage_flip_is_a_small_displacement(self) -> None:
        """The failure mode this guards: near mid-page an unflipped copy lands close
        enough to the flipped one to look correct."""
        near_middle = PAGE_H / 2.0 + 3.0
        self.assertLess(abs(flip_y(near_middle, PAGE_H) - near_middle), 7.0)
        far_from_middle = 120.0
        self.assertGreater(abs(flip_y(far_from_middle, PAGE_H) - far_from_middle), 1000.0)


class FlattenCubicTests(unittest.TestCase):
    def test_returns_requested_point_count_excluding_start(self) -> None:
        pts = flatten_cubic((0, 0), (0, 10), (10, 10), (10, 0), steps=8)
        self.assertEqual(len(pts), 8)

    def test_endpoint_is_reproduced_exactly(self) -> None:
        pts = flatten_cubic((0, 0), (0, 10), (10, 10), (10, 0), steps=8)
        self.assertAlmostEqual(pts[-1][0], 10.0, places=9)
        self.assertAlmostEqual(pts[-1][1], 0.0, places=9)

    def test_a_straight_control_polygon_stays_straight(self) -> None:
        pts = flatten_cubic((0, 0), (1, 0), (2, 0), (3, 0), steps=6)
        for _, y in pts:
            self.assertAlmostEqual(y, 0.0, places=9)

    def test_curve_is_not_a_chord(self) -> None:
        """Dropping curve items entirely is the defect; a flattened arc must bulge."""
        pts = flatten_cubic((0, 0), (0, 10), (10, 10), (10, 0), steps=8)
        self.assertGreater(max(y for _, y in pts), 1.0)


class GroupOffsetsTests(unittest.TestCase):
    def test_close_pair_collapses_to_one_group(self) -> None:
        self.assertEqual(group_offsets([-1.06, -0.83], max_gap=0.5), [(-1.06, -0.83)])

    def test_separated_lines_stay_apart(self) -> None:
        groups = group_offsets([-1.06, -0.83, 1.40, 4.80], max_gap=0.5)
        self.assertEqual(groups, [(-1.06, -0.83), (1.40, 1.40), (4.80, 4.80)])

    def test_single_line_has_coincident_faces(self) -> None:
        (near, far), = group_offsets([2.5], max_gap=0.5)
        self.assertEqual(near, far)

    def test_threshold_choice_changes_the_answer(self) -> None:
        offsets = [0.0, 0.52]
        self.assertEqual(len(group_offsets(offsets, max_gap=0.50)), 2)
        self.assertEqual(len(group_offsets(offsets, max_gap=0.60)), 1)

    def test_empty_input(self) -> None:
        self.assertEqual(group_offsets([], max_gap=0.5), [])


class BoundaryOffsetTests(unittest.TestCase):
    """The three outcomes, on the negative side unless stated."""

    GROUPS = [(-1.06, -0.83), (1.02, 1.02)]
    EDGES = [-3.95, 4.20]

    def test_cut_short_of_the_group_stops_at_the_near_face(self) -> None:
        offset, tag = boundary_offset(self.GROUPS, self.EDGES, cut_half_width=0.60, sign=-1)
        self.assertEqual(tag, "NEAR")
        self.assertAlmostEqual(offset, -0.83)

    def test_cut_entering_without_crossing_stops_at_the_far_face(self) -> None:
        offset, tag = boundary_offset(self.GROUPS, self.EDGES, cut_half_width=0.838, sign=-1)
        self.assertEqual(tag, "FAR")
        self.assertAlmostEqual(offset, -1.06)

    def test_cut_crossing_the_far_line_escalates(self) -> None:
        offset, tag = boundary_offset(self.GROUPS, self.EDGES, cut_half_width=1.50, sign=-1)
        self.assertEqual(tag, "EDGE")
        self.assertAlmostEqual(offset, -3.95)

    def test_single_line_cannot_produce_the_middle_outcome(self) -> None:
        """Reaching a one-faced feature is crossing it."""
        groups = [(-1.00, -1.00)]
        _, tag = boundary_offset(groups, self.EDGES, cut_half_width=1.20, sign=-1)
        self.assertEqual(tag, "EDGE")

    def test_entry_rule_escalates_where_the_crossing_rule_does_not(self) -> None:
        crossing = boundary_offset(self.GROUPS, self.EDGES, cut_half_width=0.838, sign=-1)
        entry = boundary_offset(self.GROUPS, self.EDGES, cut_half_width=0.838, sign=-1,
                                escalate_on_entry=True)
        self.assertEqual(crossing[1], "FAR")
        self.assertEqual(entry[1], "EDGE")
        self.assertNotAlmostEqual(crossing[0], entry[0])

    def test_positive_side_is_symmetric(self) -> None:
        groups = [(0.83, 1.06)]
        offset, tag = boundary_offset(groups, [3.95], cut_half_width=0.838, sign=1)
        self.assertEqual(tag, "FAR")
        self.assertAlmostEqual(offset, 1.06)

    def test_no_group_on_this_side_falls_through_to_the_edge(self) -> None:
        offset, tag = boundary_offset([(1.02, 1.02)], self.EDGES, cut_half_width=0.5, sign=-1)
        self.assertEqual(tag, "EDGE")
        self.assertAlmostEqual(offset, -3.95)


@unittest.skipUnless(HAVE_PAGE_DEPS, "requires optional pymupdf and shapely")
class PlanBandTests(unittest.TestCase):
    """Synthetic sheet: a standalone view title, a combined caption, and a boilerplate
    notes column that repeats both words."""

    NOTES_X = 2100.0

    def _sheet(self, *, standalone_title: bool) -> "fitz.Page":
        doc = fitz.open()
        page = doc.new_page(width=2448, height=PAGE_H)
        if standalone_title:
            # The view title sits below the plan it names but well above the halfway line:
            # on a real combined sheet it lands around 0.58 of the page height from the
            # bottom, with the profile occupying everything below it.
            page.insert_text((900, flip_y(922.0, PAGE_H)), "PLAN", fontsize=14)
        page.insert_text((900, flip_y(260.0, PAGE_H)), "PLAN", fontsize=12)
        page.insert_text((980, flip_y(260.0, PAGE_H)), "PROFILE", fontsize=12)
        page.insert_text((2200, flip_y(1100.0, PAGE_H)), "PLAN", fontsize=10)
        page.insert_text((2240, flip_y(400.0, PAGE_H)), "PROFILE", fontsize=10)
        return page

    def test_standalone_title_defines_the_band(self) -> None:
        from screen2xyz_civil.sheet_geometry import plan_band

        band = plan_band(self._sheet(standalone_title=True), PAGE_H, self.NOTES_X)
        self.assertIsNotNone(band)
        y_low, y_high, titles = band
        self.assertEqual(y_high, PAGE_H)
        self.assertGreater(y_low, PAGE_H * 0.5)
        self.assertTrue(all(x < self.NOTES_X for x, _ in titles))

    def test_combined_caption_alone_means_no_plan_view(self) -> None:
        from screen2xyz_civil.sheet_geometry import plan_band

        self.assertIsNone(plan_band(self._sheet(standalone_title=False), PAGE_H, self.NOTES_X))

    def test_notes_column_is_excluded(self) -> None:
        from screen2xyz_civil.sheet_geometry import plan_band

        band = plan_band(self._sheet(standalone_title=True), PAGE_H, self.NOTES_X)
        _, _, titles = band
        self.assertFalse(any(x >= self.NOTES_X for x, _ in titles))


@unittest.skipUnless(HAVE_PAGE_DEPS, "requires optional pymupdf and shapely")
class SegmentsAndRingsTests(unittest.TestCase):
    def _page_with_square_and_arc(self) -> "fitz.Page":
        doc = fitz.open()
        page = doc.new_page(width=2448, height=PAGE_H)
        shape = page.new_shape()
        shape.draw_rect(fitz.Rect(100, 100, 200, 200))
        shape.finish(color=(0, 0, 0), width=1)
        shape.commit()
        shape = page.new_shape()
        shape.draw_bezier(fitz.Point(400, 400), fitz.Point(400, 460),
                          fitz.Point(460, 460), fitz.Point(460, 400))
        shape.finish(color=(0, 0, 0), width=1)
        shape.commit()
        return page

    def test_segments_are_returned_in_bottom_up_space(self) -> None:
        from screen2xyz_civil.sheet_geometry import segments

        segs = segments(self._page_with_square_and_arc(), PAGE_H)
        self.assertTrue(segs)
        for (ax, ay), (bx, by), _, _ in segs:
            self.assertGreater(ay, PAGE_H / 2.0)
            self.assertGreater(by, PAGE_H / 2.0)

    def test_curve_contributes_multiple_segments(self) -> None:
        from screen2xyz_civil.sheet_geometry import segments

        few = segments(self._page_with_square_and_arc(), PAGE_H, curve_steps=2)
        many = segments(self._page_with_square_and_arc(), PAGE_H, curve_steps=16)
        self.assertGreater(len(many), len(few))

    def test_rectangle_items_are_not_dropped(self) -> None:
        """Regression: a drawn rectangle arrives as a single ``re`` item, not as four
        ``l`` items. An extractor that handles only lines and curves loses every
        axis-aligned pad and box silently."""
        from screen2xyz_civil.sheet_geometry import segments

        page = self._page_with_square_and_arc()
        kinds = {item[0] for drawing in page.get_drawings() for item in drawing["items"]}
        self.assertIn("re", kinds, "fixture no longer exercises the rectangle path")

        segs = segments(page, PAGE_H)
        square_side = [
            s for s in segs
            if abs(s[0][0] - s[1][0]) < 1e-6 or abs(s[0][1] - s[1][1]) < 1e-6
        ]
        self.assertGreaterEqual(len(square_side), 4)

    def test_square_closes_into_a_ring(self) -> None:
        from screen2xyz_civil.sheet_geometry import chains, closed_rings, segments

        segs = segments(self._page_with_square_and_arc(), PAGE_H)
        rings = closed_rings(chains(segs), units_per_pt=1.0,
                             min_area=100.0, max_area=100000.0, gap=2.0)
        self.assertTrue(rings)
        areas = [poly.area for poly, _, _, _ in rings]
        self.assertTrue(any(abs(a - 10000.0) < 600.0 for a in areas))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
