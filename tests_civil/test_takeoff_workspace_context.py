from __future__ import annotations

import unittest

from screen2xyz_civil.takeoff import LINE, TakeoffGeometry, TakeoffVertex, new_takeoff_proposal
from screen2xyz_civil.takeoff_context import (
    TakeoffEvidenceRef,
    TakeoffQuestion,
    TakeoffRelation,
)
from screen2xyz_civil.takeoff_workspace import (
    TakeoffWorkspaceError,
    add_workspace_evidence,
    add_workspace_question,
    add_workspace_takeoff,
    approve_workspace_takeoff,
    confirm_workspace_scale,
    link_workspace_evidence,
    load_takeoff_workspace,
    new_takeoff_workspace,
    resolve_workspace_question,
    save_takeoff_workspace,
)

from .helpers_civil import fresh_dir, project_and_workflow


NOW = "2026-09-02T11:20:00-07:00"
LATER = "2026-09-02T11:21:00-07:00"


def culvert():
    return new_takeoff_proposal(
        takeoff_id="TK-CULV",
        rule_id="DRIVEWAY_CULVERT_300",
        page_index=2,
        page_label="03",
        geometry=TakeoffGeometry(
            LINE,
            (TakeoffVertex(0, 0), TakeoffVertex(100, 0)),
        ),
        now=NOW,
        source_engine="synthetic-test",
        source_method="VECTOR_PROPOSAL",
        generated_by="agent",
    )


def callout():
    return TakeoffEvidenceRef(
        id="EV-CULV",
        kind="CALLOUT",
        page_label="03",
        source_method="PDF_TEXT",
        summary="PROP. 300 dia DRIVEWAY CULVERT",
        data_class="PROJECT_PRIVATE",
    )


def blocking_question():
    return TakeoffQuestion(
        id="Q-CULV",
        page_label="03",
        reason_code="ENDPOINT_UNCLEAR",
        detail="One culvert endpoint is obscured by overlapping linework.",
        next_action="Zoom the endpoint and place the line on the pipe end, not driveway width.",
        created_at=NOW,
        severity="ERROR",
        related_takeoff_ids=["TK-CULV"],
        related_evidence_ids=["EV-CULV"],
    )


class TakeoffWorkspaceContextTests(unittest.TestCase):
    def build_workspace(self):
        project, _flow = project_and_workflow()
        workspace = new_takeoff_workspace(project, now=NOW)
        add_workspace_takeoff(workspace, culvert(), now=NOW)
        add_workspace_evidence(workspace, callout(), now=NOW)
        link_workspace_evidence(
            workspace,
            TakeoffRelation("EV-CULV", "TK-CULV", "SUPPORTS"),
            now=NOW,
        )
        return workspace

    def test_evidence_link_is_persisted_with_workspace(self):
        workspace = self.build_workspace()
        root = fresh_dir()
        path = root / "context.s2t.json"
        save_takeoff_workspace(workspace, path)
        restored = load_takeoff_workspace(path)
        evidence = restored.context.evidence_for("TK-CULV")
        self.assertEqual([item.id for item in evidence], ["EV-CULV"])

    def test_open_error_question_blocks_quantity_approval(self):
        workspace = self.build_workspace()
        add_workspace_question(workspace, blocking_question(), now=NOW)
        confirm_workspace_scale(workspace, now=NOW, reason="Estimator verified scale.")
        with self.assertRaises(TakeoffWorkspaceError):
            approve_workspace_takeoff(workspace, "TK-CULV", now=LATER)

    def test_resolving_question_restores_explicit_approval_path(self):
        workspace = self.build_workspace()
        add_workspace_question(workspace, blocking_question(), now=NOW)
        confirm_workspace_scale(workspace, now=NOW, reason="Estimator verified scale.")
        resolve_workspace_question(
            workspace,
            "Q-CULV",
            now=LATER,
            resolution="Endpoint confirmed from clean vector linework.",
        )
        item = approve_workspace_takeoff(workspace, "TK-CULV", now=LATER)
        self.assertAlmostEqual(item.quantity or 0.0, 10.0)

    def test_question_and_resolution_are_audited(self):
        workspace = self.build_workspace()
        add_workspace_question(workspace, blocking_question(), now=NOW)
        resolve_workspace_question(
            workspace,
            "Q-CULV",
            now=LATER,
            resolution="Endpoint confirmed.",
        )
        actions = [entry["action"] for entry in workspace.decision_log]
        self.assertIn("TAKEOFF_QUESTION_ADDED", actions)
        self.assertIn("TAKEOFF_QUESTION_RESOLVED", actions)


if __name__ == "__main__":
    unittest.main()
