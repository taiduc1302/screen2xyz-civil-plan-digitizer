from __future__ import annotations

import unittest

from screen2xyz_civil.takeoff_context import (
    EvidenceBox,
    TakeoffContext,
    TakeoffContextError,
    TakeoffEvidenceRef,
    TakeoffQuestion,
    TakeoffRelation,
)


NOW = "2026-09-02T11:10:00-07:00"
LATER = "2026-09-02T11:11:00-07:00"


def legend(evidence_id: str = "EV-LEGEND") -> TakeoffEvidenceRef:
    return TakeoffEvidenceRef(
        id=evidence_id,
        kind="LEGEND",
        page_label="03",
        source_method="PDF_TEXT_VECTOR",
        summary="Green dot hatch is labelled DITCH INFILL.",
        source_ref="sheet-03:legend",
        locator=EvidenceBox(10, 10, 100, 80),
        confidence=0.99,
        data_class="PROJECT_PRIVATE",
    )


def question(question_id: str = "Q-MIXED") -> TakeoffQuestion:
    return TakeoffQuestion(
        id=question_id,
        page_label="03",
        reason_code="MIXED_SCOPE",
        detail="One traced ditch reach mixes regrade and relocation.",
        next_action="Split the trace at the drawing transition and review each segment.",
        created_at=NOW,
        severity="ERROR",
        related_takeoff_ids=["TK-DITCH"],
        related_evidence_ids=["EV-LEGEND"],
    )


class TakeoffContextTests(unittest.TestCase):
    def test_open_licensed_evidence_requires_license(self):
        with self.assertRaises(TakeoffContextError):
            TakeoffEvidenceRef(
                id="EV-OPEN",
                kind="DETAIL",
                page_label="",
                source_method="UPSTREAM_DOC",
                summary="Open source design reference.",
                data_class="OPEN_LICENSED",
            )

    def test_project_private_evidence_is_excluded_from_training_evidence(self):
        human = TakeoffEvidenceRef(
            id="EV-RULE",
            kind="HUMAN_REVIEW",
            page_label="03",
            source_method="ESTIMATOR",
            summary="Anchor polygons are QA-only and do not sum.",
            data_class="HUMAN_RULE",
        )
        context = TakeoffContext(evidence=[legend(), human])
        exported = context.training_evidence()
        self.assertEqual([item["id"] for item in exported], ["EV-RULE"])

    def test_relation_links_evidence_to_takeoff(self):
        context = TakeoffContext(evidence=[legend()])
        context.add_relation(
            TakeoffRelation("EV-LEGEND", "TK-DITCH", "SUPPORTS"),
            takeoff_ids=["TK-DITCH"],
        )
        supported = context.evidence_for("TK-DITCH")
        self.assertEqual([item.id for item in supported], ["EV-LEGEND"])

    def test_unknown_relation_endpoint_fails_closed(self):
        context = TakeoffContext(evidence=[legend()])
        with self.assertRaises(TakeoffContextError):
            context.add_relation(
                TakeoffRelation("EV-MISSING", "TK-DITCH", "SUPPORTS"),
                takeoff_ids=["TK-DITCH"],
            )

    def test_duplicate_relation_is_rejected(self):
        context = TakeoffContext(evidence=[legend()])
        relation = TakeoffRelation("EV-LEGEND", "TK-DITCH", "SUPPORTS")
        context.add_relation(relation, takeoff_ids=["TK-DITCH"])
        with self.assertRaises(TakeoffContextError):
            context.add_relation(relation, takeoff_ids=["TK-DITCH"])

    def test_question_is_first_class_unresolved_work(self):
        context = TakeoffContext(evidence=[legend()])
        context.add_question(question(), takeoff_ids=["TK-DITCH"])
        summary = context.unresolved_summary()
        self.assertEqual(summary["open_count"], 1)
        self.assertEqual(summary["error_count"], 1)
        self.assertEqual(summary["by_reason"], {"MIXED_SCOPE": 1})

    def test_question_resolution_requires_explicit_text(self):
        item = question()
        with self.assertRaises(TakeoffContextError):
            item.resolve(now=LATER, resolution="")
        item.resolve(
            now=LATER,
            resolution="North ditch was split at STA 1+083.91 and rechecked.",
        )
        self.assertEqual(item.status, "RESOLVED")
        self.assertEqual(item.resolved_at, LATER)

    def test_question_with_unknown_takeoff_fails_workspace_link_validation(self):
        context = TakeoffContext(evidence=[legend()])
        with self.assertRaises(TakeoffContextError):
            context.add_question(question(), takeoff_ids=["TK-OTHER"])

    def test_context_round_trip_preserves_links_and_questions(self):
        context = TakeoffContext(evidence=[legend()])
        context.add_relation(
            TakeoffRelation("EV-LEGEND", "TK-DITCH", "SUPPORTS"),
            takeoff_ids=["TK-DITCH"],
        )
        context.add_question(question(), takeoff_ids=["TK-DITCH"])
        restored = TakeoffContext.from_dict(context.to_dict())
        restored.validate_links(["TK-DITCH"])
        self.assertEqual(restored.to_dict(), context.to_dict())

    def test_duplicate_context_ids_are_rejected(self):
        with self.assertRaises(TakeoffContextError):
            TakeoffContext(evidence=[legend("EV-X"), legend("EV-X")])


if __name__ == "__main__":
    unittest.main()
