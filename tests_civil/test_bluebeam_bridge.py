from __future__ import annotations

import unittest

from screen2xyz_civil.bluebeam_bridge import (
    BridgeError,
    MAX_LABEL_CHARS,
    audit_host_text,
    cross_check_quantity,
    markup_text_plan,
    page_identity_report,
    perimeter,
    polygon_health,
    reconcile,
    render_shows_host_state,
    self_intersections,
    shoelace_area,
)


# Synthetic geometry only. Each case reproduces the shape of a failure seen on a
# real sheet without carrying any coordinate from a proprietary drawing.
CLEAN_RECT = [(100.0, 100.0), (300.0, 100.0), (300.0, 180.0), (100.0, 180.0)]

# A sane local outline with one vertex dragged far away and back - the shape
# that a host reported as a small, plausible area with a nonsense perimeter.
SPIKED_RECT = [
    (100.0, 100.0),
    (300.0, 100.0),
    (300.0, 180.0),
    (2000.0, 190.0),
    (2000.0, 195.0),
    (100.0, 180.0),
]

BOWTIE = [(0.0, 0.0), (100.0, 100.0), (100.0, 0.0), (0.0, 100.0)]


class GeometryPrimitiveTests(unittest.TestCase):
    def test_shoelace_area_of_known_rectangle(self):
        self.assertAlmostEqual(shoelace_area(CLEAN_RECT), 200.0 * 80.0, places=6)

    def test_perimeter_closed_and_open_differ_by_closing_segment(self):
        closed = perimeter(CLEAN_RECT, closed=True)
        open_path = perimeter(CLEAN_RECT, closed=False)
        self.assertAlmostEqual(closed - open_path, 80.0, places=6)

    def test_area_requires_three_points(self):
        with self.assertRaises(BridgeError):
            shoelace_area([(0.0, 0.0), (1.0, 1.0)])

    def test_non_finite_coordinates_are_rejected(self):
        with self.assertRaises(BridgeError):
            perimeter([(0.0, 0.0), (float("inf"), 1.0)])


class SelfIntersectionTests(unittest.TestCase):
    def test_clean_rectangle_has_no_crossings(self):
        self.assertEqual(self_intersections(CLEAN_RECT), [])

    def test_bowtie_is_detected(self):
        self.assertTrue(self_intersections(BOWTIE))

    def test_triangle_cannot_self_intersect(self):
        self.assertEqual(self_intersections([(0.0, 0.0), (10.0, 0.0), (5.0, 8.0)]), [])


class PolygonHealthTests(unittest.TestCase):
    def test_clean_rectangle_is_safe_to_write(self):
        report = polygon_health(CLEAN_RECT, metres_per_unit=0.1)
        self.assertTrue(report["safe_to_write"])
        self.assertFalse(report["blocking"])
        self.assertEqual(report["self_intersections"], [])
        self.assertAlmostEqual(report["area_m2"], 200.0 * 80.0 * 0.01, places=6)

    def test_self_intersecting_polygon_blocks_the_write(self):
        report = polygon_health(BOWTIE)
        self.assertFalse(report["safe_to_write"])
        self.assertTrue(report["blocking"])
        codes = {finding["code"] for finding in report["findings"]}
        self.assertIn("POLYGON_SELF_INTERSECTS", codes)

    def test_stray_vertex_outline_blocks_the_write(self):
        # The real 2026-09-02 failure: a simple, non-self-intersecting outline
        # with one vertex dragged far away. It must not be writable.
        report = polygon_health(SPIKED_RECT)
        self.assertEqual(report["self_intersections"], [])
        self.assertFalse(report["safe_to_write"])
        codes = {finding["code"] for finding in report["findings"]}
        self.assertIn("POLYGON_SLIVER_SUSPECTED", codes)

    def test_sliver_threshold_is_tunable_for_a_deliberate_override(self):
        report = polygon_health(SPIKED_RECT, sliver_ratio_threshold=1000.0)
        self.assertTrue(report["safe_to_write"])

    def test_long_thin_corridor_is_not_reported_as_a_sliver(self):
        # A real road corridor is legitimately elongated and must not trip the
        # sliver guard, or the check becomes noise the operator learns to ignore.
        corridor = [(0.0, 0.0), (1600.0, 0.0), (1600.0, 150.0), (0.0, 150.0)]
        report = polygon_health(corridor)
        self.assertTrue(report["safe_to_write"])
        self.assertEqual(report["findings"], [])

    def test_metres_per_unit_must_be_positive(self):
        with self.assertRaises(BridgeError):
            polygon_health(CLEAN_RECT, metres_per_unit=0.0)


