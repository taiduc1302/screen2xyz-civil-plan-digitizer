from __future__ import annotations

import unittest

from screen2xyz_civil.takeoff import (
    APPROVED,
    EDITED_AND_APPROVED,
    LINE,
    POLYGON,
    REVIEW_REQUIRED,
    TakeoffError,
    TakeoffGeometry,
    TakeoffMeasurement,
    TakeoffVertex,
    approve_takeoff,
    approved_totals,
    clear_takeoff_flag,
    correction_training_record,
    correct_takeoff_geometry,
    derived_area_m2,
    new_takeoff_proposal,
    quantity_for,
    reject_takeoff,
    set_takeoff_flag,
    takeoff_qa_summary,
    takeoff_rule,
)


NOW = "2026-09-02T10:30:00-07:00"
LATER = "2026-09-02T10:31:00-07:00"


def line(*coords: tuple[float, float]) -> TakeoffGeometry:
    return TakeoffGeometry(
        LINE,
        tuple(TakeoffVertex(x, y) for x, y in coords),
    )


def polygon(*coords: tuple[float, float]) -> TakeoffGeometry:
    return TakeoffGeometry(
        POLYGON,
        tuple(TakeoffVertex(x, y) for x, y in coords),
    )


def proposal(
    rule_id: str,
    geometry: TakeoffGeometry,
    *,
    takeoff_id: str = "TK-0001",
    generated_by: str = "agent",
    flags: tuple[str, ...] = (),
) -> TakeoffMeasurement:
    return new_takeoff_proposal(
        takeoff_id=takeoff_id,
        rule_id=rule_id,
        page_index=2,
        page_label="03",
        geometry=geometry,
        now=NOW,
        source_engine="synthetic-test",
        source_method="VECTOR_PROPOSAL",
        generated_by=generated_by,
        confidence=0.8,
        flags=flags,
    )


