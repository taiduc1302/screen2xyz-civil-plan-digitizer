from __future__ import annotations

import os
import sys
import unittest

from mcp import Client, StdioServerParameters

from screen2xyz_civil.agent_session import load_agent_session, new_agent_session, save_agent_session

from .helpers_civil import ROOT, fresh_dir
from .test_opentakeoff_runtime_live import make_closed_room_pdf


RUN_LIVE = os.environ.get("SCREEN2XYZ_RUN_OPERATOR_LIVE") == "1"
NOW = "2026-09-02T20:40:00+00:00"


@unittest.skipUnless(
    RUN_LIVE,
    "live operator smoke requires SCREEN2XYZ_RUN_OPERATOR_LIVE=1 and Poppler",
)
class OperatorLiveTests(unittest.IsolatedAsyncioTestCase):
    async def test_external_stdio_can_view_sheet_and_persist_proposal(self):
        root = fresh_dir()
        pdf = make_closed_room_pdf(root / "operator.pdf")
        session = new_agent_session(
            pdf,
            page_number=1,
            page_label="SYN-OP",
            name="Claude operator synthetic",
            now=NOW,
            render_dpi=150,
        )
        session_path = root / "operator.s2a.json"
        save_agent_session(session, session_path)
        params = StdioServerParameters(
            command=sys.executable,
            args=[
                "-m",
                "screen2xyz_civil",
                "mcp",
                "--session",
                str(session_path),
            ],
            env={"PYTHONPATH": str(ROOT / "src")},
        )
        async with Client(params) as client:
            status = await client.call_tool("session_status", {})
            self.assertFalse(status.is_error, status)
            self.assertEqual(status.structured_content["source"]["page_label"], "SYN-OP")

            viewed = await client.call_tool("view_sheet", {})
            self.assertFalse(viewed.is_error, viewed)
            image_blocks = [
                block
                for block in viewed.content
                if getattr(block, "type", None) == "image"
            ]
            self.assertTrue(image_blocks, viewed)
            self.assertTrue(getattr(image_blocks[0], "data", ""))

            proposed = await client.call_tool(
                "propose_polygon_takeoff",
                {
                    "rule_id": "DITCH_INFILL",
                    "points": [[100, 100], [300, 100], [300, 300], [100, 300]],
                    "coordinate_frame": "pdf_points",
                    "label": "Synthetic ditch infill",
                },
            )
            self.assertFalse(proposed.is_error, proposed)

        restored = load_agent_session(session_path)
        self.assertEqual(len(restored.measurements), 1)
        self.assertEqual(restored.measurements[0].rule_id, "DITCH_INFILL")
        self.assertIn("SCALE_UNVERIFIED", restored.measurements[0].flags)


if __name__ == "__main__":
    unittest.main()
