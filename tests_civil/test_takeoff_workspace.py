from __future__ import annotations

import unittest

from screen2xyz_civil.models import PixelPoint
from screen2xyz_civil.takeoff import (
    LINE,
    POLYGON,
    REVIEW_REQUIRED,
    TakeoffGeometry,
    TakeoffVertex,
    new_takeoff_proposal,
)
from screen2xyz_civil.takeoff_workspace import (
    TakeoffWorkspaceError,
    add_workspace_takeoff,
    approve_workspace_takeoff,
    clear_workspace_takeoff_flag,
    confirm_workspace_scale,
    correct_workspace_takeoff,
    flag_workspace_takeoff,
    load_takeoff_workspace,
    new_takeoff_workspace,
    save_takeoff_workspace,
    sync_workspace_calibration,
)

from .helpers_civil import fresh_dir, project_and_workflow


NOW = "2026-09-02T10:50:00-07:00"
LATER = "2026-09-02T10:51:00-07:00"


def culvert(takeoff_id: str = "TK-CULV"):
    return new_takeoff_proposal(
        takeoff_id=takeoff_id,
        rule_id="DRIVEWAY_CULVERT_300",
        page_index=2,
        page_label="03",
        geometry=TakeoffGeometry(
            LINE,
            (TakeoffVertex(10, 20), TakeoffVertex(110, 20)),
        ),
        now=NOW,
        source_engine="synthetic-test",
        source_method="VECTOR_PROPOSAL",
        generated_by="agent",
    )


def driveway(takeoff_id: str = "TK-DRV"):
    return new_takeoff_proposal(
        takeoff_id=takeoff_id,
        rule_id="GRAVEL_DRIVEWAY_REINSTATEMENT",
        page_index=2,
        page_label="03",
        geometry=TakeoffGeometry(
            POLYGON,
            (
                TakeoffVertex(10, 20),
                TakeoffVertex(110, 20),
                TakeoffVertex(110, 70),
                TakeoffVertex(10, 70),
            ),
        ),
        now=NOW,
        source_engine="synthetic-test",
        source_method="VECTOR_PROPOSAL",
        generated_by="agent",
    )


class TakeoffWorkspaceTests(unittest.TestCase):
    def test_workspace_links_project_without_exporting_local_source_path(self):
        project, _flow = project_and_workflow()
        workspace = new_takeoff_workspace(project, now=NOW)
        self.assertEqual(workspace.civil_project_id, project.project_id)
        self.assertAlmostEqual(workspace.metres_per_pixel or 0.0, 0.1)
        self.assertNotIn("local_path", workspace.source_identity)
        self.assertFalse(workspace.scale_verified)

    def test_approval_fails_closed_until_scale_is_confirmed(self):
        project, _flow = project_and_workflow()
        workspace = new_takeoff_workspace(project, now=NOW)
        add_workspace_takeoff(workspace, culvert(), now=NOW)
        with self.assertRaises(TakeoffWorkspaceError):
            approve_workspace_takeoff(workspace, "TK-CULV", now=LATER)

    def test_confirmed_scale_allows_approval_and_audits_quantity(self):
        project, _flow = project_and_workflow()
        workspace = new_takeoff_workspace(project, now=NOW)
        add_workspace_takeoff(workspace, culvert(), now=NOW)
        confirm_workspace_scale(
            workspace,
            now=LATER,
            reason="Estimator verified a second printed dimension.",
        )
        item = approve_workspace_takeoff(workspace, "TK-CULV", now=LATER)
        self.assertAlmostEqual(item.quantity or 0.0, 10.0)
        self.assertEqual(workspace.decision_log[-1]["action"], "TAKEOFF_APPROVED")

    def test_workspace_save_load_round_trip(self):
        project, _flow = project_and_workflow()
        workspace = new_takeoff_workspace(project, now=NOW)
        add_workspace_takeoff(workspace, driveway(), now=NOW)
        root = fresh_dir()
        path = root / "takeoff.s2t.json"
        identity = save_takeoff_workspace(workspace, path)
        restored = load_takeoff_workspace(path)
        self.assertEqual(restored.to_dict(), workspace.to_dict())
        self.assertEqual(len(identity["sha256"]), 64)

    def test_duplicate_takeoff_id_is_rejected(self):
        project, _flow = project_and_workflow()
        workspace = new_takeoff_workspace(project, now=NOW)
        add_workspace_takeoff(workspace, culvert(), now=NOW)
        with self.assertRaises(TakeoffWorkspaceError):
            add_workspace_takeoff(workspace, culvert(), now=LATER)

    def test_geometry_correction_is_audited_and_returns_to_review(self):
        project, _flow = project_and_workflow()
        workspace = new_takeoff_workspace(project, now=NOW)
        add_workspace_takeoff(workspace, driveway(), now=NOW)
        corrected = TakeoffGeometry(
            POLYGON,
            (
                TakeoffVertex(10, 20),
                TakeoffVertex(100, 20),
                TakeoffVertex(100, 70),
                TakeoffVertex(10, 70),
            ),
        )
        item = correct_workspace_takeoff(
            workspace,
            "TK-DRV",
            corrected,
            now=LATER,
            reason="Estimator aligned polygon to actual gravel boundary.",
        )
        self.assertEqual(item.review_status, REVIEW_REQUIRED)
        self.assertTrue(item.provenance.human_corrected)
        self.assertEqual(
            workspace.decision_log[-1]["action"], "TAKEOFF_GEOMETRY_CORRECTED"
        )

    def test_calibration_revision_invalidates_scaled_approved_takeoff(self):
        project, flow = project_and_workflow()
        workspace = new_takeoff_workspace(project, now=NOW)
        add_workspace_takeoff(workspace, culvert(), now=NOW)
        confirm_workspace_scale(workspace, now=NOW, reason="Estimator scale check.")
        approve_workspace_takeoff(workspace, "TK-CULV", now=NOW)
        flow.apply_calibration(
            scale_point_1=PixelPoint(0, 100),
            scale_point_2=PixelPoint(100, 100),
            known_distance_m=20.0,
            origin_pixel=PixelPoint(50, 100),
            east_reference=PixelPoint(100, 100),
        )
        sync_workspace_calibration(workspace, project, now=LATER)
        item = workspace.measurement("TK-CULV")
        self.assertEqual(item.review_status, REVIEW_REQUIRED)
        self.assertIsNone(item.quantity)
        self.assertIn("SCALE_UNVERIFIED", item.flags)
        self.assertFalse(workspace.scale_verified)

    def test_flag_lifecycle_remains_explicit(self):
        project, _flow = project_and_workflow()
        workspace = new_takeoff_workspace(project, now=NOW)
        add_workspace_takeoff(workspace, culvert(), now=NOW)
        flag_workspace_takeoff(workspace, "TK-CULV", "partial", now=LATER)
        self.assertIn("PARTIAL", workspace.measurement("TK-CULV").flags)
        clear_workspace_takeoff_flag(workspace, "TK-CULV", "partial", now=LATER)
        self.assertNotIn("PARTIAL", workspace.measurement("TK-CULV").flags)

    def test_workspace_rejects_calibration_sync_from_different_project(self):
        project, _flow = project_and_workflow()
        workspace = new_takeoff_workspace(project, now=NOW)
        other, _other_flow = project_and_workflow()
        other.project_id = "CPD-OTHER"
        with self.assertRaises(TakeoffWorkspaceError):
            sync_workspace_calibration(workspace, other, now=LATER)


if __name__ == "__main__":
    unittest.main()
