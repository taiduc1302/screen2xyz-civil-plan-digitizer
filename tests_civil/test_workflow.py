from __future__ import annotations

import unittest

from screen2xyz_civil import contracts as C
from screen2xyz_civil.detection import Rect, SymbolCandidate, TextCandidate
from screen2xyz_civil.models import CivilPoint, CropRegion, PixelPoint
from screen2xyz_civil.workflow import CivilWorkflow, WorkflowError

from .helpers_civil import FIXED_NOW, add_approved, project_and_workflow


class WorkflowTests(unittest.TestCase):
    def test_contour_line_is_persistent_reviewed_geometry(self):
        project, flow = project_and_workflow()
        line = flow.add_elevation_line(
            [PixelPoint(60, 90), PixelPoint(90, 80)],
            elevation=49.5,
        )
        self.assertEqual(line.review_status, C.UNREVIEWED)
        flow.approve_elevation_line(line.id)
        self.assertTrue(line.approved)
        self.assertEqual(project.elevation_lines[0].vertices[1], PixelPoint(90, 80))
        flow.undo()
        self.assertEqual(
            project.elevation_lines[0].review_status, C.UNREVIEWED
        )

    def test_undo_and_redo_restore_cart_mutations(self):
        project, flow = project_and_workflow()
        point = flow.add_manual_point(
            pixel=PixelPoint(60, 90),
            elevation=49.06,
            point_type=C.EXISTING_GROUND,
            page_index=2,
            page_label="3",
        )
        self.assertEqual(len(project.points), 1)
        flow.undo()
        self.assertEqual(project.points, [])
        flow.redo()
        self.assertEqual(len(project.points), 1)
        self.assertEqual(project.points[0].id, point.id)

    def test_edit_preserves_estimator_cart_fields(self):
        _project, flow = project_and_workflow()
        point = flow.add_manual_point(
            pixel=PixelPoint(60, 90),
            elevation=49.06,
            point_type=C.EXISTING_GROUND,
        )
        flow.edit_point(
            point.id,
            point_number="EX-101",
            description="EX GROUND",
            sheet="C03",
            revision_label="G",
            notes="Confirm curb return",
        )
        self.assertEqual(point.point_number, "EX-101")
        self.assertEqual(point.sheet, "C03")
        self.assertEqual(point.revision_label, "G")
        self.assertEqual(point.notes, "Confirm curb return")
        self.assertEqual(point.review_status, C.REVIEW_REQUIRED)

    def test_bulk_approve_is_one_undoable_action(self):
        project, flow = project_and_workflow()
        first = flow.add_manual_point(
            pixel=PixelPoint(60, 90),
            elevation=49.06,
            point_type=C.EXISTING_GROUND,
        )
        second = flow.add_manual_point(
            pixel=PixelPoint(80, 80),
            elevation=49.50,
            point_type=C.DESIGN_GRADE,
        )
        flow.bulk_approve([first.id, second.id])
        self.assertTrue(all(point.approved for point in project.points))
        flow.undo()
        self.assertTrue(
            all(point.review_status == C.UNREVIEWED for point in project.points)
        )

    def test_renumber_and_sort_point_cart(self):
        project, flow = project_and_workflow()
        high = flow.add_manual_point(
            pixel=PixelPoint(60, 90),
            elevation=52,
            point_type=C.EXISTING_GROUND,
        )
        low = flow.add_manual_point(
            pixel=PixelPoint(80, 80),
            elevation=48,
            point_type=C.DESIGN_GRADE,
        )
        flow.renumber_points(prefix="C03-", start=10, padding=3)
        self.assertEqual(high.point_number, "C03-010")
        self.assertEqual(low.point_number, "C03-011")
        flow.sort_points("elevation")
        self.assertEqual([point.id for point in project.points], [low.id, high.id])

    def test_assisted_cart_row_can_be_deleted_and_restored(self):
        project, flow = project_and_workflow()
        point = flow.add_manual_point(
            pixel=PixelPoint(60, 90),
            elevation=49.06,
            point_type=C.EXISTING_GROUND,
        )
        point.source_method = C.PDF_TEXT
        flow.delete_cart_point(point.id)
        self.assertEqual(project.points, [])
        flow.undo()
        self.assertEqual(project.points[0].id, point.id)

    def test_manual_point_requires_review_then_approves(self):
        _project, flow = project_and_workflow()
        point = flow.add_manual_point(
            pixel=PixelPoint(60, 90),
            elevation=49.06,
            point_type=C.EXISTING_GROUND,
        )
        self.assertEqual(point.review_status, C.UNREVIEWED)
        flow.approve_point(point.id)
        self.assertEqual(point.review_status, C.APPROVED)
        self.assertAlmostEqual(point.local_east, 1001.0)
        self.assertAlmostEqual(point.local_north, 2001.0)

    def test_approval_requires_calibration(self):
        _project, flow = project_and_workflow(calibrated=False)
        point = flow.add_manual_point(
            pixel=PixelPoint(10, 10),
            elevation=1,
            point_type=C.DESIGN_GRADE,
        )
        with self.assertRaises(WorkflowError):
            flow.approve_point(point.id)

    def test_edit_returns_point_to_review(self):
        _project, flow = project_and_workflow()
        point = add_approved(flow)
        flow.edit_point(point.id, elevation=50.25, point_type=C.DESIGN_GRADE)
        self.assertEqual(point.review_status, C.REVIEW_REQUIRED)
        self.assertEqual(point.elevation, 50.25)
        flow.approve_point(point.id)
        self.assertEqual(point.review_status, C.EDITED_AND_APPROVED)

    def test_reject_never_approves(self):
        _project, flow = project_and_workflow()
        point = flow.add_manual_point(
            pixel=PixelPoint(10, 10),
            elevation=12,
            point_type=C.EXISTING_GROUND,
        )
        flow.reject_point(point.id, "not terrain")
        self.assertEqual(point.review_status, C.REJECTED)
        self.assertIn("not terrain", point.classification_reason)

    def test_manual_point_outside_crop_rejected(self):
        _project, flow = project_and_workflow()
        with self.assertRaises(WorkflowError):
            flow.add_manual_point(
                pixel=PixelPoint(250, 10),
                elevation=1,
                point_type=C.EXISTING_GROUND,
            )

    def test_out_of_range_elevation_rejected(self):
        project, flow = project_and_workflow()
        project.plausible_elevation_min = 0
        project.plausible_elevation_max = 100
        with self.assertRaises(WorkflowError):
            flow.add_manual_point(
                pixel=PixelPoint(10, 10),
                elevation=101,
                point_type=C.EXISTING_GROUND,
            )

    def test_project_elevation_range_is_validated_and_audited(self):
        project, flow = project_and_workflow()
        flow.set_plausible_elevation_range(40, 60)
        self.assertEqual(project.plausible_elevation_min, 40)
        self.assertEqual(project.plausible_elevation_max, 60)
        self.assertEqual(
            project.decision_log[-1]["action"],
            "PLAUSIBLE_ELEVATION_RANGE_SET",
        )
        with self.assertRaises(WorkflowError):
            flow.set_plausible_elevation_range(60, 40)

    def test_non_terrain_manual_class_rejected(self):
        _project, flow = project_and_workflow()
        with self.assertRaises(WorkflowError):
            flow.add_manual_point(
                pixel=PixelPoint(10, 10),
                elevation=1,
                point_type=C.UTILITY_INVERT,
            )

    def test_recalibration_preserves_history_and_recomputes(self):
        project, flow = project_and_workflow()
        point = add_approved(flow)
        old_east = point.local_east
        flow.apply_calibration(
            scale_point_1=PixelPoint(0, 100),
            scale_point_2=PixelPoint(100, 100),
            known_distance_m=20,
            origin_pixel=PixelPoint(50, 100),
            east_reference=PixelPoint(100, 100),
        )
        self.assertEqual(len(project.calibration_history), 1)
        self.assertEqual(project.calibration.revision, 2)
        self.assertNotEqual(point.local_east, old_east)
        self.assertTrue(project.exports_stale)

    def test_automatic_candidate_cannot_arrive_approved(self):
        project, flow = project_and_workflow()
        candidate = CivilPoint(
            id="PT-9999",
            page_index=0,
            page_label="1",
            source_file="synthetic.png",
            source_sha256="a" * 64,
            pixel_x=10,
            pixel_y=10,
            elevation=12,
            point_type=C.EXISTING_GROUND,
            symbol_type="EXISTING_CROSS",
            source_method=C.PDF_TEXT,
            review_status=C.APPROVED,
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )
        with self.assertRaises(WorkflowError):
            flow.add_candidate(candidate)
        self.assertEqual(project.points, [])

    def test_duplicate_merge_rejects_second(self):
        _project, flow = project_and_workflow()
        first = add_approved(flow, pixel=PixelPoint(60, 90))
        second = flow.add_manual_point(
            pixel=PixelPoint(60.1, 90.1),
            elevation=49.06,
            point_type=C.EXISTING_GROUND,
        )
        flow.merge_duplicate(first.id, second.id)
        self.assertEqual(second.review_status, C.REJECTED)

    def test_set_crop_checks_source_boundary(self):
        project, _flow = project_and_workflow()
        flow = CivilWorkflow(project, now=lambda: FIXED_NOW)
        with self.assertRaises(WorkflowError):
            flow.set_crop(CropRegion(190, 140, 20, 20))

    def test_second_scale_check_is_preserved(self):
        project, flow = project_and_workflow()
        check = flow.verify_current_scale(
            PixelPoint(0, 0), PixelPoint(98, 0), 10.0
        )
        self.assertFalse(check.passed)
        self.assertIs(project.calibration.scale_check, check)
        self.assertTrue(project.exports_stale)

    def test_delete_manual_point_requires_explicit_manual_source(self):
        project, flow = project_and_workflow()
        point = flow.add_manual_point(
            pixel=PixelPoint(10, 10),
            elevation=1,
            point_type=C.EXISTING_GROUND,
        )
        flow.delete_manual_point(point.id)
        self.assertEqual(project.points, [])

    def test_candidate_batch_filters_percent_and_adds_decimal(self):
        project, flow = project_and_workflow()
        result = flow.ingest_text_candidates(
            [
                TextCandidate(
                    "T1", "49.06", Rect(10, 10, 30, 20), 0, C.PDF_TEXT, 1.0
                ),
                TextCandidate(
                    "T2", "2.9%", Rect(40, 10, 60, 20), 0, C.PDF_TEXT, 1.0
                ),
            ]
        )
        self.assertEqual(len(result["added"]), 1)
        self.assertEqual(len(result["filtered"]), 1)
        self.assertEqual(len(project.points), 1)
        self.assertEqual(project.points[0].review_status, C.REVIEW_REQUIRED)

    def test_alternative_association_moves_point_and_requires_review(self):
        project, flow = project_and_workflow()
        symbols = [
            SymbolCandidate(
                "S1", "DESIGN_OVAL", Rect(5, 5, 35, 25), 1.0, C.PDF_VECTOR
            ),
            SymbolCandidate(
                "S2", "EXISTING_CROSS", Rect(31, 10, 39, 18), 0.9, C.PDF_VECTOR
            ),
        ]
        result = flow.ingest_text_candidates(
            [
                TextCandidate(
                    "T1", "49.06", Rect(10, 10, 30, 20), 0, C.PDF_TEXT, 1.0
                )
            ],
            symbols,
        )
        point = result["added"][0]
        self.assertTrue(point.alternative_associations)
        old_x = point.pixel_x
        flow.use_alternative_association(point.id)
        self.assertNotEqual(point.pixel_x, old_x)
        self.assertEqual(point.review_status, C.REVIEW_REQUIRED)
