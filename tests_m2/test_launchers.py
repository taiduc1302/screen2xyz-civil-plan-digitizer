"""Static checks on the one-click PowerShell launchers (§13/§28/§30/§31/§35).
No PowerShell is executed - these assert the source text has the properties
the packaging review required, so the launchers cannot silently regress."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCHERS = ["run_screen2xyz.ps1", "run_screen2xyz_demo.ps1",
             "run_screen2xyz_validation.ps1", "run_screen2xyz_menu.ps1",
             "run_civil_plan_digitizer.ps1"]


def _text(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


class LauncherTests(unittest.TestCase):
    def test_all_launchers_exist(self):
        for name in LAUNCHERS:
            self.assertTrue((ROOT / name).is_file(), name)

    def test_use_psscriptroot_not_myinvocation(self):
        # §35: robust repo-root resolution.
        for name in LAUNCHERS:
            text = _text(name)
            self.assertIn("$PSScriptRoot", text, name)
            self.assertNotIn("MyInvocation.MyCommand.Path", text, name)

    def test_no_impossible_pip_install_editable(self):
        # §28: there is no packaging metadata, so `pip install -e .` fails and
        # is unnecessary (stdlib-only). No launcher may instruct it.
        for name in LAUNCHERS:
            self.assertNotIn("pip install -e", _text(name), name)

    def test_have_venv_check_and_error_pause(self):
        for name in LAUNCHERS:
            text = _text(name)
            self.assertIn(".venv\\Scripts\\python.exe", text, name)
            self.assertIn("Read-Host", text, name)  # keep window open

    def test_wrapped_in_try_catch(self):
        # §31: a terminating error must not close the window silently.
        for name in LAUNCHERS:
            text = _text(name)
            self.assertIn("try {", text, name)
            self.assertIn("} catch {", text, name)

    def test_demo_launcher_holds_window_on_pass(self):
        # §13: the demo report must not vanish on the PASS (exit 0) path -
        # the Read-Host must NOT be gated behind a non-zero exit code only.
        text = _text("run_screen2xyz_demo.ps1")
        self.assertIn("PASS", text)
        # The final Read-Host is unconditional (outside any exit-code branch).
        self.assertRegex(text, r'Read-Host "Press Enter to close"\s*\n\s*exit')

    def test_menu_delegates_to_dedicated_launchers(self):
        # §30: the menu must call the real launchers (shared result/pause),
        # not re-invoke the python module directly and drop the result line.
        text = _text("run_screen2xyz_menu.ps1")
        self.assertIn("run_screen2xyz.ps1", text)
        self.assertIn("run_screen2xyz_validation.ps1", text)
        self.assertIn("run_civil_plan_digitizer.ps1", text)

    def test_no_launcher_claims_double_click_runs(self):
        # §29: double-clicking a .ps1 opens an editor; no launcher may make
        # the old FALSE claim that double-clicking runs it. (Warning the user
        # AGAINST double-click is fine and expected.)
        for name in LAUNCHERS:
            text = _text(name).lower()
            self.assertNotIn("double-clicking from explorer", text, name)
            self.assertNotIn("both work identically", text, name)

    def test_guide_leads_with_right_click_run(self):
        guide = (ROOT / "docs/public/Screen2XYZ_M2_Guide_v0.1.md").read_text(
            encoding="utf-8").lower()
        self.assertIn("run with powershell", guide)
        self.assertNotIn("pip install -e", guide)


if __name__ == "__main__":
    unittest.main()
