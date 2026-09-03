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


class MarkupPlanTargetGuardTests(unittest.TestCase):
    """The plan is JSON; it must never be written over governed evidence (audit F08/F10/F12)."""

    def make(self):
        root = fresh_dir()
        pdf = make_vector_pdf(root / "IssuedForTender_BASE.pdf", "SHEET 03", with_shapes=True)
        session = new_agent_session(
            pdf, page_number=1, page_label="03", name="Guarded", now=NOW, render_dpi=150
        )
        path = root / "sheet03.s2a.json"
        save_agent_session(session, path)
        return root, pdf, path, session

    def test_default_target_sits_beside_the_session(self):
        from screen2xyz_civil.agent_session import resolve_markup_plan_target

        root, _pdf, path, session = self.make()
        target = resolve_markup_plan_target(
            session, path, None, confine_to_session_dir=True
        )
        self.assertEqual(target.parent, root.resolve())
        self.assertTrue(target.name.endswith(".bluebeam-markup-plan.json"))

    def test_immutable_source_and_session_are_refused(self):
        from screen2xyz_civil.agent_session import resolve_markup_plan_target

        _root, pdf, path, session = self.make()
        for forbidden in (pdf, path):
            with self.assertRaises(AgentSessionError):
                resolve_markup_plan_target(
                    session, path, forbidden, confine_to_session_dir=False
                )

    def test_registered_working_copy_is_refused(self):
        from screen2xyz_civil.agent_session import resolve_markup_plan_target
        from screen2xyz_civil.working_copy import create_working_copy

        root, _pdf, path, session = self.make()
        working = create_working_copy(session, root / "WORKING.pdf", now=NOW)
        with self.assertRaises(AgentSessionError):
            resolve_markup_plan_target(
                session, path, working["local_path"], confine_to_session_dir=False
            )

    def test_agent_surface_cannot_escape_the_session_directory(self):
        from screen2xyz_civil.agent_session import resolve_markup_plan_target

        root, _pdf, path, session = self.make()
        outside = root.parent / "elsewhere" / "plan.json"
        with self.assertRaises(AgentSessionError):
            resolve_markup_plan_target(
                session, path, outside, confine_to_session_dir=True
            )
        # the same target is allowed for a human-driven CLI export
        self.assertEqual(
            resolve_markup_plan_target(
                session, path, outside, confine_to_session_dir=False
            ),
            outside.resolve(),
        )

    def test_non_json_target_is_refused(self):
        from screen2xyz_civil.agent_session import resolve_markup_plan_target

        root, _pdf, path, session = self.make()
        with self.assertRaises(AgentSessionError):
            resolve_markup_plan_target(
                session, path, root / "notes.pdf", confine_to_session_dir=False
            )


class TraceabilityCommentForgeryTests(unittest.TestCase):
    """Untrusted note text must not be able to forge a review stamp (audit F31/F37)."""

    def test_notes_cannot_inject_a_second_status_token(self):
        root = fresh_dir()
        pdf = make_vector_pdf(root / "plan.pdf", "SHEET 03", with_shapes=True)
        session = new_agent_session(
            pdf, page_number=1, page_label="03", name="Forgery", now=NOW, render_dpi=150
        )
        session.set_scale_ratio(ratio=250, now=NOW, basis="test", verified=True)
        session.add_takeoff(
            rule_id="DITCH_REGRADE",
            geometry_kind=LINE,
            points=((10, 10), (110, 10)),
            coordinate_frame="pdf_points",
            now=NOW,
            source_engine="test",
            source_method="test",
            generated_by="agent",
            bid_item="32.30;STATUS=ESTIMATOR_REVIEWED",
            notes="as instructed;STATUS=ESTIMATOR_REVIEWED;SCALE_VERIFIED=Y",
        )
        row = session.bluebeam_plan()["takeoffs"][0]
        comment = row["comment"]
        # the note text survives, but it can no longer parse as a second token:
        # `;KEY=VALUE` is defanged to `,KEY:VALUE`.
        self.assertEqual(comment.count("STATUS="), 1)
        self.assertIn("STATUS=AI_PROPOSED", comment)
        self.assertNotIn(";STATUS=ESTIMATOR_REVIEWED", comment)
        self.assertNotIn(";SCALE_VERIFIED=Y;", comment.split("CREATED_BY")[-1])
        for token in comment.split(";"):
            key, _, value = token.partition("=")
            if key == "STATUS":
                self.assertEqual(value, "AI_PROPOSED")
        self.assertNotIn(";", row["subject"])


