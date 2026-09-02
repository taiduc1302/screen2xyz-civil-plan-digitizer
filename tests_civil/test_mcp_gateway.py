from __future__ import annotations

import unittest

from mcp import Client

from screen2xyz_civil.agent_session import load_agent_session, new_agent_session, save_agent_session
from screen2xyz_civil.mcp_gateway import build_mcp_server

from .helpers_civil import fresh_dir, make_vector_pdf


NOW = "2026-09-02T19:20:00+00:00"


class McpGatewayTests(unittest.IsolatedAsyncioTestCase):
    def make_gateway(self):
        root = fresh_dir()
        pdf = make_vector_pdf(root / "plan.pdf", "SHEET 03 DITCH INFILL", with_shapes=True)
        session = new_agent_session(
            pdf,
            page_number=1,
            page_label="03",
            name="MCP pilot",
            now=NOW,
            render_dpi=150,
        )
        session_path = root / "pilot.s2a.json"
        save_agent_session(session, session_path)
        return session_path, build_mcp_server(session_path)

    async def test_gateway_exposes_proposal_tools_but_no_approval_tool(self):
        _path, server = self.make_gateway()
        async with Client(server) as client:
            listed = await client.list_tools()
            names = {tool.name for tool in listed.tools}
        self.assertIn("propose_line_takeoff", names)
        self.assertIn("propose_polygon_takeoff", names)
        self.assertIn("auto_trace_area", names)
        self.assertIn("export_bluebeam_markup_plan", names)
        self.assertNotIn("approve_takeoff", names)
        self.assertNotIn("publish_final_export", names)

    async def test_session_status_discloses_human_only_boundary(self):
        _path, server = self.make_gateway()
        async with Client(server) as client:
            result = await client.call_tool("session_status", {})
        self.assertFalse(result.is_error)
        payload = result.structured_content
        self.assertEqual(payload["source"]["page_label"], "03")
        self.assertIn("approve final bid quantity", payload["human_only"])

    async def test_agent_line_proposal_persists_with_scale_blocker(self):
        path, server = self.make_gateway()
        async with Client(server) as client:
            result = await client.call_tool(
                "propose_line_takeoff",
                {
                    "rule_id": "DRIVEWAY_CULVERT_300",
                    "points": [[100, 100], [250, 100]],
                    "coordinate_frame": "render_px",
                    "bid_item": "33.01",
                    "notes": "North driveway",
                },
            )
        self.assertFalse(result.is_error)
        restored = load_agent_session(path)
        self.assertEqual(len(restored.measurements), 1)
        self.assertIn("SCALE_UNVERIFIED", restored.measurements[0].flags)
        self.assertEqual(restored.measurements[0].bid_item, "33.01")

    async def test_anchor_polygon_remains_reference_only(self):
        path, server = self.make_gateway()
        async with Client(server) as client:
            result = await client.call_tool(
                "propose_polygon_takeoff",
                {
                    "rule_id": "ANCHOR_ROADWORKS_EXTENT",
                    "points": [[50, 50], [300, 50], [300, 250], [50, 250]],
                    "coordinate_frame": "render_px",
                },
            )
            self.assertFalse(result.is_error)
            listed = await client.call_tool("list_takeoffs", {})
        row = listed.structured_content["takeoffs"][0]
        self.assertFalse(row["summable"])
        restored = load_agent_session(path)
        self.assertFalse(restored.measurements[0].summable)

    async def test_flag_and_question_are_persistent_first_class_uncertainty(self):
        path, server = self.make_gateway()
        async with Client(server) as client:
            proposed = await client.call_tool(
                "propose_line_takeoff",
                {
                    "rule_id": "DITCH_REGRADE",
                    "points": [[100, 100], [250, 100]],
                    "coordinate_frame": "render_px",
                },
            )
            takeoff_id = proposed.structured_content["takeoff"]["id"]
            flagged = await client.call_tool(
                "flag_takeoff", {"takeoff_id": takeoff_id, "flag": "MIXED"}
            )
            self.assertFalse(flagged.is_error)
            question = await client.call_tool(
                "raise_question",
                {
                    "detail": "Trace mixes ditch regrade and relocation.",
                    "next_action": "Split at the transition and review.",
                    "reason_code": "MIXED_SCOPE",
                    "severity": "ERROR",
                    "related_takeoff_ids": [takeoff_id],
                },
            )
            self.assertFalse(question.is_error)
        restored = load_agent_session(path)
        self.assertIn("MIXED", restored.measurements[0].flags)
        self.assertEqual(restored.context.unresolved_summary()["error_count"], 1)

    async def test_sheet_text_is_explicitly_untrusted_evidence(self):
        _path, server = self.make_gateway()
        async with Client(server) as client:
            result = await client.call_tool("read_sheet_text", {"max_chars": 5000})
        self.assertFalse(result.is_error)
        payload = result.structured_content
        self.assertEqual(payload["trust"], "UNTRUSTED_DRAWING_EVIDENCE")
        self.assertIn("DITCH", payload["text"])


if __name__ == "__main__":
    unittest.main()
