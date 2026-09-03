"""Deterministic tests for the plan-sheet layer extraction helpers.

Fixtures are synthetic. They reproduce the *shape* of the failures seen on a
real owner-machine sheet without carrying any drawing-derived coordinates into
the repository.
"""

from __future__ import annotations

import unittest

from screen2xyz_civil.plan_layers import (
    StationFrame,
    Viewport,
    band_extents,
    check_against_printed,
    classify_glyph,
    colour_census,
    fit_station_frame,
    offsets_from_centreline,
    polyline_length_m,
    sheet_overlap_report,
    shoelace_area_m2,
    single_viewport_check,
    split_runs,
    viewport_of,
)

PLAN = Viewport("PLAN", 100.0, 800.0, 2000.0, 1500.0, 0.08, 0.08)
PROFILE = Viewport("PROFILE", 100.0, 30.0, 2000.0, 790.0, 0.08, 0.016)


class ViewportTests(unittest.TestCase):
    def test_rejects_unnormalised_bounds(self) -> None:
        with self.assertRaises(ValueError):
            Viewport("bad", 10.0, 10.0, 5.0, 20.0, 0.08, 0.08)

    def test_rejects_non_positive_scale(self) -> None:
        with self.assertRaises(ValueError):
            Viewport("bad", 0.0, 0.0, 10.0, 10.0, 0.08, 0.0)

    def test_isotropy_flag_distinguishes_plan_from_profile(self) -> None:
        self.assertTrue(PLAN.isotropic)
        self.assertFalse(PROFILE.isotropic)

    def test_area_conversion_uses_both_axis_factors(self) -> None:
        self.assertAlmostEqual(PLAN.area_m2(10_000.0), 64.0, places=6)
        self.assertAlmostEqual(PROFILE.area_m2(10_000.0), 12.8, places=6)

    def test_profile_and_plan_area_differ_by_the_scale_ratio(self) -> None:
        # The "x5 artifact": identical vertices read in the wrong viewport.
        ratio = PLAN.area_m2(1.0) / PROFILE.area_m2(1.0)
        self.assertAlmostEqual(ratio, 5.0, places=9)


class SingleViewportCheckTests(unittest.TestCase):
    def test_plan_geometry_is_safe(self) -> None:
        square = [(200, 900), (400, 900), (400, 1000), (200, 1000)]
        result = single_viewport_check(square, [PLAN, PROFILE])
        self.assertTrue(result["safe_to_write"])
        self.assertEqual(result["viewport"], "PLAN")

    def test_profile_geometry_is_blocked_as_anisotropic(self) -> None:
        square = [(200, 100), (400, 100), (400, 300), (200, 300)]
        result = single_viewport_check(square, [PLAN, PROFILE])
        self.assertFalse(result["safe_to_write"])
        self.assertTrue(any("anisotropic" in f for f in result["findings"]))

    def test_geometry_spanning_two_viewports_is_blocked(self) -> None:
        straddling = [(200, 700), (400, 700), (400, 900), (200, 900)]
        result = single_viewport_check(straddling, [PLAN, PROFILE])
        self.assertFalse(result["safe_to_write"])

    def test_vertex_outside_every_viewport_is_reported(self) -> None:
        stray = [(200, 900), (400, 900), (400, 1000), (5000, 1000)]
        result = single_viewport_check(stray, [PLAN, PROFILE])
        self.assertFalse(result["safe_to_write"])
        self.assertTrue(any("no declared viewport" in f for f in result["findings"]))

    def test_empty_geometry_is_not_safe(self) -> None:
        self.assertFalse(single_viewport_check([], [PLAN])["safe_to_write"])

    def test_viewport_of_returns_none_outside(self) -> None:
        self.assertIsNone(viewport_of((5000, 5000), [PLAN, PROFILE]))


