"""Machine-readable scenario runner (overnight QA sprint sections 15-16):
drives the REAL LiveSessionController, REAL PowerShell capture worker, REAL
Windows OCR, and REAL journal/export path against real fixture windows (a
local Tk image viewer, real Microsoft Excel, or the built-in synthetic demo
target). This is never a fake/stand-in application - if a scenario fails,
the production controller/worker/journal failed, not a mock standing in for
it."""

from __future__ import annotations

import ctypes
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from screen2xyz_m2.controller import LiveSessionController
from screen2xyz_m2.models import SessionDefaults, SourceConfig, new_source_id
from screen2xyz_m2.targets import environment_snapshot, list_windows
from screen2xyz_m2.worker import WorkerError

REPO_ROOT = Path(__file__).resolve().parents[2]
IMAGE_VIEWER = REPO_ROOT / "tests_m2" / "fixtures" / "image_viewer.py"


class FixtureWindow:
    def __init__(self, proc, hwnd: int, pid: int, client_w: int = 0,
                client_h: int = 0):
        self.proc = proc
        self.hwnd = hwnd
        self.pid = pid
        self.client_w = client_w
        self.client_h = client_h

    def close(self) -> None:
        if self.proc is None:
            close_window_wm_close(self.hwnd)
            return
        try:
            if self.proc.stdin:
                self.proc.stdin.write("quit\n")
                self.proc.stdin.flush()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


def close_window_wm_close(hwnd: int) -> None:
    """Best-effort close via WM_CLOSE - never leaves the owner's real Excel
    open on a synthetic file after a scenario finishes."""
    WM_CLOSE = 0x0010
    ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)


def open_image_fixture(image_path: Path, *, ready_timeout: float = 10.0
                       ) -> FixtureWindow:
    """Every subprocess wait in this module is bounded (§3: no UI operation
    may hang the runner forever) via a background reader thread + a Queue
    with an explicit timeout, mirroring the same pattern the production
    DemoSession/WorkerClient stdout readers already use."""

    import threading
    from queue import Empty, Queue

    proc = subprocess.Popen(
        [sys.executable, str(IMAGE_VIEWER), str(image_path)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8")
    out_queue: "Queue[str | None]" = Queue()

    def read_one_line() -> None:
        out_queue.put(proc.stdout.readline())

    threading.Thread(target=read_one_line, daemon=True).start()
    try:
        raw = out_queue.get(timeout=ready_timeout)
    except Empty:
        proc.kill()
        raise TimeoutError(
            f"image fixture viewer did not report ready within "
            f"{ready_timeout}s for {image_path}")
    if not raw:
        proc.kill()
        raise RuntimeError(
            f"image fixture viewer exited before reporting ready: "
            f"{image_path}")
    ready = json.loads(raw)
    return FixtureWindow(proc, ready["hwnd"], ready["pid"],
                        ready["client_w"], ready["client_h"])


_EXCEL_CANDIDATE_PATHS = (
    r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
    r"C:\Program Files (x86)\Microsoft Office\root\Office16\EXCEL.EXE",
)


def _find_excel_exe() -> str | None:
    for candidate in _EXCEL_CANDIDATE_PATHS:
        if Path(candidate).is_file():
            return candidate
    return None


def open_excel_fixture(xlsx_path: Path, timeout: float = 25.0
                       ) -> FixtureWindow | None:
    """Launches the real installed Excel on a generated workbook and finds
    its window via the SAME production list_windows() the app itself uses
    for target selection. Returns None (never raises) if no matching
    window appears within `timeout` - e.g. Excel is not installed - so the
    caller can record this honestly instead of silently skipping.

    Independent audit MAJOR: the previous version had no way to correlate
    the grabbed window back to the process this call actually launched -
    it matched the FIRST window anywhere on the desktop whose title
    contained the file stem, with no PID check, so a stale leftover
    window from an earlier run (whose close() is only best-effort
    WM_CLOSE) could be silently grabbed instead of the fresh instance.
    Launching EXCEL.EXE directly (not via os.startfile/shell) yields a
    real PID to match against list_windows()'s own .pid field."""

    excel_exe = _find_excel_exe()
    excel_pid: int | None = None
    if excel_exe is not None:
        proc = subprocess.Popen([excel_exe, str(xlsx_path)])
        excel_pid = proc.pid
    else:
        # Excel not found at a known path - fall back to the shell
        # association (still no string interpolation into a command
        # line: os.startfile takes the path as a single argument, not a
        # script to parse) but without a PID to correlate against.
        import os
        os.startfile(str(xlsx_path))  # noqa: S606 - Windows-only, no shell

    stem = xlsx_path.stem
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        matches = [w for w in list_windows() if stem in w.title]
        if excel_pid is not None:
            by_pid = [w for w in matches if w.pid == excel_pid]
            if by_pid:
                return FixtureWindow(None, by_pid[0].hwnd, by_pid[0].pid)
        elif matches:
            return FixtureWindow(None, matches[0].hwnd, matches[0].pid)
        time.sleep(0.5)
    return None


def run_field_scenario(*, scope: dict[str, Any],
                       regions: list[tuple[int, int, int, int]],
                       data_type: str = "number", ticks: int = 2,
                       run_parent: Path, interval_ms: int = 200,
                       backend: str = "auto") -> dict[str, Any]:
    """Drives ONE production LiveSessionController through the complete
    chain: select target -> test capture -> configure N field(s) at the
    given regions -> preview -> confirm+arm -> start -> tick N times ->
    stop -> finalize. Uses the REAL PowerShell capture worker and REAL
    Windows OCR - not a fake harness."""

    sources = [
        SourceConfig(source_id=new_source_id(), display_name=f"F{i + 1}",
                    semantic_role="none", data_type=data_type,
                    rect=tuple(r))
        for i, r in enumerate(regions)]
    env = environment_snapshot(scope, backend)
    controller = LiveSessionController(
        scope=scope, backend=backend, sources=sources,
        defaults=SessionDefaults(interval_ms=interval_ms),
        environment_snapshot=env, run_parent=run_parent)
    result: dict[str, Any] = {"ok": False, "stage": "start",
                              "field_count": len(regions)}
    try:
        controller.machine.select_target()
        controller.machine.sources_configured()
        controller.ensure_worker()
        result["stage"] = "test_capture"
        test_reply = controller.test_capture()
        result["test_capture_status"] = test_reply.get("capture_status")
        result["effective_backend"] = controller.effective_backend
        result["stage"] = "preview"
        preview_reply = controller.preview()
        result["preview_observations"] = preview_reply.get("observations")
        result["stage"] = "arm"
        controller.confirm_preview_and_arm()
        result["stage"] = "start_recording"
        controller.start_recording()
        result["stage"] = "tick"
        tick_results = []
        for _ in range(ticks):
            tr = controller.tick()
            tick_results.append({
                "capture_status": (tr.frame or {}).get("capture_status"),
                "observations": {sid: obs.to_json()
                                for sid, obs in tr.observations.items()}})
            time.sleep(interval_ms / 1000.0)
        result["ticks"] = tick_results
        result["stage"] = "stop"
        result["summary"] = controller.stop()
        result["ok"] = True
    except WorkerError as exc:
        result["error"] = f"{exc.worker_status}: {exc.detail}"
    finally:
        if controller.worker is not None:
            controller.worker.teardown(deadline_s=2.0)
    return result
