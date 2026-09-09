from __future__ import annotations

import unittest

from screen2xyz_civil.agent_session import AgentSessionError, new_agent_session
from screen2xyz_civil.scope_ledger import (
    NOT_APPLICABLE,
    NOT_PRESENT,
    PROPOSED,
    UNSEARCHED,
    WITHHELD,
    scope_summary,
    set_scope_status,
)
from screen2xyz_civil.takeoff import LINE, RULES

from .helpers_civil import fresh_dir, make_vector_pdf


NOW = "2026-09-02T21:00:00+00:00"
LATER = "2026-09-02T21:05:00+00:00"


class ScopeLedgerTests(unittest.TestCase):
    def make_session(self):
        root = fresh_dir()
        pdf = make_vector_pdf(root / "plan.pdf", "SHEET 03", with_shapes=True)
        return new_agent_session(
            pdf,
            page_number=1,
            page_label="03",
            name="scope ledger",
            now=NOW,
            render_dpi=150,
        )

    def test_all_rules_begin_unsearched(self):
        summary = scope_summary(self.make_session())
        self.assertEqual(summary["rule_count"], len(RULES))
        self.assertEqual(summary["unsearched_count"], len(RULES))
        self.assertFalse(summary["ready_for_coverage_review"])
        self.assertTrue(all(row["status"] == UNSEARCHED for row in summary["states"]))

    def test_real_takeoff_makes_its_rule_proposed(self):
        session = self.make_session()
        session.add_takeoff(
            rule_id="DRIVEWAY_CULVERT_300",
            geometry_kind=LINE,
            points=((10, 10), (110, 10)),
            coordinate_frame="pdf_points",
            now=LATER,
            source_engine="test",
            source_method="AGENT_LINE_PROPOSAL",
            generated_by="agent",
        )
        row = next(
            row
            for row in scope_summary(session)["states"]
            if row["rule_id"] == "DRIVEWAY_CULVERT_300"
        )
        self.assertEqual(row["status"], PROPOSED)
        self.assertTrue(row["accounted"])

    def test_absent_rule_can_be_accounted_not_present_with_detail(self):
        session = self.make_session()
        set_scope_status(
            session,
            rule_id="FULL_DEPTH_ASPHALT_RR",
            status=NOT_PRESENT,
            detail="Legend contains the category but no matching hatch was found on Sheet 03.",
            now=LATER,
        )
        row = next(
            row
            for row in scope_summary(session)["states"]
            if row["rule_id"] == "FULL_DEPTH_ASPHALT_RR"
        )
        self.assertEqual(row["status"], NOT_PRESENT)
        self.assertTrue(row["accounted"])

    def test_existing_takeoff_cannot_be_erased_by_not_present_status(self):
        session = self.make_session()
        session.add_takeoff(
            rule_id="DITCH_REGRADE",
            geometry_kind=LINE,
            points=((10, 10), (110, 10)),
            coordinate_frame="pdf_points",
            now=NOW,
            source_engine="test",
            source_method="AGENT_LINE_PROPOSAL",
            generated_by="agent",
        )
        with self.assertRaises(AgentSessionError):
            set_scope_status(
                session,
                rule_id="DITCH_REGRADE",
                status=NOT_PRESENT,
                detail="Attempt to hide existing geometry.",
                now=LATER,
            )
        with self.assertRaises(AgentSessionError):
            set_scope_status(
                session,
                rule_id="DITCH_REGRADE",
                status=NOT_APPLICABLE,
                detail="Attempt to hide existing geometry.",
                now=LATER,
            )

    def test_withheld_accounts_rule_without_pretending_it_is_resolved(self):
        session = self.make_session()
        set_scope_status(
            session,
            rule_id="DITCH_RELOCATION",
            status=WITHHELD,
            detail="Transition from regrade to relocation cannot be defended from current evidence.",
            now=LATER,
        )
        summary = scope_summary(session)
        self.assertIn("DITCH_RELOCATION", summary["withheld_rule_ids"])
        self.assertEqual(summary["withheld_count"], 1)
        row = next(row for row in summary["states"] if row["rule_id"] == "DITCH_RELOCATION")
        self.assertTrue(row["accounted"])

    def test_rule_coverage_becomes_ready_only_after_every_rule_is_accounted(self):
        session = self.make_session()
        for rule_id in RULES:
            set_scope_status(
                session,
                rule_id=rule_id,
                status=WITHHELD,
                detail=f"Synthetic coverage accounting for {rule_id}.",
                now=LATER,
            )
        summary = scope_summary(session)
        self.assertEqual(summary["unsearched_count"], 0)
        self.assertEqual(summary["accounted_rate"], 1.0)
        self.assertTrue(summary["ready_for_coverage_review"])

    def test_explicit_proposed_status_without_geometry_is_rejected(self):
        session = self.make_session()
        with self.assertRaises(AgentSessionError):
            set_scope_status(
                session,
                rule_id="DITCH_INFILL",
                status=PROPOSED,
                detail="There is no takeoff geometry.",
                now=LATER,
            )


if __name__ == "__main__":
    unittest.main()


class CoverageEnforcementTests(unittest.TestCase):
    """An unsearched scope must be visible in QA and in the delivered plan."""

    def _session(self):
        from screen2xyz_civil.agent_session import new_agent_session
        from .helpers_civil import fresh_dir, make_vector_pdf

        root = fresh_dir()
        pdf = make_vector_pdf(root / "plan.pdf", "SHEET 03", with_shapes=True)
        session = new_agent_session(
            pdf,
            page_number=1,
            page_label="03",
            name="coverage",
            now="2026-09-03T00:00:00+00:00",
        )
        session.set_scale_ratio(
            ratio=250, now="2026-09-03T00:00:00+00:00", basis="test", verified=True
        )
        return session

    def test_unsearched_rules_raise_a_blocking_qa_issue(self):
        from screen2xyz_civil.takeoff import LINE

        session = self._session()
        session.add_takeoff(
            rule_id="DITCH_REGRADE",
            geometry_kind=LINE,
            points=((10.0, 10.0), (110.0, 10.0)),
            coordinate_frame="pdf_points",
            now="2026-09-03T00:00:00+00:00",
            source_engine="test",
            source_method="test",
            generated_by="agent",
        )
        qa = session.qa_summary()
        codes = {issue["code"] for issue in qa["issues"]}
        self.assertIn("SCOPE_NOT_SEARCHED", codes)
        self.assertGreaterEqual(qa["issue_counts"]["ERROR"], 1)
        self.assertGreater(qa["scope"]["unsearched_count"], 0)

    def test_exported_plan_carries_the_scope_ledger(self):
        session = self._session()
        plan = session.bluebeam_plan()
        self.assertIn("scope", plan)
        self.assertEqual(
            plan["scope"]["unsearched_count"], plan["qa"]["scope"]["unsearched_count"]
        )

    def test_overlapping_polygons_of_one_rule_are_flagged(self):
        from screen2xyz_civil.takeoff import POLYGON

        session = self._session()
        for ring in (
            ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)),
            ((10.0, 10.0), (90.0, 10.0), (90.0, 90.0), (10.0, 90.0)),
        ):
            session.add_takeoff(
                rule_id="ROAD_WIDENING_FULL_STRUCTURE",
                geometry_kind=POLYGON,
                points=ring,
                coordinate_frame="pdf_points",
                now="2026-09-03T00:00:00+00:00",
                source_engine="test",
                source_method="test",
                generated_by="agent",
            )
        codes = {issue["code"] for issue in session.qa_summary()["issues"]}
        self.assertIn("POSSIBLE_DUPLICATE_TAKEOFF", codes)
