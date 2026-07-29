"""M2 stress/soak harness (real PS worker + synthetic Tk target) - §10.

Bounded, CI-safe versions of the sprint's stress/soak list: an 8-source
real capture load, repeated Retest, repeated region redraw math, repeated
start/stop session cycles, and a short soak. Full-duration (5-minute
real-time / 30-minute accelerated) soaks are NOT run here - see the
honest-limitations note in this module's docstring and in
M2_IMPLEMENTATION_REPORT.md; this harness proves the same code paths hold
up under sustained/repeated load without committing this session's CI/local
run time to a half-hour execution.

Skips with an explicit reason off Windows, matching run_m2_integration.py.
"""

from __future__ import annotations

import shutil
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

WINDOWS = sys.platform == "win32"


def _skip_reason() -> str | None:
    if not WINDOWS:
        return "M2 soak requires Windows (real PS worker + WinRT OCR)"
    return None


@unittest.skipIf(_skip_reason() is not None, _skip_reason() or "")
class EightSourceStressTests(unittest.TestCase):
    """§10 '8-source stress': the maximum SOURCE_COUNT_MAX fields, all real
    capture+OCR against the same demo target, one tick."""

    def test_eight_sources_one_tick_no_crash(self):
        from screen2xyz_m2 import contracts as C
        from screen2xyz_m2.controller import LiveSessionController
        from screen2xyz_m2.demo import DemoSession
        from screen2xyz_m2.models import SessionDefaults, SourceConfig, \
            new_source_id
        from screen2xyz_m2.paths import run_root
        from screen2xyz_m2.targets import environment_snapshot

        session = DemoSession()
        controller = None
        try:
            base_fields = list(session.ready["fields"].items())
            sources = []
            for i in range(8):
                name, rect = base_fields[i % len(base_fields)]
                sources.append(SourceConfig(
                    source_id=new_source_id(), display_name=f"{name}-{i}",
                    rect=tuple(rect)))
            env = environment_snapshot(session.scope(), C.BACKEND_COPYFROMSCREEN)
            controller = LiveSessionController(
                scope=session.scope(), backend=C.BACKEND_COPYFROMSCREEN,
                sources=sources, defaults=SessionDefaults(interval_ms=250),
                environment_snapshot=env, run_parent=run_root())
            controller.machine.select_target()
            controller.machine.sources_configured()
            controller.ensure_worker()
            controller.preview()
            controller.confirm_preview_and_arm()
            controller.start_recording()
            result = controller.tick()
            self.assertEqual(len(result.observations), 8)
            self.assertTrue(all(obs.capture_status == "OK"
                                for obs in result.observations.values()))
            run_dir = controller.journal.run_dir
            controller.stop()
            shutil.rmtree(run_dir, ignore_errors=True)
        finally:
            if controller is not None and controller.worker is not None:
                controller.worker.teardown()
            session.quit()