class TakeoffDomainTests(unittest.TestCase):
    def test_line_quantity_uses_reviewed_scale(self):
        item = proposal("DRIVEWAY_CULVERT_300", line((0, 0), (30, 40)))
        self.assertAlmostEqual(quantity_for(item, metres_per_pixel=0.1), 5.0)

    def test_polygon_quantity_uses_shoelace_area(self):
        item = proposal(
            "ROAD_WIDENING_FULL_STRUCTURE",
            polygon((0, 0), (20, 0), (20, 10), (0, 10)),
        )
        self.assertAlmostEqual(quantity_for(item, metres_per_pixel=0.5), 50.0)

    def test_degenerate_polygon_is_rejected(self):
        with self.assertRaises(TakeoffError):
            polygon((0, 0), (10, 0), (20, 0))

    def test_anchor_is_reference_and_cannot_be_approved(self):
        item = proposal(
            "ANCHOR_ROADWORKS_EXTENT",
            polygon((0, 0), (20, 0), (20, 20), (0, 20)),
        )
        self.assertFalse(item.summable)
        with self.assertRaises(TakeoffError):
            approve_takeoff(
                item,
                metres_per_pixel=0.5,
                scale_verified=True,
                now=LATER,
            )

    def test_area_takeoff_approves_after_scale_gate(self):
        item = proposal(
            "DITCH_INFILL",
            polygon((0, 0), (10, 0), (10, 5), (0, 5)),
        )
        approve_takeoff(
            item,
            metres_per_pixel=0.2,
            scale_verified=True,
            now=LATER,
        )
        self.assertEqual(item.review_status, APPROVED)
        self.assertAlmostEqual(item.quantity or 0.0, 2.0)

    def test_culvert_centerline_can_be_polyline(self):
        item = proposal(
            "DRIVEWAY_CULVERT_300",
            line((0, 0), (3, 4), (6, 8)),
        )
        approve_takeoff(
            item,
            metres_per_pixel=1.0,
            scale_verified=True,
            now=LATER,
        )
        self.assertAlmostEqual(item.quantity or 0.0, 10.0)

    def test_gravel_shoulder_preserves_stated_width_for_derived_area(self):
        item = proposal("GRAVEL_SHOULDER_030", line((0, 0), (100, 0)))
        self.assertAlmostEqual(item.stated_width_m or 0.0, 0.30)
        self.assertAlmostEqual(
            derived_area_m2(item, metres_per_pixel=0.1) or 0.0,
            3.0,
        )

    def test_blocker_flag_prevents_approval(self):
        item = proposal(
            "DITCH_RELOCATION",
            line((0, 0), (100, 0)),
            flags=("partial",),
        )
        with self.assertRaises(TakeoffError):
            approve_takeoff(
                item,
                metres_per_pixel=0.1,
                scale_verified=True,
                now=LATER,
            )
        self.assertIn("PARTIAL", item.blocker_flags)

    def test_clearing_blocker_returns_to_review_then_allows_approval(self):
        item = proposal(
            "DITCH_REGRADE",
            line((0, 0), (100, 0)),
            flags=("MIXED",),
        )
        clear_takeoff_flag(item, "mixed", now=LATER)
        self.assertEqual(item.review_status, REVIEW_REQUIRED)
        approve_takeoff(
            item,
            metres_per_pixel=0.1,
            scale_verified=True,
            now=LATER,
        )
        self.assertAlmostEqual(item.quantity or 0.0, 10.0)

    def test_human_correction_preserves_original_proposal(self):
        original = polygon((0, 0), (10, 0), (10, 10), (0, 10))
        corrected = polygon((0, 0), (12, 0), (12, 10), (0, 10))
        item = proposal("GRAVEL_DRIVEWAY_REINSTATEMENT", original)
        correct_takeoff_geometry(item, corrected, now=LATER)
        self.assertEqual(item.provenance.original_geometry, original)
        self.assertEqual(item.geometry, corrected)
        self.assertTrue(item.provenance.human_corrected)

    def test_corrected_item_uses_edited_and_approved_status(self):
        item = proposal(
            "ROAD_WIDENING_FULL_STRUCTURE",
            polygon((0, 0), (10, 0), (10, 10), (0, 10)),
        )
        correct_takeoff_geometry(
            item,
            polygon((0, 0), (20, 0), (20, 10), (0, 10)),
            now=LATER,
        )
        approve_takeoff(
            item,
            metres_per_pixel=0.1,
            scale_verified=True,
            now=LATER,
        )
        self.assertEqual(item.review_status, EDITED_AND_APPROVED)

    def test_correction_training_record_contains_proposal_and_reviewed_geometry(self):
        item = proposal(
            "DITCH_INFILL",
            polygon((0, 0), (10, 0), (10, 10), (0, 10)),
        )
        corrected = polygon((0, 0), (8, 0), (8, 10), (0, 10))
        correct_takeoff_geometry(item, corrected, now=LATER)
        record = correction_training_record(item)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["rule_id"], "DITCH_INFILL")
        self.assertNotEqual(record["proposal_geometry"], record["reviewed_geometry"])

    def test_manual_proposal_gets_original_snapshot_when_first_corrected(self):
        item = proposal(
            "GRAVEL_DRIVEWAY_REINSTATEMENT",
            polygon((0, 0), (10, 0), (10, 10), (0, 10)),
            generated_by="human",
        )
        self.assertIsNone(item.provenance.original_geometry)
        correct_takeoff_geometry(
            item,
            polygon((0, 0), (9, 0), (9, 10), (0, 10)),
            now=LATER,
        )
        self.assertIsNotNone(item.provenance.original_geometry)

    def test_approved_totals_exclude_reference_and_unreviewed_records(self):
        area = proposal(
            "ROAD_WIDENING_FULL_STRUCTURE",
            polygon((0, 0), (10, 0), (10, 10), (0, 10)),
            takeoff_id="TK-A",
        )
        approve_takeoff(
            area,
            metres_per_pixel=0.1,
            scale_verified=True,
            now=LATER,
        )
        anchor = proposal(
            "ANCHOR_ROADWORKS_EXTENT",
            polygon((0, 0), (20, 0), (20, 20), (0, 20)),
            takeoff_id="TK-B",
        )
        pending = proposal(
            "DRIVEWAY_CULVERT_300",
            line((0, 0), (10, 0)),
            takeoff_id="TK-C",
        )
        totals = approved_totals([area, anchor, pending])
        self.assertAlmostEqual(totals["m2"], 1.0)
        self.assertEqual(totals["m"], 0.0)

    def test_takeoff_serialization_round_trip_preserves_provenance(self):
        item = proposal(
            "DITCH_INFILL",
            polygon((0, 0), (10, 0), (10, 10), (0, 10)),
        )
        set_takeoff_flag(item, "unresolved", now=LATER)
        restored = TakeoffMeasurement.from_dict(item.to_dict())
        self.assertEqual(restored.to_dict(), item.to_dict())

    def test_rejected_takeoff_cannot_be_approved(self):
        item = proposal("DRIVEWAY_CULVERT_300", line((0, 0), (10, 0)))
        reject_takeoff(item, now=LATER, reason="not in contractor scope")
        with self.assertRaises(TakeoffError):
            approve_takeoff(
                item,
                metres_per_pixel=0.1,
                scale_verified=True,
                now=LATER,
            )

    def test_line_and_area_approval_requires_scale_verification(self):
        item = proposal("DRIVEWAY_CULVERT_300", line((0, 0), (10, 0)))
        with self.assertRaises(TakeoffError):
            approve_takeoff(
                item,
                metres_per_pixel=0.1,
                scale_verified=False,
                now=LATER,
            )

    def test_quantity_requires_valid_calibration(self):
        item = proposal("DRIVEWAY_CULVERT_300", line((0, 0), (10, 0)))
        with self.assertRaises(TakeoffError):
            quantity_for(item, metres_per_pixel=None)

    def test_unknown_rule_fails_closed(self):
        with self.assertRaises(TakeoffError):
            takeoff_rule("NOT_A_REAL_RULE")

    def test_qa_summary_exposes_reference_blocker_and_correction_counts(self):
        anchor = proposal(
            "ANCHOR_ROADWORKS_EXTENT",
            polygon((0, 0), (10, 0), (10, 10), (0, 10)),
            takeoff_id="TK-A",
        )
        mixed = proposal(
            "DITCH_RELOCATION",
            line((0, 0), (10, 0)),
            takeoff_id="TK-B",
            flags=("MIXED",),
        )
        corrected = proposal(
            "DITCH_INFILL",
            polygon((0, 0), (10, 0), (10, 10), (0, 10)),
            takeoff_id="TK-C",
        )
        correct_takeoff_geometry(
            corrected,
            polygon((0, 0), (8, 0), (8, 10), (0, 10)),
            now=LATER,
        )
        summary = takeoff_qa_summary([anchor, mixed, corrected])
        self.assertEqual(summary["references"], 1)
        self.assertEqual(summary["blocked"], 1)
        self.assertEqual(summary["human_corrected"], 1)
        self.assertEqual(summary["issue_counts"]["ERROR"], 1)


