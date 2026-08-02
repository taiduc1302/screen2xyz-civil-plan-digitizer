from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from screen2xyz_app import __version__
from screen2xyz_app.dependencies import poppler_capability, tesseract_capability
from screen2xyz_app.ui.layout import HOME_MODES, WIZARD_STEPS
from screen2xyz_app.ui.guide import first_run_pending, load_steps, mark_first_run_complete


class LauncherTests(unittest.TestCase):
    def test_home_has_exactly_three_plain_modes(self) -> None:
        self.assertEqual(
            HOME_MODES,
            ("Live screen capture", "Load PDF", "Load image"),
        )

    def test_wizard_has_five_steps(self) -> None:
        self.assertEqual(len(WIZARD_STEPS), 5)
        self.assertEqual(__version__, "2.5.0")

    def test_bundled_quick_start_has_five_illustrated_steps(self) -> None:
        steps = load_steps()
        self.assertEqual(len(steps), 5)
        self.assertTrue(all(image.is_file() for _title, _body, image in steps))

    def test_first_run_marker_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            self.assertTrue(first_run_pending(path))
            mark_first_run_complete(path)
            self.assertFalse(first_run_pending(path))

    def test_missing_tools_have_exact_install_help(self) -> None:
        with patch("screen2xyz_app.dependencies.TesseractOcrAdapter.find_executable", return_value=None):
            tesseract = tesseract_capability()
        with patch("screen2xyz_app.dependencies._resolve_renderer", return_value=None):
            poppler = poppler_capability()
        self.assertFalse(tesseract.available)
        self.assertIn("winget install", tesseract.install_command)
        self.assertTrue(tesseract.download_url.startswith("https://"))
        self.assertFalse(poppler.available)
        self.assertIn("winget install", poppler.install_command)
        self.assertIn("disabled", poppler.detail)


if __name__ == "__main__":
    unittest.main()