class StationFrameTests(unittest.TestCase):
    def test_fit_recovers_a_linear_chainage(self) -> None:
        frame = fit_station_frame([(1000.0, 1000.0), (887.0, 1010.0), (774.0, 1020.0)])
        self.assertAlmostEqual(frame.points_per_metre, 11.3, places=1)
        self.assertAlmostEqual(frame.station(1000.0), 1000.0, places=2)

    def test_round_trip_station_and_raw_x(self) -> None:
        frame = StationFrame(points_per_metre=11.34, ref_raw_x=1000.0, ref_station_m=1080.0)
        self.assertAlmostEqual(frame.raw_x(frame.station(742.0)), 742.0, places=6)

    def test_two_samples_are_refused(self) -> None:
        with self.assertRaises(ValueError):
            fit_station_frame([(1000.0, 1000.0), (887.0, 1010.0)])

    def test_a_misread_label_is_refused(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            fit_station_frame(
                [(1000.0, 1000.0), (887.0, 1010.0), (774.0, 1055.0)]
            )
        self.assertIn("disagree", str(ctx.exception))


class GlyphAndRunTests(unittest.TestCase):
    def test_flow_arrow_and_scallop_are_separated(self) -> None:
        self.assertEqual(classify_glyph(13.4, 3.4), "flow_arrow")
        self.assertEqual(classify_glyph(11.6, 5.9), "vegetation_scallop")

    def test_degenerate_glyph_is_unknown(self) -> None:
        self.assertEqual(classify_glyph(10.0, 0.0), "unknown")
        self.assertEqual(classify_glyph(4.0, 4.0), "unknown")

    def test_split_runs_breaks_at_a_crossing(self) -> None:
        xs = [100, 112, 124, 136, 300, 312, 324]
        runs = split_runs(xs, metres_per_point=0.08, max_gap_m=6.0)
        self.assertEqual([len(r) for r in runs], [4, 3])

    def test_split_runs_keeps_a_dense_chain_whole(self) -> None:
        xs = [100, 112, 124, 136, 148]
        self.assertEqual(len(split_runs(xs, metres_per_point=0.08)), 1)

    def test_split_runs_handles_empty_input(self) -> None:
        self.assertEqual(split_runs([], metres_per_point=0.08), [])


class MeasurementTests(unittest.TestCase):
    def test_shoelace_area_in_plan_viewport(self) -> None:
        square = [(200, 900), (300, 900), (300, 1000), (200, 1000)]
        self.assertAlmostEqual(shoelace_area_m2(square, PLAN), 64.0, places=6)

    def test_degenerate_polygon_has_no_area(self) -> None:
        self.assertEqual(shoelace_area_m2([(0, 0), (1, 1)], PLAN), 0.0)

    def test_polyline_length_in_plan_viewport(self) -> None:
        self.assertAlmostEqual(
            polyline_length_m([(200, 900), (300, 900)], PLAN), 8.0, places=6
        )

    def test_length_in_anisotropic_viewport_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            polyline_length_m([(200, 100), (300, 100)], PROFILE)

    def test_band_extents_drop_sparse_columns(self) -> None:
        columns = [(10.0, [1.0, 2.0, 3.0]), (20.0, [5.0]), (30.0, [4.0, 6.0, 8.0])]
        self.assertEqual(
            band_extents(columns), [(10.0, 1.0, 3.0), (30.0, 4.0, 8.0)]
        )

    def test_offsets_from_centreline_label_sides(self) -> None:
        rows = offsets_from_centreline([1150.0, 1300.0], 1225.0, metres_per_point=0.08)
        self.assertEqual(rows[0][2], "L")
        self.assertEqual(rows[1][2], "R")
        self.assertAlmostEqual(rows[0][1], 6.0, places=6)


class ValidationTests(unittest.TestCase):
    def test_measurement_matching_a_printed_dimension_passes(self) -> None:
        result = check_against_printed(9.69, 9.70)
        self.assertTrue(result["agrees"])
        self.assertFalse(result["blocking"])

    def test_measurement_missing_a_printed_dimension_blocks(self) -> None:
        result = check_against_printed(15.87, 9.70)
        self.assertTrue(result["blocking"])
        self.assertTrue(result["findings"])

    def test_colour_census_orders_by_frequency(self) -> None:
        pixels = [(255, 255, 255)] * 3 + [(229, 229, 229)] * 2 + [(0, 0, 0)]
        census = colour_census(pixels)
        self.assertEqual(census[0], ((255, 255, 255), 3))
        self.assertEqual(census[1], ((229, 229, 229), 2))

    def test_overlapping_matchlines_are_reported(self) -> None:
        report = sheet_overlap_report(1157.0, 1137.8, agreed_cut_station=1140.0)
        self.assertAlmostEqual(report["overlap_m"], 19.2, places=2)
        self.assertTrue(report["blocking"])
        self.assertTrue(report["cut_inside_overlap"])

    def test_cut_outside_the_overlap_is_flagged(self) -> None:
        report = sheet_overlap_report(1157.0, 1137.8, agreed_cut_station=1100.0)
        self.assertFalse(report["cut_inside_overlap"])
        self.assertTrue(any("neither takeoff" in f for f in report["findings"]))

    def test_shared_matchline_reports_no_overlap(self) -> None:
        report = sheet_overlap_report(1140.0, 1140.0)
        self.assertEqual(report["overlap_m"], 0.0)
        self.assertFalse(report["blocking"])


if __name__ == "__main__":
    unittest.main()
