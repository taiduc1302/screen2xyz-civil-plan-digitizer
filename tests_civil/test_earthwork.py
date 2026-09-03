from __future__ import annotations

import unittest

from screen2xyz_civil.earthwork import (
    EarthworkError,
    SectionArea,
    average_end_area_volume,
    compare_to_tender,
    section_areas_between_surfaces,
    tonnes_from_volume,
)


class SectionAreaTests(unittest.TestCase):
    def test_areas_are_magnitudes_and_reject_a_signed_number(self):
        with self.assertRaises(EarthworkError):
            SectionArea(station_m=1000.0, cut_area_m2=-4.0)

    def test_a_section_may_carry_both_cut_and_fill(self):
        section = SectionArea(station_m=1000.0, cut_area_m2=3.0, fill_area_m2=1.5)
        self.assertEqual(section.to_dict()["cut_area_m2"], 3.0)
        self.assertEqual(section.to_dict()["fill_area_m2"], 1.5)


class AverageEndAreaTests(unittest.TestCase):
    def test_prism_of_constant_area_is_area_times_length(self):
        result = average_end_area_volume(
            [
                SectionArea(station_m=1000.0, cut_area_m2=10.0),
                SectionArea(station_m=1020.0, cut_area_m2=10.0),
            ]
        )
        self.assertAlmostEqual(result["cut_m3"], 200.0, places=6)
        self.assertAlmostEqual(result["fill_m3"], 0.0, places=6)

    def test_linear_taper_uses_the_mean_of_the_end_areas(self):
        result = average_end_area_volume(
            [
                SectionArea(station_m=0.0, cut_area_m2=0.0),
                SectionArea(station_m=10.0, cut_area_m2=8.0),
            ]
        )
        self.assertAlmostEqual(result["cut_m3"], 40.0, places=6)

    def test_cut_and_fill_are_reported_separately_and_never_netted(self):
        result = average_end_area_volume(
            [
                SectionArea(station_m=0.0, cut_area_m2=6.0, fill_area_m2=2.0),
                SectionArea(station_m=10.0, cut_area_m2=6.0, fill_area_m2=2.0),
            ]
        )
        self.assertAlmostEqual(result["cut_m3"], 60.0, places=6)
        self.assertAlmostEqual(result["fill_m3"], 20.0, places=6)
        self.assertIn("must not be netted", result["net_note"])

    def test_three_sections_sum_their_intervals(self):
        result = average_end_area_volume(
            [
                SectionArea(station_m=0.0, cut_area_m2=4.0),
                SectionArea(station_m=10.0, cut_area_m2=6.0),
                SectionArea(station_m=20.0, cut_area_m2=2.0),
            ]
        )
        # (4+6)/2*10 + (6+2)/2*10
        self.assertAlmostEqual(result["cut_m3"], 50.0 + 40.0, places=6)
        self.assertEqual(len(result["intervals"]), 2)

    def test_range_is_reported_and_never_extrapolated(self):
        result = average_end_area_volume(
            [
                SectionArea(station_m=1080.0, cut_area_m2=5.0),
                SectionArea(station_m=1100.0, cut_area_m2=5.0),
            ]
        )
        self.assertEqual(result["from_station_m"], 1080.0)
        self.assertEqual(result["to_station_m"], 1100.0)
        self.assertEqual(result["covered_length_m"], 20.0)
        codes = {finding["code"] for finding in result["findings"]}
        self.assertIn("RANGE_NOT_EXTRAPOLATED", codes)

    def test_wide_section_spacing_is_flagged(self):
        result = average_end_area_volume(
            [
                SectionArea(station_m=0.0, cut_area_m2=5.0),
                SectionArea(station_m=60.0, cut_area_m2=5.0),
            ]
        )
        codes = {finding["code"] for finding in result["findings"]}
        self.assertIn("SECTION_SPACING_TOO_WIDE", codes)

    def test_normal_spacing_is_not_flagged(self):
        result = average_end_area_volume(
            [
                SectionArea(station_m=0.0, cut_area_m2=5.0),
                SectionArea(station_m=20.0, cut_area_m2=5.0),
            ]
        )
        codes = {finding["code"] for finding in result["findings"]}
        self.assertNotIn("SECTION_SPACING_TOO_WIDE", codes)

    def test_out_of_order_stations_are_rejected(self):
        with self.assertRaises(EarthworkError):
            average_end_area_volume(
                [
                    SectionArea(station_m=20.0, cut_area_m2=5.0),
                    SectionArea(station_m=10.0, cut_area_m2=5.0),
                ]
            )

    def test_duplicate_stations_are_rejected(self):
        with self.assertRaises(EarthworkError):
            average_end_area_volume(
                [
                    SectionArea(station_m=10.0, cut_area_m2=5.0),
                    SectionArea(station_m=10.0, cut_area_m2=6.0),
                ]
            )

    def test_a_single_section_cannot_produce_a_volume(self):
        with self.assertRaises(EarthworkError):
            average_end_area_volume([SectionArea(station_m=0.0, cut_area_m2=5.0)])


class TonnesConversionTests(unittest.TestCase):
    def test_conversion_uses_the_supplied_density(self):
        result = tonnes_from_volume(100.0, density_t_per_m3=2.1, basis="Geotech 24-9924")
        self.assertAlmostEqual(result["tonnes"], 210.0, places=6)
        self.assertEqual(result["classification"], "ESTIMATOR_INPUT_NOT_A_MEASUREMENT")

    def test_density_must_be_supplied_and_positive(self):
        with self.assertRaises(EarthworkError):
            tonnes_from_volume(100.0, density_t_per_m3=0.0, basis="anything")

    def test_an_unsourced_density_is_refused(self):
        with self.assertRaises(EarthworkError):
            tonnes_from_volume(100.0, density_t_per_m3=2.1, basis="   ")