class CrossCheckQuantityTests(unittest.TestCase):
    def test_agreeing_values_pass(self):
        result = cross_check_quantity(expected=17.6388, reported=17.64, unit="m")
        self.assertTrue(result["agrees"])
        self.assertFalse(result["blocking"])
        self.assertIsNone(result["integer_ratio"])

    def test_exact_integer_ratio_is_called_out_as_a_host_fault(self):
        result = cross_check_quantity(expected=1682.4, reported=336.48, unit="m2")
        self.assertFalse(result["agrees"])
        self.assertTrue(result["blocking"])
        self.assertEqual(result["integer_ratio"], 5)
        codes = {finding["code"] for finding in result["findings"]}
        self.assertIn("HOST_QUANTITY_INTEGER_RATIO", codes)

    def test_ordinary_mismatch_is_reported_without_an_integer_ratio(self):
        result = cross_check_quantity(expected=100.0, reported=87.3, unit="m2")
        self.assertTrue(result["blocking"])
        self.assertIsNone(result["integer_ratio"])
        codes = {finding["code"] for finding in result["findings"]}
        self.assertIn("HOST_QUANTITY_MISMATCH", codes)

    def test_expected_quantity_must_be_positive(self):
        with self.assertRaises(BridgeError):
            cross_check_quantity(expected=0.0, reported=1.0, unit="m")


class MarkupTextTests(unittest.TestCase):
    def test_label_is_never_populated_and_provenance_is_handed_back(self):
        plan = markup_text_plan(
            rule_id="DITCH_INFILL",
            instance="North driveway crossing",
            quantity_text="19.79 sq m",
            sheet_label="DEMO-001-03",
            provenance="Long provenance paragraph that must not reach the drawing." * 5,
        )
        self.assertEqual(plan["label"], "")
        self.assertTrue(plan["session_notes"])
        self.assertIn("DITCH_INFILL", plan["subject"])

    def test_overlong_subject_is_trimmed(self):
        plan = markup_text_plan(
            rule_id="ROAD_WIDENING_FULL_STRUCTURE",
            instance="x" * 200,
        )
        self.assertLessEqual(len(plan["subject"]), 96)
        codes = {finding["code"] for finding in plan["findings"]}
        self.assertIn("SUBJECT_TRUNCATED", codes)

    def test_rule_id_is_required(self):
        with self.assertRaises(BridgeError):
            markup_text_plan(rule_id="   ", instance="anything")

    def test_audit_flags_host_markups_that_render_as_clutter(self):
        audit = audit_host_text(
            {
                "AAA-1": {"subject": "31.02 | driveway", "label": ""},
                "BBB-2": {"subject": "31.02 | driveway", "label": "y" * (MAX_LABEL_CHARS + 1)},
            }
        )
        self.assertFalse(audit["clean"])
        self.assertEqual(len(audit["offenders"]), 1)
        self.assertEqual(audit["offenders"][0]["markup_id"], "BBB-2")

    def test_audit_passes_clean_markups(self):
        audit = audit_host_text({"AAA-1": {"subject": "33.01 | culvert", "label": ""}})
        self.assertTrue(audit["clean"])


