from __future__ import annotations

import unittest

from screen2xyz_civil.feature_identity import (
    CALLOUT_LEADER,
    DRAWING_TABLE,
    DRAWN_OUTLINE,
    GEOMETRIC_FIT,
    LEGEND_SWATCH,
    PEN_ONLY,
    PRINTED_STATION_OFFSET,
    FeatureIdentityError,
    identification_report,
)


def codes(report):
    return {f["code"] for f in report["findings"]}


class IdentificationTests(unittest.TestCase):
    def test_a_legend_swatch_plus_a_drawn_outline_passes(self):
        report = identification_report(
            identified_by=[LEGEND_SWATCH], boundary_from=[DRAWN_OUTLINE]
        )
        self.assertTrue(report["safe_to_write"])
        self.assertEqual(report["findings"], [])

    def test_a_pen_alone_cannot_identify_a_feature(self):
        # The whole failure mode: a colour or angle filter narrows candidates.
        report = identification_report(identified_by=[PEN_ONLY], boundary_from=[DRAWN_OUTLINE])
        self.assertFalse(report["safe_to_write"])
        self.assertIn("FEATURE_NOT_IDENTIFIED", codes(report))

    def test_a_geometric_fit_alone_cannot_identify_a_feature(self):
        # Five arcs matched a printed 10.0 m radius to 0.01 pt rms; one was the
        # storm line and two were gas. Utilities run concentric with the curb.
        report = identification_report(
            identified_by=[GEOMETRIC_FIT], boundary_from=[PRINTED_STATION_OFFSET]
        )
        self.assertFalse(report["safe_to_write"])
        self.assertIn("FEATURE_NOT_IDENTIFIED", codes(report))

    def test_a_fit_becomes_acceptable_once_a_callout_names_the_feature(self):
        report = identification_report(
            identified_by=[CALLOUT_LEADER, GEOMETRIC_FIT],
            boundary_from=[PRINTED_STATION_OFFSET],
        )
        self.assertTrue(report["safe_to_write"])

    def test_a_table_row_both_names_and_fixes(self):
        report = identification_report(
            identified_by=[DRAWING_TABLE], boundary_from=[DRAWING_TABLE]
        )
        # It names and it fixes, but it is still the only source for both.
        self.assertIn("SAME_SOURCE_IDENTIFIES_AND_BOUNDS", codes(report))


class BoundaryTests(unittest.TestCase):
    def test_a_boundary_from_a_pen_is_refused(self):
        report = identification_report(
            identified_by=[LEGEND_SWATCH], boundary_from=[PEN_ONLY]
        )
        self.assertFalse(report["safe_to_write"])
        self.assertIn("BOUNDARY_FROM_A_PEN", codes(report))

    def test_a_legend_swatch_cannot_bound_because_it_does_not_say_where(self):
        report = identification_report(
            identified_by=[LEGEND_SWATCH], boundary_from=[LEGEND_SWATCH]
        )
        self.assertIn("BOUNDARY_NOT_FIXED_BY_THE_DRAWING", codes(report))

    def test_one_source_may_not_both_find_the_item_and_draw_its_edge(self):
        # The angle filter that found the hatch discarded the outline drawn in
        # the same pen, so the edge could only be the hatch envelope.
        report = identification_report(
            identified_by=[DRAWN_OUTLINE], boundary_from=[DRAWN_OUTLINE]
        )
        self.assertIn("SAME_SOURCE_IDENTIFIES_AND_BOUNDS", codes(report))

    def test_separate_sources_for_identity_and_edge_pass(self):
        report = identification_report(
            identified_by=[LEGEND_SWATCH, PEN_ONLY], boundary_from=[DRAWN_OUTLINE]
        )
        self.assertTrue(report["safe_to_write"])


class CountTests(unittest.TestCase):
    def test_a_count_needs_no_boundary(self):
        report = identification_report(identified_by=[LEGEND_SWATCH], is_a_boundary=False)
        self.assertTrue(report["safe_to_write"])
        self.assertEqual(report["boundary_from"], [])

    def test_an_area_without_a_boundary_source_is_refused_outright(self):
        with self.assertRaises(FeatureIdentityError):
            identification_report(identified_by=[LEGEND_SWATCH])

    def test_a_count_identified_only_by_a_pen_is_still_refused(self):
        report = identification_report(identified_by=[PEN_ONLY], is_a_boundary=False)
        self.assertFalse(report["safe_to_write"])


class InputTests(unittest.TestCase):
    def test_an_unknown_source_is_refused_rather_than_ignored(self):
        with self.assertRaises(FeatureIdentityError):
            identification_report(identified_by=["I LOOKED AT IT"], boundary_from=[DRAWN_OUTLINE])

    def test_an_empty_claim_is_refused(self):
        with self.assertRaises(FeatureIdentityError):
            identification_report(identified_by=[], boundary_from=[DRAWN_OUTLINE])

    def test_sources_are_case_insensitive_and_trimmed(self):
        report = identification_report(
            identified_by=["  legend_swatch "], boundary_from=["drawn_outline"]
        )
        self.assertTrue(report["safe_to_write"])
        self.assertEqual(report["identified_by"], [LEGEND_SWATCH])


if __name__ == "__main__":
    unittest.main()
