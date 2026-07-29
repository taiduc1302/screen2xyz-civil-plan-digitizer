"""Disposable owner-run S7 target-compatibility gate; not production code.

Run one invocation for each required trial (present, absent, and occluded). Each
invocation performs one finite two-backend capture sequence after a visible
countdown. Temporary previews are reviewed locally and removed on normal
completion unless --save explicitly promotes them to ignored local evidence.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPOSITORY_ROOT = HERE.parents[2]
IGNORED_SAVE_ROOT = REPOSITORY_ROOT / ".lab_work" / "m2_research" / "s7_preview"
HELPER = HERE / "spike_s3_capture.ps1"
BACKENDS = ("printwindow_clientonly", "copyfromscreen")

if sys.platform != "win32":
    raise SystemExit("S7 is a Windows-only planning gate.")

user32 = ctypes.windll.user32
ENUM_WINDOWS_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.SetProcessDpiAwarenessContext.argtypes = [wintypes.HANDLE]
user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
user32.EnumWindows.argtypes = [ENUM_WINDOWS_PROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetDpiForWindow.argtypes = [wintypes.HWND]
user32.GetDpiForWindow.restype = wintypes.UINT


def enable_per_monitor_v2() -> None:
    """Set PMv2 before any window coordinates are queried."""
    if not user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
        raise RuntimeError("PMv2 initialization failed")


def window_pid(hwnd: int) -> int:
    pid = wintypes.DWORD()
    thread_id = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if thread_id == 0 or pid.value == 0:
        raise RuntimeError("target identity query failed")
    return int(pid.value)


def validate_window(hwnd: int, expected_pid: int) -> int:
    if not user32.IsWindow(hwnd) or not user32.IsWindowVisible(hwnd):
        raise RuntimeError("selected target is no longer a visible window")
    if user32.IsIconic(hwnd):
        raise RuntimeError("selected target is minimized")
    if window_pid(hwnd) != expected_pid:
        raise RuntimeError("selected target identity changed; choose it again")
    dpi = int(user32.GetDpiForWindow(hwnd))
    if dpi == 0:
        raise RuntimeError("GetDpiForWindow returned 0")
    return dpi


def terminal_safe_title(title: str) -> str:
    """Bound a local display label and remove terminal control characters."""
    printable = "".join(character if character.isprintable() else " " for character in title)
    bounded = printable.encode("utf-8")[:512].decode("utf-8", errors="ignore")
    return bounded[:90]


def list_visible_windows() -> list[tuple[int, str, int]]:
    found: list[tuple[int, str, int]] = []

    @ENUM_WINDOWS_PROC
    def enum_window(hwnd: int, _lparam: int) -> bool:
        if user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buffer = ctypes.create_unicode_buffer(length + 1)
                if user32.GetWindowTextW(hwnd, buffer, length + 1) > 0:
                    try:
                        found.append((int(hwnd), buffer.value, window_pid(hwnd)))
                    except RuntimeError:
                        pass
        return True

    if not user32.EnumWindows(enum_window, 0):
        raise RuntimeError("EnumWindows failed")
    return found


def choose_window(windows: list[tuple[int, str, int]]) -> tuple[int, str, int]:
    for index, (_hwnd, title, _pid) in enumerate(windows):
        print(f"[{index}] {terminal_safe_title(title)}")
    try:
        choice = int(input("Number of the authorized target window: "))
        if choice < 0 or choice >= len(windows):
            raise ValueError("selection is outside the displayed range")
        return windows[choice]
    except (ValueError, IndexError) as exc:
        raise ValueError("invalid window selection") from exc


def prepare_trial(trial: str, countdown_seconds: int) -> None:
    instructions = {
        "present": "place the pointer over a value so the hover treatment is visible",
        "absent": "move the pointer away so no hover treatment is visible",
        "occluded": (
            "cover the identified value area with a benign, non-confidential "
            "occluder while leaving the target otherwise unchanged"
        ),
    }
    input(
        f"Prepare the {trial!r} trial: {instructions[trial]}. "
        "Press Enter, then return the pointer to the required position."
    )
    for remaining in range(countdown_seconds, 0, -1):
        print(f"Capturing in {remaining}...", flush=True)
        time.sleep(1)
    print("Capture sequence started; keep the desktop unchanged.", flush=True)


def discard_unowned_preview(output_path: Path) -> str | None:
    """Remove an output that never became a validated capture result."""
    failures = []
    candidates = [output_path, *output_path.parent.glob(f"{output_path.name}.partial-*")]
    for candidate in candidates:
        try:
            candidate.unlink(missing_ok=True)
        except OSError as exc:
            failures.append(f"{candidate.name}:{type(exc).__name__}")
    return "unvalidated output cleanup failed: " + ",".join(failures) if failures else None


def failed_capture_result(
    backend: str,
    elapsed_ms: int,
    detail: str,
    *,
    process_exit_code: int | None,
    outcome_kind: str,
    output_path: Path,
) -> dict[str, object]:
    cleanup_error = discard_unowned_preview(output_path)
    if cleanup_error:
        detail = f"{detail}; {cleanup_error}"
        outcome_kind = "trial_invalid"
    return {
        "backend": backend,
        "api_success": False,
        "outcome_kind": outcome_kind,
        "process_exit_code": process_exit_code,
        "elapsed_ms": elapsed_ms,
        "detail": detail,
    }


def capture_once(
    hwnd: int,
    expected_pid: int,
    backend: str,
    output_path: Path,
) -> dict[str, object]:
    started = time.monotonic()
    if output_path.exists():
        return {
            "backend": backend,
            "api_success": False,
            "outcome_kind": "trial_invalid",
            "process_exit_code": None,
            "elapsed_ms": 0,
            "detail": "controlled output path unexpectedly already exists",
        }
    try:
        validate_window(hwnd, expected_pid)
    except RuntimeError as exc:
        return failed_capture_result(
            backend,
            0,
            str(exc),
            process_exit_code=None,
            outcome_kind="trial_invalid",
            output_path=output_path,
        )
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(HELPER),
                "-Hwnd",
                str(hwnd),
                "-ExpectedPid",
                str(expected_pid),
                "-Mode",
                backend,
                "-OutPath",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return failed_capture_result(
            backend,
            round((time.monotonic() - started) * 1000),
            "capture helper exceeded the 60-second research-gate bound",
            process_exit_code=None,
            outcome_kind="trial_invalid",
            output_path=output_path,
        )
    elapsed_ms = round((time.monotonic() - started) * 1000)
    if completed.returncode != 0:
        detail = completed.stderr.strip().replace("\r", " ").replace("\n", " ")[:160]
        return failed_capture_result(
            backend,
            elapsed_ms,
            detail or "capture helper failed without diagnostic text",
            process_exit_code=completed.returncode,
            outcome_kind=(
                "capture_api_failure" if completed.returncode == 24 else "trial_invalid"
            ),
            output_path=output_path,
        )
    try:
        payload = json.loads(completed.stdout.strip())
    except json.JSONDecodeError as exc:
        return failed_capture_result(
            backend,
            elapsed_ms,
            f"invalid helper JSON: {exc.msg}",
            process_exit_code=completed.returncode,
            outcome_kind="trial_invalid",
            output_path=output_path,
        )
    required_integer_fields = (
        "w",
        "h",
        "origin_x",
        "origin_y",
        "window_dpi",
        "capture_ms",
        "sample_count",
        "png_bytes",
    )
    try:
        published_size = output_path.stat().st_size
    except OSError:
        published_size = None
    valid_payload = (
        isinstance(payload, dict)
        and payload.get("backend") == backend
        and all(type(payload.get(key)) is int for key in required_integer_fields)
        and isinstance(payload.get("mean_luma"), (int, float))
        and isinstance(payload.get("luma_range"), (int, float))
        and isinstance(payload.get("frame_content_status"), str)
        and payload.get("w", 0) > 0
        and payload.get("h", 0) > 0
        and payload.get("window_dpi", 0) > 0
        and payload.get("png_bytes", 0) > 0
        and published_size == payload.get("png_bytes")
    )
    if not valid_payload:
        return failed_capture_result(
            backend,
            elapsed_ms,
            "helper response or published PNG failed validation",
            process_exit_code=completed.returncode,
            outcome_kind="trial_invalid",
            output_path=output_path,
        )
    payload.update(
        {
            "backend": backend,
            "api_success": True,
            "outcome_kind": "success",
            "process_exit_code": completed.returncode,
            "elapsed_ms": elapsed_ms,
        }
    )
    return payload


def collect_visual_verdict(
    trial: str,
    result: dict[str, object],
    preview_path: Path,
) -> None:
    """Display a preview in-process and collect a non-persisted local verdict."""
    if not result["api_success"] or not preview_path.is_file():
        result["visual_verdict"] = "not_available"
        return

    try:
        import tkinter as tk
    except ImportError:
        result["visual_verdict"] = "viewer_error"
        result["detail"] = "Tk preview viewer is unavailable"
        return

    choices = {
        "present": (
            ("Target/value readable", "target_value_readable"),
            ("Wrong or unreadable", "wrong_or_unreadable"),
        ),
        "absent": (
            ("Value absent as expected", "value_absent_as_expected"),
            ("Value remains readable", "target_value_readable"),
            ("Wrong or unreadable", "wrong_or_unreadable"),
        ),
        "occluded": (
            ("Underlying value remains readable", "target_value_readable"),
            ("Occluder appears over value", "occluder_visible_over_value"),
            ("Wrong or unreadable", "wrong_or_unreadable"),
        ),
    }
    verdict = {"value": "uncertain"}
    root = None
    try:
        root = tk.Tk()
        root.title(f"S7 local preview — {trial} — {result['backend']}")
        root.attributes("-topmost", True)
        tk.Label(
            root,
            text=(
                "Inspect this local, temporary full-client preview. Choose the "
                "factual result; this does not itself pass G-E."
            ),
            wraplength=1000,
            padx=12,
            pady=8,
        ).pack()
        original = tk.PhotoImage(file=str(preview_path))
        viewport = tk.Frame(root)
        viewport.pack(padx=8, pady=8)
        canvas = tk.Canvas(
            viewport,
            width=min(original.width(), 1000),
            height=min(original.height(), 650),
            highlightthickness=1,
        )
        horizontal = tk.Scrollbar(viewport, orient=tk.HORIZONTAL, command=canvas.xview)
        vertical = tk.Scrollbar(viewport, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        canvas.create_image(0, 0, anchor=tk.NW, image=original)
        canvas.configure(scrollregion=(0, 0, original.width(), original.height()))
        canvas.image = original
        buttons = tk.Frame(root)
        buttons.pack(padx=8, pady=8)

        def choose(value: str) -> None:
            verdict["value"] = value
            root.quit()

        for label, value in choices[trial]:
            tk.Button(buttons, text=label, command=lambda v=value: choose(v)).pack(
                side=tk.LEFT, padx=4
            )
        tk.Button(buttons, text="Uncertain", command=lambda: choose("uncertain")).pack(
            side=tk.LEFT, padx=4
        )
        root.protocol("WM_DELETE_WINDOW", lambda: choose("uncertain"))
        root.bind("<Escape>", lambda _event: choose("uncertain"))
        root.mainloop()
        result["visual_verdict"] = verdict["value"]
    except (OSError, tk.TclError):
        result["visual_verdict"] = "viewer_error"
        result["detail"] = "local Tk preview viewer failed"
    finally:
        if root is not None:
            try:
                root.destroy()
            except tk.TclError:
                pass


def result_summary(
    trial: str,
    result: dict[str, object],
    saved_path: Path | None,
) -> dict[str, object]:
    summary = {
        "trial": trial,
        "backend": result["backend"],
        "api_success": result["api_success"],
        "outcome_kind": result["outcome_kind"],
        "process_exit_code": result["process_exit_code"],
        "elapsed_ms": result["elapsed_ms"],
    }
    for key in (
        "w",
        "h",
        "origin_x",
        "origin_y",
        "window_dpi",
        "capture_ms",
        "sample_count",
        "mean_luma",
        "luma_range",
        "frame_content_status",
        "png_bytes",
        "visual_verdict",
        "preview_sha256",
        "comparison_status",
        "trial_valid",
        "trial_invalid_reasons",
        "trial_incomplete_reasons",
        "trial_record_complete",
        "detail",
    ):
        if key in result:
            summary[key] = result[key]
    if saved_path is not None and result["api_success"]:
        summary["saved_preview"] = str(saved_path.relative_to(REPOSITORY_ROOT))
    return summary


def print_result(trial: str, result: dict[str, object], saved_path: Path | None) -> None:
    summary = result_summary(trial, result, saved_path)
    print("S7_RESULT " + json.dumps(summary, ensure_ascii=True, sort_keys=True))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_new_file(path: Path, payload: bytes) -> None:
    """Write once in the unique trial directory and publish by rename."""
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path.name}")
    partial = path.with_name(f".{path.name}.partial")
    try:
        with partial.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.rename(partial, path)
    finally:
        partial.unlink(missing_ok=True)


def write_saved_evidence(
    args: argparse.Namespace,
    output_dir: Path,
    results: tuple[dict[str, object], dict[str, object]],
    paths: tuple[Path, Path],
) -> None:
    """Bind saved previews to factual verdicts in a no-overwrite local record."""
    for result, path in zip(results, paths, strict=True):
        if result["api_success"]:
            result["preview_sha256"] = sha256_file(path)

    record_path = output_dir / "trial_record.json"
    manifest_path = output_dir / "evidence_manifest_sha256.txt"
    record = {
        "schema_version": "screen2xyz.s7.1",
        "trial": args.trial,
        "countdown_seconds": args.countdown,
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "target_identity_included": False,
        "evidence_manifest": manifest_path.name,
        "trial_record_complete": results[0]["trial_record_complete"],
        "results": [
            result_summary(args.trial, result, path if result["api_success"] else None)
            for result, path in zip(results, paths, strict=True)
        ],
    }
    record_bytes = (
        json.dumps(record, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    manifest_entries = []
    for result, path in zip(results, paths, strict=True):
        if result["api_success"]:
            manifest_entries.append((str(result["preview_sha256"]), path.name))
    manifest_entries.append((hashlib.sha256(record_bytes).hexdigest(), record_path.name))
    manifest_bytes = "".join(
        f"{digest}  {name}\n" for digest, name in sorted(manifest_entries, key=lambda item: item[1])
    ).encode("ascii")

    # Publish the manifest first and the record last. A complete record can
    # therefore never exist without the manifest it names and binds.
    write_new_file(manifest_path, manifest_bytes)
    if manifest_path.read_bytes() != manifest_bytes:
        raise OSError("saved evidence manifest verification failed")
    for expected_digest, name in manifest_entries:
        if name != record_path.name and sha256_file(output_dir / name) != expected_digest:
            raise OSError(f"saved preview verification failed for {name}")
    write_new_file(record_path, record_bytes)


def cross_backend_invalid_reasons(
    results: tuple[dict[str, object], dict[str, object]],
) -> list[str]:
    successful = [result for result in results if result["api_success"]]
    if len(successful) != 2:
        for result in results:
            result["comparison_status"] = "NOT_APPLICABLE"
        return []
    fields = ("w", "h", "origin_x", "origin_y", "window_dpi")
    mismatched = [field for field in fields if successful[0][field] != successful[1][field]]
    if not mismatched:
        for result in results:
            result["comparison_status"] = "MATCH"
        return []
    for result in results:
        result["comparison_status"] = "MISMATCH"
    return ["cross-backend geometry/DPI mismatch: " + ", ".join(mismatched)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run exactly one finite S7 compatibility trial with both MVP backends."
    )
    parser.add_argument(
        "--trial",
        choices=("present", "absent", "occluded"),
        required=True,
        help="required target state for this invocation",
    )
    parser.add_argument(
        "--countdown",
        type=int,
        choices=(3, 4, 5),
        default=3,
        help="visible preparation countdown in seconds (default: 3)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="preserve validated previews with an ignored local trial record and SHA-256 manifest",
    )
    return parser.parse_args()


def run_trial(args: argparse.Namespace, output_dir: Path) -> int:
    windows = list_visible_windows()
    if not windows:
        print("No visible titled windows were enumerated.", file=sys.stderr)
        return 1
    try:
        hwnd, title, pid = choose_window(windows)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    try:
        dpi = validate_window(hwnd, pid)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Selected local window: {terminal_safe_title(title)!r}; pid={pid}; dpi={dpi}")
    prepare_trial(args.trial, args.countdown)

    first_path = output_dir / f"s7_{args.trial}_{BACKENDS[0]}.png"
    second_path = output_dir / f"s7_{args.trial}_{BACKENDS[1]}.png"
    first = capture_once(hwnd, pid, BACKENDS[0], first_path)
    second = capture_once(hwnd, pid, BACKENDS[1], second_path)
    results = (first, second)
    paths = (first_path, second_path)
    invalid_reasons = [
        f"{result['backend']}: {result.get('detail', 'trial-invalid execution failure')}"
        for result in results
        if result["outcome_kind"] == "trial_invalid"
    ]
    invalid_reasons.extend(cross_backend_invalid_reasons(results))

    collect_visual_verdict(args.trial, first, first_path)
    collect_visual_verdict(args.trial, second, second_path)

    explicit = {
        "target_value_readable",
        "value_absent_as_expected",
        "occluder_visible_over_value",
        "wrong_or_unreadable",
    }
    successful = [result for result in results if result["outcome_kind"] == "success"]
    incomplete_reasons = []
    if not successful:
        incomplete_reasons.append("no backend produced a validated preview")
    for result in successful:
        if result.get("visual_verdict") not in explicit:
            incomplete_reasons.append(
                f"{result['backend']}: explicit visual verdict was not recorded"
            )
    trial_valid = not invalid_reasons
    trial_record_complete = trial_valid and not incomplete_reasons
    for result in results:
        result["trial_valid"] = trial_valid
        result["trial_invalid_reasons"] = invalid_reasons
        result["trial_incomplete_reasons"] = incomplete_reasons
        result["trial_record_complete"] = trial_record_complete

    save_record_error = None
    if args.save:
        try:
            write_saved_evidence(args, output_dir, results, paths)
        except OSError as exc:
            save_record_error = f"saved evidence binding failed: {type(exc).__name__}"
            incomplete_reasons.append(save_record_error)
            trial_record_complete = False
            for result in results:
                result["trial_incomplete_reasons"] = incomplete_reasons
                result["trial_record_complete"] = False

    print_result(args.trial, first, first_path if args.save else None)
    print_result(args.trial, second, second_path if args.save else None)

    if args.save:
        if save_record_error:
            print(
                f"{save_record_error}. The unique ignored directory is incomplete and is "
                "not a complete S7 evidence record; never commit or share its contents."
            )
        else:
            print(
                f"Sensitive previews retained locally in {output_dir.relative_to(REPOSITORY_ROOT)}. "
                "The no-overwrite trial_record.json and SHA-256 manifest bind each validated "
                "preview to its backend and verdict; preserve them and never commit or share them."
            )
    else:
        print(
            "Temporary previews are removed on normal completion. Forced termination may "
            "leave sensitive non-evidence files in the OS temporary directory."
        )
    print(
        "Record both S7_RESULT lines. Exit zero means the trial has no infrastructure/"
        "state invalidation, at least one validated preview, and explicit verdicts for all "
        "validated previews; it does not mean G-E passed."
    )
    return 0 if trial_record_complete else 1


def main() -> int:
    args = parse_args()
    if not HELPER.is_file():
        print("Capture helper is missing.", file=sys.stderr)
        return 1
    try:
        enable_per_monitor_v2()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.save:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output_dir = IGNORED_SAVE_ROOT / f"{stamp}-{args.trial}"
        output_dir.mkdir(parents=True, exist_ok=False)
        return run_trial(args, output_dir)

    with tempfile.TemporaryDirectory(prefix="screen2xyz-s7-") as temporary:
        return run_trial(args, Path(temporary))


if __name__ == "__main__":
    raise SystemExit(main())