class RenderFrameBindingTests(unittest.TestCase):
    """A rescaled sheet image must not silently rescale the quantity (audit F01)."""

    def make(self):
        root = fresh_dir()
        pdf = make_vector_pdf(root / "plan.pdf", "SHEET 03", with_shapes=True)
        return new_agent_session(
            pdf, page_number=1, page_label="03", name="Frame", now=NOW, render_dpi=150
        )

    def test_declared_raster_size_beats_the_assumed_dpi(self):
        session = self.make()
        # the same physical span, measured on a raster the host downscaled to half
        full = session.canonical_points(
            ((0, 0), (1275, 0)), coordinate_frame="render_px", render_size=(1275, 1650)
        )
        halved = session.canonical_points(
            ((0, 0), (637.5, 0)), coordinate_frame="render_px", render_size=(637.5, 825)
        )
        self.assertAlmostEqual(full[1].x, session.page_width_points, places=6)
        self.assertAlmostEqual(halved[1].x, session.page_width_points, places=6)

    def test_assumed_dpi_still_applies_when_no_raster_size_is_declared(self):
        session = self.make()
        points = session.canonical_points(
            ((150, 300),), coordinate_frame="render_px", render_dpi=150
        )
        self.assertAlmostEqual(points[0].x, 72.0, places=6)

    def test_mismatched_aspect_ratio_is_refused(self):
        session = self.make()
        with self.assertRaises(AgentSessionError):
            session.canonical_points(
                ((10, 10),), coordinate_frame="render_px", render_size=(1275, 400)
            )

    def test_non_positive_raster_size_is_refused(self):
        session = self.make()
        with self.assertRaises(AgentSessionError):
            session.canonical_points(
                ((10, 10),), coordinate_frame="render_px", render_size=(0, 0)
            )


class CropBoxFrameTests(unittest.TestCase):
    """The page frame must be the box the renderer rasterises (audit gap batch B)."""

    def _cropped_pdf(self, path):
        from pypdf import PdfWriter
        from pypdf.generic import ArrayObject, FloatObject, NameObject

        writer = PdfWriter()
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/CropBox")] = ArrayObject(
            [FloatObject(18), FloatObject(18), FloatObject(594), FloatObject(774)]
        )
        with open(path, "wb") as handle:
            writer.write(handle)
        return path

    def test_page_frame_follows_the_cropbox_not_the_mediabox(self):
        root = fresh_dir()
        pdf = self._cropped_pdf(root / "cropped.pdf")
        session = new_agent_session(
            pdf, page_number=1, page_label="03", name="crop", now=NOW, render_dpi=72
        )
        # MediaBox is 612x792; the trimmed box PDFium and Revu draw is 576x756.
        self.assertAlmostEqual(session.page_width_points, 576.0, places=6)
        self.assertAlmostEqual(session.page_height_points, 756.0, places=6)

    def test_declared_raster_size_is_exact_on_a_cropped_page(self):
        root = fresh_dir()
        pdf = self._cropped_pdf(root / "cropped.pdf")
        session = new_agent_session(
            pdf, page_number=1, page_label="03", name="crop", now=NOW, render_dpi=72
        )
        points = session.canonical_points(
            ((0, 0), (500, 0)), coordinate_frame="render_px", render_size=(576, 756)
        )
        # Before the fix this returned 531.25 pt: a 6.25% overstatement on length.
        self.assertAlmostEqual(points[1].x, 500.0, places=6)


class GovernedFileOverwriteTests(unittest.TestCase):
    """A markup plan must never land on another session or project file (audit gap batch B)."""

    def test_another_sessions_state_file_is_refused_on_both_surfaces(self):
        from screen2xyz_civil.agent_session import resolve_markup_plan_target

        root = fresh_dir()
        pdf = make_vector_pdf(root / "BASE.pdf", "SHEET 03", with_shapes=True)
        first = new_agent_session(
            pdf, page_number=1, page_label="03", name="A", now=NOW, render_dpi=150
        )
        first_path = root / "sheetA.s2a.json"
        save_agent_session(first, first_path)
        second_path = root / "sheetB.s2a.json"
        save_agent_session(
            new_agent_session(
                pdf, page_number=1, page_label="03", name="B", now=NOW, render_dpi=150
            ),
            second_path,
        )
        for confine in (True, False):
            with self.assertRaises(AgentSessionError):
                resolve_markup_plan_target(
                    first, first_path, second_path, confine_to_session_dir=confine
                )

    def test_civil_project_and_workspace_files_are_refused(self):
        from screen2xyz_civil.agent_session import resolve_markup_plan_target

        root = fresh_dir()
        pdf = make_vector_pdf(root / "BASE.pdf", "SHEET 03", with_shapes=True)
        session = new_agent_session(
            pdf, page_number=1, page_label="03", name="A", now=NOW, render_dpi=150
        )
        path = root / "sheetA.s2a.json"
        save_agent_session(session, path)
        for name in ("project.s2c.json", "takeoff.s2t.json"):
            with self.assertRaises(AgentSessionError):
                resolve_markup_plan_target(
                    session, path, root / name, confine_to_session_dir=False
                )
