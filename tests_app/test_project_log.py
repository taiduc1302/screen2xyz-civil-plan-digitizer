from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProjectLogGuardTests(unittest.TestCase):
    def test_project_log_exists(self) -> None:
        self.assertTrue((ROOT / "docs" / "PROJECT_LOG.md").is_file())

    def test_agents_points_to_project_log(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("docs/PROJECT_LOG.md", agents)

    def test_agents_has_no_deleted_control_file_references(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertNotIn("docs/control/PROJECT_STATE.md", agents)
        self.assertNotIn("docs/control/NEXT_ACTION.md", agents)


if __name__ == "__main__":
    unittest.main()