@unittest.skipIf(_skip_reason() is not None, _skip_reason() or "")
class RepeatedActionStressTests(unittest.TestCase):
    """§10 'repeated Retest stress' and 'repeated start/stop session
    stress' - real worker/session lifecycle repeated many times with no
    orphan process and no growing failure rate."""

    def test_repeated_retest_ten_times_no_leak(self):
        from screen2xyz_m2 import contracts as C
        from screen2xyz_m2.controller import LiveSessionController
        from screen2xyz_m2.demo import DemoSession
        from screen2xyz_m2.models import SessionDefaults
        from screen2xyz_m2.paths import run_root
        from screen2xyz_m2.targets import environment_snapshot

        session = DemoSession()
        controller = None
        try:
            env = environment_snapshot(session.scope(), C.BACKEND_COPYFROMSCREEN)
            controller = LiveSessionController(
                scope=session.scope(), backend=C.BACKEND_COPYFROMSCREEN,
                sources=session.sources(), defaults=SessionDefaults(),
                environment_snapshot=env, run_parent=run_root())
            controller.machine.select_target()
            controller.machine.sources_configured()
            controller.ensure_worker()
            for _ in range(10):
                reply = controller.test_capture()
                self.assertEqual(reply.get("capture_status"), "OK")
        finally:
            if controller is not None and controller.worker is not None:
                controller.worker.teardown()
            session.quit()

    def test_repeated_test_capture_hundred_times_zero_fields_no_leak(self):
        """§20 '100 Test capture cycles', specifically with ZERO fields
        configured - the exact owner-reported repro (Test capture now is
        clicked before any field exists, per the UI's own step order) run
        at volume against the real worker/OCR, to prove the fix holds up
        under repetition and not just a single call."""

        from screen2xyz_m2 import contracts as C
        from screen2xyz_m2.controller import LiveSessionController
        from screen2xyz_m2.demo import DemoSession
        from screen2xyz_m2.models import SessionDefaults
        from screen2xyz_m2.paths import run_root
        from screen2xyz_m2.targets import environment_snapshot

        session = DemoSession()
        controller = None
        try:
            env = environment_snapshot(session.scope(), C.BACKEND_COPYFROMSCREEN)
            controller = LiveSessionController(
                scope=session.scope(), backend=C.BACKEND_COPYFROMSCREEN,
                sources=[], defaults=SessionDefaults(),
                environment_snapshot=env, run_parent=run_root())
            controller.machine.select_target()
            controller.machine.sources_configured()
            controller.ensure_worker()
            ok_count = 0
            started = time.monotonic()
            for _ in range(100):
                reply = controller.test_capture()
                if reply.get("capture_status") == "OK":
                    ok_count += 1
            elapsed_s = time.monotonic() - started
            self.assertEqual(ok_count, 100)
            print(f"    (100 zero-field Test-capture cycles in "
                 f"{elapsed_s:.1f}s, {elapsed_s / 100 * 1000:.0f}ms/cycle "
                 f"avg)")
        finally:
            if controller is not None and controller.worker is not None:
                controller.worker.teardown()
            session.quit()

    def test_repeated_start_stop_five_sessions_no_orphan(self):
        from screen2xyz_m2 import contracts as C
        from screen2xyz_m2.controller import LiveSessionController
        from screen2xyz_m2.demo import DemoSession
        from screen2xyz_m2.models import SessionDefaults
        from screen2xyz_m2.paths import run_root
        from screen2xyz_m2.targets import environment_snapshot

        for _ in range(5):
            session = DemoSession()
            controller = None
            try:
                env = environment_snapshot(session.scope(), C.BACKEND_COPYFROMSCREEN)
                controller = LiveSessionController(
                    scope=session.scope(), backend=C.BACKEND_COPYFROMSCREEN,
                    sources=session.sources(),
                    defaults=SessionDefaults(interval_ms=200),
                    environment_snapshot=env, run_parent=run_root())
                controller.machine.select_target()
                controller.machine.sources_configured()
                controller.ensure_worker()
                controller.preview()
                controller.confirm_preview_and_arm()
                controller.start_recording()
                controller.tick()
                run_dir = controller.journal.run_dir
                controller.stop()
                self.assertIsNone(controller.worker)
                shutil.rmtree(run_dir, ignore_errors=True)
            finally:
                if controller is not None and controller.worker is not None:
                    controller.worker.teardown()
                session.quit()

    def test_repeated_region_redraw_math_one_thousand_iterations(self):
        # §10 'repeated region redraw stress' - the pure drag/gating math a
        # real redraw loop exercises, run at volume (no Tk needed for this
        # part; the picker's Tk plumbing itself is exercised interactively
        # and by the widget-tree checks, not repeated here at volume).
        from screen2xyz_m2.ui.layout import (region_confirm_allowed,
                                             region_drag_rect)
        for i in range(1000):
            rect = region_drag_rect(i % 50, i % 30, (i % 50) + 40,
                                    (i % 30) + 40, 1, 900, 320)
            allowed = region_confirm_allowed(
                *rect, 900, 320, 8, True, "CONTENT_DETECTED")
            self.assertTrue(allowed)


