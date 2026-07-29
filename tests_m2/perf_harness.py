"""Performance harness: 3-source and 8-source tick-duration distributions.

Windows-only (real worker). Reports measured tick timings against the
research §7 budget without inventing numbers. Skips elsewhere.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _measure(source_count: int, ticks: int) -> dict:
    import ctypes
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    import shutil
    import subprocess
    from screen2xyz_m2.controller import LiveSessionController
    from screen2xyz_m2.models import (SessionDefaults, SourceConfig,
                                      new_source_id)
    target = subprocess.Popen(
        [sys.executable,
         str(ROOT / "docs/research/spikes/spike_s7_synthetic_target.py"),
         "S2XYZ-PERF"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8")
    ready = json.loads(target.stdout.readline())
    client_h = ready["client_h"]
    band = max(20, client_h // (source_count + 1))
    sources = [SourceConfig(source_id=new_source_id(),
                            display_name=f"S{i}",
                            rect=(10, 4 + i * band, 460, min(band - 6, 44)))
               for i in range(source_count)]
    controller = LiveSessionController(
        scope={"type": "window", "hwnd": ready["hwnd"], "pid": ready["pid"],
               "title": "perf"},
        backend="printwindow_clientonly", sources=sources,
        defaults=SessionDefaults(interval_ms=250),
        environment_snapshot={"window": {"client_w": ready["client_w"],
                                         "client_h": client_h,
                                         "dpi": ready["dpi"]}},
        run_parent=ROOT / ".lab_work" / "m2_runs")
    try:
        controller.machine.select_target()
        controller.machine.sources_configured()
        controller.ensure_worker()
        controller.preview()
        controller.confirm_preview_and_arm()
        controller.start_recording()
        durations = []
        for _ in range(ticks):
            started = time.monotonic()
            controller.tick()
            durations.append((time.monotonic() - started) * 1000)
        controller.stop()
        if controller.journal:
            shutil.rmtree(controller.journal.run_dir, ignore_errors=True)
    finally:
        target.stdin.write('{"cmd":"quit"}\n')
        target.stdin.flush()
        try:
            target.wait(timeout=5)
        except Exception:
            target.kill()
    ordered = sorted(durations)
    return {"sources": source_count, "ticks": ticks,
            "mean_ms": round(statistics.mean(durations), 1),
            "p50_ms": round(ordered[len(ordered) // 2], 1),
            "p95_ms": round(ordered[int(len(ordered) * 0.95) - 1], 1),
            "max_ms": round(max(durations), 1)}


def main() -> int:
    if sys.platform != "win32":
        print(json.dumps({"skipped": "perf harness requires Windows"}))
        return 0
    report = {"budget_note": "research §7 target: typical tick <= 200 ms",
              "runs": [_measure(3, 40), _measure(8, 40)]}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
