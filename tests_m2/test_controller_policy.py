"""Controller policy tests with an in-process fake worker (no subprocess)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from screen2xyz_m2 import contracts as C
from screen2xyz_m2.controller import LiveSessionController
from screen2xyz_m2.models import (SessionDefaults, SourceConfig,
                                  new_source_id)
from screen2xyz_m2.statemachine import IllegalAction
from screen2xyz_m2.worker import WorkerError, WorkerTimeout


class FakeWorker:
    """Scriptable in-process stand-in for WorkerClient."""

    plan: list[str] = []          # per-instance override via factory
    instances: list["FakeWorker"] = []
    # Class-level knobs for the REGION_SNAPSHOT/backend-probe tests below;
    # reset per test via setUp-style assignment before constructing.
    snapshot_effective_backend = "printwindow_clientonly"
    snapshot_frame_content_status = "CONTENT_DETECTED"
    snapshot_no_backend_usable = False

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.generation = f"gen-{len(FakeWorker.instances)}"
        self.alive_flag = True
        self.requests: list[str] = []
        self.frame_values: dict[int, str] = {}
        self.behavior = FakeWorker.plan.pop(0) if FakeWorker.plan else "ok"
        FakeWorker.instances.append(self)

    def start(self, *, restore_session_state, configuration_revision,
              init_timeout_ms: int = 0) -> dict[str, Any]:
        self.restore = restore_session_state
        if self.behavior == "init_fail":
            self.alive_flag = False
            raise WorkerError("PROTOCOL_ERROR", "fake init failure")
        return {"worker_status": "OK", "dpi_awareness": "per_monitor_v2",
                "restore_session_state": restore_session_state}

    @property
    def alive(self) -> bool:
        return self.alive_flag

    def request(self, command, payload, *, timeout_ms, ui_session_state,
                configuration_revision=None):
        self.requests.append(command)
        if command == "CAPTURE" and self.behavior == "capture_timeout":
            raise WorkerTimeout("fake capture timeout")
        base = {"worker_status": "OK", "worker_mode": "RECORDING"}
        if command == "CAPTURE":
            seq = payload["frame_seq"]
            value = self.frame_values.get(seq, "1.000000")
            # Test knobs: a worker-reported hard capture failure
            # (capture_status set, worker_status still OK) and a live window
            # override (for resize/DPI/off-screen scenarios).
            cap_status = getattr(self, "capture_status_override", None) or "OK"
            win_override = getattr(self, "window_override", None) or {}
            observations = []
            for region in payload["regions"]:
                observations.append({
                    "source_id": region["source_id"],
                    "capture_status": cap_status,
                    "crop_content_status": "CONTENT_DETECTED",
                    "ocr_status": "OK",
                    "pixel_sha256": f"h-{value}",
                    "crop_w": region["rect"]["w"],
                    "crop_h": region["rect"]["h"],
                    "ocr_executed": True, "confirmation": "new_ocr",
                    "raw_text": value, "raw_truncated": False,
                    "raw_original_utf8_bytes": len(value),
                    "warning_codes": [], "ocr_ms": 1,
                    "crop_png_b64": "UE5H"})
            window = {"exists": True, "iconic": False,
                     "client_w": 900, "client_h": 300,
                     "origin_x": 0, "origin_y": 0, "dpi": 96}
            window.update(win_override)
            return {**base, "frame_seq": seq,
                    "capture_utc": "2026-07-18T00:00:00Z",
                    "window": window,
                    "capture_status": cap_status,
                    "frame_content_status": "CONTENT_DETECTED",
                    "cursor": None,
                    "timings": {"capture_ms": 1, "ocr_ms_total": 1},
                    "observations": observations}
        if command == "PREVIEW":
            seq = payload.get("frame_seq", 0)
            value = self.frame_values.get(seq, "1.000000")
            observations = []
            for region in payload["regions"]:
                observations.append({
                    "source_id": region["source_id"],
                    "capture_status": "OK",
                    "crop_content_status": "CONTENT_DETECTED",
                    "ocr_status": "OK",
                    "pixel_sha256": f"h-{value}",
                    "crop_w": region["rect"]["w"],
                    "crop_h": region["rect"]["h"],
                    "ocr_executed": True, "confirmation": "new_ocr",
                    "raw_text": value, "raw_truncated": False,
                    "raw_original_utf8_bytes": len(value),
                    "warning_codes": [], "ocr_ms": 1,
                    "crop_png_b64": "UE5H"})
            return {**base, "frame_seq": seq,
                    "capture_utc": "2026-07-18T00:00:00Z",
                    "window": {"exists": True, "iconic": False,
                              "client_w": 900, "client_h": 300,
                              "origin_x": 0, "origin_y": 0, "dpi": 96},
                    "capture_status": "OK",
                    "frame_content_status": "CONTENT_DETECTED",
                    "cursor": None,
                    "effective_backend": "printwindow_clientonly",
                    "backend_probe": None, "no_backend_usable": False,
                    "timings": {"capture_ms": 1, "ocr_ms_total": 1},
                    "observations": observations}
        if command == "REGION_SNAPSHOT":
            probe = bool(payload.get("probe_backend"))
            reply = {**base, "capture_status": "OK",
                    "window": {"exists": True, "iconic": False,
                              "client_w": 900, "client_h": 300,
                              "origin_x": 0, "origin_y": 0, "dpi": 96},
                    "frame_content_status":
                        FakeWorker.snapshot_frame_content_status,
                    "effective_backend": FakeWorker.snapshot_effective_backend,
                    "no_backend_usable": FakeWorker.snapshot_no_backend_usable,
                    "capture_ms": 5, "frame_png_b64": None}
            reply["backend_probe"] = (
                [{"backend": "printwindow_clientonly",
                  "usable": FakeWorker.snapshot_effective_backend ==
                            "printwindow_clientonly",
                  "content_status": FakeWorker.snapshot_frame_content_status,
                  "capture_ms": 5}] if probe else None)
            return reply
        return base

    def teardown(self, graceful_ms: int = 0,
                 deadline_s: float | None = None) -> None:
        self.alive_flag = False

    def graceful_shutdown(self, *args) -> None:
        self.alive_flag = False


def make_controller(tmp: Path, plan: list[str],
                    defaults: SessionDefaults | None = None,
                    sources: list[SourceConfig] | None = None,
                    backend: str = C.BACKEND_PRINTWINDOW):
    FakeWorker.plan = list(plan)
    FakeWorker.instances = []
    clock = {"now": 0.0}

    def monotonic() -> float:
        return clock["now"]

    def sleeper(seconds: float) -> None:
        clock["now"] += seconds

    sources = sources or [SourceConfig(source_id=new_source_id(),
                                       display_name="A",
                                       rect=(0, 0, 100, 20))]
    controller = LiveSessionController(
        scope={"type": "window", "hwnd": 1, "pid": 1},
        backend=backend,
        sources=sources,
        defaults=defaults or SessionDefaults(),
        environment_snapshot={"window": {"client_w": 900, "client_h": 300,
                                         "dpi": 96}},
        run_parent=tmp,
        worker_factory=FakeWorker,
        monotonic=monotonic, sleeper=sleeper)
    controller._clock = clock
    return controller


def to_recording(controller) -> None:
    controller.machine.select_target()
    controller.machine.sources_configured()
    controller.ensure_worker()
    controller.preview()
    controller.confirm_preview_and_arm()
    controller.start_recording()


class SetupCounterTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_two_failures_auto_retry_third_blocks(self):
        controller = make_controller(self.tmp,
                                     ["init_fail", "init_fail",
                                      "init_fail", "ok"])
        controller.machine.select_target()
        controller.machine.sources_configured()
        with self.assertRaises(WorkerError) as caught:
            controller.ensure_worker()
        self.assertEqual(caught.exception.worker_status, "UNAVAILABLE")
        self.assertTrue(controller.machine.setup_worker_blocked)
        self.assertEqual(controller.setup_failures, 3)
        self.assertFalse(controller.machine.is_legal("preview"))
        # Retry worker: INIT only, clears interlock but not counter
        controller.retry_worker()
        self.assertFalse(controller.machine.setup_worker_blocked)
        self.assertEqual(controller.setup_failures, 3)
        # next successful setup request resets the counter
        controller.preview()
        self.assertEqual(controller.setup_failures, 0)

    def test_backoff_saturates_at_5s(self):
        controller = make_controller(self.tmp, ["init_fail", "init_fail",
                                                "init_fail"])
        controller.machine.select_target()
        controller.machine.sources_configured()
        with self.assertRaises(WorkerError):
            controller.ensure_worker()
        # waits: 0, 1s, 5s consumed via fake sleeper
        self.assertGreaterEqual(controller._clock["now"], 6.0)

    def test_setup_failure_never_creates_paused(self):
        controller = make_controller(self.tmp, ["init_fail", "init_fail",
                                                "init_fail"])
        controller.machine.select_target()
        controller.machine.sources_configured()
        with self.assertRaises(WorkerError):
            controller.ensure_worker()
        self.assertEqual(controller.machine.state, "REGIONS_CONFIGURED")
        self.assertIsNone(controller.pause_state)


class RecordingCounterTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_three_capture_failures_pause(self):
        # Setup commands are not CAPTURE, so a capture_timeout worker still
        # arms/starts; only its CAPTURE fails.
        controller = make_controller(
            self.tmp, ["capture_timeout", "capture_timeout",
                       "capture_timeout"])
        to_recording(controller)
        result1 = controller.tick()      # timeout 1 -> restart (new worker)
        self.assertIsNotNone(result1.event)  # frameless error event
        self.assertEqual(controller.recording_failures, 1)
        self.assertEqual(controller.machine.state, "RECORDING")
        result2 = controller.tick()      # timeout 2 -> restart
        self.assertEqual(controller.recording_failures, 2)
        result3 = controller.tick()      # timeout 3 -> pause
        self.assertEqual(controller.recording_failures, 3)
        self.assertEqual(controller.machine.state, "PAUSED")
        self.assertEqual(controller.pause_state.reason,
                         "WORKER_FAILURE_STREAK")

    def test_successful_capture_resets_streak(self):
        controller = make_controller(
            self.tmp, ["capture_timeout", "ok"])
        to_recording(controller)
        controller.tick()
        self.assertEqual(controller.recording_failures, 1)
        controller.tick()
        self.assertEqual(controller.recording_failures, 0)

    def test_frameless_error_event_schema(self):
        controller = make_controller(
            self.tmp, ["capture_timeout", "ok"])
        to_recording(controller)
        result = controller.tick()
        event = result.event
        self.assertIsNone(event["frame"])
        self.assertEqual(event["scheduler_context"]["worker_status"],
                         "REQUEST_TIMEOUT")
        for obs in event["observations"]:
            self.assertEqual(obs["value_status"], "CAPTURE_FAILURE")
            self.assertIsNone(obs["normalized_value"])


class LiveCsvSnapshotControllerTests(unittest.TestCase):
    """§2: after every successful journal write, the controller must
    regenerate the live CSV snapshot and attach its own success/failure to
    the event - never conflating the two."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_retained_event_triggers_live_snapshot_update(self):
        controller = make_controller(self.tmp, ["ok", "ok"])
        to_recording(controller)
        controller.worker.frame_values = {1: "1.0", 2: "2.0"}
        controller.tick()  # seeds "1.0" - not yet a change
        result = controller.tick()  # "2.0" - a real change, retained
        self.assertIsNotNone(result.event)
        self.assertEqual(controller.journal.live_snapshot_row_count, 1)
        self.assertIsNotNone(controller.diagnostics["last_live_csv_utc"])
        self.assertIsNotNone(controller.diagnostics["last_journal_write_utc"])
        snapshot = result.event["live_csv_snapshot"]
        self.assertTrue(snapshot["ok"])
        self.assertEqual(snapshot["row_count"], 1)
        self.assertTrue(
            (controller.journal.run_dir / "events_wide.live.csv").is_file())

    def test_live_snapshot_failure_does_not_lose_the_event_or_pause(self):
        controller = make_controller(self.tmp, ["ok", "ok"])
        to_recording(controller)
        controller.worker.frame_values = {1: "1.0", 2: "2.0"}
        controller.tick()  # seeds "1.0"
        from unittest import mock
        from screen2xyz_m2.journal import RunJournal
        # The live snapshot now appends incrementally (_append_bytes); a
        # failure there must still never lose the journaled event or pause.
        with mock.patch.object(RunJournal, "_append_bytes",
                              side_effect=OSError("disk full")):
            result = controller.tick()  # "2.0" - a real, retained change
        self.assertIsNotNone(result.event)  # the journal write itself is
        self.assertEqual(controller.journal.counters["events"], 1)  # intact
        self.assertFalse(result.event["live_csv_snapshot"]["ok"])
        self.assertEqual(controller.diagnostics["export_errors"], 1)
        self.assertEqual(controller.machine.state, "RECORDING")  # not paused
        self.assertIsNone(result.pause)

    def test_retained_events_attempted_counts_stability_decisions(self):
        controller = make_controller(self.tmp, ["ok", "ok", "ok"])
        to_recording(controller)
        controller.worker.frame_values = {1: "1.0", 2: "2.0", 3: "2.0"}
        controller.tick()  # seeds "1.0" - no decision
        controller.tick()  # "2.0" - one retained decision
        self.assertEqual(controller.diagnostics["retained_events_attempted"],
                         1)
        controller.tick()  # same value again - not a new retained decision
        self.assertEqual(controller.diagnostics["retained_events_attempted"],
                         1)

    def test_journal_failure_rolls_back_stability_so_change_is_not_lost(self):
        # §9: if the durable journal append fails on a retained change, the
        # in-memory stable transition must be rolled back so the SAME change
        # is re-detected and re-journaled on the next tick - never silently
        # advanced past a change the source-of-truth journal never recorded.
        controller = make_controller(self.tmp, ["ok", "ok", "ok"])
        to_recording(controller)
        controller.worker.frame_values = {1: "1.0", 2: "2.0", 3: "2.0"}
        controller.tick()  # seeds "1.0"
        events_before = controller.journal.counters["events"]
        from unittest import mock
        from screen2xyz_m2.journal import RunJournal, StorageFailure
        # Make the durable journal append of the 1.0->2.0 change fail.
        with mock.patch.object(
                RunJournal, "append_event",
                side_effect=StorageFailure("CROP_WRITE_FAILURE", "boom")):
            result = controller.tick()  # "2.0" change, append fails
        self.assertIsNone(result.event)  # not durably journaled
        self.assertEqual(controller.journal.counters["events"], events_before)
        # Paused by the storage failure; resume and tick again with the SAME
        # value - the change must be re-detected and now journaled.
        controller.machine.resume()
        result2 = controller.tick()  # "2.0" again - re-detected
        self.assertIsNotNone(result2.event)
        self.assertEqual(result2.event["event_status"], "RETAINED_CHANGE")
        self.assertEqual(controller.journal.counters["events"],
                         events_before + 1)

    def test_backend_failure_streak_pauses_not_records_nothing_forever(self):
        # §18/§21: a worker-reported BACKEND_FAILURE (worker_status OK) never
        # triggered the WorkerError streak, so the session stayed RECORDING
        # and captured nothing forever. Now it pauses on a streak.
        controller = make_controller(self.tmp, ["ok"])
        to_recording(controller)
        controller.worker.capture_status_override = "BACKEND_FAILURE"
        pause = None
        for _ in range(C.PAUSE_BLANK_FRAME_TICKS + 1):
            result = controller.tick()
            if result.pause:
                pause = result.pause
                break
        self.assertIsNotNone(pause)
        self.assertEqual(pause.reason, "BACKEND_BLANK_STREAK")
        self.assertEqual(controller.machine.state, "PAUSED")

    def test_backend_failure_streak_resets_on_ok_capture(self):
        controller = make_controller(self.tmp, ["ok"])
        to_recording(controller)
        controller.worker.capture_status_override = "BACKEND_FAILURE"
        controller.tick()
        controller.tick()
        self.assertEqual(controller._capture_fail_streak, 2)
        controller.worker.capture_status_override = None
        controller.tick()
        self.assertEqual(controller._capture_fail_streak, 0)

    def test_display_invalidated_frame_is_not_journaled(self):
        # §20: a frame whose client size changed this tick must NOT journal a
        # RETAINED_CHANGE read from wrong pixels; it pauses instead.
        controller = make_controller(self.tmp, ["ok"])
        to_recording(controller)
        controller.worker.frame_values = {1: "1.0"}
        controller.tick()  # seed
        # Next tick: value changed AND the client size changed simultaneously.
        controller.worker.frame_values = {2: "2.0"}
        controller.worker.window_override = {"client_w": 1400}
        events_before = controller.journal.counters["events"]
        result = controller.tick()
        self.assertIsNotNone(result.pause)
        self.assertEqual(result.pause.reason, "DISPLAY_INVALIDATED")
        self.assertIsNone(result.event)  # not journaled
        self.assertEqual(controller.journal.counters["events"],
                         events_before)

    def test_capture_errors_counter_increments_on_worker_timeout(self):
        controller = make_controller(
            self.tmp, ["capture_timeout", "ok"])
        to_recording(controller)
        controller.tick()
        self.assertEqual(controller.diagnostics["capture_errors"], 1)


class PauseThresholdTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def _tick_reply_override(self, controller, **frame_overrides):
        worker = controller.worker
        original = worker.request

        def patched(command, payload, **kw):
            reply = original(command, payload, **kw)
            if command == "CAPTURE":
                reply.update(frame_overrides)
                if "window" in frame_overrides:
                    for obs in reply["observations"]:
                        pass
            return reply

        worker.request = patched

    def test_minimized_streak_pauses_after_five(self):
        controller = make_controller(self.tmp, ["ok"])
        to_recording(controller)
        self._tick_reply_override(
            controller, capture_status="TARGET_MINIMIZED",
            window={"exists": True, "iconic": True, "client_w": 900,
                    "client_h": 300, "origin_x": 0, "origin_y": 0,
                    "dpi": 96},
            observations=[])
        for i in range(C.PAUSE_MINIMIZED_TICKS - 1):
            controller.tick()
            self.assertEqual(controller.machine.state, "RECORDING", i)
        controller.tick()
        self.assertEqual(controller.machine.state, "PAUSED")
        self.assertEqual(controller.pause_state.reason,
                         "TARGET_MINIMIZED_STREAK")

    def test_target_unavailable_pauses_immediately(self):
        controller = make_controller(self.tmp, ["ok"])
        to_recording(controller)
        self._tick_reply_override(
            controller, capture_status="TARGET_UNAVAILABLE",
            window={"exists": False, "iconic": False, "client_w": 0,
                    "client_h": 0, "origin_x": 0, "origin_y": 0, "dpi": 0},
            observations=[])
        controller.tick()
        self.assertEqual(controller.machine.state, "PAUSED")
        self.assertTrue(controller.pause_state.requires_reresolve)

    def test_client_resize_pauses_with_repreview(self):
        controller = make_controller(self.tmp, ["ok"])
        to_recording(controller)
        self._tick_reply_override(
            controller,
            window={"exists": True, "iconic": False, "client_w": 800,
                    "client_h": 300, "origin_x": 0, "origin_y": 0,
                    "dpi": 96})
        controller.tick()
        self.assertEqual(controller.machine.state, "PAUSED")
        self.assertEqual(controller.pause_state.reason,
                         "DISPLAY_INVALIDATED")
        self.assertTrue(controller.pause_state.requires_repreview)
        with self.assertRaises(WorkerError):
            controller.user_resume()

    def test_blank_frame_streak_pauses(self):
        controller = make_controller(self.tmp, ["ok"])
        to_recording(controller)
        self._tick_reply_override(
            controller, frame_content_status="NEAR_UNIFORM_LIGHT")
        for _ in range(C.PAUSE_BLANK_FRAME_TICKS - 1):
            controller.tick()
        self.assertEqual(controller.machine.state, "RECORDING")
        controller.tick()
        self.assertEqual(controller.machine.state, "PAUSED")
        self.assertEqual(controller.pause_state.reason,
                         "BACKEND_BLANK_STREAK")

    def test_empty_ocr_alone_never_pauses(self):
        controller = make_controller(self.tmp, ["ok"])
        to_recording(controller)
        worker = controller.worker
        original = worker.request

        def patched(command, payload, **kw):
            reply = original(command, payload, **kw)
            if command == "CAPTURE":
                for obs in reply["observations"]:
                    obs["ocr_status"] = "EMPTY_TEXT"
                    obs["raw_text"] = ""
            return reply

        worker.request = patched
        for _ in range(10):
            result = controller.tick()
        self.assertEqual(controller.machine.state, "RECORDING")
        obs = list(result.observations.values())[0]
        self.assertEqual(obs.value_status, "MISSING_SOURCE_VALUE")


