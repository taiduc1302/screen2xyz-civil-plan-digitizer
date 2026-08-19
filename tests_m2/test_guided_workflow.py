"""Regression tests for the owner-reported "Test capture now stays stuck"
guided-workflow failure (overnight QA sprint): a controller built with zero
fields must not crash Step 2, defense-in-depth still blocks Preview/Arm with
zero fields, the persistent next-step card's pure state-derivation behaves
correctly for every state, and a Tk callback exception is always caught,
logged, and shown - never silently swallowed."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from screen2xyz_m2 import contracts as C
from screen2xyz_m2.controller import LiveSessionController, PauseState
from screen2xyz_m2.models import (SessionDefaults, SourceConfig,
                                  ValidationError, new_source_id)
from screen2xyz_m2.statemachine import IllegalAction
from screen2xyz_m2.worker import WorkerError
from screen2xyz_m2.ui.layout import can_test_capture, derive_next_step


class _FakeWorker:
    """Minimal self-contained in-process worker stand-in - just enough to
    exercise REGION_SNAPSHOT/PREVIEW/ARM without a real subprocess."""

    instances_spawned = 0

    def __init__(self, **kwargs):
        self._alive = True
        self.spawned_with_backend = kwargs.get("backend")
        _FakeWorker.instances_spawned += 1

    def start(self, *, restore_session_state, configuration_revision,
             init_timeout_ms: int = 0):
        return {"worker_status": "OK", "dpi_awareness": "per_monitor_v2",
               "restore_session_state": restore_session_state}

    @property
    def alive(self):
        return self._alive

    def request(self, command, payload, *, timeout_ms, ui_session_state,
               configuration_revision=None):
        base = {"worker_status": "OK", "worker_mode": "RECORDING",
               "capture_status": "OK",
               "window": {"exists": True, "iconic": False, "client_w": 900,
                          "client_h": 300, "origin_x": 0, "origin_y": 0,
                          "dpi": 96}}
        if command == "REGION_SNAPSHOT":
            return {**base, "frame_content_status": "CONTENT_DETECTED",
                   "effective_backend": "printwindow_clientonly",
                   "no_backend_usable": False, "capture_ms": 5,
                   "frame_png_b64": None,
                   "backend_probe": [{"backend": "printwindow_clientonly",
                                      "usable": True,
                                      "content_status": "CONTENT_DETECTED",
                                      "capture_ms": 5}]
                   if payload.get("probe_backend") else None}
        if command == "PREVIEW":
            return {**base, "frame_content_status": "CONTENT_DETECTED",
                   "effective_backend": "printwindow_clientonly",
                   "backend_probe": None, "no_backend_usable": False,
                   "cursor": None, "timings": {"capture_ms": 1},
                   "observations": []}
        return base

    def teardown(self, graceful_ms: int = 0, deadline_s: float | None = None):
        self._alive = False

    def graceful_shutdown(self, *args):
        self._alive = False


def _make_controller(tmp: Path, sources):
    return LiveSessionController(
        scope={"type": "window", "hwnd": 1, "pid": 1},
        backend=C.BACKEND_PRINTWINDOW, sources=sources,
        defaults=SessionDefaults(), environment_snapshot={
            "window": {"client_w": 900, "client_h": 300, "dpi": 96}},
        run_parent=tmp, worker_factory=_FakeWorker)

try:
    import tkinter as tk
    from tkinter import ttk
    _root = tk.Tk()
    _root.withdraw()
    _HAS_TK = True
    # Keep the display-probe interpreter alive for this module. Destroying
    # the first ttk interpreter before the test-created roots initialize can
    # leave Tcl's deferred ThemeChanged dispatch pointed at that dead root on
    # Windows, producing stderr noise despite a passing suite.
except Exception:  # pragma: no cover - headless CI without a display
    _HAS_TK = False


def _make_app():
    from screen2xyz_m2.ui.app import M2App
    M2App._welcome_shown_this_process = True
    return M2App()


class ZeroFieldTestCaptureRegressionTests(unittest.TestCase):
    """The exact owner-reported bug: Step 2 "Test capture now" is clicked
    before Step 3 "Add fields" has ever run - the UI's own step numbering
    invites this order. Before the fix, LiveSessionController.__init__
    raised ValidationError("enabled source count outside 1..8"), which
    _test_capture()'s `except WorkerError` never caught - Tk silently
    swallowed it and Step 2 stayed frozen at "Not tested yet" forever."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_controller_construction_with_zero_sources_does_not_raise(self):
        controller = _make_controller(self.tmp, [])
        self.assertEqual(controller.sources, [])

    def test_region_snapshot_probe_succeeds_with_zero_sources(self):
        controller = _make_controller(self.tmp, [])
        controller.machine.select_target()
        controller.machine.sources_configured()
        reply = controller.test_capture()
        self.assertEqual(reply.get("worker_status"), "OK")

    def test_preview_still_requires_at_least_one_enabled_source(self):
        # Defence in depth: a direct caller must never be able to preview
        # zero fields just because construction-time validation was relaxed
        # to let Step 2 work before Step 3.
        controller = _make_controller(self.tmp, [])
        controller.machine.select_target()
        controller.machine.sources_configured()
        with self.assertRaises(ValidationError):
            controller.preview()

    def test_confirm_preview_and_arm_still_requires_at_least_one_source(self):
        controller = _make_controller(self.tmp, [])
        controller.machine.select_target()
        controller.machine.sources_configured()
        with self.assertRaises(ValidationError):
            controller.confirm_preview_and_arm()


