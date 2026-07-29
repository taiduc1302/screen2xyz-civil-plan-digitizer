"""Deterministic, mocked tests for demo.run_self_test_with_retries.

Spawning the real demo target + PowerShell worker belongs to manual/CI-
integration verification (python -m screen2xyz_m2 demo); this file exercises
only the retry-selection logic itself, with run_self_test mocked out.
"""

from __future__ import annotations

import unittest
from unittest import mock

from screen2xyz_m2 import demo


class RetryLogicTests(unittest.TestCase):
    def test_pass_on_first_attempt_does_not_retry(self):
        calls = []

        def fake(on_progress=None, interval_ms=300):
            calls.append(1)
            return {"overall": "PASS", "checks": {"a": True}, "notes": {}}

        with mock.patch.object(demo, "run_self_test", fake):
            report = demo.run_self_test_with_retries(max_attempts=3)
        self.assertEqual(report["overall"], "PASS")
        self.assertEqual(report["attempts"], 1)
        self.assertEqual(len(calls), 1)

    def test_ipc_timeout_retries_up_to_max_attempts(self):
        calls = []

        def fake(on_progress=None, interval_ms=300):
            calls.append(1)
            return {"overall": "FAIL", "checks": {},
                    "error": "TimeoutError: demo target did not respond "
                            "within 8.0s",
                    "notes": {"failed_phase": "preview"}}

        with mock.patch.object(demo, "run_self_test", fake):
            report = demo.run_self_test_with_retries(max_attempts=3)
        self.assertEqual(report["overall"], "FAIL")
        self.assertEqual(report["attempts"], 3)
        self.assertEqual(len(calls), 3)  # exhausted every attempt

    def test_ipc_timeout_then_pass_stops_early(self):
        calls = []

        def fake(on_progress=None, interval_ms=300):
            calls.append(1)
            if len(calls) < 2:
                return {"overall": "FAIL", "checks": {},
                        "error": "TimeoutError: demo target did not "
                                "respond within 8.0s", "notes": {}}
            return {"overall": "PASS", "checks": {"a": True}, "notes": {}}

        with mock.patch.object(demo, "run_self_test", fake):
            report = demo.run_self_test_with_retries(max_attempts=3)
        self.assertEqual(report["overall"], "PASS")
        self.assertEqual(report["attempts"], 2)
        self.assertEqual(len(calls), 2)  # stopped as soon as it passed

    def test_genuine_assertion_failure_never_retries(self):
        # A real assertion failure (not an IPC timeout) must be returned
        # immediately - retrying it would waste time on a failure that is
        # not going to fix itself with a fresh process.
        calls = []

        def fake(on_progress=None, interval_ms=300):
            calls.append(1)
            return {"overall": "FAIL",
                    "checks": {"changing_values_retained": False},
                    "notes": {"failed_phase": "changing case"}}

        with mock.patch.object(demo, "run_self_test", fake):
            report = demo.run_self_test_with_retries(max_attempts=3)
        self.assertEqual(report["overall"], "FAIL")
        self.assertEqual(report["attempts"], 1)
        self.assertEqual(len(calls), 1)  # never retried a real failure

    def test_progress_callback_forwarded(self):
        messages = []

        def fake(on_progress=None, interval_ms=300):
            if on_progress:
                on_progress("hello")
            return {"overall": "PASS", "checks": {}, "notes": {}}

        with mock.patch.object(demo, "run_self_test", fake):
            demo.run_self_test_with_retries(on_progress=messages.append,
                                            max_attempts=2)
        self.assertIn("hello", messages)
