from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from screen2xyz_app import __version__
from screen2xyz_app.ui.layout import APP_TITLE
from screen2xyz_app.dependencies import poppler_capability, tesseract_capability
from screen2xyz_app.ui.layout import HOME_MODES, WIZARD_STEPS
from screen2xyz_app.ui.guide import first_run_pending, load_steps, mark_first_run_complete
from screen2xyz_civil.ocr import adapter_script_path


class LauncherTests(unittest.TestCase):
    def test_home_exposes_capture_and_civil_digitizer_modes(self) -> None:
        self.assertEqual(
            HOME_MODES,
            (
                "Live screen capture", "Load PDF", "Load image",
                "Civil Plan Digitizer",
            ),
        )

    def test_wizard_has_five_steps(self) -> None:
        self.assertEqual(len(WIZARD_STEPS), 5)
        self.assertEqual(__version__, "2.7.0")
        self.assertEqual(APP_TITLE, "Screen2XYZ v2.7")

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

    def test_windows_ocr_helper_resolves_next_to_packaged_module(self) -> None:
        path = adapter_script_path(Path("missing-repository"), "ocr_windows_boxes.ps1")
        self.assertTrue(path.is_file())
        self.assertEqual(path.name, "ocr_windows_boxes.ps1")


if __name__ == "__main__":
    unittest.main()