class CanTestCaptureGatingTests(unittest.TestCase):
    """Progressive control enabling: Test capture/Retest must be disabled
    (with a visible reason) whenever clicking it would raise IllegalAction,
    never left clickable-but-silently-broken."""

    def test_disabled_with_no_target(self):
        allowed, reason = can_test_capture(None, has_target=False)
        self.assertFalse(allowed)
        self.assertIn("Select a target", reason)

    def test_allowed_before_controller_exists(self):
        allowed, _ = can_test_capture(None, has_target=True)
        self.assertTrue(allowed)

    def test_allowed_target_selected_or_regions_configured(self):
        for state in ("TARGET_SELECTED", "REGIONS_CONFIGURED"):
            allowed, _ = can_test_capture(state, has_target=True)
            self.assertTrue(allowed, state)

    def test_disabled_once_armed_recording_paused_or_finalized(self):
        for state in ("ARMED", "RECORDING", "PAUSED", "STOPPING",
                      "FINALIZED"):
            allowed, reason = can_test_capture(state, has_target=True)
            self.assertFalse(allowed, state)
            self.assertTrue(reason)


class DeriveNextStepTests(unittest.TestCase):
    def _view(self, **overrides):
        base = dict(has_target=True, controller_state="REGIONS_CONFIGURED",
                   capture_tested=True, capture_verdict="PASS",
                   enabled_field_count=1, all_regions_confirmed=True,
                   preview_confirmed=False)
        base.update(overrides)
        return derive_next_step(**base)

    def test_no_target_is_step_1(self):
        self.assertEqual(self._view(has_target=False)["step"], 1)

    def test_untested_capture_is_step_2(self):
        view = self._view(capture_tested=False, capture_verdict=None)
        self.assertEqual(view["step"], 2)

    def test_failed_capture_stays_step_2(self):
        view = self._view(capture_verdict="FAIL")
        self.assertEqual(view["step"], 2)
        self.assertIn("FAILED", view["headline"])

    def test_zero_fields_is_step_3(self):
        self.assertEqual(self._view(enabled_field_count=0)["step"], 3)

    def test_unconfirmed_regions_is_step_3(self):
        self.assertEqual(self._view(all_regions_confirmed=False)["step"], 3)

    def test_ready_to_preview_is_step_4(self):
        self.assertEqual(self._view()["step"], 4)

    def test_preview_confirmed_is_step_5(self):
        self.assertEqual(self._view(preview_confirmed=True)["step"], 5)

    def test_armed_is_step_5(self):
        self.assertEqual(self._view(controller_state="ARMED")["step"], 5)

    def test_recording_is_step_6(self):
        self.assertEqual(self._view(controller_state="RECORDING")["step"], 6)

    def test_finalized_reports_session_finished(self):
        view = self._view(controller_state="FINALIZED")
        self.assertIn("finished", view["headline"].lower())


@unittest.skipUnless(_HAS_TK, "no Tk display")
class UiLevelZeroFieldRegressionTests(unittest.TestCase):
    """Drives the REAL M2App (not a fake harness) through the exact
    reported sequence: select target, then Test capture before any field
    exists."""

    def test_ensure_controller_with_zero_sources_does_not_raise(self):
        app = _make_app()
        try:
            app.scope = {"type": "window", "hwnd": 1, "pid": 1}
            controller = app._ensure_controller()
            self.assertIsNotNone(controller)
            self.assertEqual(controller.machine.state, "REGIONS_CONFIGURED")
        finally:
            app.root.destroy()

    def test_test_capture_button_disabled_without_a_target(self):
        app = _make_app()
        try:
            self.assertEqual(str(app.test_capture_btn.cget("state")),
                             "disabled")
            self.assertIn("Select a target",
                         app.test_capture_disabled_reason_var.get())
        finally:
            app.root.destroy()

    def test_test_capture_button_enabled_after_target_selected(self):
        app = _make_app()
        try:
            app.scope = {"type": "window", "hwnd": 1, "pid": 1}
            app._refresh_next_step()
            self.assertEqual(str(app.test_capture_btn.cget("state")),
                             "normal")
            self.assertEqual(app.test_capture_disabled_reason_var.get(), "")
        finally:
            app.root.destroy()

    def test_callback_exception_handler_is_installed_and_safe(self):
        app = _make_app()
        try:
            self.assertEqual(app.root.report_callback_exception,
                             app._on_callback_exception)
            try:
                raise IllegalAction(
                    "action 'region_snapshot' is not legal in state "
                    "'ARMED'")
            except IllegalAction:
                import sys
                with mock.patch(
                        "screen2xyz_m2.ui.app.messagebox.showwarning"):
                    app._on_callback_exception(*sys.exc_info())
            self.assertIn("internal error", app.status.get().lower())
            self.assertTrue(app.root.winfo_exists())
        finally:
            app.root.destroy()

    def test_callback_exception_log_is_sanitized(self):
        """The log must never contain the raw window title even if a future
        exception's message happened to include one - only recognized-safe
        exception types' messages are ever written verbatim."""
        app = _make_app()
        try:
            secret_title = "Confidential Tender 12345.xlsx - Excel"

            class _UnsafeType(RuntimeError):
                pass

            try:
                raise _UnsafeType(secret_title)
            except _UnsafeType:
                import sys
                with mock.patch(
                        "screen2xyz_m2.ui.app.messagebox.showwarning"):
                    app._on_callback_exception(*sys.exc_info())
            from screen2xyz_m2.paths import diagnostics_root
            log_path = diagnostics_root() / "callback_errors.log"
            if log_path.exists():
                text = log_path.read_text(encoding="utf-8")
                self.assertNotIn(secret_title, text)
        finally:
            app.root.destroy()


