"""Automated synthetic S7 gate (G-E-SYNTHETIC, OD-M2-9) — disposable tool.

Runs the three S7 trials (present / absent / occluded) against the
deterministic synthetic target for both MVP backends without any human
input, replacing the visual judgment with machine-readable oracles:

- capture-API success and helper payload validation;
- exact client geometry and stable cross-backend origin;
- window DPI equality with the target's self-reported DPI;
- magenta marker-pixel signature (content proof) in every capture;
- field-area pixel state (white when absent; orange occluder under
  copyfromscreen when occluded);
- expected OCR text present/absent per trial (baseline OCR adapter);
- target identity intact before/after (helper-enforced PID revalidation);
- cleanup (target exits; temp previews removed).

Emits one `S7SYN_RESULT` JSON line per trial+backend, writes a full report
to `.lab_work/m2_research/s7_synthetic_report.json`, prints the provisional
backend chosen by the recorded OD-M2-2 rule, and exits non-zero on any
mismatch. Synthetic evidence only: this passes G-E-SYNTHETIC and never
G-E-REAL.
"""

from __future__ import annotations

import ctypes
import json
import shutil
import subprocess
import sys
import time
import tkinter as tk
import uuid
from pathlib import Path

ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
HELPER = HERE / "spike_s3_capture.ps1"
OCR = ROOT / "legacy/src/screen2xyz_lab/adapters/ocr_windows.ps1"
REPORT_DIR = ROOT / ".lab_work" / "m2_research"
BACKENDS = ("printwindow_clientonly", "copyfromscreen")
TRIALS = ("present", "absent", "occluded")


def pixel(image: tk.PhotoImage, x: int, y: int) -> tuple[int, int, int]:
    value = image.get(x, y)
    if isinstance(value, str):
        parts = [int(part) for part in value.split()]
        return parts[0], parts[1], parts[2]
    return int(value[0]), int(value[1]), int(value[2])


def is_magenta(rgb: tuple[int, int, int]) -> bool:
    return rgb[0] > 200 and rgb[1] < 90 and rgb[2] > 200


def is_orange(rgb: tuple[int, int, int]) -> bool:
    return rgb[0] > 200 and 90 < rgb[1] < 200 and rgb[2] < 90


def is_whiteish(rgb: tuple[int, int, int]) -> bool:
    return rgb[0] > 230 and rgb[1] > 230 and rgb[2] > 230


def ocr_text(png: Path) -> str:
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(OCR),
         "-ImagePath", str(png)],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        return "<OCR_FAILED>"
    return json.loads(proc.stdout.strip()).get("raw_text", "")


def capture(hwnd: int, pid: int, backend: str, out: Path) -> dict:
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(HELPER),
         "-Hwnd", str(hwnd), "-ExpectedPid", str(pid), "-Mode", backend,
         "-OutPath", str(out)],
        capture_output=True, text=True, timeout=90,
    )
    if proc.returncode != 0:
        return {"api_success": False, "exit": proc.returncode,
                "detail": proc.stderr.strip()[:200]}
    payload = json.loads(proc.stdout.strip())
    payload["api_success"] = True
    payload["exit"] = 0
    return payload