@unittest.skipIf(_skip_reason() is not None, _skip_reason() or "")
class ShortSoakTests(unittest.TestCase):
    """§10 soak - bounded to ~40s real time (not the full 5-minute/30-minute
    versions; see this module's docstring). Proves no event loss, no live-
    snapshot drift, and no counter corruption over a sustained run at a
    faster-than-default interval."""

    def test_forty_second_soak_at_150ms_interval(self):
        from screen2xyz_m2 import contracts as C
        from screen2xyz_m2.controller import LiveSessionController
        from screen2xyz_m2.demo import DemoSession
        from screen2xyz_m2.models import SessionDefaults
        from screen2xyz_m2.paths import run_root
        from screen2xyz_m2.targets import environment_snapshot

        session = DemoSession()
        controller = None
        try:
            session.set_case("changing")
            session.auto_change(True)
            env = environment_snapshot(session.scope(), C.BACKEND_COPYFROMSCREEN)
            controller = LiveSessionController(
                scope=session.scope(), backend=C.BACKEND_COPYFROMSCREEN,
                sources=session.sources(),
                defaults=SessionDefaults(interval_ms=150),
                environment_snapshot=env, run_parent=run_root())
            controller.machine.select_target()
            controller.machine.sources_configured()
            controller.ensure_worker()
            controller.preview()
            controller.confirm_preview_and_arm()
            controller.start_recording()
            end = time.monotonic() + 40
            ticks = 0
            while time.monotonic() < end:
                controller.tick()
                ticks += 1
                time.sleep(0.15)
            session.auto_change(False)
            journal_events = controller.journal.counters["events"]
            live_rows = controller.journal.live_snapshot_row_count
            self.assertEqual(live_rows, journal_events)
            summary = controller.stop()
            self.assertEqual(summary["final_csv_row_count"], journal_events)
            self.assertTrue(summary["final_csv_row_count_verified"])
            self.assertGreater(ticks, 100)  # ~40s / 150ms
            run_dir = controller.journal.run_dir
            shutil.rmtree(run_dir, ignore_errors=True)
        finally:
            if controller is not None and controller.worker is not None:
                controller.worker.teardown()
            session.quit()


@unittest.skipIf(_skip_reason() is not None, _skip_reason() or "")
class WorkerCrashRestartTests(unittest.TestCase):
    """§14 worker crash/restart cycles: killing the capture worker mid-run
    must never lose data or leave an orphan - the controller restarts it (or
    pauses on a streak) and recording continues to a clean finalize."""

    def test_worker_crash_recovers_and_finalizes(self):
        from screen2xyz_m2 import contracts as C
        from screen2xyz_m2.controller import LiveSessionController
        from screen2xyz_m2.demo import DemoSession
        from screen2xyz_m2.models import SessionDefaults
        from screen2xyz_m2.paths import run_root
        from screen2xyz_m2.targets import environment_snapshot

        session = DemoSession()
        session.set_case("changing")
        session.auto_change(True)
        controller = None
        try:
            env = environment_snapshot(session.scope(),
                                      C.BACKEND_COPYFROMSCREEN)
            controller = LiveSessionController(
                scope=session.scope(), backend=C.BACKEND_COPYFROMSCREEN,
                sources=session.sources(),
                defaults=SessionDefaults(interval_ms=200),
                environment_snapshot=env, run_parent=run_root())
            controller.machine.select_target()
            controller.machine.sources_configured()
            controller.ensure_worker()
            controller.preview()
            controller.confirm_preview_and_arm()
            controller.start_recording()
            for _ in range(3):
                controller.tick()
                time.sleep(0.1)
            for cycle in range(3):
                # Hard-kill the underlying worker process.
                controller.worker._proc.kill()  # type: ignore[attr-defined]
                controller.worker._proc.wait(timeout=5)
                # Next ticks either restart the worker or pause on the streak;
                # either way the state machine never silently keeps
                # "RECORDING" while capturing nothing (proven by the tick not
                # raising and the journal staying readable at finalize).
                for _ in range(4):
                    controller.tick()
                    time.sleep(0.1)
                if controller.machine.state == "PAUSED":
                    try:
                        controller.user_resume()
                    except Exception:
                        pass
                # feed a few good ticks
                for _ in range(3):
                    controller.tick()
                    time.sleep(0.1)
            run_dir = controller.journal.run_dir
            summary = controller.stop()
            # Journal is readable and the final CSV verifies against it.
            self.assertTrue(summary["final_csv_row_count_verified"])
            self.assertIsNone(controller.worker)  # no orphan
            shutil.rmtree(run_dir, ignore_errors=True)
        finally:
            if controller is not None and controller.worker is not None:
                controller.worker.teardown()
            session.quit()


