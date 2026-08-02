"""Static checks for the single public Screen2XYZ v2 launcher."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCHERS = ["run_screen2xyz.ps1"]


def _text(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


class LauncherTests(unittest.TestCase):
    def test_all_launchers_exist(self):
        for name in LAUNCHERS:
            self.assertTrue((ROOT / name).is_file(), name)

    def test_use_psscriptroot_not_myinvocation(self):
        for name in LAUNCHERS:
            text = _text(name)
            self.assertIn("$PSScriptRoot", text, name)
            self.assertNotIn("MyInvocation.MyCommand.Path", text, name)

    def test_no_impossible_pip_install_editable(self):
        for name in LAUNCHERS:
            self.assertNotIn("pip install -e", _text(name), name)

    def test_have_venv_check_and_error_pause(self):
        text = _text("run_screen2xyz.ps1")
        self.assertIn(".venv\\Scripts\\python.exe", text)
        self.assertIn("Read-Host", text)

    def test_wrapped_in_try_catch(self):
        text = _text("run_screen2xyz.ps1")
        self.assertIn("try {", text)
        self.assertIn("} catch {", text)

    def test_launcher_calls_unified_app(self):
        self.assertIn("-m screen2xyz_app", _text("run_screen2xyz.ps1"))

    def test_no_legacy_launcher_delegation(self):
        text = _text("run_screen2xyz.ps1")
        self.assertNotIn("screen2xyz_m1", text)
        self.assertNotIn("screen2xyz_lab", text)

    def test_no_launcher_claims_double_click_runs(self):
        text = _text("run_screen2xyz.ps1").lower()
        self.assertNotIn("double-clicking from explorer", text)
        self.assertNotIn("both work identically", text)

    def test_guide_leads_with_unified_workflow(self):
        guide = (ROOT / "docs/public/Screen2XYZ_V2_Guide.md").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn("screen_zone_ocr", guide)
        self.assertIn("export xlsx", guide)


if __name__ == "__main__":
    unittest.main()