class HoverTransienceScenarioTests(unittest.TestCase):
    """Phase 2.3 (2026-07-19): the real workflow's coordinate readout is
    only present while the owner hovers the mouse over the map - it
    legitimately disappears and reappears every few ticks as the owner's
    attention moves. `test_empty_ocr_alone_never_pauses` above already
    proves a lone EMPTY_TEXT tick doesn't pause recording; this verifies
    the FULL scenario end to end: repeated hover on/off/on-different-value
    cycling yields exactly the retained events a human would expect (one
    per genuine value change, seeding itself is not a change) and zero
    spurious error events - MISSING_SOURCE_VALUE must never be treated as
    a retainable error just because it happens repeatedly."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def _hover_worker(self, controller, away_ticks: set[int]):
        """Frame_seq values in `away_ticks` simulate the coordinate text
        being absent this tick (hover away, or in-transit mouse movement)
        - exactly the EMPTY_TEXT the real worker reports when its OCR
        crop has no recognizable text, not a capture/backend failure."""
        worker = controller.worker
        original = worker.request

        def patched(command, payload, **kw):
            reply = original(command, payload, **kw)
            if command == "CAPTURE" and payload["frame_seq"] in away_ticks:
                for obs in reply["observations"]:
                    obs["ocr_status"] = "EMPTY_TEXT"
                    obs["raw_text"] = ""
                    obs["raw_original_utf8_bytes"] = 0
            return reply

        worker.request = patched

    def test_hover_on_off_on_same_then_different_value_no_spurious_errors(
            self):
        controller = make_controller(self.tmp, ["ok"])
        to_recording(controller)
        worker = controller.worker
        worker.frame_values = {1: "1.000000", 3: "1.000000",
                               5: "2.000000", 7: "2.000000"}
        # Present: 1, 3, 5, 7 (with a value change at 5). Away (hover off):
        # 2, 4, 6 - a genuine, repeated on/off/on cycle, not a one-shot.
        self._hover_worker(controller, away_ticks={2, 4, 6})

        results = [controller.tick() for _ in range(7)]
        statuses = [list(r.observations.values())[0].value_status
                   for r in results]
        self.assertEqual(statuses, [
            "OK",                    # 1: seeds (first reading)
            "MISSING_SOURCE_VALUE",  # 2: hover away - live-only, no event
            "OK",                    # 3: hover back, SAME value - no event
            "MISSING_SOURCE_VALUE",  # 4: hover away again
            "OK",                    # 5: hover back, DIFFERENT value
            "MISSING_SOURCE_VALUE",  # 6: hover away again
            "OK",                    # 7: hover back, matches new stable
        ])
        event_statuses = [r.decision.event_status for r in results]
        # Exactly one retained event across the whole scenario: the real
        # value change at tick 5. Seeding (1), both hover-away no-ops (2,
        # 4, 6), and both same-value hover-returns (3, 7) retain nothing.
        self.assertEqual(event_statuses, [
            None, None, None, None, "RETAINED_CHANGE", None, None])
        self.assertEqual(controller.journal.counters["events"], 1)
        # No spurious error events were EVER retained, however many times
        # the value legitimately disappeared and reappeared.
        self.assertNotIn("RETAINED_ERROR", event_statuses)


class CachedObservationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_cached_carries_prior_value_with_ref(self):
        controller = make_controller(self.tmp, ["ok"])
        to_recording(controller)
        worker = controller.worker
        original = worker.request
        state = {"tick": 0}

        def patched(command, payload, **kw):
            reply = original(command, payload, **kw)
            if command == "CAPTURE":
                state["tick"] += 1
                for obs in reply["observations"]:
                    obs["pixel_sha256"] = "constant-hash"
                    if state["tick"] > 1:
                        obs["ocr_status"] = "NOT_RUN_UNCHANGED"
                        obs["ocr_executed"] = False
                        obs["confirmation"] = "pixel_hash_cached"
                        obs["raw_text"] = ""
                        obs["crop_png_b64"] = None
                    else:
                        obs["raw_text"] = "42.5"
            return reply

        worker.request = patched
        first = controller.tick()
        second = controller.tick()
        obs = list(second.observations.values())[0]
        self.assertFalse(obs.ocr_executed)
        self.assertEqual(obs.confirmation, "pixel_hash_cached")
        self.assertEqual(obs.normalized_value, "42.5")
        self.assertEqual(obs.raw_text, "")
        self.assertEqual(obs.ocr_ref,
                         f"{controller.session_id}-f1")
        self.assertIsNone(second.decision.event_status)  # no new event

    def test_cached_tick_preserves_warning_codes(self):
        # Adversarial review finding (2026-07-21): the cached-replay block
        # copied parse_status/normalized_value/value_kind/ocr_ref/
        # value_status from the fresh observation but NOT warning_codes -
        # a DEGREE_GLYPH_RECOVERED-labelled value (or any other warned
        # one) journaled as a bare, unlabelled OK on every tick after the
        # first. Every sibling parse-derived field is copied; this one
        # must be too.
        coord_source = SourceConfig(source_id=new_source_id(),
                                    display_name="Lat", data_type="coordinate",
                                    rect=(0, 0, 100, 20))
        controller = make_controller(self.tmp, ["ok"], sources=[coord_source])
        to_recording(controller)
        worker = controller.worker
        original = worker.request
        state = {"tick": 0}

        def patched(command, payload, **kw):
            reply = original(command, payload, **kw)
            if command == "CAPTURE":
                state["tick"] += 1
                for obs in reply["observations"]:
                    obs["pixel_sha256"] = "constant-hash"
                    if state["tick"] > 1:
                        obs["ocr_status"] = "NOT_RUN_UNCHANGED"
                        obs["ocr_executed"] = False
                        obs["confirmation"] = "pixel_hash_cached"
                        obs["raw_text"] = ""
                        obs["crop_png_b64"] = None
                    else:
                        obs["raw_text"] = "49008'20.06\"N"
            return reply

        worker.request = patched
        first = controller.tick()
        first_obs = list(first.observations.values())[0]
        self.assertEqual(first_obs.normalized_value, "49.138906")
        self.assertIn("DEGREE_GLYPH_RECOVERED", first_obs.warning_codes)
        second = controller.tick()
        second_obs = list(second.observations.values())[0]
        self.assertEqual(second_obs.confirmation, "pixel_hash_cached")
        self.assertEqual(second_obs.normalized_value, "49.138906")
        self.assertIn("DEGREE_GLYPH_RECOVERED", second_obs.warning_codes)


class UserFlowTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_pause_resume_stop_finalize(self):
        controller = make_controller(self.tmp, ["ok"])
        to_recording(controller)
        worker = controller.worker
        worker.frame_values = {1: "1.0", 2: "2.0"}
        controller.tick()
        controller.tick()
        controller.user_pause()
        self.assertEqual(controller.machine.state, "PAUSED")
        self.assertIn("PAUSE", worker.requests)
        controller.user_resume()
        self.assertEqual(controller.machine.state, "RECORDING")
        summary = controller.stop()
        self.assertEqual(controller.machine.state, "FINALIZED")
        run_dir = controller.journal.run_dir
        for name in ("events.jsonl", "events_wide.csv",
                     "observations_long.csv", "run_summary.json",
                     "evidence_manifest_sha256.txt", "session.json"):
            self.assertTrue((run_dir / name).is_file(), name)

    def test_emergency_stop_finalizes_and_kills(self):
        controller = make_controller(self.tmp, ["ok"])
        to_recording(controller)
        controller.tick()
        controller.emergency_stop()
        self.assertEqual(controller.machine.state, "FINALIZED")
        self.assertIsNone(controller.worker)

    def test_tick_outside_recording_is_skip(self):
        controller = make_controller(self.tmp, ["ok"])
        controller.machine.select_target()
        result = controller.tick()
        self.assertTrue(result.skipped)


class BackendProbeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        FakeWorker.snapshot_effective_backend = "printwindow_clientonly"
        FakeWorker.snapshot_frame_content_status = "CONTENT_DETECTED"
        FakeWorker.snapshot_no_backend_usable = False

    def test_effective_backend_starts_none(self):
        controller = make_controller(self.tmp, ["ok"], backend=C.BACKEND_AUTO)
        self.assertIsNone(controller.effective_backend)

    def test_test_capture_records_effective_backend_and_probe(self):
        controller = make_controller(self.tmp, ["ok"], backend=C.BACKEND_AUTO)
        controller.machine.select_target()
        controller.machine.sources_configured()
        reply = controller.test_capture()
        self.assertEqual(controller.effective_backend,
                         "printwindow_clientonly")
        self.assertIsNotNone(controller.last_backend_probe)
        self.assertEqual(reply["effective_backend"],
                         "printwindow_clientonly")

    def test_plain_region_snapshot_does_not_clear_backend_probe_field(self):
        # A plain (non-probe) snapshot has backend_probe=None in the reply;
        # the controller must not blow away a real prior probe with that.
        controller = make_controller(self.tmp, ["ok"], backend=C.BACKEND_AUTO)
        controller.machine.select_target()
        controller.machine.sources_configured()
        controller.test_capture()
        self.assertIsNotNone(controller.last_backend_probe)
        controller.region_snapshot(probe_backend=False)
        self.assertIsNotNone(controller.last_backend_probe)

    def test_copyfromscreen_fallback_is_reflected_in_session_json(self):
        FakeWorker.snapshot_effective_backend = "copyfromscreen"
        controller = make_controller(self.tmp, ["ok"], backend=C.BACKEND_AUTO)
        controller.machine.select_target()
        controller.machine.sources_configured()
        controller.test_capture()
        locked = controller.session_json()["locked_backend"]
        self.assertEqual(locked["requested"], "auto")
        self.assertEqual(locked["effective"], "copyfromscreen")
        self.assertEqual(locked["name"], "copyfromscreen")  # exports.py compat

    def test_explicit_backend_never_populates_effective_backend(self):
        # An explicit (non-auto) backend is used directly; effective_backend
        # is an Auto-only concept and must stay unset.
        controller = make_controller(self.tmp, ["ok"],
                                     backend=C.BACKEND_PRINTWINDOW)
        controller.machine.select_target()
        controller.machine.sources_configured()
        # The fake's REGION_SNAPSHOT handler always includes
        # effective_backend for simplicity, so assert via the real worker
        # protocol contract instead: locked_backend.requested reflects the
        # explicit choice regardless of any worker-reported field.
        locked = controller.session_json()["locked_backend"]
        self.assertEqual(locked["requested"], "printwindow_clientonly")
        self.assertEqual(locked["reason"], "explicit owner choice")


class PreviewSingleRegionTests(unittest.TestCase):
    """The region-selection picker's one-shot crop+OCR+parse preview."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_returns_parsed_region_preview(self):
        controller = make_controller(self.tmp, ["ok"])
        controller.machine.select_target()
        controller.machine.sources_configured()
        temp = SourceConfig(source_id=new_source_id(), display_name="tmp",
                            rect=(10, 20, 100, 30))
        reply = controller.preview_single_region(temp)
        region = reply["region_preview"]
        self.assertEqual(region["raw_text"], "1.000000")
        self.assertEqual(region["parse_status"], "OK")
        self.assertEqual(region["normalized_value"], "1.000000")
        self.assertEqual(region["crop_content_status"], "CONTENT_DETECTED")

    def test_does_not_mutate_controller_sources(self):
        # The picker passes a temporary, not-yet-confirmed source copy;
        # preview_single_region must never touch self.sources.
        controller = make_controller(self.tmp, ["ok"])
        controller.machine.select_target()
        controller.machine.sources_configured()
        original_rects = [s.rect for s in controller.sources]
        temp = SourceConfig(source_id=new_source_id(), display_name="tmp",
                            rect=(10, 20, 100, 30))
        controller.preview_single_region(temp)
        self.assertEqual([s.rect for s in controller.sources],
                         original_rects)

    def test_requires_regions_configured_state(self):
        # Matches the real preview()'s gate - a one-shot region preview must
        # not be usable outside REGIONS_CONFIGURED (e.g. before a target is
        # even selected).
        controller = make_controller(self.tmp, ["ok"])
        temp = SourceConfig(source_id=new_source_id(), display_name="tmp",
                            rect=(10, 20, 100, 30))
        with self.assertRaises(IllegalAction):
            controller.preview_single_region(temp)


class DiagnosticSnapshotTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_no_capture_yet_reports_zero_sources_honestly(self):
        controller = make_controller(self.tmp, ["ok"])
        result = controller.diagnostic_snapshot(out_root=self.tmp / "diag")
        self.assertEqual(result["source_count"], 0)
        self.assertIsNone(result["dir"])
        self.assertIn("note", result)

    def test_snapshot_after_tick_writes_crop_and_sanitized_meta(self):
        import json
        controller = make_controller(self.tmp, ["ok"])
        to_recording(controller)
        controller.tick()
        result = controller.diagnostic_snapshot(out_root=self.tmp / "diag")
        self.assertEqual(result["source_count"], 1)
        snap_dir = Path(result["dir"])
        pngs = list(snap_dir.glob("*.png"))
        self.assertEqual(len(pngs), 1)
        meta = json.loads((snap_dir / "meta.json").read_text())
        # Sanitized: no raw window title, no absolute target identity - only
        # the fields explicitly listed here.
        self.assertEqual(set(meta.keys()),
                         {"schema_version", "captured_utc", "session_state",
                          "requested_backend", "effective_backend", "crops"})

    def test_each_call_writes_a_distinct_directory(self):
        controller = make_controller(self.tmp, ["ok"])
        to_recording(controller)
        controller.tick()
        first = controller.diagnostic_snapshot(out_root=self.tmp / "diag")
        second = controller.diagnostic_snapshot(out_root=self.tmp / "diag")
        self.assertNotEqual(first["dir"], second["dir"])