if __name__ == "__main__":
    unittest.main()


class DegenerateGeometryTests(unittest.TestCase):
    """Coverage must be earned by real geometry (audit gap batch A/B)."""

    def test_zero_length_line_is_refused(self):
        with self.assertRaises(TakeoffError):
            TakeoffGeometry(
                LINE, vertices=(TakeoffVertex(10.0, 10.0), TakeoffVertex(10.0, 10.0))
            )

    def test_self_intersecting_ring_is_refused(self):
        crossed = (
            TakeoffVertex(0.0, 200.0),
            TakeoffVertex(100.0, 200.0),
            TakeoffVertex(0.0, 300.0),
            TakeoffVertex(160.0, 300.0),
        )
        with self.assertRaises(TakeoffError):
            TakeoffGeometry(POLYGON, vertices=crossed)

    def test_concave_but_simple_ring_is_still_accepted(self):
        # An L-shaped widening or a ditch infill is concave and perfectly valid;
        # the self-intersection guard must not reject ordinary civil geometry.
        concave = (
            TakeoffVertex(0.0, 0.0),
            TakeoffVertex(100.0, 0.0),
            TakeoffVertex(100.0, 40.0),
            TakeoffVertex(40.0, 40.0),
            TakeoffVertex(40.0, 100.0),
            TakeoffVertex(0.0, 100.0),
        )
        geometry = TakeoffGeometry(POLYGON, vertices=concave)
        self.assertAlmostEqual(geometry.area_px2, 6400.0, places=6)
