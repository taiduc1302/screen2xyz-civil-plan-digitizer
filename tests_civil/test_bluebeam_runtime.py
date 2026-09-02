from __future__ import annotations

import unittest
from pathlib import Path

from screen2xyz_civil.bluebeam_runtime import (
    BLUEBEAM_OVERRIDE_ENV,
    bluebeam_claude_registration,
    candidate_bluebeam_mcp_paths,
    claude_stdio_add_command,
    resolve_bluebeam_mcp_executable,
)

from .helpers_civil import fresh_dir


class BluebeamRuntimeTests(unittest.TestCase):
    def test_override_candidate_is_first_and_deterministic(self):
        root = fresh_dir()
        override = root / "Bluebeam MCP Server.exe"
        env = {
            BLUEBEAM_OVERRIDE_ENV: str(override),
            "ProgramFiles": str(root / "Program Files"),
            "ProgramW6432": str(root / "Program Files"),
        }
        candidates = candidate_bluebeam_mcp_paths(env)
        self.assertEqual(candidates[0], override)
        self.assertEqual(len({str(path).casefold() for path in candidates}), len(candidates))

    def test_existing_override_resolves_without_claiming_live_measurement(self):
        root = fresh_dir()
        executable = root / "Bluebeam MCP Server.exe"
        executable.write_bytes(b"synthetic-test-placeholder")
        env = {BLUEBEAM_OVERRIDE_ENV: str(executable)}
        resolved = resolve_bluebeam_mcp_executable(env)
        self.assertEqual(resolved, executable.resolve())
        registration = bluebeam_claude_registration(env)
        self.assertTrue(registration["available"])
        self.assertFalse(registration["live_tested"])
        self.assertEqual(
            registration["capability_state"],
            "DISCOVERED_STDIO_ROUTE_NOT_LIVE_TESTED",
        )
        self.assertIn("bluebeam-revu", registration["claude_command"])
        self.assertIn(str(executable.resolve()), registration["claude_command"])

    def test_claude_stdio_command_separates_host_options_from_server_args(self):
        command = claude_stdio_add_command(
            name="screen2xyz",
            executable=Path(r"C:\Tools With Space\python.exe"),
            args=("-m", "screen2xyz_civil", "--session", r"C:\Tender\S 03.s2a.json"),
            env={"PYTHONPATH": r"C:\Repo With Space\src"},
        )
        self.assertIn("claude mcp add --transport stdio", command)
        self.assertIn("--env 'PYTHONPATH=C:\\Repo With Space\\src'", command)
        self.assertIn("screen2xyz -- 'C:\\Tools With Space\\python.exe'", command)
        self.assertIn("'C:\\Tender\\S 03.s2a.json'", command)


if __name__ == "__main__":
    unittest.main()
