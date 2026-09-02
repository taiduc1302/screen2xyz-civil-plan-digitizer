from __future__ import annotations

import math
import unittest

from screen2xyz_civil.agent_session import (
    AgentSessionError,
    export_bluebeam_plan,
    load_agent_session,
    new_agent_session,
    save_agent_session,
)
from screen2xyz_civil.takeoff import LINE, POLYGON

from .helpers_civil import fresh_dir, make_vector_pdf


NOW = "2026-09-02T19:00:00+00:00"
LATER = "2026-09-02T19:05:00+00:00"


class AgentSessionTests(unittest.TestCase):
    def make_session(self):
        root = fresh_dir()
        pdf = make_vector_pdf(root / "plan.pdf", "SHEET 03", with_shapes=True)
        session = new_agent_session(
            pdf,
            page_number=1,
            page_label="03",
            name="King Road pilot",
            now=NOW,
            render_dpi=150,
        )
        return root, pdf, session

    def test_session_uses_resolution_independent_rendered_pdf_points(self):
        _root, _pdf, session = self.make_session()
        self.assertEqual(session.page_width_points, 612.0)
        self.assertEqual(session.page_height_points, 792.0)
        self.assertEqual(session.coordinate_frame, "PDF_VIEW_POINTS_TOP_LEFT")

    def test_render_pixels_convert_to_canonical_pdf_points(self):
        _root, _pdf, session = self.make_session()
        points = session.canonical_points(
            ((150, 300),), coordinate_frame="render_px", render_dpi=150
        )
        self.assertAlmostEqual(points[0].x, 72.0)
        self.assertAlmostEqual(points[0].y, 144.0)

    def test_opentakeoff_pixels_convert_back_to_pdf_points(self):
        _root, _pdf, session = self.make_session()
        points = session.canonical_points(
            ((144, 288),), coordinate_frame="opentakeoff_px"
        )
        self.assertEqual((points[0].x, points[0].y), (72.0, 144.0))

    def test_printed_ratio_resolves_expected_metric_scale(self):
        _root, _pdf, session = self.make_session()
        session.set_scale_ratio(
            250, now=LATER, basis="PLAN 1:250", verified=False
        )
        expected = 250 * 0.0254 / 72.0
        self.assertAlmostEqual(session.scale.metres_per_point or 0.0, expected)
        self.assertTrue(session.scale.resolved)
        self.assertFalse(session.scale.verified)

    def test_independent_dimension_can_verify_resolved_scale(self):
        _root, _pdf, session = self.make_session()
        session.set_scale_ratio(100, now=LATER, basis="PLAN 1:100")
        mpp = session.scale.metres_per_point or 0.0
        known = 10.0
        point_distance = known / mpp
        result = session.verify_scale(
            (10, 10),
            (10 + point_distance, 10),
            known_distance_m=known,
            coordinate_frame="pdf_points",
            now=LATER,
            basis="Independent 10 m dimension",
            tolerance_percent=0.01,
        )
        self.assertTrue(result["passed"])
        self.assertTrue(session.scale.verified)

    def test_unverified_scale_marks_agent_line_as_blocked(self):
        _root, _pdf, session = self.make_session()
        session.set_scale_ratio(250, now=LATER, basis="printed ratio")
        item = session.add_takeoff(
            rule_id="DRIVEWAY_CULVERT_300",
            geometry_kind=LINE,
            points=((10, 10), (110, 10)),
            coordinate_frame="pdf_points",
            now=LATER,
            source_engine="test",
            source_method="AGENT_LINE_PROPOSAL",
            generated_by="agent",
        )
        self.assertIn("SCALE_UNVERIFIED", item.flags)
        self.assertIsNotNone(session.preview_quantity(item))

    def test_verified_scale_allows_clean_quantity_preview_but_not_auto_approval(self):
        _root, _pdf, session = self.make_session()
        session.set_scale_ratio(
            100,
            now=LATER,
            basis="Printed 1:100 plus independent dimension",
            verified=True,
        )
        item = session.add_takeoff(
            rule_id="DRIVEWAY_CULVERT_300",
            geometry_kind=LINE,
            points=((10, 10), (110, 10)),
            coordinate_frame="pdf_points",
            now=LATER,
            source_engine="test",
            source_method="AGENT_LINE_PROPOSAL",
            generated_by="agent",
        )
        self.assertNotIn("SCALE_UNVERIFIED", item.flags)
        self.assertFalse(item.approved)
        expected = 100 * (100 * 0.0254 / 72.0)
        self.assertAlmostEqual(session.preview_quantity(item) or 0.0, expected)

    def test_anchor_is_exported_as_reference_do_not_sum(self):
        _root, _pdf, session = self.make_session()
        item = session.add_takeoff(
            rule_id="ANCHOR_ROADWORKS_EXTENT",
            geometry_kind=POLYGON,
            points=((10, 10), (100, 10), (100, 100), (10, 100)),
            coordinate_frame="pdf_points",
            now=LATER,
            source_engine="test",
            source_method="AGENT_POLYGON_PROPOSAL",
            generated_by="agent",
        )
        row = next(row for row in session.bluebeam_plan()["takeoffs"] if row["takeoff_id"] == item.id)
        self.assertFalse(row["summable"])
        self.assertEqual(row["bluebeam_creation_policy"], "REFERENCE_ONLY_DO_NOT_SUM")

    def test_edit_preserves_original_machine_geometry(self):
        _root, _pdf, session = self.make_session()
        item = session.add_takeoff(
            rule_id="GRAVEL_DRIVEWAY_REINSTATEMENT",
            geometry_kind=POLYGON,
            points=((10, 10), (100, 10), (100, 80), (10, 80)),
            coordinate_frame="pdf_points",
            now=NOW,
            source_engine="test",
            source_method="AGENT_POLYGON_PROPOSAL",
            generated_by="agent",
        )
        original = item.provenance.original_geometry
        session.edit_takeoff(
            item.id,
            points=((10, 10), (90, 10), (90, 80), (10, 80)),
            coordinate_frame="pdf_points",
            now=LATER,
            reason="aligned to gravel boundary",
        )
        self.assertIsNotNone(original)
        self.assertEqual(item.provenance.original_geometry, original)
        self.assertTrue(item.provenance.human_corrected)

    def test_save_load_round_trip_and_source_hash_guard(self):
        root, pdf, session = self.make_session()
        path = root / "takeoff.s2a.json"
        save_agent_session(session, path)
        restored = load_agent_session(path)
        self.assertEqual(restored.to_dict(), session.to_dict())
        pdf.write_bytes(pdf.read_bytes() + b"\n% changed revision")
        with self.assertRaises(AgentSessionError):
            load_agent_session(path)

    def test_bluebeam_plan_contains_traceability_contract(self):
        _root, _pdf, session = self.make_session()
        item = session.add_takeoff(
            rule_id="DRIVEWAY_CULVERT_300",
            geometry_kind=LINE,
            points=((10, 10), (110, 10)),
            coordinate_frame="pdf_points",
            now=LATER,
            source_engine="test",
            source_method="AGENT_LINE_PROPOSAL",
            generated_by="agent",
            bid_item="33.01",
            notes="North driveway",
        )
        row = session.bluebeam_plan()["takeoffs"][0]
        self.assertIn("33.01", row["subject"])
        self.assertIn(f"PLAN_ID={item.id}", row["comment"])
        self.assertIn("SHEET=03", row["comment"])
        self.assertIn("SCALE_VERIFIED=N", row["comment"])

    def test_export_bluebeam_plan_writes_auditable_json(self):
        root, _pdf, session = self.make_session()
        target = root / "plan.bluebeam-markup-plan.json"
        identity = export_bluebeam_plan(session, target)
        self.assertTrue(target.is_file())
        self.assertEqual(len(identity["sha256"]), 64)
        self.assertIn("bluebeam-markup-plan/1.0", target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
