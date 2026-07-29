from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from screen2xyz_m2 import contracts as C
from screen2xyz_m2 import profiles as profiles_mod
from screen2xyz_m2.models import (SessionDefaults, SourceConfig,
                                  ValidationError, new_source_id)
from screen2xyz_m2.profiles import (Profile, environment_mismatches,
                                    load_profile, new_profile, save_profile)

ROOT = Path(__file__).resolve().parents[1]


def sources() -> list[SourceConfig]:
    return [SourceConfig(source_id=new_source_id(), display_name=name,
                         rect=(10, 10 + 40 * index, 180, 28))
            for index, name in enumerate(("A", "B", "C"))]


class ProfileTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        patcher = mock.patch.object(profiles_mod, "profile_root",
                                    lambda: Path(self._tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def test_round_trip(self):
        profile = new_profile("Demo", {"type": "window"}, sources(),
                              SessionDefaults(),
                              {"window": {"client_w": 900, "client_h": 300,
                                          "dpi": 96}})
        save_profile(profile)
        loaded = load_profile(profile.profile_id)
        self.assertEqual(len(loaded.sources), 3)
        self.assertEqual(loaded.defaults.interval_ms, 1000)
        self.assertFalse(loaded.defaults.cursor_metadata)

    def test_oversized_profile_rejected(self):
        profile = new_profile("Big", {"type": "window"}, sources(),
                              SessionDefaults(), {})
        profile.sources[0].notes = "x" * 400
        with mock.patch.object(profiles_mod.C, "PROFILE_FILE_MAX_BYTES", 512):
            with self.assertRaises(ValidationError):
                save_profile(profile)

    def test_traversal_rejected_on_load(self):
        from screen2xyz_m2.paths import UnsafePath
        with self.assertRaises(UnsafePath):
            load_profile("../../evil")

    def test_mismatch_detection(self):
        snapshot = {"window": {"client_w": 900, "client_h": 300, "dpi": 96},
                    "monitors": [{"index": 0}], "backend": "printwindow_clientonly"}
        live_same = {"window": {"client_w": 900, "client_h": 300, "dpi": 96},
                     "monitors": [{"index": 0}],
                     "backend": "printwindow_clientonly"}
        self.assertEqual(environment_mismatches(snapshot, live_same), [])
        live_resized = {"window": {"client_w": 800, "client_h": 300,
                                   "dpi": 96},
                        "monitors": [{"index": 0}],
                        "backend": "printwindow_clientonly"}
        self.assertTrue(any("client_w" in item for item in
                            environment_mismatches(snapshot, live_resized)))
        live_dpi = {"window": {"client_w": 900, "client_h": 300, "dpi": 120},
                    "monitors": [{"index": 0}],
                    "backend": "printwindow_clientonly"}
        self.assertTrue(any("dpi" in item for item in
                            environment_mismatches(snapshot, live_dpi)))
        live_topology = {"window": {"client_w": 900, "client_h": 300,
                                    "dpi": 96},
                         "monitors": [{"index": 0}, {"index": 1}],
                         "backend": "printwindow_clientonly"}
        self.assertTrue(any("topology" in item for item in
                            environment_mismatches(snapshot, live_topology)))


class SourceScanTests(unittest.TestCase):
    """No-network / no-hidden-capture / no-pointer-control source scan."""

    def _source_text(self) -> str:
        package = ROOT / "src" / "screen2xyz_m2"
        return "\n".join(path.read_text(encoding="utf-8")
                         for path in package.rglob("*")
                         if path.is_file()
                         and path.suffix in (".py", ".ps1"))

    def test_no_network(self):
        text = self._source_text().lower()
        for token in ("import socket", "import urllib", "import requests",
                      "http://", "https://", "httpclient", "webrequest",
                      "invoke-webrequest", "invoke-restmethod"):
            self.assertNotIn(token, text, token)

    def test_no_pointer_control_or_keylogging(self):
        text = self._source_text()
        for token in ("SetCursorPos", "mouse_event", "SendInput",
                      "keybd_event", "SetWindowsHookEx",
                      "GetAsyncKeyState", "RegisterHotKey"):
            self.assertNotIn(token, text, token)

    def test_no_hidden_capture_or_autostart(self):
        text = self._source_text()
        for token in ("CurrentVersion\\Run", "schtasks", "New-Service",
                      "Register-ScheduledTask"):
            self.assertNotIn(token, text, token)

    def test_no_undocumented_printwindow_flag(self):
        self.assertNotIn("PW_RENDERFULLCONTENT", self._source_text())

    def test_no_baseline_private_parser_imports(self):
        text = self._source_text()
        self.assertNotIn("_canonical_decimal", text)
        self.assertNotIn("_NUMBER_RE", text)
        self.assertNotIn("from screen2xyz_lab.parser import", text)


class RunOutputHygieneTests(unittest.TestCase):
    def test_run_roots_are_ignored(self):
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".lab_work/", ignore)
        self.assertTrue(C.RUN_ROOT_RELATIVE.startswith(".lab_work/"))
        self.assertTrue(C.PROFILE_ROOT_RELATIVE.startswith(".lab_work/"))
