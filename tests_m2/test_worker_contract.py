from __future__ import annotations

import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from screen2xyz_m2 import worker as worker_mod
from screen2xyz_m2.worker import WorkerClient, WorkerError, WorkerTimeout

HERE = Path(__file__).resolve().parent
MOCK = HERE / "mock_worker.py"


def client(behavior: str = "normal") -> WorkerClient:
    return WorkerClient(
        session_id="s", scope={"type": "window", "hwnd": 1, "pid": 1},
        backend="printwindow_clientonly",
        spawn_command=[sys.executable, "-u", str(MOCK), behavior])


class WorkerContractTests(unittest.TestCase):
    def test_init_negotiation_and_echo(self):
        c = client()
        try:
            reply = c.start(restore_session_state="REGIONS_CONFIGURED",
                            configuration_revision=3)
            self.assertEqual(reply["dpi_awareness"], "per_monitor_v2")
            self.assertEqual(reply["configuration_revision"], 3)
            self.assertEqual(reply["worker_generation"], c.generation)
            self.assertEqual(reply["limits"]["max_crop_png_bytes"], 8388608)
        finally:
            c.teardown()

    def test_bad_dpi_refused(self):
        c = client("bad_dpi")
        try:
            with self.assertRaises(WorkerError) as caught:
                c.start(restore_session_state="REGIONS_CONFIGURED",
                        configuration_revision=0)
            self.assertIn("PMv2", str(caught.exception))
        finally:
            c.teardown()

    def test_init_error_raises(self):
        c = client("init_error")
        try:
            with self.assertRaises(WorkerError):
                c.start(restore_session_state="REGIONS_CONFIGURED",
                        configuration_revision=0)
        finally:
            c.teardown()

    def test_capture_roundtrip_one_response_per_request(self):
        c = client()
        try:
            c.start(restore_session_state="RECORDING",
                    configuration_revision=0)
            reply = c.request("CAPTURE",
                              {"frame_seq": 7, "regions":
                               [{"source_id": "src-a",
                                 "rect": {"x": 0, "y": 0, "w": 10,
                                          "h": 10}}]},
                              timeout_ms=5000,
                              ui_session_state="RECORDING",
                              configuration_revision=0)
            self.assertEqual(reply["frame_seq"], 7)
            self.assertEqual(len(reply["observations"]), 1)
            # M2-FR-042: exactly one capture invocation per CAPTURE request
            self.assertEqual(reply["capture_calls"], 1)
            self.assertEqual(reply["timings"]["capture_ms"], 1)
        finally:
            c.teardown()

    def test_stale_reply_dropped(self):
        c = client("stale_then_ok")
        try:
            c.start(restore_session_state="RECORDING",
                    configuration_revision=0)
            reply = c.request("CAPTURE",
                              {"frame_seq": 1, "regions": []},
                              timeout_ms=5000,
                              ui_session_state="RECORDING",
                              configuration_revision=0)
            self.assertEqual(reply["frame_seq"], 1)
            self.assertTrue(any("stale" in line
                                for line in c.stderr_lines))
        finally:
            c.teardown()

    def test_timeout_and_no_prior_value_reuse(self):
        c = client("slow_capture")
        try:
            c.start(restore_session_state="RECORDING",
                    configuration_revision=0)
            started = time.monotonic()
            with self.assertRaises(WorkerTimeout):
                c.request("CAPTURE", {"frame_seq": 1, "regions": []},
                          timeout_ms=500,
                          ui_session_state="RECORDING",
                          configuration_revision=0)
            self.assertLess(time.monotonic() - started, 5)
        finally:
            c.teardown()
            self.assertFalse(c.alive)

    def test_malformed_stdout_fails_closed(self):
        c = client("malformed")
        try:
            c.start(restore_session_state="RECORDING",
                    configuration_revision=0)
            with self.assertRaises(WorkerError) as caught:
                c.request("CAPTURE", {"frame_seq": 1, "regions": []},
                          timeout_ms=5000,
                          ui_session_state="RECORDING",
                          configuration_revision=0)
            self.assertEqual(caught.exception.worker_status,
                             "PROCESS_EXITED")
        finally:
            c.teardown()

    def test_overlapping_request_refused(self):
        c = client("slow_capture")
        try:
            c.start(restore_session_state="RECORDING",
                    configuration_revision=0)
            errors: list[Exception] = []

            def long_request():
                try:
                    c.request("CAPTURE", {"frame_seq": 1, "regions": []},
                              timeout_ms=2000,
                              ui_session_state="RECORDING",
                              configuration_revision=0)
                except Exception as exc:
                    errors.append(exc)

            thread = threading.Thread(target=long_request)
            thread.start()
            time.sleep(0.3)
            with self.assertRaises(WorkerError) as caught:
                c.request("HEALTH", {}, timeout_ms=1000,
                          ui_session_state="RECORDING",
                          configuration_revision=0)
            self.assertIn("overlapping", caught.exception.detail)
            thread.join()
        finally:
            c.teardown()

    def test_worker_exit_detected(self):
        c = client("exit_after_init")
        try:
            c.start(restore_session_state="REGIONS_CONFIGURED",
                    configuration_revision=0)
            time.sleep(0.5)
            with self.assertRaises(WorkerError):
                c.request("HEALTH", {}, timeout_ms=2000,
                          ui_session_state="REGIONS_CONFIGURED",
                          configuration_revision=0)
        finally:
            c.teardown()

    def test_teardown_reaps_and_joins(self):
        c = client()
        c.start(restore_session_state="REGIONS_CONFIGURED",
                configuration_revision=0)
        proc = c._proc
        c.teardown()
        self.assertIsNotNone(proc.poll())
        self.assertFalse(c.alive)
        for reader in c._readers:
            self.assertFalse(reader.is_alive())

    def test_start_collects_cycles_before_reader_threads(self):
        c = client()
        try:
            with mock.patch.object(worker_mod.gc, "collect") as collect:
                c.start(restore_session_state="REGIONS_CONFIGURED",
                        configuration_revision=0)
            collect.assert_called_once_with()
        finally:
            c.teardown()

    def test_bounded_reader_rejects_oversized_line(self):
        with mock.patch.object(worker_mod.C, "JSON_LINE_MAX_BYTES", 64):
            c = client()
            try:
                with self.assertRaises(WorkerError):
                    c.start(restore_session_state="REGIONS_CONFIGURED",
                            configuration_revision=0)
            finally:
                c.teardown()
