from __future__ import annotations

import unittest
from pathlib import Path

from screen2xyz_m1.assist import (
    AssistRequest,
    AssistantUnavailable,
    NullAssistant,
    OpenAIAssistantBoundary,
)
from screen2xyz_m1.evaluation import build_m1_scenarios, _ground_truth_bytes

from .helpers_m1 import ROOT


def _m1_source_text() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "src/screen2xyz_m1").rglob("*")
        if path.is_file() and path.suffix in {".py", ".ps1"}
    )


class BoundaryTests(unittest.TestCase):
    def test_no_network_code_in_m1_sources(self):
        text = _m1_source_text().lower()
        for token in ("import socket", "import urllib", "import requests", "http://", "https://"):
            self.assertNotIn(token, text)

    def test_no_screen_capture_in_m1_sources(self):
        text = _m1_source_text()
        self.assertNotIn("CopyFromScreen", text)
        self.assertNotIn("keybd_event", text)
        self.assertNotIn("GetAsyncKeyState", text)

    def test_null_assistant_reports_disabled(self):
        request = AssistRequest("raw", "1", "2", "3", ())
        result = NullAssistant().review_note(request)
        self.assertFalse(result.available)

    def test_openai_boundary_fails_closed(self):
        request = AssistRequest("raw", "1", "2", "3", ())
        result = OpenAIAssistantBoundary().review_note(request)
        self.assertFalse(result.available)
        with self.assertRaises(AssistantUnavailable):
            OpenAIAssistantBoundary(opted_in=True).review_note(request)

    def test_assist_request_carries_text_only(self):
        # The request dataclass must not accept image bytes or paths.
        fields = set(AssistRequest.__dataclass_fields__)
        self.assertEqual(
            fields,
            {
                "raw_text_display",
                "parsed_latitude",
                "parsed_longitude",
                "parsed_elevation_m",
                "reason_codes",
            },
        )

    def test_m1_scenarios_are_deterministic(self):
        first = build_m1_scenarios()
        second = build_m1_scenarios()
        self.assertEqual(first, second)
        self.assertEqual(len(first), 24)
        ids = [row["scenario_id"] for row in first]
        self.assertEqual(len(set(ids)), 24)
        self.assertEqual(sum(row["expected_disposition"] == "ACCEPT" for row in first), 15)
        self.assertEqual(sum(row["expected_disposition"] == "REJECT" for row in first), 9)
        self.assertEqual(_ground_truth_bytes(first), _ground_truth_bytes(second))

    def test_run_outputs_stay_out_of_git(self):
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".lab_work/", ignore)
        self.assertTrue(str(Path(".lab_work/m1_runs")).startswith(".lab_work"))
