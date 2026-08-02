from __future__ import annotations

import unittest

from screen2xyz_app import __version__
from screen2xyz_app.ui.layout import HOME_MODES, WIZARD_STEPS


class LauncherTests(unittest.TestCase):
    def test_home_has_exactly_three_plain_modes(self) -> None:
        self.assertEqual(
            HOME_MODES,
            ("Live screen capture", "Load PDF", "Load image"),
        )

    def test_wizard_has_five_steps(self) -> None:
        self.assertEqual(len(WIZARD_STEPS), 5)
        self.assertEqual(__version__, "2.0.0")


if __name__ == "__main__":
    unittest.main()
