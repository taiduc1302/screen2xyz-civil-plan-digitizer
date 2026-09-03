from __future__ import annotations

import unittest

from screen2xyz_civil.cross_sections import (
    CrossSectionError,
    Panel,
    SectionSheetSpec,
    Segment,
    _collapse_twins,
    _crown_check,
    _display_rect,
    _envelope,
    _join_runs,
    _measure_to_subgrade,
    _merge_collinear,
    _simplify,
    _widest_non_overlapping,
    measure_sections,
)


# 1:100 horizontal against 1:50 vertical, as on DEMO-001-09/10.
CX = 0.0352777777777778
CY = 0.0176388888888889


def _panel(**overrides) -> Panel:
    base = dict(
        index=1,
        bbox_gd=(1283.0, 1348.7, 2133.0, 1490.4),
        bbox_display=(251.0, 193.6, 1101.0, 335.3),
        centreline_x_gd=1707.8,
        base_y_gd=1348.7,
        grid_dx_pt=141.72,
        grid_dy_pt=28.35,
        metres_per_point_x=CX,
        metres_per_point_y=CY,
    )
    base.update(overrides)
    return Panel(**base)


class GridMergeTests(unittest.TestCase):
    def test_pieces_broken_at_labels_become_one_line(self):
        # A grid line is drawn in three pieces around the offset labels.
        pieces = [Segment(1282.6, 1348.7, 1424.3, 1348.7),
                  Segment(1424.3, 1348.7, 1991.2, 1348.7),
                  Segment(1991.2, 1348.7, 2132.9, 1348.7)]
        spans = _merge_collinear(pieces, axis="h")
        self.assertEqual(len(spans), 1)
        self.assertAlmostEqual(spans[0][1], 1282.6)
        self.assertAlmostEqual(spans[0][2], 2132.9)

    def test_two_panels_in_one_row_are_not_welded_together(self):
        # Both panels of a row share every grid y. Joining everything at one
        # y produced four boxes twice as wide instead of eight.
        left = Segment(1283.0, 1348.7, 2133.0, 1348.7)
        right = Segment(262.0, 1348.7, 1112.0, 1348.7)
        spans = _merge_collinear([left, right], axis="h")
        self.assertEqual(len(spans), 2)


class DisplayRectTests(unittest.TestCase):
    def test_rotation_180_flips_both_axes_for_rendering(self):
        # The data frame flips y only; the render clip flips both. Using the
        # data x as a clip rendered the panel labelled 1+160 instead of 1+080.
        self.assertEqual(
            _display_rect((1264.0, 1314.0, 2144.0, 1514.0), 2384.0, 1684.0, 180),
            (240.0, 170.0, 1120.0, 370.0),
        )

    def test_rotation_0_is_the_identity(self):
        self.assertEqual(_display_rect((1, 2, 3, 4), 100.0, 100.0, 0), (1, 2, 3, 4))

    def test_other_rotations_are_refused_not_guessed(self):
        with self.assertRaises(CrossSectionError):
            _display_rect((1, 2, 3, 4), 100.0, 100.0, 90)


class TwinCollapseTests(unittest.TestCase):
    def test_copies_of_a_heavy_line_average_to_its_centre(self):
        # Drawn three times, 1.1 pt apart. Taking the top copy would bias every
        # area by a point of elevation.
        copies = [Segment(0, 10.0, 100, 12.0), Segment(0, 11.1, 100, 13.1),
                  Segment(100, 10.9, 0, 8.9)]  # third copy drawn right to left
        merged = _collapse_twins(copies, 2.5)
        self.assertEqual(len(merged), 1)
        self.assertAlmostEqual(merged[0].y0, (10.0 + 11.1 + 8.9) / 3, places=6)

    def test_distinct_lines_are_kept_apart(self):
        merged = _collapse_twins([Segment(0, 10, 100, 10), Segment(0, 40, 100, 40)], 2.5)
        self.assertEqual(len(merged), 2)