class TenderComparisonTests(unittest.TestCase):
    def test_close_measurement_is_within_tolerance(self):
        result = compare_to_tender(2100.0, 2160.0, unit="m3")
        self.assertTrue(result["within_tolerance"])

    def test_large_gap_is_flagged_and_the_tendered_quantity_still_governs(self):
        result = compare_to_tender(1200.0, 2160.0, unit="m3")
        self.assertFalse(result["within_tolerance"])
        self.assertIn("tendered quantity still governs", result["action"])

    def test_tendered_quantity_must_be_positive(self):
        with self.assertRaises(EarthworkError):
            compare_to_tender(10.0, 0.0, unit="m3")



class SectionAreaFromSurfacesTests(unittest.TestCase):
    # Deliberately anisotropic, like a real cross-section sheet drawn 1:100
    # horizontal against 1:50 vertical. Converting per axis *before* computing
    # the area is the whole point; doing it after with one factor is the
    # mistake that produced a quantity out by the ratio of the two axes.
    CX = 0.0352778
    CY = 0.0176389

    def _flat(self, y_points, width_m=10.0):
        return [(0.0, y_points), (width_m / self.CX, y_points)]

    def test_design_below_ground_is_pure_cut(self):
        result = section_areas_between_surfaces(
            existing=self._flat(0.0),
            proposed=self._flat(-1.0 / self.CY),
            metres_per_point_x=self.CX,
            metres_per_point_y=self.CY,
            station_m=1080.0,
        )
        self.assertAlmostEqual(result["cut_area_m2"], 10.0, places=6)
        self.assertAlmostEqual(result["fill_area_m2"], 0.0, places=6)

    def test_design_above_ground_is_pure_fill(self):
        result = section_areas_between_surfaces(
            existing=self._flat(0.0),
            proposed=self._flat(1.0 / self.CY),
            metres_per_point_x=self.CX,
            metres_per_point_y=self.CY,
            station_m=1080.0,
        )
        self.assertAlmostEqual(result["fill_area_m2"], 10.0, places=6)
        self.assertAlmostEqual(result["cut_area_m2"], 0.0, places=6)

    def test_crossing_surfaces_split_into_cut_and_fill_at_the_crossing(self):
        result = section_areas_between_surfaces(
            existing=self._flat(0.0),
            proposed=[(0.0, -1.0 / self.CY), (10.0 / self.CX, 1.0 / self.CY)],
            metres_per_point_x=self.CX,
            metres_per_point_y=self.CY,
            station_m=1100.0,
        )
        self.assertAlmostEqual(result["cut_area_m2"], 2.5, places=6)
        self.assertAlmostEqual(result["fill_area_m2"], 2.5, places=6)
        codes = {f["code"] for f in result["findings"]}
        self.assertIn("SECTION_HAS_BOTH_CUT_AND_FILL", codes)

    def test_the_two_axis_factors_are_applied_separately(self):
        # Same drawn geometry, vertical factor doubled -> area doubles. If a
        # single factor were used the result would be out by its square.
        common = dict(
            existing=self._flat(0.0),
            proposed=self._flat(-1.0 / self.CY),
            metres_per_point_x=self.CX,
            station_m=0.0,
        )
        single = section_areas_between_surfaces(metres_per_point_y=self.CY, **common)
        doubled = section_areas_between_surfaces(metres_per_point_y=self.CY * 2, **common)
        self.assertAlmostEqual(doubled["cut_area_m2"], single["cut_area_m2"] * 2, places=6)

    def test_only_the_shared_width_is_measured_and_the_rest_is_reported(self):
        result = section_areas_between_surfaces(
            existing=[(0.0, 0.0), (20.0 / self.CX, 0.0)],
            proposed=[(0.0, -1.0 / self.CY), (10.0 / self.CX, -1.0 / self.CY)],
            metres_per_point_x=self.CX,
            metres_per_point_y=self.CY,
            station_m=0.0,
        )
        self.assertAlmostEqual(result["measured_width_m"], 10.0, places=6)
        self.assertAlmostEqual(result["cut_area_m2"], 10.0, places=6)
        codes = {f["code"] for f in result["findings"]}
        self.assertIn("SECTION_PARTIALLY_COVERED", codes)

    def test_a_surface_that_doubles_back_is_refused(self):
        with self.assertRaises(EarthworkError):
            section_areas_between_surfaces(
                existing=[(0.0, 0.0), (100.0, 0.0), (50.0, 0.0)],
                proposed=self._flat(-1.0 / self.CY),
                metres_per_point_x=self.CX,
                metres_per_point_y=self.CY,
                station_m=0.0,
            )

    def test_surfaces_that_do_not_overlap_are_refused(self):
        with self.assertRaises(EarthworkError):
            section_areas_between_surfaces(
                existing=[(0.0, 0.0), (100.0, 0.0)],
                proposed=[(500.0, 0.0), (600.0, 0.0)],
                metres_per_point_x=self.CX,
                metres_per_point_y=self.CY,
                station_m=0.0,
            )

    def test_result_feeds_straight_into_the_volume_calculation(self):
        a = section_areas_between_surfaces(
            existing=self._flat(0.0), proposed=self._flat(-1.0 / self.CY),
            metres_per_point_x=self.CX, metres_per_point_y=self.CY, station_m=1080.0)
        b = section_areas_between_surfaces(
            existing=self._flat(0.0), proposed=self._flat(-1.0 / self.CY),
            metres_per_point_x=self.CX, metres_per_point_y=self.CY, station_m=1100.0)
        volume = average_end_area_volume([a["section"], b["section"]])
        self.assertAlmostEqual(volume["cut_m3"], 200.0, places=6)

if __name__ == "__main__":
    unittest.main()
