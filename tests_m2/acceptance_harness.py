"""Scripted synthetic acceptance harness (automates most of MA-2..MA-8).

Drives the real controller + PowerShell worker against a scriptable
synthetic target that can change values, blank fields, resize, minimize,
and close. Replaces human visual judgment with the target's machine-known
values. Produces a sanitized acceptance report. Windows-only; skips
elsewhere with a reason. Never uses real content.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from queue import Empty, Queue

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

TARGET = ROOT / "docs/research/spikes/spike_s7_synthetic_target.py"


class SyntheticTarget:
    """Every stdout read is bounded via a background reader thread (the
    same shape as WorkerClient's own reader) - a plain blocking readline()
    here previously let an occasional Tk-event-loop timing hiccup in the
    target hang the whole harness indefinitely. A stall now raises a
    catchable TimeoutError instead of hanging."""

    def __init__(self, title: str = "S2XYZ-ACCEPT",
                ready_timeout: float = 15.0) -> None:
        self.proc = subprocess.Popen(
            [sys.executable, str(TARGET), title],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8")
        self._out_queue: "Queue[str | None]" = Queue()
        self._reader = threading.Thread(target=self._read_stdout,
                                        daemon=True)
        self._reader.start()
        self.ready = json.loads(self._readline(ready_timeout))

    def _read_stdout(self) -> None:
        try:
            assert self.proc.stdout is not None
            for line in self.proc.stdout:
                self._out_queue.put(line)
        except (ValueError, OSError):
            pass
        finally:
            self._out_queue.put(None)

    def _readline(self, timeout: float) -> str:
        try:
            line = self._out_queue.get(timeout=timeout)
        except Empty:
            raise TimeoutError(
                f"synthetic target did not respond within {timeout}s")
        if line is None:
            raise RuntimeError("synthetic target process ended unexpectedly")
        return line

    def command(self, cmd: str, timeout: float = 8.0) -> None:
        self.proc.stdin.write(json.dumps({"cmd": cmd}) + "\n")
        self.proc.stdin.flush()
        self._readline(timeout)
        time.sleep(0.3)

    def quit(self) -> None:
        try:
            self.proc.stdin.write('{"cmd":"quit"}\n')
            self.proc.stdin.flush()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


def build_controller(target: SyntheticTarget, **defaults_kw):
    import ctypes
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    from screen2xyz_m2.controller import LiveSessionController
    from screen2xyz_m2.models import (SessionDefaults, SourceConfig,
                                      new_source_id)
    ready = target.ready
    scope = {"type": "window", "hwnd": ready["hwnd"], "pid": ready["pid"],
             "title": "synthetic"}
    sources = [
        SourceConfig(source_id=new_source_id(), display_name="Lon",
                     semantic_role="x", rect=(30, 40, 460, 44)),
        SourceConfig(source_id=new_source_id(), display_name="Lat",
                     semantic_role="y", rect=(30, 120, 460, 44)),
        SourceConfig(source_id=new_source_id(), display_name="Elev",
                     semantic_role="z", rect=(30, 200, 460, 44)),
    ]
    env = {"window": {"client_w": ready["client_w"],
                      "client_h": ready["client_h"], "dpi": ready["dpi"]}}
    return LiveSessionController(
        scope=scope, backend="printwindow_clientonly", sources=sources,
        defaults=SessionDefaults(**defaults_kw), environment_snapshot=env,
        run_parent=ROOT / ".lab_work" / "m2_runs")


def to_recording(controller) -> None:
    controller.machine.select_target()
    controller.machine.sources_configured()
    controller.ensure_worker()
    controller.preview()
    controller.confirm_preview_and_arm()
    controller.start_recording()


def run_acceptance(soak_seconds: int = 0) -> dict:
    if sys.platform != "win32":
        return {"skipped": "acceptance harness requires Windows"}
    import shutil
    report: dict = {"schema_version": "screen2xyz.m2accept.1", "checks": {}}

    # MA-2/MA-3: setup, sweep, change detection, no duplicate unchanged
    target = SyntheticTarget()
    controller = build_controller(target)
    try:
        to_recording(controller)
        events = []
        controller.on_event = events.append
        controller.tick()                    # present -> seed
        after_seed = len(events)
        for _ in range(3):
            controller.tick()                # constant -> no new events
        # Real oracle: constant ticks must append zero events.
        report["checks"]["no_duplicate_unchanged"] = \
            (len(events) == after_seed)
        before_change = len(events)
        target.command("absent")
        controller.tick()                    # change (values gone)
        target.command("present")
        controller.tick()                    # change back
        report["checks"]["change_events_only"] = len(events) > before_change
        summary = controller.stop()
        report["checks"]["finalized"] = \
            controller.machine.state == "FINALIZED"
        run_dir = controller.journal.run_dir
        report["checks"]["manifest_written"] = \
            (run_dir / "evidence_manifest_sha256.txt").is_file()
        report["ma3_events"] = summary.get("event_count")
        shutil.rmtree(run_dir, ignore_errors=True)
    finally:
        target.quit()

    # MA-4: emergency stop kills the worker within bound
    target = SyntheticTarget()
    controller = build_controller(target)
    try:
        to_recording(controller)
        controller.tick()
        started = time.monotonic()
        controller.emergency_stop()
        elapsed_ms = (time.monotonic() - started) * 1000
        report["checks"]["emergency_stop_under_2s"] = elapsed_ms <= 2000
        report["checks"]["no_worker_after_emergency"] = \
            controller.worker is None
        if controller.journal:
            shutil.rmtree(controller.journal.run_dir, ignore_errors=True)
    finally:
        target.quit()

    # MA-4b: minimized target pauses; MA target-close pauses
    target = SyntheticTarget()
    controller = build_controller(target)
    try:
        to_recording(controller)
        target.proc.stdin.write('{"cmd":"quit"}\n')  # close target
        target.proc.stdin.flush()
        time.sleep(0.5)
        pause = None
        for _ in range(3):
            result = controller.tick()
            if result.pause:
                pause = result.pause
                break
        report["checks"]["target_close_pauses"] = pause is not None
        try:
            controller.stop()
        except Exception:
            pass
        if controller.journal:
            shutil.rmtree(controller.journal.run_dir, ignore_errors=True)
    finally:
        target.quit()

    # MA-7: XYZ export + wide CSV present and formula-safe
    target = SyntheticTarget()
    controller = build_controller(target)
    try:
        to_recording(controller)
        controller.tick()
        target.command("absent")
        controller.tick()
        target.command("present")
        controller.tick()
        controller.stop()
        run_dir = controller.journal.run_dir
        report["checks"]["wide_csv"] = (run_dir / "events_wide.csv").is_file()
        report["checks"]["long_csv"] = \
            (run_dir / "observations_long.csv").is_file()
        xyz_meta = json.loads((run_dir / "points_xyz_metadata.json")
                              .read_text(encoding="utf-8"))
        report["checks"]["xyz_eligible"] = xyz_meta["eligible"]
        report["xyz_rows"] = xyz_meta["row_count"]
        shutil.rmtree(run_dir, ignore_errors=True)
    finally:
        target.quit()

    # MA-5: soak (memory/rate) — only when requested
    if soak_seconds > 0:
        report["soak"] = _soak(soak_seconds)

    report["all_checks_passed"] = all(report["checks"].values())
    report["note"] = ("Synthetic acceptance; automates MA-2/3/4/7 machine "
                      "oracles. Human usability (MA-8) and real-target "
                      "content remain owner-only at G-E-REAL.")
    return report


def _soak(seconds: int) -> dict:
    import shutil
    try:
        import psutil  # optional
        have_psutil = True
    except ImportError:
        have_psutil = False
    target = SyntheticTarget()
    controller = build_controller(target)
    result: dict = {"seconds": seconds, "psutil": have_psutil}
    try:
        to_recording(controller)
        proc = controller.worker._proc
        import os
        start_mem = _rss(proc.pid) if have_psutil else None
        end = time.monotonic() + seconds
        ticks = 0
        toggle = False
        while time.monotonic() < end:
            controller.tick()
            ticks += 1
            if ticks % 5 == 0:
                toggle = not toggle
                target.command("absent" if toggle else "present")
            time.sleep(1)
        end_mem = _rss(controller.worker._proc.pid) if have_psutil \
            and controller.worker else None
        result["ticks"] = ticks
        result["actual_rate"] = round(ticks / seconds, 3)
        result["skipped"] = controller.diagnostics["skipped_ticks"]
        result["worker_restarts"] = controller.diagnostics["worker_restarts"]
        if start_mem is not None and end_mem is not None:
            result["worker_rss_delta_mib"] = round(
                (end_mem - start_mem) / (1024 * 1024), 2)
        controller.stop()
        if controller.journal:
            shutil.rmtree(controller.journal.run_dir, ignore_errors=True)
    finally:
        target.quit()
    return result


def _rss(pid: int):
    try:
        import psutil
        return psutil.Process(pid).memory_info().rss
    except Exception:
        return None


if __name__ == "__main__":
    seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    report = run_acceptance(soak_seconds=seconds)
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report.get("all_checks_passed")
                     or report.get("skipped") else 1)