class EnvelopeTests(unittest.TestCase):
    # A pavement box under a crowned surface: top edge at the surface, three
    # layer lines below, bottom 0.63 m down.
    SURFACE = [(-100.0, 90.0, 0.0, 100.0), (0.0, 100.0, 100.0, 90.0)]
    BOX = [(-100.0, 80.0, -50.0, 85.0), (-100.0, 54.3, -50.0, 59.3)]

    def test_upper_envelope_is_the_finished_surface(self):
        top = _envelope(self.SURFACE + self.BOX, upper=True)
        self.assertIn((0.0, 100.0), top)
        self.assertNotIn((-100.0, 54.3), top)

    def test_lower_envelope_is_the_structure_bottom_under_the_box_and_the_surface_elsewhere(self):
        bottom = _envelope(self.SURFACE + self.BOX, upper=False)
        self.assertIn((-100.0, 54.3), bottom)
        self.assertIn((100.0, 90.0), bottom)

    def test_lower_envelope_steps_vertically_at_the_box_edge(self):
        # The box side is a vertical stroke and is not in the input. Without a
        # sample just past the edge the envelope ran diagonally up to the next
        # sample, inventing about 0.7 sq m of cut per edge on the real sheets.
        bottom = _envelope(self.SURFACE + self.BOX, upper=False)
        just_left = [y for x, y in bottom if -50.01 <= x <= -50.0]
        just_right = [y for x, y in bottom if -50.0 < x <= -49.99]
        self.assertTrue(just_left and just_right)
        self.assertLess(max(just_left), 60.0)  # still on the box bottom
        self.assertGreater(min(just_right), 90.0)  # already on the surface


class SimplifyTests(unittest.TestCase):
    def test_collinear_points_are_dropped_and_corners_kept(self):
        pts = [(0, 0), (1, 1), (2, 2), (3, 1), (4, 0)]
        self.assertEqual(_simplify(pts, 0.05), [(0, 0), (2, 2), (4, 0)])

    def test_the_crown_survives_dense_sampling(self):
        # Samples a thousandth of a point either side of the peak. A local
        # three-neighbour test saw every one as collinear with its neighbours
        # and flattened the road; the whole surface came out as two points.
        crown = [(-100.0, 90.0), (-0.001, 99.9999), (0.0, 100.0), (0.001, 99.9999), (100.0, 90.0)]
        kept = _simplify(crown, 0.05)
        self.assertIn((0.0, 100.0), kept)
        self.assertEqual(kept[0], (-100.0, 90.0))
        self.assertEqual(kept[-1], (100.0, 90.0))


class RunAssemblyTests(unittest.TestCase):
    def test_takes_the_runs_that_together_cover_the_most(self):
        # Two true ground runs and one stray stroke overlapping the first.
        left = [(-400.0, 0.0), (-10.0, 0.0)]
        right = [(0.0, 0.0), (400.0, 0.0)]
        stray = [(-200.0, 30.0), (150.0, 30.0)]  # wider than either, narrower than both
        chosen = _widest_non_overlapping([stray, left, right])
        self.assertEqual(chosen, [left, right])

    def test_a_single_wide_run_beats_two_narrow_ones(self):
        wide = [(-400.0, 0.0), (400.0, 0.0)]
        a = [(-400.0, 5.0), (-300.0, 5.0)]
        b = [(300.0, 5.0), (400.0, 5.0)]
        self.assertEqual(_widest_non_overlapping([a, wide, b]), [wide])


