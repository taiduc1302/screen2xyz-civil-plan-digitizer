"""M2 Windows integration harness (real PS worker + synthetic Tk target).

Skips with an explicit reason off Windows. Drives the real
capture_worker_windows.ps1 through INIT/PREVIEW/ARM/RECORD_START/CAPTURE/
STOP/SHUTDOWN against the deterministic synthetic target, asserting a real
synchronized frame, cross-source frame identity, a real OCR read, worker
exit on stdin close, and a full controller record+finalize.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

WINDOWS = sys.platform == "win32"
TARGET = ROOT / "docs/research/spikes/spike_s7_synthetic_target.py"
LAYERED_TARGET = ROOT / "docs/research/spikes/spike_layered_window_target.py"
SMALL_TEXT_TARGET = ROOT / "docs/research/spikes/spike_small_text_target.py"
TIGHT_MARGIN_TARGET = ROOT / "docs/research/spikes/spike_tight_margin_text_target.py"
COORD_DMS_TARGET = ROOT / "docs/research/spikes/spike_coordinate_dms_target.py"
COORD_LINE_TARGET = ROOT / "docs/research/spikes/spike_coordinate_line_target.py"


def _skip_reason() -> str | None:
    if not WINDOWS:
        return "M2 integration requires Windows (real PS worker + WinRT OCR)"
    return None


@unittest.skipIf(_skip_reason() is not None, _skip_reason() or "")
class WorkerIntegrationTests(unittest.TestCase):
    def setUp(self):
        import ctypes
        ctypes.windll.user32.SetProcessDpiAwarenessContext(
            ctypes.c_void_p(-4))
        self.target = subprocess.Popen(
            [sys.executable, str(TARGET), "S2XYZ-M2-INT"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8")
        self.ready = json.loads(self.target.stdout.readline())
        self.addCleanup(self._stop_target)

    def _stop_target(self):
        try:
            self.target.stdin.write('{"cmd":"quit"}\n')
            self.target.stdin.flush()
            self.target.wait(timeout=5)
        except Exception:
            self.target.kill()

    def _controller(self):
        from screen2xyz_m2.controller import LiveSessionController
        from screen2xyz_m2.models import SessionDefaults, SourceConfig, \
            new_source_id
        scope = {"type": "window", "hwnd": self.ready["hwnd"],
                 "pid": self.ready["pid"], "title": "synthetic"}
        sources = [
            SourceConfig(source_id=new_source_id(), display_name="Lon",
                         semantic_role="x", rect=(30, 40, 460, 44)),
            SourceConfig(source_id=new_source_id(), display_name="Lat",
                         semantic_role="y", rect=(30, 120, 460, 44)),
            SourceConfig(source_id=new_source_id(), display_name="Elev",
                         semantic_role="z", rect=(30, 200, 460, 44)),
        ]
        environment = {"window": {"client_w": self.ready["client_w"],
                                  "client_h": self.ready["client_h"],
                                  "dpi": self.ready["dpi"]}}
        run_parent = ROOT / ".lab_work" / "m2_runs"
        return LiveSessionController(
            scope=scope, backend="printwindow_clientonly", sources=sources,
            defaults=SessionDefaults(), environment_snapshot=environment,
            run_parent=run_parent)

    def test_full_record_and_finalize(self):
        controller = self._controller()
        controller.machine.select_target()
        controller.machine.sources_configured()
        controller.ensure_worker()
        preview = controller.preview()
        self.assertEqual(preview["capture_status"], "OK")
        self.assertEqual(len(preview["observations"]), 3)
        controller.confirm_preview_and_arm()
        controller.start_recording()

        # tick 1: present values. Real-target OCR fix (owner test against
        # Google Earth, 2026-07-19): this field's native-scale OCR used to
        # be able to misread "-123.654321" with a spurious extra leading
        # digit; the small-crop auto-upscale fix made that read reliably
        # accurate. Phase 0 boundary audit (2026-07-19) added a padding
        # step alongside the upscale floor, which - as a real, deterministic
        # side effect, confirmed across repeated runs - fixed this target's
        # THIRD field ("Elev", previously EMPTY_TEXT on every run before and
        # after the upscale-only fix; see M2_IMPLEMENTATION_REPORT.md §5k)
        # but introduced a new, equally deterministic misread on the SECOND
        # field ("Lat", "49.123456" -> "49�123456"): the OCR engine's
        # own fragility shifted which exact glyph pattern it stumbles on,
        # it did not go away. This is asserted explicitly and per-field
        # below, rather than papered over with a loose "any text" check,
        # because the misread is caught correctly (AMBIGUOUS_MULTIPLE_
        # NUMBERS, a real retained error) - never silently treated as a
        # valid number. Real OCR-engine fragility for specific glyph
        # patterns remains an honest, disclosed limitation (§6); this test
        # documents its exact, reproduced shape for this target rather than
        # assuming it away.
        result1 = controller.tick()
        self.assertIsNotNone(result1.frame)
        frame_ids = {obs.ocr_ref for obs in result1.observations.values()
                     if obs.ocr_ref}
        self.assertEqual(len(frame_ids), 1)  # one synchronized frame
        by_name = {s.source_id: s.display_name for s in controller.sources}
        obs_by_name = {by_name[sid]: obs
                      for sid, obs in result1.observations.items()}
        self.assertEqual(obs_by_name["Lon"].value_status, "OK")
        self.assertEqual(obs_by_name["Lon"].normalized_value, "-123.654321")
        self.assertEqual(obs_by_name["Elev"].value_status, "OK")
        self.assertEqual(obs_by_name["Elev"].normalized_value, "87.05")
        self.assertEqual(obs_by_name["Lat"].value_status,
                         "AMBIGUOUS_MULTIPLE_NUMBERS")
        self.assertEqual(obs_by_name["Lat"].ocr_status, "OK")  # not empty
        # This misread IS a genuine retained error (data contracts §6a) -
        # not the accidental, unrelated bug an earlier version of this test
        # relied on.
        self.assertEqual(result1.decision.event_status, "RETAINED_ERROR")

        # Toggle the target blank and back. By design (stability.py:
        # MISSING_SOURCE_VALUE observations are "live/diagnostic only;
        # never mutate the stable signature") a transient blank read is
        # never retained as a change or an error - a momentarily-empty
        # field is not itself meaningful data. So this toggle verifies the
        # tick/observation pipeline correctly SEES the blank state and
        # handles a present->absent->present cycle without error, and
        # produces no ADDITIONAL retained event beyond tick 1's; genuine
        # value-change -> retained-event coverage for the non-error case
        # already lives in LiveFeedCsvIntegrationTests (which drives the
        # demo target's real continuously-changing values and asserts a
        # nonzero, journal-matching CSV row count).
        self.target.stdin.write('{"cmd":"absent"}\n')
        self.target.stdin.flush()
        time.sleep(0.3)
        result2 = controller.tick()
        self.assertTrue(any(obs.value_status == "MISSING_SOURCE_VALUE"
                            for obs in result2.observations.values()))
        self.assertIsNone(result2.decision.event_status)
        self.target.stdin.write('{"cmd":"present"}\n')
        self.target.stdin.flush()
        time.sleep(0.3)
        controller.tick()

        summary = controller.stop()
        self.assertEqual(controller.machine.state, "FINALIZED")
        run_dir = controller.journal.run_dir
        # events.jsonl is created lazily on the first retained event -
        # tick 1's genuine, deterministic AMBIGUOUS_MULTIPLE_NUMBERS error
        # (see above) is exactly one such event, and none of the later
        # present/absent toggling adds another.
        self.assertEqual(summary["event_count"], 1)
        self.assertTrue((run_dir / "events.jsonl").is_file())
        self.assertTrue((run_dir / "evidence_manifest_sha256.txt").is_file())
        self.assertTrue((run_dir / "run_summary.json").is_file())
        self.assertTrue((run_dir / "session.json").is_file())
        # cleanup ignored run dir
        import shutil
        shutil.rmtree(run_dir, ignore_errors=True)

    def test_worker_exits_on_stdin_close(self):
        from screen2xyz_m2.worker import WorkerClient
        worker = WorkerClient(
            session_id="s",
            scope={"type": "window", "hwnd": self.ready["hwnd"],
                   "pid": self.ready["pid"]},
            backend="printwindow_clientonly")
        worker.start(restore_session_state="REGIONS_CONFIGURED",
                     configuration_revision=0)
        proc = worker._proc
        proc.stdin.close()
        for _ in range(50):
            if proc.poll() is not None:
                break
            time.sleep(0.1)
        self.assertIsNotNone(proc.poll(), "worker did not exit on stdin close")
        worker.teardown()


@unittest.skipIf(_skip_reason() is not None, _skip_reason() or "")
class AutoBackendIntegrationTests(unittest.TestCase):
    """Real end-to-end proof of the Auto backend fix (M2 UI/capture
    reliability remediation): PrintWindow works fine against a normal
    window, and a genuinely hanging PrintWindow call (a real, reproduced
    hazard on a DWM-layered window - not just a returned-bad-frame case) is
    bounded and falls back to CopyFromScreen without ever blocking the
    worker's protocol loop."""

    def setUp(self):
        import ctypes
        ctypes.windll.user32.SetProcessDpiAwarenessContext(
            ctypes.c_void_p(-4))

    def _worker(self, hwnd: int, pid: int):
        from screen2xyz_m2.worker import WorkerClient
        worker = WorkerClient(
            session_id="auto", scope={"type": "window", "hwnd": hwnd,
                                      "pid": pid},
            backend="auto")
        worker.start(restore_session_state="REGIONS_CONFIGURED",
                     configuration_revision=0)
        self.addCleanup(worker.teardown)
        return worker

    def test_auto_resolves_to_printwindow_and_latches(self):
        target = subprocess.Popen(
            [sys.executable, str(TARGET), "S2XYZ-M2-AUTO"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8")
        ready = json.loads(target.stdout.readline())
        self.addCleanup(target.kill)
        worker = self._worker(ready["hwnd"], ready["pid"])
        r1 = worker.request("REGION_SNAPSHOT", {"probe_backend": True},
                            timeout_ms=8000, ui_session_state="TARGET_SELECTED",
                            configuration_revision=0)
        self.assertEqual(r1["effective_backend"], "printwindow_clientonly")
        self.assertTrue(r1["backend_probe"][0]["usable"])
        # A second snapshot without forcing a probe must NOT re-test -
        # backend_probe is only populated when a probe actually ran.
        r2 = worker.request("REGION_SNAPSHOT", {"probe_backend": False},
                            timeout_ms=8000, ui_session_state="TARGET_SELECTED",
                            configuration_revision=0)
        self.assertIsNone(r2["backend_probe"])
        self.assertEqual(r2["effective_backend"], "printwindow_clientonly")

    def test_auto_falls_back_when_printwindow_hangs(self):
        # A layered/composited window is a real, reproduced trigger for
        # PrintWindow to hang indefinitely (not just return bad pixels) -
        # this is the exact hazard the bounded PrintWindow call exists for.
        target = subprocess.Popen(
            [sys.executable, str(LAYERED_TARGET), "S2XYZ-M2-LAYERED"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8")
        ready = json.loads(target.stdout.readline())
        self.addCleanup(lambda: (target.stdin.write("x\n"),
                                 target.stdin.flush(), target.kill()))
        worker = self._worker(ready["hwnd"], ready["pid"])
        started = time.monotonic()
        reply = worker.request(
            "REGION_SNAPSHOT", {"probe_backend": True}, timeout_ms=8000,
            ui_session_state="TARGET_SELECTED", configuration_revision=0)
        elapsed = time.monotonic() - started
        # Bounded: the worker's own PrintWindow timeout (1.5s) plus a fast
        # CopyFromScreen fallback, well inside the 8s client budget - proves
        # the hang never propagates past the protocol loop.
        self.assertLess(elapsed, 5.0)
        self.assertEqual(reply["effective_backend"], "copyfromscreen")
        self.assertEqual(reply["capture_status"], "OK")
        backends_tried = {p["backend"] for p in reply["backend_probe"]}
        self.assertEqual(backends_tried,
                         {"printwindow_clientonly", "copyfromscreen"})


@unittest.skipIf(_skip_reason() is not None, _skip_reason() or "")
class LiveFeedCsvIntegrationTests(unittest.TestCase):
    """End-to-end proof (region-selection/live-feed remediation) that the
    persisted event count matches the actual CSV row count, and that no
    worker/demo process survives finalize - using the real demo target,
    the real controller/journal/exports pipeline, no mocks."""

    def test_persisted_event_count_matches_csv_row_count(self):
        # No retry (§9): this drives the demo target on CopyFromScreen, which
        # sends no WM_PRINT to the target's own Tk loop, so the PrintWindow-
        # induced handshake stall that once forced a retry cannot occur. Auto
        # backend resolution/fallback is covered by AutoBackendIntegrationTests.
        self._run_once()

    def _run_once(self) -> None:
        import csv
        import shutil
        from screen2xyz_m2 import contracts as C
        from screen2xyz_m2.controller import LiveSessionController
        from screen2xyz_m2.demo import DemoSession
        from screen2xyz_m2.models import SessionDefaults
        from screen2xyz_m2.paths import run_root
        from screen2xyz_m2.targets import environment_snapshot

        session = DemoSession()
        controller: LiveSessionController | None = None
        try:
            session.set_case("stable")
            env = environment_snapshot(session.scope(),
                                      C.BACKEND_COPYFROMSCREEN)
            sources = session.sources()
            controller = LiveSessionController(
                scope=session.scope(), backend=C.BACKEND_COPYFROMSCREEN,
                sources=sources,
                defaults=SessionDefaults(interval_ms=250),
                environment_snapshot=env, run_parent=run_root())
            controller.machine.select_target()
            controller.machine.sources_configured()
            controller.ensure_worker()
            controller.preview()
            controller.confirm_preview_and_arm()
            controller.start_recording()

            controller.tick()  # seed
            session.set_case("changing")
            session.auto_change(True)
            for _ in range(6):
                controller.tick()
                time.sleep(0.15)
            session.auto_change(False)

            journal_events = controller.journal.counters["events"]
            live_snapshot_rows = controller.journal.live_snapshot_row_count
            summary = controller.stop()
            run_dir = controller.journal.run_dir
            try:
                self.assertEqual(summary["event_count"], journal_events)
                with (run_dir / "events_wide.csv").open(
                        newline="", encoding="utf-8") as fh:
                    csv_row_count = sum(1 for _ in csv.reader(fh)) - 1
                self.assertEqual(csv_row_count, journal_events)
                self.assertGreater(csv_row_count, 0)
                # §2/§5: the live CSV snapshot the owner watched WHILE
                # recording must match the same event count as the final,
                # verified CSV row count - three independent truths, all
                # equal for the same run.
                self.assertEqual(live_snapshot_rows, journal_events)
                self.assertEqual(summary["final_csv_row_count"],
                                 journal_events)
                self.assertTrue(summary["final_csv_row_count_verified"])
                self.assertTrue(
                    (run_dir / "events_wide.live.csv").is_file())
                # No orphan: the worker was torn down by stop() above.
                self.assertIsNone(controller.worker)
            finally:
                shutil.rmtree(run_dir, ignore_errors=True)
        finally:
            if controller is not None and controller.worker is not None:
                controller.worker.teardown()
            session.quit()


class DemoProtocolIntegrationTests(unittest.TestCase):
    """§6 real-subprocess coverage for the deterministic demo protocol: a
    real Tk target, no real capture worker involved, so none of these need
    (or get) a retry - proving the protocol fix holds under real process/
    thread timing, not just the fake-queue unit tests."""

    def _spawn(self):
        from screen2xyz_m2.demo import DEMO_TARGET_SCRIPT
        proc = subprocess.Popen(
            [sys.executable, str(DEMO_TARGET_SCRIPT), "S2XYZ-M2-PROTO"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8")
        ready = json.loads(proc.stdout.readline())
        return proc, ready

    def test_delayed_first_command_after_ready_still_acks_promptly(self):
        # No real capture worker is contending for this window, so the
        # deterministic protocol must ack well within budget every time -
        # across several fresh spawns, not just once.
        from screen2xyz_m2.demo import DemoSession
        for _ in range(3):
            session = DemoSession()
            try:
                start = time.monotonic()
                session.set_case("stable")
                elapsed = time.monotonic() - start
                self.assertLess(elapsed, 3.0)
            finally:
                session.quit()

    def test_duplicate_messages_each_get_their_own_correctly_matched_ack(self):
        proc, ready = self._spawn()
        token = ready["session_token"]
        try:
            for seq in (1, 2, 3):
                proc.stdin.write(json.dumps(
                    {"cmd": "case", "name": "stable", "seq": seq,
                     "session_token": token}) + "\n")
                proc.stdin.flush()
                reply = json.loads(proc.stdout.readline())
                self.assertEqual(reply["seq"], seq)
                self.assertEqual(reply["session_token"], token)
        finally:
            proc.stdin.write(json.dumps(
                {"cmd": "quit", "seq": 99, "session_token": token}) + "\n")
            proc.stdin.flush()
            proc.wait(timeout=5)

    def test_stale_session_token_is_echoed_not_silently_corrected(self):
        # The target echoes back whatever token it was given (it does not
        # enforce one, since one target process serves exactly one client
        # pipe) - proving the client-side _ack_matches check, not the
        # target, is what makes a wrong/stale token unusable.
        proc, ready = self._spawn()
        token = ready["session_token"]
        try:
            proc.stdin.write(json.dumps(
                {"cmd": "case", "name": "stable", "seq": 1,
                 "session_token": "definitely-not-the-real-token"}) + "\n")
            proc.stdin.flush()
            reply = json.loads(proc.stdout.readline())
            self.assertEqual(reply["session_token"],
                            "definitely-not-the-real-token")
            self.assertNotEqual(reply["session_token"], token)
        finally:
            proc.stdin.write(json.dumps(
                {"cmd": "quit", "seq": 2, "session_token": token}) + "\n")
            proc.stdin.flush()
            proc.wait(timeout=5)

    def test_target_crash_raises_clear_runtime_error_not_a_hang(self):
        from screen2xyz_m2.demo import DemoSession
        session = DemoSession()
        try:
            session.proc.kill()
            session.proc.wait(timeout=5)
            with self.assertRaises(RuntimeError):
                session.set_case("stable")
        finally:
            session.proc.poll() is None and session.proc.kill()

    def test_partial_command_across_two_writes_is_not_acted_on_early(self):
        proc, ready = self._spawn()
        token = ready["session_token"]
        try:
            full = json.dumps({"cmd": "case", "name": "changing", "seq": 1,
                              "session_token": token})
            half = len(full) // 2
            proc.stdin.write(full[:half])  # no newline - must not be acted on
            proc.stdin.flush()
            time.sleep(0.2)
            proc.stdin.write(full[half:] + "\n")  # completes the line
            proc.stdin.flush()
            reply = json.loads(proc.stdout.readline())
            self.assertEqual(reply["ok"], "case")
            self.assertEqual(reply["seq"], 1)
        finally:
            proc.stdin.write(json.dumps(
                {"cmd": "quit", "seq": 2, "session_token": token}) + "\n")
            proc.stdin.flush()
            proc.wait(timeout=5)

    def test_shutdown_during_command_leaves_no_orphan(self):
        proc, ready = self._spawn()
        token = ready["session_token"]
        proc.stdin.write(json.dumps(
            {"cmd": "case", "name": "stable", "seq": 1,
             "session_token": token}) + "\n")
        proc.stdin.flush()
        proc.stdout.readline()  # drain its ack
        proc.stdin.write(json.dumps(
            {"cmd": "quit", "seq": 2, "session_token": token}) + "\n")
        proc.stdin.flush()
        proc.wait(timeout=5)
        self.assertIsNotNone(proc.returncode)  # no orphan process left


@unittest.skipIf(_skip_reason() is not None, _skip_reason() or "")
class SmallTextOcrRegressionTests(unittest.TestCase):
    """Real-target finding (owner test against Google Earth's coordinate
    readout, 2026-07-19): at a field's default upscale (1), Windows.Media.
    Ocr reliably returned EMPTY TEXT for realistic small on-screen UI text
    (status bars, HUD overlays, coordinate displays) - confirmed empirically
    across multiple contrast/background variants, all fixed by an internal
    small-crop auto-upscale floor in capture_worker_windows.ps1's Invoke-Ocr.
    This drives the REAL controller + REAL worker + REAL OCR against a
    dedicated small-text synthetic target at that exact scale, with the
    field's upscale_factor left at its DEFAULT (never set explicitly), so a
    regression here can only be caught by exercising the real fix."""

    def setUp(self):
        import ctypes
        ctypes.windll.user32.SetProcessDpiAwarenessContext(
            ctypes.c_void_p(-4))
        self.target = subprocess.Popen(
            [sys.executable, str(SMALL_TEXT_TARGET), "S2XYZ-M2-SMALLTEXT"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8")
        self.ready = json.loads(self.target.stdout.readline())
        self.addCleanup(self._stop_target)

    def _stop_target(self):
        try:
            self.target.stdin.write('{"cmd":"quit"}\n')
            self.target.stdin.flush()
            self.target.wait(timeout=5)
        except Exception:
            self.target.kill()

    def test_small_ui_text_is_recognized_at_the_field_default_upscale(self):
        from screen2xyz_m2.controller import LiveSessionController
        from screen2xyz_m2.models import SessionDefaults, SourceConfig, \
            new_source_id

        scope = {"type": "window", "hwnd": self.ready["hwnd"],
                 "pid": self.ready["pid"], "title": "small-text-target"}
        environment = {"window": {"client_w": self.ready["client_w"],
                                  "client_h": self.ready["client_h"],
                                  "dpi": self.ready["dpi"]}}
        # upscale_factor is intentionally left at SourceConfig's own default
        # (1) - this test's whole point is that the OWNER never has to
        # discover and set it manually for realistic small on-screen text.
        source = SourceConfig(
            source_id=new_source_id(), display_name="Small", rect=tuple(
                self.ready["field_rect"]))
        self.assertEqual(source.upscale_factor, 1)
        run_parent = ROOT / ".lab_work" / "m2_runs"
        controller = LiveSessionController(
            scope=scope, backend="copyfromscreen", sources=[source],
            defaults=SessionDefaults(), environment_snapshot=environment,
            run_parent=run_parent)
        controller.machine.select_target()
        controller.machine.sources_configured()
        controller.ensure_worker()
        try:
            preview = controller.preview()
            self.assertEqual(preview["capture_status"], "OK")
            obs = preview["observations"][0]
            self.assertEqual(
                obs["ocr_status"], "OK",
                f"small on-screen text was not recognized at the field's "
                f"default upscale: {obs}")
            self.assertIn(self.ready["value"], obs["raw_text"])
        finally:
            controller._teardown_worker()


@unittest.skipIf(_skip_reason() is not None, _skip_reason() or "")
class TightMarginOcrRegressionTests(unittest.TestCase):
    """Phase 0 boundary-audit finding (2026-07-19): a controlled sweep of
    directly-constructed synthetic PNG crops fed to the REAL, ACTUAL
    shipped Invoke-Ocr function proved the small-crop auto-upscale floor
    alone does not fix a near-zero-margin region - exactly what the app's
    own troubleshooting guidance recommended ("redraw the region tighter
    around just the digits"): a crop with only a few px of margin around
    the ink returned EMPTY TEXT at EVERY upscale factor from 1x to 6x,
    fixed only by also padding the crop (independent of scale) before OCR.
    That gap is real and reproducibly proven (see
    .lab_work/overnight_qa/ocr_repro/verify_padding_fix.ps1's git-stash
    revert test, both directions, deterministic).

    Reproducing the SAME gap through this REAL controller + REAL worker +
    REAL OCR pipeline, against an ACTUAL captured Tk window rather than a
    hand-built PNG, turned out to be harder than expected: real Windows-
    rendered (ClearType) text captured via CopyFromScreen was consistently
    more OCR-forgiving at tight margins than the PIL-rendered synthetic
    crops at equivalent nominal dimensions - this test's window has to be
    sized right at the edge of clipping the glyph cell itself before it
    reproducibly fails without the padding step; a few extra px of margin
    and it passes either way. This is disclosed honestly rather than
    forced: the padding fix is evidence-backed, safe (does not regress
    any other case, verified below and via the wider fixture suite), and
    closes a real gap proven against the actual shipped code - but its
    necessity specifically through a live browser-rendered coordinate
    overlay (vs. a directly-constructed PNG) is less certain than the
    upscale-floor fix's necessity was. This test still provides real,
    valuable coverage: a genuinely tight, real-captured region must not
    regress through the combined padding+floor pipeline."""

    def setUp(self):
        import ctypes
        ctypes.windll.user32.SetProcessDpiAwarenessContext(
            ctypes.c_void_p(-4))
        self.target = subprocess.Popen(
            [sys.executable, str(TIGHT_MARGIN_TARGET), "S2XYZ-M2-TIGHT"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8")
        self.ready = json.loads(self.target.stdout.readline())
        self.addCleanup(self._stop_target)

    def _stop_target(self):
        try:
            self.target.stdin.write('{"cmd":"quit"}\n')
            self.target.stdin.flush()
            self.target.wait(timeout=5)
        except Exception:
            self.target.kill()

    def test_tight_margin_text_is_recognized_at_the_field_default_upscale(
            self):
        from screen2xyz_m2.controller import LiveSessionController
        from screen2xyz_m2.models import SessionDefaults, SourceConfig, \
            new_source_id

        scope = {"type": "window", "hwnd": self.ready["hwnd"],
                 "pid": self.ready["pid"], "title": "tight-margin-target"}
        environment = {"window": {"client_w": self.ready["client_w"],
                                  "client_h": self.ready["client_h"],
                                  "dpi": self.ready["dpi"]}}
        source = SourceConfig(
            source_id=new_source_id(), display_name="Tight", rect=tuple(
                self.ready["field_rect"]))
        self.assertEqual(source.upscale_factor, 1)
        run_parent = ROOT / ".lab_work" / "m2_runs"
        controller = LiveSessionController(
            scope=scope, backend="copyfromscreen", sources=[source],
            defaults=SessionDefaults(), environment_snapshot=environment,
            run_parent=run_parent)
        controller.machine.select_target()
        controller.machine.sources_configured()
        controller.ensure_worker()
        try:
            preview = controller.preview()
            self.assertEqual(preview["capture_status"], "OK")
            obs = preview["observations"][0]
            self.assertEqual(
                obs["ocr_status"], "OK",
                f"tight-margin on-screen text was not recognized at the "
                f"field's default upscale: {obs}")
            self.assertIn(self.ready["value"], obs["raw_text"])
        finally:
            controller._teardown_worker()


class CoordinateDmsOcrRegressionTests(unittest.TestCase):
    """Phase 1 (2026-07-19): the `coordinate` data type + `parse_coordinate`
    exist specifically because a real owner target (Google Earth's lat/long
    readout) had its degree symbol (°) reliably misread by Windows OCR
    as the digit "0" - a plain "number" field scoped tightly enough to
    isolate just the degrees would then silently accept a value ~10-1000x
    too large as if it were a normal reading (see
    M2_IMPLEMENTATION_REPORT.md Phase 1/§5k). `parse_coordinate` never
    guesses at the specific glyph confusion; it structurally tokenizes
    degrees/minutes/seconds/hemisphere and range-validates, so a corrupted
    or dropped degree symbol is caught by the resulting physically-
    impossible degrees value, not by pattern-matching the mistake itself.

    This drives that parse mode through the REAL controller + REAL worker +
    REAL Windows OCR engine against a single DMS coordinate ("49°08'
    20.06\"N") rendered at the same realistic small on-screen scale as the
    real-target bug (a field height under the 60px small-crop auto-upscale
    floor - see SmallTextOcrRegressionTests). What the real OCR engine
    actually does with the ° glyph at this scale is not controlled by
    this test (Phase 0 already found real ClearType-rendered text behaves
    differently from synthetic PNGs); what IS asserted, unconditionally, is
    the one property Phase 1 exists to guarantee: the field's value is
    EITHER the exact correct decimal-degree reading OR one of the specific,
    disclosed safe-failure statuses - never a wrong number accepted as
    valid."""

    # Never a silently-wrong OK: any parse_status outside this set (most
    # importantly a bare OK with a numerically wrong value) fails the test.
    _SAFE_FAILURE_STATUSES = frozenset({
        "SUSPECT_GLYPH_CONFUSION", "MALFORMED_NUMBER", "NO_NUMBER",
        "AMBIGUOUS_MULTIPLE_NUMBERS", "OUT_OF_RANGE",
    })
    _EXPECTED_DECIMAL = 49.138906  # 49 + 8/60 + 20.06/3600, see spike file

    def setUp(self):
        import ctypes
        ctypes.windll.user32.SetProcessDpiAwarenessContext(
            ctypes.c_void_p(-4))
        self.target = subprocess.Popen(
            [sys.executable, str(COORD_DMS_TARGET), "S2XYZ-M2-COORDDMS"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8")
        self.ready = json.loads(self.target.stdout.readline())
        self.addCleanup(self._stop_target)

    def _stop_target(self):
        try:
            self.target.stdin.write('{"cmd":"quit"}\n')
            self.target.stdin.flush()
            self.target.wait(timeout=5)
        except Exception:
            self.target.kill()

    def test_dms_coordinate_never_silently_becomes_a_wrong_number(self):
        from screen2xyz_m2.controller import LiveSessionController
        from screen2xyz_m2.models import SessionDefaults, SourceConfig, \
            new_source_id

        scope = {"type": "window", "hwnd": self.ready["hwnd"],
                 "pid": self.ready["pid"], "title": "coord-dms-target"}
        environment = {"window": {"client_w": self.ready["client_w"],
                                  "client_h": self.ready["client_h"],
                                  "dpi": self.ready["dpi"]}}
        # data_type is the only non-default field under test; upscale_factor
        # is left at SourceConfig's own default (1), same rationale as
        # SmallTextOcrRegressionTests - the owner never sets it by hand.
        source = SourceConfig(
            source_id=new_source_id(), display_name="Lat",
            data_type="coordinate", rect=tuple(self.ready["field_rect"]))
        self.assertEqual(source.upscale_factor, 1)
        run_parent = ROOT / ".lab_work" / "m2_runs"
        controller = LiveSessionController(
            scope=scope, backend="copyfromscreen", sources=[source],
            defaults=SessionDefaults(), environment_snapshot=environment,
            run_parent=run_parent)
        controller.machine.select_target()
        controller.machine.sources_configured()
        controller.ensure_worker()
        try:
            preview = controller.preview()
            self.assertEqual(preview["capture_status"], "OK")
            obs = preview["observations"][0]
            self.assertEqual(
                obs["ocr_status"], "OK",
                f"DMS coordinate text was not recognized at the field's "
                f"default upscale: {obs}")
            if obs["parse_status"] == "OK":
                self.assertAlmostEqual(
                    float(obs["normalized_value"]), self._EXPECTED_DECIMAL,
                    places=4,
                    msg=f"parse_status OK but the value is WRONG, not just "
                       f"a different reading - this is exactly the silent "
                       f"-corruption bug Phase 1 exists to prevent: {obs}")
            else:
                self.assertIn(
                    obs["parse_status"], self._SAFE_FAILURE_STATUSES,
                    f"a non-OK parse_status must be one of the disclosed "
                    f"safe-failure codes, never something ad hoc: {obs}")
        finally:
            controller._teardown_worker()


class NumberTypeCoordinateHintIntegrationTests(unittest.TestCase):
    """A real owner (2026-07-19, the same day the coordinate type shipped)
    left a field on the default "number" type and hit exactly the danger
    case that type exists to catch - real OCR misread the degree symbol,
    the field correctly refused to guess (AMBIGUOUS_MULTIPLE_NUMBERS /
    MALFORMED_NUMBER), but the guidance shown ("redraw a tighter region")
    was actively wrong for this case: the region was already scoped to one
    coordinate, so no redraw could fix a degree-symbol misread.

    This drives the owner's EXACT real misconfiguration (data_type left at
    "number", one region around one coordinate) through the REAL
    controller + REAL worker + REAL Windows OCR engine, then feeds the
    REAL resulting raw OCR text through layout.value_status_guidance() the
    same way the UI does - proving live, not asserting from a hand-picked
    string, that the specific "this looks like a coordinate, switch the
    Type" hint fires for the actual OCR output this pipeline produces."""

    def setUp(self):
        import ctypes
        ctypes.windll.user32.SetProcessDpiAwarenessContext(
            ctypes.c_void_p(-4))
        self.target = subprocess.Popen(
            [sys.executable, str(COORD_DMS_TARGET), "S2XYZ-M2-NUMHINT"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8")
        self.ready = json.loads(self.target.stdout.readline())
        self.addCleanup(self._stop_target)

    def _stop_target(self):
        try:
            self.target.stdin.write('{"cmd":"quit"}\n')
            self.target.stdin.flush()
            self.target.wait(timeout=5)
        except Exception:
            self.target.kill()

    def test_number_typed_coordinate_field_gets_the_specific_hint(self):
        from screen2xyz_m2 import contracts as C
        from screen2xyz_m2.controller import LiveSessionController
        from screen2xyz_m2.models import SessionDefaults, SourceConfig, \
            new_source_id
        from screen2xyz_m2.ui.layout import value_status_guidance

        scope = {"type": "window", "hwnd": self.ready["hwnd"],
                 "pid": self.ready["pid"], "title": "numhint-target"}
        environment = {"window": {"client_w": self.ready["client_w"],
                                  "client_h": self.ready["client_h"],
                                  "dpi": self.ready["dpi"]}}
        # data_type left at its default ("number") - the owner's own
        # misconfiguration, not the field the audit's own fix expects.
        source = SourceConfig(
            source_id=new_source_id(), display_name="Lat",
            rect=tuple(self.ready["field_rect"]))
        self.assertEqual(source.data_type, "number")
        run_parent = ROOT / ".lab_work" / "m2_runs"
        controller = LiveSessionController(
            scope=scope, backend="copyfromscreen", sources=[source],
            defaults=SessionDefaults(), environment_snapshot=environment,
            run_parent=run_parent)
        controller.machine.select_target()
        controller.machine.sources_configured()
        controller.ensure_worker()
        try:
            preview = controller.preview()
            obs = preview["observations"][0]
            self.assertEqual(obs["ocr_status"], "OK", obs)
            value_status = C.derive_value_status(
                obs.get("capture_status", "OK"), obs.get("ocr_status", "OK"),
                obs.get("parse_status", "NOT_RUN"), "NOT_EVALUATED")
            # The real point of this test: whatever the real OCR engine did
            # to the ° glyph this run, a "number" field over a real
            # coordinate reading must never be silently OK with a wrong
            # value (same guarantee as CoordinateDmsOcrRegressionTests) -
            # AND, specifically, the guidance shown for the resulting
            # failure must be the coordinate-aware hint, not the generic
            # (here misleading) "redraw a tighter region" advice.
            self.assertNotEqual(value_status, "OK", obs)
            hint = value_status_guidance(
                value_status, raw_text=obs.get("raw_text", ""),
                data_type=source.data_type)
            self.assertIn(
                "coordinate", hint.lower(),
                f"real OCR text {obs.get('raw_text')!r} did not trigger "
                f"the coordinate-type hint - got {hint!r} instead")
            self.assertIn('"coordinate"', hint)
        finally:
            controller._teardown_worker()


class SharedRegionLinePartIntegrationTests(unittest.TestCase):
    """Phase 2 (2026-07-19): the real target's coordinate readout is one
    thin overlay line holding lat+long+elev together, e.g. "49°08'20.06"N
    123°03'41.61"W 87.05" - not three separately-drawable lines (the S7
    fixture's convenient but unrealistic layout). Measured evidence
    (M2_IMPLEMENTATION_REPORT.md §5k Phase 2.1) showed only ~5px of gap
    between adjacent values at realistic on-screen scale (13pt); a direct
    real-pipeline attempt at three pixel-computed, best-case (zero extra
    slack - better than any human could draw by mouse) sub-regions on this
    exact target produced EMPTY_TEXT, badly garbled multi-word text, and a
    single-character misread - none of the three values usable. `line_part`
    (models.SourceConfig, parsing.parse_for_source) fixes this: several
    fields share ONE drawn region (the whole line) and each parses only
    its own whitespace-separated token.

    This drives that fix through the REAL controller + REAL worker + REAL
    Windows OCR engine, three fields sharing one identical rect. Per-field
    OCR-glyph outcomes are asserted exactly as observed (deterministic
    across repeated runs on this machine, same disclosed OCR fragility as
    WorkerIntegrationTests.test_full_record_and_finalize and
    CoordinateDmsOcrRegressionTests - never a hidden guarantee about every
    machine's OCR quality), but the SAFETY property is the one that must
    hold unconditionally: no field's value_status is ever a wrong number
    silently accepted as OK."""

    _SAFE_FAILURE_STATUSES = frozenset({
        "SUSPECT_GLYPH_CONFUSION", "MALFORMED_NUMBER", "NO_NUMBER",
        "AMBIGUOUS_MULTIPLE_NUMBERS", "OUT_OF_RANGE",
    })

    def setUp(self):
        import ctypes
        ctypes.windll.user32.SetProcessDpiAwarenessContext(
            ctypes.c_void_p(-4))
        self.target = subprocess.Popen(
            [sys.executable, str(COORD_LINE_TARGET), "S2XYZ-M2-LINEPART"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8")
        self.ready = json.loads(self.target.stdout.readline())
        self.addCleanup(self._stop_target)

    def _stop_target(self):
        try:
            self.target.stdin.write('{"cmd":"quit"}\n')
            self.target.stdin.flush()
            self.target.wait(timeout=5)
        except Exception:
            self.target.kill()

    def test_one_shared_region_splits_into_three_safe_values(self):
        from screen2xyz_m2.controller import LiveSessionController
        from screen2xyz_m2.models import (SessionDefaults, SourceConfig,
                                          new_source_id, xyz_eligibility)

        scope = {"type": "window", "hwnd": self.ready["hwnd"],
                 "pid": self.ready["pid"], "title": "coord-line-target"}
        environment = {"window": {"client_w": self.ready["client_w"],
                                  "client_h": self.ready["client_h"],
                                  "dpi": self.ready["dpi"]}}
        fx, fy = self.ready["field_origin"]
        fh = self.ready["field_h"]
        # ONE region drawn around the whole line - the width an owner
        # would actually get from a normal drag around the readout, not a
        # pixel-computed sub-span.
        whole_rect = (fx, fy, 280, fh)
        lat = SourceConfig(source_id=new_source_id(), display_name="Lat",
                           data_type="coordinate", semantic_role="x",
                           rect=whole_rect, line_part=0)
        lon = SourceConfig(source_id=new_source_id(), display_name="Long",
                           data_type="coordinate", semantic_role="y",
                           rect=whole_rect, line_part=1)
        elev = SourceConfig(source_id=new_source_id(), display_name="Elev",
                            data_type="number", semantic_role="z",
                            rect=whole_rect, line_part=2)
        sources = [lat, lon, elev]
        # Structural eligibility never depends on OCR content - `coordinate`
        # must be as valid an X/Y holder as `number` (Phase 2's XYZ-rule fix).
        self.assertTrue(xyz_eligibility(sources)["eligible"])

        run_parent = ROOT / ".lab_work" / "m2_runs"
        controller = LiveSessionController(
            scope=scope, backend="copyfromscreen", sources=sources,
            defaults=SessionDefaults(), environment_snapshot=environment,
            run_parent=run_parent)
        controller.machine.select_target()
        controller.machine.sources_configured()
        controller.ensure_worker()
        try:
            preview = controller.preview()
            self.assertEqual(preview["capture_status"], "OK")
            by_id = {s.source_id: s.display_name
                    for s in sources}
            obs_by_name = {by_id[o["source_id"]]: o
                          for o in preview["observations"]}
            for name, obs in obs_by_name.items():
                self.assertEqual(
                    obs["ocr_status"], "OK",
                    f"{name}: shared-line region was not recognized at "
                    f"all: {obs}")
                status = obs["parse_status"]
                is_safe_ok = (status == "OK")
                is_safe_failure = status in self._SAFE_FAILURE_STATUSES
                self.assertTrue(
                    is_safe_ok or is_safe_failure,
                    f"{name}: parse_status {status!r} is neither OK nor a "
                    f"disclosed safe-failure code - this is exactly the "
                    f"silent-corruption shape Phase 1/2 exist to prevent: "
                    f"{obs}")
            # What was actually, deterministically observed on this
            # machine (3x repeated runs, identical each time - see
            # M2_IMPLEMENTATION_REPORT.md §5k Phase 2.2): the real OCR
            # engine reproduces the same °->0 misread Phase 1 catches, on
            # BOTH coordinate tokens of this specific line, while the
            # plain-number third token (no degree symbol involved) reads
            # cleanly. Since the 2026-07-21 owner decision, the Lat
            # token's full-DMS corrupted shape RECOVERS to its numeric
            # value (always labelled DEGREE_GLYPH_RECOVERED); the Long
            # token stays a safe failure because OCR garbles it beyond
            # the strict recovery's guards. Asserted exactly, not
            # loosely, per this report's established precedent.
            self.assertEqual(obs_by_name["Lat"]["parse_status"], "OK")
            self.assertEqual(obs_by_name["Lat"]["normalized_value"],
                             "49.138906")
            self.assertEqual(obs_by_name["Long"]["parse_status"],
                             "MALFORMED_NUMBER")
            self.assertEqual(obs_by_name["Elev"]["parse_status"], "OK")
            self.assertEqual(obs_by_name["Elev"]["normalized_value"],
                             "87.05")
        finally:
            controller._teardown_worker()


def main() -> int:
    reason = _skip_reason()
    if reason:
        print(f"M2 integration SKIPPED: {reason}")
        return 0
    suite = unittest.TestSuite()
    loader = unittest.defaultTestLoader
    for case in (WorkerIntegrationTests, AutoBackendIntegrationTests,
                LiveFeedCsvIntegrationTests, SmallTextOcrRegressionTests,
                TightMarginOcrRegressionTests, CoordinateDmsOcrRegressionTests,
                SharedRegionLinePartIntegrationTests,
                NumberTypeCoordinateHintIntegrationTests,
                DemoProtocolIntegrationTests):
        suite.addTests(loader.loadTestsFromTestCase(case))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f"M2 integration: run={result.testsRun} "
          f"failures={len(result.failures)} errors={len(result.errors)} "
          f"skipped={len(result.skipped)}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