class PageIdentityTests(unittest.TestCase):
    def test_drawing_number_found_in_page_text_confirms_the_page(self):
        report = page_identity_report(
            expected_drawing_number="DEMO-001-03",
            page_text="CONSULTANT DWG. NO. DEMO-001-03  SHEET 03 OF 17",
            viewer_page_label="03 STA 1+000",
        )
        self.assertTrue(report["confirmed"])
        self.assertFalse(report["blocking"])

    def test_missing_drawing_number_blocks(self):
        report = page_identity_report(
            expected_drawing_number="DEMO-001-03",
            page_text="CONSULTANT DWG. NO. DEMO-001-05",
        )
        self.assertFalse(report["confirmed"])
        self.assertTrue(report["blocking"])

    def test_viewer_label_that_disagrees_is_flagged_but_not_blocking(self):
        report = page_identity_report(
            expected_drawing_number="DEMO-001-03",
            page_text="DEMO-001-03",
            viewer_page_label="01 STA 1+000 TO 1+140",
        )
        self.assertTrue(report["confirmed"])
        codes = {finding["code"] for finding in report["findings"]}
        self.assertIn("VIEWER_LABEL_DIFFERS_FROM_DRAWING_NUMBER", codes)
        self.assertFalse(report["blocking"])

    def test_expected_drawing_number_is_required(self):
        with self.assertRaises(BridgeError):
            page_identity_report(expected_drawing_number="", page_text="anything")


class RenderTrustTests(unittest.TestCase):
    def test_matching_counts_support_visual_verification(self):
        report = render_shows_host_state(host_markup_count=4, rendered_annotation_count=4)
        self.assertTrue(report["visual_verification_supported"])
        self.assertEqual(report["findings"], [])

    def test_unsaved_host_state_is_flagged(self):
        report = render_shows_host_state(host_markup_count=11, rendered_annotation_count=0)
        self.assertFalse(report["visual_verification_supported"])
        codes = {finding["code"] for finding in report["findings"]}
        self.assertIn("RENDER_STALE_VS_HOST", codes)


class _FakeProvenance:
    def __init__(self, markup_id: str = "") -> None:
        self.extra = {"bluebeam_markup_id": markup_id} if markup_id else {}


class _FakeTakeoff:
    def __init__(self, takeoff_id: str, rule_id: str, markup_id: str = "") -> None:
        self.id = takeoff_id
        self.rule_id = rule_id
        self.provenance = _FakeProvenance(markup_id)


class _FakeSession:
    def __init__(self, measurements) -> None:
        self.measurements = measurements


class ReconcileTests(unittest.TestCase):
    def test_fully_linked_session_is_in_sync(self):
        session = _FakeSession(
            [
                _FakeTakeoff("TK-0001", "DRIVEWAY_CULVERT_300", "AAA-1"),
                _FakeTakeoff("TK-0002", "DITCH_INFILL", "BBB-2"),
            ]
        )
        report = reconcile(session, ["AAA-1", "BBB-2"])
        self.assertTrue(report["in_sync"])
        self.assertEqual(report["linked_count"], 2)
        self.assertEqual(report["host_markups_without_proposal"], [])

    def test_host_markup_without_a_proposal_breaks_sync(self):
        session = _FakeSession([_FakeTakeoff("TK-0001", "DITCH_INFILL", "AAA-1")])
        report = reconcile(session, ["AAA-1", "ORPHAN-9"])
        self.assertFalse(report["in_sync"])
        self.assertEqual(report["host_markups_without_proposal"], ["ORPHAN-9"])

    def test_proposal_naming_a_deleted_markup_is_reported(self):
        session = _FakeSession([_FakeTakeoff("TK-0001", "DITCH_INFILL", "GONE-1")])
        report = reconcile(session, [])
        statuses = {row["status"] for row in report["rows"]}
        self.assertIn("HOST_MARKUP_MISSING", statuses)
        self.assertFalse(report["in_sync"])

    def test_proposal_without_any_host_link_is_reported(self):
        session = _FakeSession([_FakeTakeoff("TK-0001", "DITCH_INFILL")])
        report = reconcile(session, [])
        statuses = {row["status"] for row in report["rows"]}
        self.assertIn("NO_HOST_LINK", statuses)


if __name__ == "__main__":
    unittest.main()