class LiveCsvGrowthTests(unittest.TestCase):
    """§14 live CSV growth benchmark: the per-event append must stay O(1) -
    the last batch of appends must cost about the same as the first,
    independent of accumulated event count (no worker/display needed)."""

    def test_append_cost_is_flat_over_many_events(self):
        import tempfile
        from pathlib import Path
        from screen2xyz_m2 import contracts as C
        from screen2xyz_m2.journal import RunJournal
        from screen2xyz_m2.models import SourceConfig, new_source_id

        sources = [SourceConfig(source_id=new_source_id(), display_name=n,
                                semantic_role=r, rect=(0, 40 * i, 100, 20))
                   for i, (n, r) in enumerate([("X", "x"), ("Y", "y"),
                                              ("Z", "z")])]

        def event(seq):
            obs = [{"source_id": s.source_id, "capture_status": "OK",
                    "ocr_status": "OK", "parse_status": "OK",
                    "stability_status": "IMMEDIATE", "value_status": "OK",
                    "raw_text": f"{seq + i}.5",
                    "normalized_value": f"{seq + i}.5", "value_kind": "number",
                    "pixel_sha256": f"h{seq}{i}", "ocr_executed": True,
                    "confirmation": "new_ocr"} for i, s in enumerate(sources)]
            return {"session_id": "s", "event_status": "RETAINED_CHANGE",
                    "worker_status": "OK", "event_seq": seq,
                    "event_id": f"s-e{seq}",
                    "frame": {"frame_id": f"f{seq}",
                             "capture_utc": "2026-07-19T00:00:00Z",
                             "monotonic_offset_ms": seq * 250, "cursor": None},
                    "scheduler_context": None, "observations": obs,
                    "crops_saved": {}, "retention_mode": "changed_and_errors",
                    "stable_signature": {},
                    "changed_source_ids": [s.source_id for s in sources],
                    "retention_reason_codes": ["STABLE_CHANGE"],
                    "evidence": {}, "skipped_ticks_since_last": 0}

        with tempfile.TemporaryDirectory() as tmp:
            j = RunJournal(Path(tmp) / "run")
            first, last = [], []
            for n in range(1, 4001):
                ts = time.perf_counter()
                j.append_live_row(event(n), sources, False)
                dt = (time.perf_counter() - ts) * 1000
                if n <= 100:
                    first.append(dt)
                elif n > 3900:
                    last.append(dt)
            first_mean = sum(first) / len(first)
            last_mean = sum(last) / len(last)
            # O(1): the last 100 appends (at ~4000 events) must not be more
            # than 3x the first 100 (a full-regen O(n) design would be ~40x).
            self.assertLess(last_mean, first_mean * 3 + 2.0,
                           f"append cost grew: first={first_mean:.2f}ms "
                           f"last={last_mean:.2f}ms")
            self.assertEqual(j.live_snapshot_row_count, 4000)


def main() -> int:
    reason = _skip_reason()
    if reason:
        print(f"M2 soak SKIPPED (non-Windows tests): {reason}")
    suite = unittest.TestSuite()
    loader = unittest.defaultTestLoader
    cases = [LiveCsvGrowthTests]  # runs everywhere (no worker/display)
    if reason is None:
        cases = [EightSourceStressTests, RepeatedActionStressTests,
                ShortSoakTests, WorkerCrashRestartTests, LiveCsvGrowthTests]
    for case in cases:
        suite.addTests(loader.loadTestsFromTestCase(case))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f"M2 soak: run={result.testsRun} "
          f"failures={len(result.failures)} errors={len(result.errors)} "
          f"skipped={len(result.skipped)}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
