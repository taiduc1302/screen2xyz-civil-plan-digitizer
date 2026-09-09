from __future__ import annotations

import sys
import unittest

from mcp import Client, StdioServerParameters

from screen2xyz_civil.agent_session import load_agent_session, new_agent_session, save_agent_session

from .helpers_civil import ROOT, fresh_dir, make_vector_pdf


NOW = "2026-09-02T20:20:00+00:00"


class McpGatewayStdioTests(unittest.IsolatedAsyncioTestCase):
    def make_server_params(self):
        root = fresh_dir()
        pdf = make_vector_pdf(root / "plan.pdf", "SHEET 03 300 DIA CULVERT", with_shapes=True)
        session = new_agent_session(
            pdf,
            page_number=1,
            page_label="03",
            name="stdio pilot",
            now=NOW,
            render_dpi=150,
        )
        session_path = root / "stdio.s2a.json"
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
        return session_path, params

    async def test_real_stdio_subprocess_initializes_and_lists_safe_tools(self):
        _path, params = self.make_server_params()
        async with Client(params) as client:
            listed = await client.list_tools()
            names = {tool.name for tool in listed.tools}
            self.assertIn("session_status", names)
            self.assertIn("propose_line_takeoff", names)
            self.assertNotIn("approve_takeoff", names)

    async def test_real_stdio_subprocess_can_persist_agent_proposal(self):
        path, params = self.make_server_params()
        async with Client(params) as client:
            result = await client.call_tool(
                "propose_line_takeoff",
                {
                    "rule_id": "DRIVEWAY_CULVERT_300",
                    "points": [[100, 100], [250, 100]],
                    "coordinate_frame": "render_px",
                    "bid_item": "33.01",
                    "notes": "Claude-style stdio subprocess smoke",
                },
            )
            self.assertFalse(result.is_error, result)
        restored = load_agent_session(path)
        self.assertEqual(len(restored.measurements), 1)
        self.assertEqual(restored.measurements[0].bid_item, "33.01")
        self.assertIn("SCALE_UNVERIFIED", restored.measurements[0].flags)


if __name__ == "__main__":
    unittest.main()