class RunJoiningTests(unittest.TestCase):
    DESIGN = [(-300.0, 50.0), (0.0, 60.0), (300.0, 50.0)]

    def test_gap_on_the_design_surface_is_closed_along_the_design(self):
        # The consultant does not draw existing ground where it coincides with
        # the new pavement. Following the design there adds no area.
        runs = [[(-300.0, 40.0), (-200.0, 53.3)], [(200.0, 53.3), (300.0, 40.0)]]
        pts, findings = _join_runs(runs, self.DESIGN, coincidence_pt=3.0, short_gap_pt=15.0, metres_per_point_x=CX)
        self.assertIn((0.0, 60.0), pts)
        self.assertEqual([f["code"] for f in findings], ["EXISTING_FOLLOWS_DESIGN"])
        self.assertFalse(findings[0]["blocking"])

    def test_gap_off_the_design_is_closed_straight_and_flagged(self):
        runs = [[(-300.0, 20.0), (-200.0, 20.0)], [(-100.0, 20.0), (300.0, 20.0)]]
        pts, findings = _join_runs(runs, self.DESIGN, coincidence_pt=3.0, short_gap_pt=15.0, metres_per_point_x=CX)
        self.assertNotIn((0.0, 60.0), pts)
        self.assertEqual(findings[0]["code"], "EXISTING_GROUND_GAP")

    def test_a_long_unknown_gap_blocks(self):
        # 100 pt at 1:100 is 3.5 m of ground nobody drew.
        runs = [[(-300.0, 20.0), (-200.0, 20.0)], [(-100.0, 20.0), (300.0, 20.0)]]
        _, findings = _join_runs(runs, self.DESIGN, coincidence_pt=3.0, short_gap_pt=15.0, metres_per_point_x=CX)
        self.assertTrue(findings[0]["blocking"])

    def test_a_short_gap_is_closed_silently(self):
        runs = [[(-300.0, 20.0), (-10.0, 20.0)], [(0.0, 20.0), (300.0, 20.0)]]
        _, findings = _join_runs(runs, self.DESIGN, coincidence_pt=3.0, short_gap_pt=15.0, metres_per_point_x=CX)
        self.assertEqual(findings, [])


class SubgradeTests(unittest.TestCase):
    def test_structure_depth_is_reported_and_areas_measured_to_the_bottom(self):
        # Flat ground at 50 pt; design at 60 pt (fill 10 pt); structure bottom
        # 0.63 m below the design across a 10 m width.
        depth_pt = 0.63 / CY
        width_pt = 10.0 / CX
        panel = _panel(
            existing=[(-width_pt / 2, 50.0), (width_pt / 2, 50.0)],
            design=[(-width_pt / 2, 60.0), (width_pt / 2, 60.0)],
            subgrade=[(-width_pt / 2, 60.0 - depth_pt), (width_pt / 2, 60.0 - depth_pt)],
        )
        _measure_to_subgrade(panel)
        self.assertAlmostEqual(panel.max_structure_depth_m, 0.63, places=3)
        # Bottom sits 0.63 - 10*CY below ground: cut, not fill.
        expected_cut = (depth_pt - 10.0) * CY * 10.0
        self.assertAlmostEqual(panel.cut_to_subgrade_m2, expected_cut, places=3)
        self.assertAlmostEqual(panel.fill_to_subgrade_m2, 0.0, places=6)

    def test_an_impossible_depth_withholds_the_subgrade_numbers(self):
        panel = _panel(
            existing=[(-100.0, 50.0), (100.0, 50.0)],
            design=[(-100.0, 60.0), (100.0, 60.0)],
            subgrade=[(-100.0, 60.0 - 2.0 / CY), (100.0, 60.0 - 2.0 / CY)],
        )
        _measure_to_subgrade(panel)
        self.assertIsNone(panel.cut_to_subgrade_m2)
        self.assertIn("SUBGRADE_DEPTH_SUSPECT", [f["code"] for f in panel.findings])


class CrownCheckTests(unittest.TestCase):
    def test_a_crowned_section_passes(self):
        three = 3.0 / CX
        panel = _panel(design=[(-2 * three, 90.0), (0.0, 100.0), (2 * three, 90.0)])
        _crown_check(panel)
        self.assertEqual(panel.findings, [])

    def test_an_inverted_section_is_questioned_not_refused(self):
        three = 3.0 / CX
        panel = _panel(design=[(-2 * three, 100.0), (0.0, 90.0), (2 * three, 100.0)])
        _crown_check(panel)
        codes = [f["code"] for f in panel.findings]
        self.assertIn("SECTION_ORIENTATION_SUSPECT", codes)
        self.assertFalse(panel.blocking)