def main() -> int:
    token = f"S2XYZ-SYNGATE-{uuid.uuid4().hex[:8]}"
    target = subprocess.Popen(
        [sys.executable, str(HERE / "spike_s7_synthetic_target.py"), token],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8",
    )
    failures: list[str] = []
    results: list[dict] = []
    viewer = tk.Tk()
    viewer.withdraw()
    try:
        ready_line = target.stdout.readline()
        ready = json.loads(ready_line)
        if not ready.get("ready"):
            raise RuntimeError("synthetic target did not report ready")
        hwnd, pid = ready["hwnd"], ready["pid"]
        marker_x, marker_y = ready["marker_center"]
        field_x, field_y = ready["field_center"]
        values = ready["values"]

        def command(name: str) -> None:
            target.stdin.write(json.dumps({"cmd": name}) + "\n")
            target.stdin.flush()
            ack = json.loads(target.stdout.readline())
            if ack.get("ok") != name:
                raise RuntimeError(f"target did not acknowledge {name}")
            time.sleep(0.4)

        # WinRT StorageFile access is brokered in some sandboxes and cannot
        # open %TEMP% paths; the capture helper additionally allowlists only
        # the OS temp root and the ignored S7 preview root, so gate scratch
        # lives under the preview root inside the repo tree.
        temp_dir = (REPORT_DIR / "s7_preview" / f"s7syn_{token[-8:]}").resolve()
        temp_dir.mkdir(parents=True, exist_ok=False)
        try:
            for trial in TRIALS:
                if trial == "present":
                    command("clear_occlude")
                    command("present")
                elif trial == "absent":
                    command("clear_occlude")
                    command("absent")
                else:
                    command("present")
                    command("occlude")
                origins: list[tuple[int, int]] = []
                for backend in BACKENDS:
                    out = temp_dir / f"{trial}_{backend}.png"
                    payload = capture(hwnd, pid, backend, out)
                    checks: dict[str, bool] = {}
                    entry = {"trial": trial, "backend": backend, **{
                        key: payload.get(key) for key in (
                            "api_success", "exit", "w", "h", "origin_x", "origin_y",
                            "window_dpi", "capture_ms", "mean_luma", "luma_range",
                            "frame_content_status", "png_bytes", "detail",
                        ) if key in payload}}
                    if not payload.get("api_success"):
                        checks["api_success"] = False
                    else:
                        checks["api_success"] = True
                        checks["geometry"] = (
                            payload["w"] == ready["client_w"]
                            and payload["h"] == ready["client_h"])
                        checks["dpi"] = payload["window_dpi"] == ready["dpi"]
                        checks["png_nonempty"] = (
                            payload["png_bytes"] > 0
                            and out.is_file()
                            and out.stat().st_size == payload["png_bytes"])
                        origins.append((payload["origin_x"], payload["origin_y"]))
                        image = tk.PhotoImage(master=viewer, file=str(out))
                        marker_rgb = pixel(image, marker_x, marker_y)
                        field_rgb = pixel(image, field_x, field_y)
                        checks["marker_signature"] = is_magenta(marker_rgb)
                        text = ocr_text(out)
                        # OCR may tokenize "-123 . 654321"; compare space-free.
                        flat = text.replace(" ", "")
                        has_values = all(value in flat for value in values)
                        has_none = not any(value in flat for value in values)
                        if trial == "present":
                            checks["ocr_expected"] = has_values
                            checks["field_pixels"] = not is_orange(field_rgb)
                        elif trial == "absent":
                            checks["ocr_expected"] = has_none
                            checks["field_pixels"] = is_whiteish(field_rgb)
                        else:  # occluded
                            if backend == "printwindow_clientonly":
                                # S3-verified behavior for GDI/Tk targets:
                                # window content, occlusion-immune.
                                checks["ocr_expected"] = has_values
                                checks["field_pixels"] = not is_orange(field_rgb)
                            else:
                                # visible pixels: the occluder is captured.
                                checks["ocr_expected"] = has_none
                                checks["field_pixels"] = is_orange(field_rgb)
                        entry["marker_rgb"] = marker_rgb
                        entry["field_rgb"] = field_rgb
                        entry["ocr_contains_all_values"] = has_values
                    entry["checks"] = checks
                    entry["passed"] = all(checks.values())
                    if not entry["passed"]:
                        failed = [name for name, ok in checks.items() if not ok]
                        failures.append(f"{trial}/{backend}: {','.join(failed)}")
                    results.append(entry)
                    print("S7SYN_RESULT " + json.dumps(entry, sort_keys=True))
                if len(origins) == 2 and origins[0] != origins[1]:
                    failures.append(f"{trial}: cross-backend origin mismatch {origins}")
        finally:
            if not failures:
                shutil.rmtree(temp_dir, ignore_errors=True)
        command("quit")
        target.wait(timeout=10)
    finally:
        viewer.destroy()
        if target.poll() is None:
            target.kill()

    pw_present = next((r for r in results
                       if r["trial"] == "present"
                       and r["backend"] == "printwindow_clientonly"), None)
    cfs_ok = all(r["passed"] for r in results if r["backend"] == "copyfromscreen")
    pw_ok = all(r["passed"] for r in results if r["backend"] == "printwindow_clientonly")
    if pw_present and pw_present["passed"] and pw_ok:
        provisional = "printwindow_clientonly"
    elif cfs_ok:
        provisional = "copyfromscreen"
    else:
        provisional = "NONE"
    report = {
        "schema_version": "screen2xyz.s7syn.1",
        "gate": "G-E-SYNTHETIC",
        "trials": results,
        "failures": failures,
        "all_passed": not failures,
        "provisional_backend": provisional,
        "note": ("Synthetic-target evidence only (OD-M2-9). This result never "
                 "closes G-E-REAL and makes no real-target support claim."),
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "s7_synthetic_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"S7SYN_SUMMARY all_passed={not failures} "
          f"provisional_backend={provisional} report={report_path}")
    if failures:
        print("FAILURES: " + "; ".join(failures), file=sys.stderr)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