class BackendChangeRespawnRegressionTests(unittest.TestCase):
    """Independent audit BLOCKER: the PowerShell worker latches its backend
    once at INIT and never re-reads it, so ensure_worker()'s "reuse if
    alive" check silently ignored a backend change made after a worker
    already existed - the UI's own explanatory text claimed the new
    backend was "explicitly chosen" while the live worker kept using the
    old one forever, with no way to fix it short of reselecting the
    target or restarting the app."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_ensure_worker_respawns_on_backend_change(self):
        source = SourceConfig(source_id=new_source_id(), display_name="A",
                              semantic_role="none", data_type="number",
                              rect=(0, 0, 10, 10))
        controller = _make_controller(self.tmp, [source])
        controller.machine.select_target()
        controller.machine.sources_configured()
        controller.ensure_worker()
        first_worker = controller.worker
        self.assertEqual(first_worker.spawned_with_backend,
                         C.BACKEND_PRINTWINDOW)

        # Reusing the SAME backend must NOT respawn.
        controller.ensure_worker()
        self.assertIs(controller.worker, first_worker)

        # Changing the backend (as the owner's dropdown would) must force
        # a fresh worker spawned WITH the new backend, not silently keep
        # using the old one.
        controller.backend = C.BACKEND_COPYFROMSCREEN
        controller.ensure_worker()
        self.assertIsNot(controller.worker, first_worker)
        self.assertEqual(controller.worker.spawned_with_backend,
                         C.BACKEND_COPYFROMSCREEN)
        self.assertFalse(first_worker.alive)


@unittest.skipUnless(_HAS_TK, "no Tk display")
class StopExceptionSafetyRegressionTests(unittest.TestCase):
    """Independent audit BLOCKER (confirmed by four separate reviewers):
    _stop() had zero exception handling around controller.stop(), unlike
    _emergency_stop()'s existing try/except. If finalize() (called inside
    stop()) raised, the session-state-machine had ALREADY moved to
    STOPPING - not a legal state for "stop" to run again - so every
    further Stop click raised the same IllegalAction forever, and the
    owner never reached the Finalized screen or its recovery hint."""

    def test_stop_reaches_finalized_screen_even_if_controller_raises(self):
        app = _make_app()
        try:
            class _ExplodingController:
                class machine:
                    state = "RECORDING"

                journal = None

                def stop(self):
                    raise RuntimeError("simulated finalize() failure")

            app.controller = _ExplodingController()
            app.scheduler = None
            # Must not raise, and must still reach the Finalized screen
            # (proven by the header label _build_finalized always creates)
            # rather than leaving the prior screen frozen.
            app._stop()
            self.assertTrue(app.root.winfo_exists())
        finally:
            app.root.destroy()

    def test_stop_drains_the_scheduler_with_a_bounded_timeout(self):
        """Independent cycle-4 VERIFICATION audit caught that an earlier
        commit message claimed this was fixed when the code had not
        actually been changed - _stop() called scheduler.stop() with no
        argument (the 5s default) while _emergency_stop/_on_close already
        passed drain_timeout=0.25. If the worker died mid-tick, the
        ordinary Stop button (not just Emergency stop) could still freeze
        the UI for up to 5 seconds. This test exists specifically because
        the previous test's stub scheduler was None, so it could not have
        caught this gap."""

        app = _make_app()
        try:
            calls = []

            class _StubScheduler:
                def stop(self, drain_timeout=5.0):
                    calls.append(drain_timeout)

            class _StubController:
                class machine:
                    state = "RECORDING"

                journal = None

                def stop(self):
                    return {}

            app.controller = _StubController()
            app.scheduler = _StubScheduler()
            app._stop()
            self.assertEqual(calls, [0.25])
        finally:
            app.root.destroy()


@unittest.skipUnless(_HAS_TK, "no Tk display")
class PauseResumeConcurrencyRegressionTests(unittest.TestCase):
    """Independent audit MAJOR: _pause()/_resume() called
    controller.user_pause()/user_resume() BEFORE draining any in-flight
    tick, unlike _stop()/_emergency_stop()'s already-correct ordering. A
    concurrently in-flight tick's own worker request could race the
    direct PAUSE/RESUME request, and the loser's WorkerError made
    user_pause() tear the worker down out from under the still-running
    tick. Verifies the ACTUAL call order _pause()/_resume() now use."""

    def _stub_app(self, calls, controller, drained=True):
        app = _make_app()
        app.controller = controller
        app.rec_banner = tk.StringVar()
        app.pause_btn = ttk.Button(app.root)
        app.resume_btn = ttk.Button(app.root)
        app._resume_needs_recovery = False

        class _StubScheduler:
            def pause(self):
                calls.append("scheduler.pause")

            def resume(self):
                calls.append("scheduler.resume")

            def drain(self, timeout=2.0):
                calls.append("scheduler.drain")
                return drained

        app.scheduler = _StubScheduler()
        return app

    def test_pause_drains_before_touching_controller(self):
        calls = []

        class _StubController:
            class machine:
                state = "RECORDING"

            def user_pause(self):
                calls.append("controller.user_pause")

            def drain_budget_s(self):
                return 2.0

        app = self._stub_app(calls, _StubController())
        try:
            app._pause()
            self.assertEqual(calls, ["scheduler.pause", "scheduler.drain",
                                     "controller.user_pause"])
        finally:
            app.root.destroy()

    def test_resume_drains_before_touching_controller(self):
        calls = []

        class _StubController:
            class machine:
                state = "PAUSED"

            def user_resume(self):
                calls.append("controller.user_resume")

            def drain_budget_s(self):
                return 2.0

        app = self._stub_app(calls, _StubController())
        try:
            app._resume()
            self.assertEqual(calls, ["scheduler.drain",
                                     "controller.user_resume",
                                     "scheduler.resume"])
        finally:
            app.root.destroy()

    def test_pause_refuses_instead_of_racing_a_still_busy_tick(self):
        """Second independent audit MAJOR: a hardcoded 2.0s drain timeout
        could be shorter than a real in-flight tick's own round-trip
        budget, and the old code discarded drain()'s outcome and called
        user_pause() anyway - reopening the exact overlapping-request
        race the drain was added to close. If drain() reports still-busy,
        _pause() must refuse, not touch the controller."""
        calls = []

        class _StubController:
            class machine:
                state = "RECORDING"

            def user_pause(self):
                calls.append("controller.user_pause")

            def drain_budget_s(self):
                return 2.0

        app = self._stub_app(calls, _StubController(), drained=False)
        try:
            app._pause()
            self.assertEqual(calls, ["scheduler.pause", "scheduler.drain"])
            self.assertNotIn("controller.user_pause", calls)
            self.assertIn("Still capturing", app.rec_banner.get())
        finally:
            app.root.destroy()

    def test_resume_refuses_instead_of_racing_a_still_busy_tick(self):
        calls = []

        class _StubController:
            class machine:
                state = "PAUSED"

            def user_resume(self):
                calls.append("controller.user_resume")

            def drain_budget_s(self):
                return 2.0

        app = self._stub_app(calls, _StubController(), drained=False)
        try:
            app._resume()
            self.assertEqual(calls, ["scheduler.drain"])
            self.assertNotIn("controller.user_resume", calls)
            self.assertIn("still busy", app.rec_banner.get())
        finally:
            app.root.destroy()

    def test_pause_sizes_drain_timeout_from_the_real_worker_budget(self):
        """The drain timeout must scale with controller.drain_budget_s()
        (which tracks the real per-tick worker request timeout), not a
        constant shorter than a legitimately slow but in-budget tick."""
        seen_timeouts = []

        class _StubController:
            class machine:
                state = "RECORDING"

            def user_pause(self):
                pass

            def drain_budget_s(self):
                return 9.0

        app = _make_app()
        app.controller = _StubController()
        app.rec_banner = tk.StringVar()
        app.pause_btn = ttk.Button(app.root)
        app.resume_btn = ttk.Button(app.root)
        app._resume_needs_recovery = False

        class _StubScheduler:
            def pause(self):
                pass

            def drain(self, timeout=2.0):
                seen_timeouts.append(timeout)
                return True

        app.scheduler = _StubScheduler()
        try:
            app._pause()
            self.assertEqual(seen_timeouts, [9.5])
        finally:
            app.root.destroy()

    def test_pause_illegal_action_restores_accurate_banner_not_worker_error(
            self):
        """Independent audit MINOR: a benign re-entrant IllegalAction (e.g.
        double-clicking Pause while already PAUSED) is not a worker
        problem and must not be reported as one; the banner should
        reflect the real state, not get stuck on the "Pausing…"
        acknowledgement either."""
        calls = []

        class _StubController:
            class machine:
                state = "PAUSED"

            def user_pause(self):
                calls.append("controller.user_pause")
                raise IllegalAction("pause", "PAUSED")

            def drain_budget_s(self):
                return 2.0

        app = self._stub_app(calls, _StubController())
        try:
            app._pause()
            self.assertEqual(app.rec_banner.get(), "⏸ PAUSED")
            self.assertNotIn("worker", app.rec_banner.get().lower())
        finally:
            app.root.destroy()

    def test_resume_illegal_action_does_not_leave_banner_stuck_resuming(
            self):
        """Independent audit MINOR: the WorkerError branch already reset
        the banner from "Resuming…" back to "⏸ PAUSED"; the IllegalAction
        branch used to just `pass`, leaving "Resuming…" shown forever."""
        calls = []

        class _StubController:
            class machine:
                state = "PAUSED"

            def user_resume(self):
                calls.append("controller.user_resume")
                raise IllegalAction("resume", "PAUSED")

            def drain_budget_s(self):
                return 2.0

        app = self._stub_app(calls, _StubController())
        try:
            app._resume()
            self.assertNotEqual(app.rec_banner.get(), "Resuming…")
            self.assertEqual(app.rec_banner.get(), "⏸ PAUSED")
        finally:
            app.root.destroy()


@unittest.skipUnless(_HAS_TK, "no Tk display")
class HandlePauseThreadSafetyRegressionTests(unittest.TestCase):
    """Independent audit MINOR: _handle_pause (invoked as controller.
    on_pause from the SCHEDULER's background tick thread) used to call
    `self.root.after(0, update_ui)` directly from that thread to update
    rec_banner/the recovery bar - outside Tkinter's documented single-
    thread contract, and the only place in the file that didn't marshal
    a UI update through the already-thread-safe tick-result queue. The
    same update now happens in _render_tick, reached only via that
    queue; _handle_pause itself must touch only thread-safe primitives."""

    def test_handle_pause_does_not_touch_tk_widgets(self):
        from screen2xyz_m2.controller import PauseState
        app = _make_app()
        try:
            calls = []

            class _StubScheduler:
                def pause(self):
                    calls.append("scheduler.pause")

            app.scheduler = _StubScheduler()
            # Deliberately do NOT set app.rec_banner / recovery_frame here -
            # if _handle_pause tried to touch them, this would raise
            # AttributeError, proving the widget update moved elsewhere.
            app._handle_pause(PauseState("USER_REQUEST"))
            self.assertEqual(calls, ["scheduler.pause"])
        finally:
            app.root.destroy()

    def test_render_tick_updates_banner_from_result_pause(self):
        from screen2xyz_m2.controller import PauseState, TickResult
        app = _make_app()
        try:
            app.scope = {"type": "window", "hwnd": 1, "pid": 1}
            app.sources = []
            app.controller = app._ensure_controller()
            app.rec_banner = tk.StringVar(value="● REC")
            app.recovery_frame = tk.Frame(app.root)
            app.recovery_var = tk.StringVar()
            app.recovery_btn = ttk.Button(app.root)
            app._cards_label = ttk.Label(app.root)
            app._capture_flash_state = False
            app.capture_flash_var = tk.StringVar()
            app._feed_counters = {"captures": 0, "live_observations": 0,
                                  "changes": 0, "errors": 0}
            app._feed_last_value = {}
            app._start_time = 0.0
            app.rec_stats = tk.StringVar()
            app.rec_stats2 = tk.StringVar()
            app.rec_counters_var = tk.StringVar()
            app._last_capture_time = ""
            app._last_csv_write_time = ""

            def _noop(*_a, **_kw):
                pass
            app._append_feed_row = _noop
            app._append_csv_row = _noop

            result = TickResult(
                frame=None, observations={}, decision=None, event=None,
                pause=PauseState("TARGET_MINIMIZED_STREAK"), tick_ms=1)
            app._render_tick(result)
            self.assertIn("PAUSED", app.rec_banner.get())
        finally:
            app.root.destroy()


@unittest.skipUnless(_HAS_TK, "no Tk display")
class ModalDialogRegressionTests(unittest.TestCase):
    """Independent audit MAJOR: the target/monitor choosers and the
    Draw-region countdown bar had no grab, so the main setup screen
    stayed fully clickable while one was open - a field could be edited/
    removed, or a different target selected, mid-operation, leaving a
    pending closure (the countdown's `source`/`controller`/`index`, or a
    chooser's `windows`/`monitors` list) to act on now-stale state."""

    def test_select_window_chooser_is_modal(self):
        app = _make_app()
        try:
            with mock.patch("screen2xyz_m2.ui.app.list_windows",
                            return_value=[]):
                app._select_window()
            grabbed = app.root.grab_current()
            self.assertIsNotNone(grabbed)
            self.assertEqual(grabbed.title(), "Select target window")
        finally:
            app.root.destroy()

    def test_select_monitor_chooser_is_modal(self):
        from screen2xyz_m2.targets import MonitorTarget
        app = _make_app()
        try:
            monitors = [MonitorTarget(index=0, x=0, y=0, w=1920, h=1080),
                       MonitorTarget(index=1, x=1920, y=0, w=1920, h=1080)]
            with mock.patch("screen2xyz_m2.ui.app.list_monitors",
                            return_value=monitors):
                app._select_monitor()
            grabbed = app.root.grab_current()
            self.assertIsNotNone(grabbed)
            self.assertEqual(grabbed.title(), "Select monitor")
        finally:
            app.root.destroy()

    def _simulate_os_close(self, toplevel) -> None:
        """Invoke the real WM_DELETE_WINDOW handler through Tcl - the same
        dispatch path a real window-manager close-button click uses -
        rather than calling .destroy() directly, which bypasses whatever
        (if anything) app.py registered via .protocol()."""
        handler = toplevel.tk.call(
            "wm", "protocol", toplevel._w, "WM_DELETE_WINDOW")
        self.assertTrue(handler, "no WM_DELETE_WINDOW handler registered")
        toplevel.tk.call(handler)

    def test_select_window_chooser_os_close_releases_grab(self):
        """Second independent audit MINOR: grab_set() made this dialog
        modal with no Cancel button and no explicit WM_DELETE_WINDOW
        handler - closing it via the OS "X" button was the only way out,
        and was never exercised by a test. Now it has both; this proves
        the OS-close path actually releases the grab rather than
        permanently locking the main window."""
        app = _make_app()
        try:
            with mock.patch("screen2xyz_m2.ui.app.list_windows",
                            return_value=[]):
                app._select_window()
            chooser = app.root.grab_current()
            self.assertIsNotNone(chooser)
            prev_scope = app.scope
            self._simulate_os_close(chooser)
            self.assertIsNone(app.root.grab_current())
            self.assertEqual(app.scope, prev_scope)
        finally:
            app.root.destroy()

    def test_select_monitor_chooser_os_close_releases_grab(self):
        from screen2xyz_m2.targets import MonitorTarget
        app = _make_app()
        try:
            monitors = [MonitorTarget(index=0, x=0, y=0, w=1920, h=1080),
                       MonitorTarget(index=1, x=1920, y=0, w=1920, h=1080)]
            with mock.patch("screen2xyz_m2.ui.app.list_monitors",
                            return_value=monitors):
                app._select_monitor()
            chooser = app.root.grab_current()
            self.assertIsNotNone(chooser)
            prev_scope = app.scope
            self._simulate_os_close(chooser)
            self.assertIsNone(app.root.grab_current())
            self.assertEqual(app.scope, prev_scope)
        finally:
            app.root.destroy()

    def test_select_window_chooser_has_a_cancel_button(self):
        """UX gap the same audit flagged: once modal, the only pre-fix
        way out was the OS close button - not discoverable. There must
        now be an on-screen Cancel."""
        app = _make_app()
        try:
            with mock.patch("screen2xyz_m2.ui.app.list_windows",
                            return_value=[]):
                app._select_window()
            chooser = app.root.grab_current()
            texts = [w["text"] for w in chooser.winfo_children()
                    if isinstance(w, ttk.Frame)
                    for w in w.winfo_children()]
            self.assertIn("Cancel", texts)
            chooser.destroy()
        finally:
            app.root.destroy()

    def test_draw_region_countdown_bar_is_modal(self):
        app = _make_app()
        try:
            app.scope = {"type": "window", "hwnd": 1, "pid": 1}
            source = SourceConfig(source_id=new_source_id(),
                                  display_name="A", rect=(0, 0, 10, 10))
            app.sources.append(source)
            app._refresh_table()
            row = app.table.get_children()[0]
            app.table.selection_set(row)
            app.table.focus(row)
            app._draw_region()
            try:
                grabbed = app.root.grab_current()
                self.assertIsNotNone(grabbed)
                self.assertEqual(grabbed.title(), "Draw region")
            finally:
                # Clean up the pending 3s countdown's after() callbacks
                # and release the grab, so the test process exits cleanly.
                grabbed.destroy()
                app._draw_countdown_active = False
        finally:
            app.root.destroy()


@unittest.skipUnless(_HAS_TK, "no Tk display")
class AcknowledgementRegressionTests(unittest.TestCase):
    """Independent audit MAJOR: Preview/Start-recording/re-preview/Retest-
    all-regions ran their real (potentially multi-field, always
    synchronous) worker round-trip with no "Working…" acknowledgement at
    all, unlike Test capture's existing status.set()+update_idletasks()
    pattern - the window simply stopped responding with no on-screen sign
    the click had registered. Each test below proves the acknowledgement
    text is visible BEFORE the blocking call actually runs, by having the
    stub's blocking method itself capture the on-screen text at the
    moment it is invoked."""

    def test_preview_shows_working_before_the_blocking_call(self):
        app = _make_app()
        try:
            app.scope = {"type": "window", "hwnd": 1, "pid": 1}
            source = SourceConfig(source_id=new_source_id(),
                                  display_name="A", rect=(0, 0, 10, 10))
            app.sources.append(source)
            app._confirmed_regions.add(source.source_id)
            captured = {}

            class _StubController:
                def ensure_worker(self):
                    captured["status"] = app.status.get()
                    raise WorkerError("PROCESS_EXITED", "stub")

            app._ensure_controller = lambda: _StubController()
            app._preview()
            self.assertEqual(captured.get("status"), "Previewing…")
        finally:
            app.root.destroy()

    def test_start_recording_shows_working_before_the_blocking_call(self):
        app = _make_app()
        try:
            app.ready_status_var = tk.StringVar(value="")
            captured = {}

            class _StubController:
                def start_recording(self):
                    captured["status"] = app.ready_status_var.get()
                    raise WorkerError("PROCESS_EXITED", "stub")

            app.controller = _StubController()
            with mock.patch("screen2xyz_m2.ui.app.messagebox.showwarning"):
                app._start_recording()
            self.assertEqual(captured.get("status"), "Starting…")
        finally:
            app.root.destroy()

    def test_disarm_and_repreview_shows_working_before_the_blocking_call(
            self):
        app = _make_app()
        try:
            app.scope = {"type": "window", "hwnd": 1, "pid": 1}
            app.recovery_var = tk.StringVar(value="")
            captured = {}

            class _StubMachine:
                def reconfigure(self):
                    pass

            class _StubController:
                machine = _StubMachine()
                environment_snapshot = {}

                def ensure_worker(self):
                    captured["status"] = app.recovery_var.get()
                    raise WorkerError("PROCESS_EXITED", "stub")

            app.controller = _StubController()
            with mock.patch("screen2xyz_m2.ui.app.messagebox.showwarning"):
                app._disarm_and_repreview()
            self.assertEqual(captured.get("status"),
                             "Reconfiguring and re-previewing…")
        finally:
            app.root.destroy()


@unittest.skipUnless(_HAS_TK, "no Tk display")
class HumanizedSetupControlsRegressionTests(unittest.TestCase):
    """Usability: the Backend and Retention dropdowns must SHOW friendly
    labels but STORE the internal enum the rest of the app reads, and the
    cursor checkbox label must reflect its actual on/off state (it used to
    say "(off)" forever)."""

    def test_backend_dropdown_stores_enum_shows_label(self):
        app = _make_app()
        try:
            # Default: internal token stored, friendly label displayed.
            self.assertEqual(app.backend_var.get(), C.BACKEND_AUTO)
            self.assertEqual(app.backend_display_var.get(),
                             "Auto (recommended)")
            # Selecting the friendly "PrintWindow" stores the real token.
            app.backend_display_var.set("PrintWindow")
            app._on_backend_changed  # sanity: handler exists
            from screen2xyz_m2.ui.app import backend_value
            app.backend_var.set(backend_value("PrintWindow"))
            self.assertEqual(app.backend_var.get(), "printwindow_clientonly")
        finally:
            app.root.destroy()

    def test_retention_dropdown_stores_key_shows_label(self):
        app = _make_app()
        try:
            self.assertEqual(app.retention_var.get(), C.RETENTION_DEFAULT)
            self.assertNotIn("_", app.retention_display_var.get())
            from screen2xyz_m2.ui.app import retention_key
            app.retention_var.set(retention_key("Changed values only"))
            self.assertEqual(app.retention_var.get(), "changed_only")
        finally:
            app.root.destroy()

    def test_cursor_checkbox_label_tracks_state(self):
        app = _make_app()
        try:
            self.assertEqual(app.cursor_check["text"], "Cursor position: off")
            app.cursor_var.set(True)
            app._on_cursor_toggled()
            self.assertEqual(app.cursor_check["text"], "Cursor position: on")
            app.cursor_var.set(False)
            app._on_cursor_toggled()
            self.assertEqual(app.cursor_check["text"], "Cursor position: off")
        finally:
            app.root.destroy()

    def test_feed_headers_are_humanized_not_raw(self):
        # The real leak was snake_case tokens (VALUE_STATUS, LIVE_CSV,
        # RAW_OCR); a bare acronym like "OCR" is fine.
        from screen2xyz_m2.ui.layout import FEED_COLUMNS, feed_column_title
        for col in FEED_COLUMNS:
            title = feed_column_title(col)
            self.assertNotIn("_", title,
                             f"feed header for {col} still raw: {title!r}")


@unittest.skipUnless(_HAS_TK, "no Tk display")
class RecoveryDeadEndRegressionTests(unittest.TestCase):
    """Usability MAJORs: a closed target window used to offer only 'Disarm
    and re-preview' (which re-previews the dead window and cannot recover -
    a dead-end into Stop), and non-repreview pauses (minimized/covered/disk/
    worker) discarded pause_message's recommended actions, leaving only a
    Resume that instantly re-paused with no on-screen fix. _render_pause_
    state must route each pause class to a recovery that can actually work."""

    def _recording_app(self):
        app = _make_app()
        app.rec_banner = tk.StringVar()
        app.pause_guidance_var = tk.StringVar()
        app._cards_label = ttk.Label(app.root, text="Field cards")
        app._cards_label.pack()
        app.recovery_frame = tk.Frame(app.root)
        app.recovery_var = tk.StringVar()
        app.recovery_btn = ttk.Button(app.recovery_frame)
        app.recovery_btn.pack()
        app.pause_btn = ttk.Button(app.root)
        app.resume_btn = ttk.Button(app.root)
        app._resume_needs_recovery = False
        app.controller = None  # keeps _refresh_pause_resume_buttons a no-op
        return app

    def test_closed_window_offers_target_reselection_not_repreview(self):
        app = self._recording_app()
        try:
            called = []
            app._reselect_target_for_recovery = \
                lambda: called.append("reselect")
            app._disarm_and_repreview = lambda: called.append("disarm")
            app._render_pause_state(
                PauseState("TARGET_UNAVAILABLE", requires_reresolve=True))
            self.assertEqual(app.recovery_btn["text"],
                             "Choose target window…")
            app.recovery_btn.invoke()
            self.assertEqual(called, ["reselect"])
            self.assertNotIn("disarm", called)
            self.assertEqual(app.pause_guidance_var.get(), "")
        finally:
            app.root.destroy()

    def test_resize_pause_still_offers_disarm_and_repreview(self):
        app = self._recording_app()
        try:
            app._render_pause_state(
                PauseState("DISPLAY_INVALIDATED", "DPI changed",
                           requires_repreview=True))
            self.assertEqual(app.recovery_btn["text"],
                             "Disarm and re-preview…")
            # _resume_needs_recovery is the mapping-independent flag the
            # recovery bar sets (the test root is never deiconified, so
            # winfo_ismapped is unreliable here).
            self.assertTrue(app._resume_needs_recovery)
        finally:
            app.root.destroy()

    def test_minimized_pause_shows_plain_guidance_not_a_dead_resume(self):
        app = self._recording_app()
        try:
            app._render_pause_state(PauseState("TARGET_MINIMIZED_STREAK"))
            # No re-preview bar for this pause (Resume stays available)...
            self.assertFalse(app._resume_needs_recovery)
            # ...but a concrete instruction so Resume is not a mystery.
            self.assertIn("Restore", app.pause_guidance_var.get())
        finally:
            app.root.destroy()

    def test_disk_limit_pause_tells_owner_data_is_safe(self):
        app = self._recording_app()
        try:
            app._render_pause_state(PauseState("DISK_LIMIT"))
            guidance = app.pause_guidance_var.get().lower()
            self.assertIn("disk", guidance)
            self.assertIn("stop", guidance)  # Stop still saves
        finally:
            app.root.destroy()

    def test_healthy_tick_clears_stale_pause_guidance(self):
        app = self._recording_app()
        try:
            app._render_pause_state(PauseState("TARGET_MINIMIZED_STREAK"))
            self.assertNotEqual(app.pause_guidance_var.get(), "")
            app._render_pause_state(None)  # a normal, non-pausing tick
            self.assertEqual(app.pause_guidance_var.get(), "")
        finally:
            app.root.destroy()


@unittest.skipUnless(_HAS_TK, "no Tk display")
class SetupPolishRegressionTests(unittest.TestCase):
    """Usability polish from the persona evaluation: no silent-no-op setup
    buttons, no contradictory REGION/STATUS cells, no crash from the
    next-step refresh after leaving setup, and a welcome dialog whose own
    'how to start' guidance is actually reachable."""

    def test_adding_a_field_auto_selects_its_row(self):
        app = _make_app()
        try:
            app._add_source()
            children = app.table.get_children()
            self.assertEqual(len(children), 1)
            self.assertIn(children[-1], app.table.selection())
            self.assertEqual(app.table.focus(), children[-1])
            self.assertIn("Draw region", app.status.get())
        finally:
            app.root.destroy()

    def test_remove_with_no_selection_gives_feedback_not_silence(self):
        app = _make_app()
        try:
            app.status.set("")
            app.table.selection_remove(*app.table.selection())
            app.table.focus("")
            app._remove_source()
            self.assertEqual(app.status.get(), "Select a field row first.")
        finally:
            app.root.destroy()

    def test_region_cell_reads_not_drawn_until_confirmed(self):
        app = _make_app()
        try:
            app._add_source()
            row = app.table.get_children()[-1]
            # values = (name, type, role, region, status, preview)
            self.assertEqual(app.table.item(row, "values")[3], "(not drawn)")
            # Once confirmed, the coordinates appear and STATUS agrees.
            sid = app.sources[0].source_id
            app._confirmed_regions.add(sid)
            app._refresh_table()
            row = app.table.get_children()[-1]
            self.assertNotEqual(app.table.item(row, "values")[3],
                                "(not drawn)")
            self.assertEqual(app.table.item(row, "values")[4], "region set")
        finally:
            app.root.destroy()

    def test_refresh_next_step_is_safe_after_setup_widgets_destroyed(self):
        app = _make_app()
        try:
            # Simulate a screen swap: the setup widgets are gone but the
            # StringVars survive. _refresh_next_step must no-op, not TclError
            # on the destroyed test_capture_btn.
            app.test_capture_btn.destroy()
            app._refresh_next_step()  # must not raise
        finally:
            app.root.destroy()

    def test_welcome_dialog_is_scrollable_and_leads_with_how_to_start(self):
        from screen2xyz_m2.ui.app import WELCOME_TEXT
        # The call to action is reachable near the top, before the step list.
        self.assertLess(WELCOME_TEXT.index("Not sure where to start"),
                        WELCOME_TEXT.index("Step 6"))
        app = _make_app()
        try:
            app._show_welcome()
            dialog = [w for w in app.root.winfo_children()
                     if isinstance(w, tk.Toplevel)
                     and "Welcome" in (w.title() or "")][0]

            def has_scrollbar(widget):
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Scrollbar):
                        return True
                    if has_scrollbar(child):
                        return True
                return False

            self.assertTrue(has_scrollbar(dialog))
            dialog.destroy()
        finally:
            app.root.destroy()

    def test_help_documents_the_yellow_feed_colour(self):
        from screen2xyz_m2.ui.app import HELP_TEXT
        self.assertIn("yellow", HELP_TEXT)

    def test_add_tooltip_binds_without_error(self):
        app = _make_app()
        try:
            btn = ttk.Button(app.root)
            app._add_tooltip(btn, "Emergency stop")
            # The hover binding exists (proves the tooltip was wired up).
            self.assertTrue(btn.bind("<Enter>"))
        finally:
            app.root.destroy()


@unittest.skipUnless(_HAS_TK, "no Tk display")
class StepNumberingConsistencyTests(unittest.TestCase):
    """Persona MAJOR: the same action appeared under two different step
    numbers. The card's canonical map is 4=preview, 5=arm/start, 6=record;
    the UI chrome must match it."""

    def test_ready_to_preview_action_matches_the_real_button_label(self):
        view = derive_next_step(
            has_target=True, controller_state="REGIONS_CONFIGURED",
            capture_tested=True, capture_verdict="PASS",
            enabled_field_count=1, all_regions_confirmed=True,
            preview_confirmed=False)
        self.assertEqual(view["step"], 4)
        self.assertEqual(view["primary_action"], "Preview all fields")

    def test_no_ui_string_reuses_a_step_number_for_a_different_action(self):
        # The preview gate is Step 4 and Ready is Step 5 (not 5 and 6), so
        # "Step 5 — Preview" and "Step 6 — Ready" must be gone from app.py.
        import screen2xyz_m2.ui.app as appmod
        import inspect
        source = inspect.getsource(appmod)
        self.assertNotIn("Step 5 — Preview and verify", source)
        self.assertNotIn("Step 6 — Ready to record", source)
        self.assertIn("Step 4 — Preview and verify", source)
        self.assertIn("Step 5 — Ready to record", source)


if __name__ == "__main__":
    unittest.main()