class MeasureSectionsTests(unittest.TestCase):
    def _extraction(self, page, panels):
        return {"page_index": page, "_panels": panels}

    def test_volume_needs_the_surface_stated(self):
        p = _panel(cut_area_m2=1.0, fill_area_m2=2.0, cut_to_subgrade_m2=3.0, fill_to_subgrade_m2=1.0)
        with self.assertRaises(TypeError):
            measure_sections([self._extraction(8, [p])], {(8, 1): 1080.0})  # type: ignore[call-arg]
        with self.assertRaises(CrossSectionError):
            measure_sections([self._extraction(8, [p])], {(8, 1): 1080.0}, surface="top")

    def test_finished_and_subgrade_give_different_volumes_from_the_same_panels(self):
        a = _panel(index=1, cut_area_m2=1.0, fill_area_m2=2.0, cut_to_subgrade_m2=4.0, fill_to_subgrade_m2=1.0)
        b = _panel(index=2, cut_area_m2=1.0, fill_area_m2=2.0, cut_to_subgrade_m2=4.0, fill_to_subgrade_m2=1.0)
        ex = [self._extraction(8, [a, b])]
        stations = {(8, 1): 1080.0, (8, 2): 1100.0}
        finished = measure_sections(ex, stations, surface="finished")
        subgrade = measure_sections(ex, stations, surface="subgrade")
        self.assertAlmostEqual(finished["cut_m3"], 20.0)
        self.assertAlmostEqual(subgrade["cut_m3"], 80.0)
        self.assertEqual(subgrade["surface"], "subgrade")

    def test_panels_across_sheets_are_ordered_by_station_not_by_sheet(self):
        p9 = _panel(index=8, cut_area_m2=2.0, fill_area_m2=0.0, cut_to_subgrade_m2=2.0, fill_to_subgrade_m2=0.0)
        p10 = _panel(index=1, cut_area_m2=2.0, fill_area_m2=0.0, cut_to_subgrade_m2=2.0, fill_to_subgrade_m2=0.0)
        result = measure_sections(
            [self._extraction(9, [p10]), self._extraction(8, [p9])],
            {(9, 1): 1260.0, (8, 8): 1240.0},
            surface="finished",
        )
        self.assertEqual(result["stations_used"], [1240.0, 1260.0])
        self.assertAlmostEqual(result["cut_m3"], 40.0)

    def test_an_unnamed_panel_is_reported_and_a_blocked_one_refused(self):
        ok = _panel(index=1, cut_area_m2=1.0, fill_area_m2=0.0, cut_to_subgrade_m2=1.0, fill_to_subgrade_m2=0.0)
        other = _panel(index=2, cut_area_m2=1.0, fill_area_m2=0.0, cut_to_subgrade_m2=1.0, fill_to_subgrade_m2=0.0)
        spare = _panel(index=3)
        result = measure_sections([self._extraction(8, [ok, other, spare])], {(8, 1): 0.0, (8, 2): 20.0}, surface="finished")
        self.assertEqual(result["panels_unnamed"], [[8, 3]])
        blocked = _panel(index=4, cut_area_m2=1.0, fill_area_m2=0.0,
                         findings=[{"code": "X", "blocking": True, "severity": "BLOCKER", "detail": ""}])
        with self.assertRaises(CrossSectionError):
            measure_sections([self._extraction(8, [ok, blocked])], {(8, 1): 0.0, (8, 4): 20.0}, surface="finished")

    def test_the_missing_1_200_section_shows_as_wide_spacing_not_as_an_invented_panel(self):
        # DEMO-001-09 carries 1+180 then 1+220. The volume code must say so.
        a = _panel(index=6, cut_area_m2=1.0, fill_area_m2=0.0, cut_to_subgrade_m2=1.0, fill_to_subgrade_m2=0.0)
        b = _panel(index=7, cut_area_m2=1.0, fill_area_m2=0.0, cut_to_subgrade_m2=1.0, fill_to_subgrade_m2=0.0)
        result = measure_sections([self._extraction(8, [a, b])], {(8, 6): 1180.0, (8, 7): 1220.0}, surface="finished")
        self.assertIn("SECTION_SPACING_TOO_WIDE", {f["code"] for f in result["findings"]})


class SpecTests(unittest.TestCase):
    def test_defaults_are_the_measured_example_plan_values(self):
        spec = SectionSheetSpec()
        self.assertEqual(spec.grid_stroke_pt, 0.12)
        self.assertEqual(spec.surface_stroke_pt, 0.84)
        self.assertGreater(spec.max_dash_pt, 11.3)  # longest measured dash
        self.assertLess(spec.max_dash_pt, 25.5)  # shortest measured design stroke


if __name__ == "__main__":
    unittest.main()
