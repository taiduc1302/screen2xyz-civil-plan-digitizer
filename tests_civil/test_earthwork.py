from __future__ import annotations

import unittest

from screen2xyz_civil.earthwork import (
    EarthworkError,
    SectionArea,
    average_end_area_volume,
    compare_to_tender,
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


if __name__ == "__main__":
    unittest.main()
