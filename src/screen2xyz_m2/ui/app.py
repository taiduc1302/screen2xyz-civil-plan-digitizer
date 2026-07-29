"""M2-Live Tkinter application: guided setup -> preview -> record -> finalize.

The window layer is thin: it drives LiveSessionController and TickScheduler
and renders their state. All decision logic lives in the controller; the
testable UI logic lives in `layout.py`.
"""

from __future__ import annotations

import base64
import os
import queue
import threading
import time
import tkinter as tk
from collections import deque
from tkinter import messagebox, ttk
from typing import Any

from .. import contracts as C
from ..controller import LiveSessionController, PauseState
from ..dpi import enable_pmv2
from ..models import (SessionDefaults, SourceConfig, ValidationError,
                      new_source_id, validate_source_set, xyz_missing_axes)
from ..paths import diagnostics_root, repository_root
from ..scheduler import TickScheduler
from ..statemachine import IllegalAction
from ..targets import (environment_snapshot, list_monitors, list_windows,
                       window_client_info)
from ..worker import WorkerError
from .layout import (backend_explanation, backend_label, backend_value,
                     can_test_capture,
                     classify_capture_test, content_status_label,
                     csv_preview_title, derive_next_step,
                     feed_column_title, FEED_COLOR_LEGEND, feed_row_color,
                     FEED_COLUMN_WIDTHS, FEED_COLUMNS,
                     FEED_PRESET_NAMES, FEED_PRESETS, field_card_status,
                     format_elapsed,
                     mini_controller_position, missing_value_guidance,
                     pause_guidance, pause_message,
                     persistence_state, PERSISTENCE_FINAL_CSV,
                     PERSISTENCE_JOURNAL, PERSISTENCE_LIVE_CSV,
                     PERSISTENCE_OBSERVED_LIVE, picker_scale_factor,
                     region_confirm_allowed, region_drag_rect,
                     region_on_cancel, region_on_confirm, region_on_press,
                     region_on_redraw, region_on_release, region_stale,
                     REGION_CONFIRMED, REGION_DRAGGING, REGION_NO_SELECTION,
                     REGION_SELECTION_READY, RETENTION_LABELS, retention_key,
                     retention_label, suggest_field_type, value_changed,
                     value_status_guidance, value_status_label,
                     warning_sentence, xyz_outcome_sentence,
                     xyz_status_sentence)

# Exception types whose message text is always a static, safe, internally-
# authored string (never derived from a window title, captured OCR text, or
# a confidential path) - safe to write into the local callback-error log.
# Anything else logs only its type name and source location.
_SAFE_MESSAGE_EXCEPTION_TYPES = (ValidationError, IllegalAction, WorkerError)

WELCOME_TEXT = (
    "Screen2XYZ M2-Live watches a window (or monitor) and turns the numbers "
    "it displays into a data record you can export.\n\n"
    "Not sure where to start? Click \"Demo mode\" to try the whole "
    "workflow against a safe, synthetic target with no real data, or "
    "\"Guided demo\" to step through it one visible action at a time. "
    "\"How this works\" (this window) and \"Help\" are always in the "
    "top-right corner.\n\n"
    "The whole thing is six steps, shown in the \"Next step\" card that is "
    "always on screen:\n\n"
    "Step 1 — Choose what to capture (a window or a monitor).\n"
    "Step 2 — Test capture: confirm Screen2XYZ can actually see it.\n"
    "Step 3 — Add your fields and draw a rectangle around each value.\n"
    "Step 4 — Preview: check each field is reading the right thing.\n"
    "Step 5 — Start recording.\n"
    "Step 6 — Watch the values change and be saved, then Stop to export.\n\n"
    "While recording you can see exactly what is being read, and the three "
    "separate truths for each value: Persisted to journal (durably saved), "
    "Live CSV snapshot updated (a live preview file), and Final CSV "
    "finalized (only after you press Stop).")

BACKEND_CHOICES = (C.BACKEND_AUTO, C.BACKEND_PRINTWINDOW,
                   C.BACKEND_COPYFROMSCREEN)

# Bounded ring buffer size for the live feed and Saved CSV rows views - the
# underlying journal/CSV data is never truncated, only what the UI displays.
FEED_MAX_ROWS = 500

HELP_TEXT = """\
Select target window / Select monitor
  Choose what Screen2XYZ should watch. A window follows Windows' own \
resize/move/minimize rules; a monitor captures whatever is visible there, \
including other windows on top.

Backend (Auto / PrintWindow / CopyFromScreen)
  Auto (recommended) tries PrintWindow first, checks the result is real \
content (not solid black or white), and falls back to CopyFromScreen if \
not - then remembers the choice for the rest of the session. PrintWindow \
can see a window even if something else covers it, but not every app \
supports it. CopyFromScreen always works but only sees pixels that are \
actually on screen (nothing covered or off-screen monitor edges).

Test capture now / Retest
  Takes one real capture right now and shows you exactly what Screen2XYZ \
sees, with a PASS/WARNING/FAIL verdict. Retest forces a fresh check even \
if Auto already picked a backend.

Add field
  Creates one named value to track (a number, plain text, or auto-detect), \
with an optional X/Y/Z/Metadata role for exports.

Draw region
  Opens REGION SELECTION MODE: a large banner makes it unmistakable that \
you are now selecting, with a crosshair cursor, the area outside your drag \
dimmed, and live x/y/width/height shown in original physical pixels no \
matter how far you zoom in or out.

Confirm this region
  Only enabled once a real drag produced an in-bounds, non-blank crop - a \
plain click can never confirm a region, and a crop that looks solid black \
or white is refused so you notice a wrong selection immediately. A crop \
that is a single flat color other than black/white (e.g. a genuinely blank \
field) is also blocked by default; "Use anyway (advanced)" lets you \
confirm it after a second explicit confirmation, and the override is \
recorded in this session's saved metadata. If the target resizes or its \
DPI changes while the picker is open, Confirm is blocked until you Redraw \
against a fresh snapshot.

Redraw
  Clears the current in-progress selection so you can drag again; it never \
touches the field's previously confirmed region until you actually confirm \
a new one.

Review selected regions
  Shows one screenshot with every field's region outlined and numbered, \
plus a details panel with that field's latest crop and OCR; click a \
region to select that field, then Edit, Redraw, Remove, or "Re-test all \
regions" to refresh every field's preview at once.

Setup table crop/OCR column
  After you confirm a region, the setup table keeps showing its last known \
crop thumbnail, raw OCR, and normalized value - select the row to see them \
full-size in the details panel below the table, without reopening the \
picker.

Preview
  Runs a real capture + OCR for every field so you can confirm each one is \
reading the right thing before you commit to recording.

Arm / Start
  Arming locks in the current setup. Start begins the actual ~1x/second \
capture loop.

Pause / Resume / Stop / Emergency stop
  Pause/Resume keep the session open. Stop finalizes it, writing all the \
exports. Emergency stop (or Esc) kills the capture worker immediately, \
within about 2 seconds, no matter what state it is in.

Field cards
  One compact card per field, always visible while recording: its latest \
crop thumbnail, raw OCR, normalized value, value/stability status, when it \
last changed and last persisted, its region coordinates, and a warning \
badge if capture or OCR is having trouble. Scroll sideways if you have more \
fields than fit the window - up to 8 fields are supported without any card \
being clipped.

Live capture feed
  A scrolling row per field per tick, color-coded so you can tell at a \
glance: gray (observed live only), blue (a candidate awaiting stability \
confirmation), green (persisted to journal AND the live CSV snapshot \
updated), orange (persisted to journal but the live CSV snapshot update \
failed), yellow (a problem was seen this tick - empty/failed OCR or a \
capture hiccup - and NOT kept), red (retained error). The same legend is \
shown on-screen just above the feed. Column presets (Simple/OCR/Persistence/\
Diagnostics/All) show only the columns you need; "All" adds a horizontal \
scrollbar for the rest. It keeps the latest 500 rows on screen; nothing \
recorded is ever lost, and "Clear screen feed" only clears what is \
displayed, never the recorded data.

Four persistence states (the truth, in order)
  1) Observed live - this tick's reading, nothing saved yet.
  2) Persisted to journal - durably fsynced to this run's events.jsonl; \
this is the real, crash-safe record and can never be lost from here on.
  3) Live CSV snapshot updated - a best-effort preview file \
(events_wide.live.csv) was atomically regenerated so you can inspect \
progress in a spreadsheet while still recording; if this step fails the \
journal entry is still safe, and the failure is shown, never hidden.
  4) Final CSV finalized - only after you press Stop: events_wide.csv and \
observations_long.csv are written and their row count is verified against \
the journal.
  The old single "written to CSV" label conflated steps 2-4; the feed and \
Saved CSV rows tab now show which of the four states each row is actually \
in.

Saved CSV rows
  While recording, shows the live CSV snapshot rows (clearly labeled "live \
snapshot, updates during recording"); after Stop, the Finalized screen \
shows the real, verified final CSV row count instead. Never a guess in \
advance of the actual write.

retained event
  A value change (or an error transition) that stability confirmation and \
your retention-mode setting decided is worth keeping permanently, as \
opposed to a value that was only observed live and then moved on.

stability state
  Whether a changed value has been confirmed enough times yet (per your \
Advanced settings) before it is retained. A value can be "live-only" \
(gray), "awaiting confirmation" (blue), or "persisted" (green/orange).

Diagnostic snapshot
  Saves the current frame and every field's crop locally under \
.lab_work/m2_diagnostics/ so you can inspect exactly what was captured. \
Nothing is uploaded, ever.

Retention mode
  Controls which ticks get a permanent record: changed values only, \
changes + errors (default), every tick (diagnostic), or values only.
"""


class M2App:
    _welcome_shown_this_process = False

    def __init__(self) -> None:
        enable_pmv2()
        self.root = tk.Tk()
        self.root.title("Screen2XYZ M2-Live — Region Watch")
        self.root.geometry("1040x760")
        self.scope: dict[str, Any] | None = None
        self.sources: list[SourceConfig] = []
        self.defaults = SessionDefaults()
        self.controller: LiveSessionController | None = None
        self.scheduler: TickScheduler | None = None
        self.mini: tk.Toplevel | None = None
        self._start_time = 0.0
        self._snapshot_image: tk.PhotoImage | None = None
        self._test_thumb_image: tk.PhotoImage | None = None
        self._demo_session = None
        self._capture_flash_state = False
        self._setup_previews: dict[str, dict[str, Any]] = {}
        # source_ids whose region the user (or a programmatic setup) has
        # actually CONFIRMED - distinct from the placeholder rect every new
        # field carries (§3), so the setup table never lies "region set" for
        # an undrawn field and Preview can require a real region per field.
        self._confirmed_regions: set[str] = set()
        # §6: a Tk button callback that raises ANY exception the caller did
        # not explicitly handle (a stale-state IllegalAction, a validation
        # error, a future bug) is otherwise swallowed by Tk's default
        # handler - printed to a stderr the owner never sees when launched
        # via a .ps1 script - leaving the screen frozen with no visible
        # acknowledgement. This is the exact shape of the reported "Test
        # capture now does nothing" failure. Every callback failure must now
        # be logged locally, shown to the owner, and leave the app usable.
        self.root.report_callback_exception = self._on_callback_exception
        self._build_setup()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Escape>", lambda _e: self._emergency_stop())
        if not M2App._welcome_shown_this_process:
            M2App._welcome_shown_this_process = True
            self.root.after(150, self._show_welcome)

    # -- callback exception safety net (§6) --------------------------------

    def _on_callback_exception(self, exc_type, exc_value, exc_tb) -> None:
        """Installed as root.report_callback_exception: the last-resort
        catch-all for any Tk button/binding callback that raises an
        exception no inner try/except handled. Never lets the UI go silent -
        always logs (sanitized) and always tells the owner something broke,
        while leaving the app fully usable."""

        import json
        import traceback
        from datetime import datetime, timezone

        safe_message = (str(exc_value)
                        if isinstance(exc_value, _SAFE_MESSAGE_EXCEPTION_TYPES)
                        else "(message withheld - not a recognized-safe "
                             "exception type)")
        repo = repository_root()
        frames = []
        for frame in traceback.extract_tb(exc_tb)[-5:]:
            try:
                from pathlib import Path
                rel = str(Path(frame.filename).resolve().relative_to(repo))
            except ValueError:
                rel = "<external>"
            frames.append(f"{rel}:{frame.lineno} in {frame.name}")
        entry = {"utc": datetime.now(timezone.utc).isoformat(),
                "exception_type": exc_type.__name__,
                "message": safe_message, "frames": frames}
        try:
            root = diagnostics_root()
            root.mkdir(parents=True, exist_ok=True)
            with (root / "callback_errors.log").open(
                    "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, sort_keys=True) + "\n")
        except OSError:
            pass
        try:
            self.status.set(
                f"An internal error occurred ({exc_type.__name__}) - "
                f"Screen2XYZ is still running. Try the action again.")
        except Exception:
            pass
        try:
            messagebox.showwarning(
                "Screen2XYZ — action could not complete",
                f"{exc_type.__name__}: {safe_message}\n\n"
                "Screen2XYZ is still running and safe to keep using. "
                "This was logged locally under .lab_work/m2_diagnostics/ "
                "(never uploaded).")
        except Exception:
            pass

    # -- help / welcome / demo ---------------------------------------------

    def _show_welcome(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Welcome to Screen2XYZ M2-Live")
        # Scrollbar + taller box so the "Not sure where to start?" call to
        # action (now at the top) and all six steps are reachable - the
        # welcome text used to clip its own guidance below the fold with no
        # way to scroll, unlike the Help dialog.
        frame = ttk.Frame(dialog)
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, width=74, height=22, wrap="word", padx=10,
                       pady=10)
        scroll = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.insert("1.0", WELCOME_TEXT)
        text.configure(state="disabled")
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        ttk.Button(dialog, text="Got it", command=dialog.destroy).pack(pady=8)

    def _show_help(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("How this works")
        frame = ttk.Frame(dialog)
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, width=88, height=32, wrap="word", padx=10,
                       pady=10)
        scroll = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.insert("1.0", HELP_TEXT)
        text.configure(state="disabled")
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=8)

    def _launch_demo(self) -> None:
        from .. import demo as demo_mod
        if self._demo_session is not None:
            messagebox.showinfo("Demo already running",
                                "Close the existing demo target first.")
            return
        try:
            self._demo_session = demo_mod.launch_interactive()
        except Exception as exc:
            messagebox.showerror("Demo failed to launch", str(exc))
            return
        panel = tk.Toplevel(self.root)
        panel.title("Demo target running")
        panel.attributes("-topmost", True)
        ttk.Label(panel, text="A safe synthetic X/Y/Z target is running.\n"
                             "Select it as your target window above, or "
                             "just close it when done.",
                 padding=10).pack()

        def close_demo() -> None:
            if self._demo_session is not None:
                self._demo_session.quit()
                self._demo_session = None
            panel.destroy()

        ttk.Button(panel, text="Close demo target",
                  command=close_demo).pack(pady=8)
        panel.protocol("WM_DELETE_WINDOW", close_demo)

    def _guided_demo(self) -> None:
        """A step-by-step walkthrough that drives the real app (not a
        separate simulation) against the safe synthetic demo target,
        advancing only when the owner clicks Next - including after
        interacting with a step's own dialog (region picker, preview
        gate), so nothing is auto-confirmed on the owner's behalf."""

        from .. import demo as demo_mod
        if self._demo_session is not None:
            messagebox.showinfo("Demo already running",
                                "Close the existing demo target first.")
            return
        try:
            self._demo_session = demo_mod.launch_interactive()
        except Exception as exc:
            messagebox.showerror("Demo failed to launch", str(exc))
            return
        self._demo_session.set_case("changing")
        self._demo_session.auto_change(True)

        steps = [
            ("Target selected",
             "The demo target is running and selected as the target "
             "window."),
            ("Add fields",
             "X, Y, and Z fields are added, matching the demo target's "
             "labeled values."),
            ("Test capture",
             "Runs a real capture and shows a PASS/WARNING/FAIL verdict "
             "with a thumbnail."),
            ("Enter REGION SELECTION MODE",
             "The X field's region picker opens for real: notice the "
             "banner, the crosshair, and the dimmed area outside your "
             "drag. Drag around the X value, then Confirm this region, "
             "then click Next here."),
            ("Preview all fields",
             "The real preview screen opens with live crop thumbnails and "
             "OCR. Tick each field as aligned, click Confirm preview, then "
             "click Next here."),
            ("Start recording",
             "Recording begins - notice the field cards (crop thumbnail, "
             "raw OCR, normalized value per field) and the Live feed."),
            ("Watch values change",
             "The demo target's values are changing automatically - watch "
             "each field card and Live feed row move gray (observed live) "
             "-> blue (pending stability) -> green (persisted to journal "
             "AND the live CSV snapshot updated), and new rows appear in "
             "Saved CSV rows (labeled as the LIVE snapshot, not the final "
             "CSV yet)."),
            ("Resize the target",
             "The target is resized. Watch the status line show a pause "
             "reason - a size/DPI change always pauses and requires "
             "reconfiguration before resuming, so a stale region can never "
             "silently keep reading the wrong pixels."),
            ("Disarm and re-preview",
             "Click 'Disarm and re-preview…' for real, tick every field "
             "aligned again, click Confirm preview, then click Next here."),
            ("Resume recording",
             "Back on the Ready screen - click 'START RECORDING' for real "
             "(this continues the SAME run, not a new one), then click "
             "Next here."),
            ("Minimize the target",
             "The target is minimized. After a few ticks, watch the "
             "session auto-pause - a minimized window cannot be captured."),
            ("Restore and resume",
             "The target is restored. Click Resume for real, then Next."),
            ("Pause", "Pauses the session - the feed stops updating."),
            ("Resume", "Resumes - the feed starts updating again."),
            ("Stop and finalize",
             "Writes events_wide.csv, observations_long.csv, and the "
             "manifest - the Finalized screen shows the verified final "
             "CSV row count, distinct from the live snapshot you saw "
             "while recording."),
            ("Open the run folder",
             "Shows exactly where the exported files live."),
        ]

        wizard = tk.Toplevel(self.root)
        wizard.title("Guided demo")
        wizard.attributes("-topmost", True)
        title_var = tk.StringVar()
        body_var = tk.StringVar()
        ttk.Label(wizard, textvariable=title_var,
                 font=("Segoe UI", 12, "bold"),
                 padding=(10, 10, 10, 0)).pack(anchor="w")
        ttk.Label(wizard, textvariable=body_var, wraplength=420,
                 padding=10).pack(anchor="w")
        next_btn = ttk.Button(wizard, text="Next →")
        next_btn.pack(pady=8)
        progress = {"step": 0}

        def finish() -> None:
            if self._demo_session is not None:
                self._demo_session.quit()
                self._demo_session = None
            wizard.destroy()

        def do_step() -> None:
            i = progress["step"]
            if i >= len(steps):
                finish()
                return
            title, body = steps[i]
            title_var.set(f"Step {i + 1}/{len(steps)}: {title}")
            body_var.set(body)
            try:
                self._guided_demo_action(i)
            except Exception as exc:
                body_var.set(f"{body}\n\n(this step's action reported: "
                            f"{exc})")
            progress["step"] += 1
            if progress["step"] >= len(steps):
                next_btn.configure(text="Finish", command=finish)

        next_btn.configure(command=do_step)
        wizard.protocol("WM_DELETE_WINDOW", finish)
        do_step()

    def _guided_demo_action(self, i: int) -> None:
        session = self._demo_session
        if i == 0:
            info = window_client_info(session.ready["hwnd"])
            self.scope = {"type": "window", "hwnd": session.ready["hwnd"],
                          "pid": session.ready["pid"],
                          "title": "Screen2XYZ demo target",
                          "client_w": info["client_w"],
                          "client_h": info["client_h"],
                          "origin_x": info["origin_x"],
                          "origin_y": info["origin_y"]}
            self.scope_label.set(
                f"Screen2XYZ demo target · requested backend: "
                f"{backend_label(self.backend_var.get())}")
            self._drop_controller()
        elif i == 1:
            for name, role in (("X", "x"), ("Y", "y"), ("Z", "z")):
                rect = session.ready["fields"][name]
                src = SourceConfig(
                    source_id=new_source_id(), display_name=name,
                    semantic_role=role, rect=tuple(rect))
                self.sources.append(src)
                # The demo target reports its real field rects, so these are
                # genuine confirmed regions (not placeholders).
                self._confirmed_regions.add(src.source_id)
            self._refresh_table()
            children = self.table.get_children()
            if children:  # select the X row so step 3's Draw region has
                self.table.selection_set(children[0])  # a target field
                self.table.focus(children[0])
        elif i == 2:
            self._test_capture()
        elif i == 3:
            self._draw_region()
        elif i == 4:
            self._preview()
        elif i == 5:
            self._start_recording()
        elif i == 6:
            pass  # nothing to trigger - the scheduler is already ticking
        elif i == 7:
            session.resize(1400, 760)  # the environmental action; the
            # controller detects it on its own next scheduled tick
        elif i == 8:
            pass  # the owner clicks the real "Disarm and re-preview…"
            # button and confirms the real preview gate themselves
        elif i == 9:
            pass  # the owner clicks the real "START RECORDING" button
        elif i == 10:
            session.minimize()
        elif i == 11:
            session.restore()  # the owner then clicks the real Resume
        elif i == 12:
            self._pause()
        elif i == 13:
            self._resume()
        elif i == 14:
            self._stop()
        elif i == 15:
            self._open_run_folder()

    def _run_self_test(self) -> None:
        progress = tk.Toplevel(self.root)
        progress.title("Running self-test")
        status_var = tk.StringVar(value="Starting...")
        ttk.Label(progress, textvariable=status_var, padding=14,
                 width=60).pack()
        result_queue: "queue.Queue[dict]" = queue.Queue()
        progress_queue: "queue.Queue[str]" = queue.Queue()

        def worker() -> None:
            from .. import demo as demo_mod
            report = demo_mod.run_self_test_with_retries(
                on_progress=progress_queue.put)
            result_queue.put(report)

        threading.Thread(target=worker, daemon=True).start()

        def poll() -> None:
            try:
                while True:
                    status_var.set(progress_queue.get_nowait())
            except queue.Empty:
                pass
            try:
                report = result_queue.get_nowait()
            except queue.Empty:
                progress.after(150, poll)
                return
            progress.destroy()
            self._show_self_test_report(report)

        progress.after(150, poll)

    def _show_self_test_report(self, report: dict[str, Any]) -> None:
        dialog = tk.Toplevel(self.root)
        overall = report.get("overall", "FAIL")
        dialog.title(f"Self-test: {overall}")
        color = "#1a7f37" if overall == "PASS" else "#b42318"
        ttk.Label(dialog, text=f"Self-test result: {overall}",
                 font=("Segoe UI", 13, "bold"), foreground=color,
                 padding=(10, 10, 10, 0)).pack(anchor="w")
        body = tk.Text(dialog, width=70, height=20, wrap="word", padx=10,
                       pady=6)
        lines = []
        for name, ok in report.get("checks", {}).items():
            lines.append(f"{'PASS' if ok else 'FAIL'}  {name}")
        if report.get("error"):
            lines.append(f"\nerror: {report['error']}")
        if report.get("attempts", 1) > 1:
            lines.append(f"\n(needed {report['attempts']} attempts - a "
                        f"demo-target timing hiccup, not a product issue)")
        body.insert("1.0", "\n".join(lines))
        body.configure(state="disabled")
        body.pack(fill="both", expand=True)
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=8)

    # -- setup screen -----------------------------------------------------

    def _build_setup(self) -> None:
        for widget in self.root.winfo_children():
            widget.destroy()
        outer = ttk.Frame(self.root, padding=8)
        outer.pack(fill="both", expand=True)

        top = ttk.Frame(outer)
        top.pack(fill="x")
        ttk.Button(top, text="Help", command=self._show_help).pack(
            side="right", padx=2)
        ttk.Button(top, text="How this works",
                  command=self._show_welcome).pack(side="right", padx=2)
        ttk.Button(top, text="Demo mode",
                  command=self._launch_demo).pack(side="right", padx=2)
        ttk.Button(top, text="Guided demo",
                  command=self._guided_demo).pack(side="right", padx=2)
        ttk.Button(top, text="Run full self-test",
                  command=self._run_self_test).pack(side="right", padx=2)

        # -- persistent "next recommended step" card (§8/§9) -----------
        # One always-visible, always-current readout: what state Screen2XYZ
        # thinks it's in, what the last action did, and what to do next -
        # so the owner is never left guessing whether a click did anything.
        next_card = ttk.LabelFrame(outer, text="Next step", padding=8)
        next_card.pack(fill="x", pady=(4, 8))
        self.next_step_headline_var = tk.StringVar(value="")
        self.next_step_detail_var = tk.StringVar(value="")
        ttk.Label(next_card, textvariable=self.next_step_headline_var,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(next_card, textvariable=self.next_step_detail_var,
                 wraplength=980, foreground="#444444").pack(anchor="w")

        # -- Step 1 ---------------------------------------------------
        step1 = ttk.LabelFrame(outer, text="Step 1 — Choose what to capture",
                              padding=8)
        step1.pack(fill="x", pady=(8, 4))
        row1 = ttk.Frame(step1)
        row1.pack(fill="x")
        ttk.Button(row1, text="Select target window…",
                  command=self._select_window).pack(side="left")
        ttk.Button(row1, text="Select monitor…",
                  command=self._select_monitor).pack(side="left", padx=6)
        ttk.Label(row1, text="Backend").pack(side="left", padx=(16, 2))
        # backend_var holds the internal enum token (the source of truth read
        # everywhere); the dropdown shows friendly labels ("Auto
        # (recommended)" / "PrintWindow" / "CopyFromScreen") matching the Help
        # text, and maps the chosen label back to the token. A raw
        # "printwindow_clientonly" must never appear in the menu.
        self.backend_var = tk.StringVar(value=C.BACKEND_AUTO)
        self.backend_display_var = tk.StringVar(
            value=backend_label(C.BACKEND_AUTO))

        def _pick_backend(label: str) -> None:
            self.backend_var.set(backend_value(label))
            self._on_backend_changed()

        ttk.OptionMenu(row1, self.backend_display_var,
                      backend_label(C.BACKEND_AUTO),
                      *[backend_label(b) for b in BACKEND_CHOICES],
                      command=_pick_backend).pack(side="left")
        self.scope_label = tk.StringVar(value="No target selected")
        ttk.Label(step1, textvariable=self.scope_label,
                 wraplength=980).pack(anchor="w", pady=(4, 0))
        self.backend_explain_var = tk.StringVar(
            value=backend_explanation(C.BACKEND_AUTO, None))
        ttk.Label(step1, textvariable=self.backend_explain_var,
                 wraplength=980, foreground="#444444").pack(anchor="w")

        # -- Step 2 ---------------------------------------------------
        step2 = ttk.LabelFrame(outer, text="Step 2 — Test capture",
                              padding=8)
        step2.pack(fill="x", pady=4)
        row2 = ttk.Frame(step2)
        row2.pack(fill="x")
        self.test_capture_btn = ttk.Button(
            row2, text="Test capture now", command=self._test_capture)
        self.test_capture_btn.pack(side="left")
        self.retest_btn = ttk.Button(row2, text="Retest",
                                     command=self._test_capture)
        self.retest_btn.pack(side="left", padx=6)
        # Independent audit (BLOCKER): after 3 consecutive worker setup
        # failures the controller latches setup_worker_blocked=True, and
        # Test capture/Retest can never succeed again until retry_worker()
        # explicitly clears it - previously there was no in-app control
        # that ever called it, a genuine dead end.
        self.retry_worker_btn = ttk.Button(
            row2, text="Retry", command=self._retry_worker, state="disabled")
        self.retry_worker_btn.pack(side="left", padx=6)
        self.test_capture_disabled_reason_var = tk.StringVar(value="")
        ttk.Label(step2, textvariable=self.test_capture_disabled_reason_var,
                 foreground="#b42318", wraplength=980).pack(anchor="w")
        ttk.Button(row2, text="Save diagnostic screenshot locally",
                  command=self._save_diagnostic_setup).pack(side="left",
                                                            padx=6)
        ttk.Button(row2, text="Open diagnostics folder",
                  command=self._open_diagnostics_folder).pack(side="left",
                                                              padx=6)
        result_row = ttk.Frame(step2)
        result_row.pack(fill="x", pady=(8, 0))
        self.test_thumb_label = tk.Label(result_row, text="(no capture yet)",
                                         width=30, height=6, bg="#eeeeee",
                                         relief="groove")
        self.test_thumb_label.pack(side="left")
        detail = ttk.Frame(result_row)
        detail.pack(side="left", fill="both", expand=True, padx=10)
        self.test_verdict_var = tk.StringVar(value="Not tested yet")
        self.test_verdict_label = ttk.Label(
            detail, textvariable=self.test_verdict_var,
            font=("Segoe UI", 12, "bold"))
        self.test_verdict_label.pack(anchor="w")
        self.test_detail_var = tk.StringVar(value="")
        ttk.Label(detail, textvariable=self.test_detail_var,
                 wraplength=650).pack(anchor="w")
        self.test_explain_var = tk.StringVar(value="")
        ttk.Label(detail, textvariable=self.test_explain_var,
                 wraplength=650, foreground="#444444").pack(anchor="w")

        # -- Step 3 -----------------------------------------------------
        step3 = ttk.LabelFrame(outer, text="Step 3 — Add fields and draw "
                                          "regions", padding=8)
        step3.pack(fill="both", expand=True, pady=4)
        controls = ttk.Frame(step3)
        controls.pack(fill="x")
        ttk.Button(controls, text="+ Add field",
                  command=self._add_source).pack(side="left")
        # The checkbox label reflects the ACTUAL state - it used to read
        # "cursor metadata (off)" permanently, still saying "(off)" after
        # the owner turned it on.
        self.cursor_var = tk.BooleanVar(value=False)
        self.cursor_check = ttk.Checkbutton(
            controls, text="Cursor position: off", variable=self.cursor_var,
            command=self._on_cursor_toggled)
        self.cursor_check.pack(side="left", padx=8)
        # retention_var holds the internal key; the dropdown shows friendly
        # labels (no raw "changed_and_errors" in front of the owner) and this
        # caption says what the dropdown is for (it had none).
        ttk.Label(controls, text="Keep").pack(side="left", padx=(8, 2))
        self.retention_var = tk.StringVar(value=C.RETENTION_DEFAULT)
        self.retention_display_var = tk.StringVar(
            value=retention_label(C.RETENTION_DEFAULT))
        ttk.OptionMenu(
            controls, self.retention_display_var,
            retention_label(C.RETENTION_DEFAULT),
            *[retention_label(m) for m in C.RETENTION_MODES],
            command=lambda label: self.retention_var.set(
                retention_key(label))).pack(side="left", padx=8)
        ttk.Label(controls, text="Capture every (ms)").pack(
            side="left", padx=(8, 2))
        self.interval_var = tk.IntVar(value=C.INTERVAL_DEFAULT_MS)
        ttk.Entry(controls, textvariable=self.interval_var,
                  width=7).pack(side="left")
        ttk.Label(controls, text="1000 = once per second",
                 foreground="#444444").pack(side="left", padx=(4, 0))

        columns = ("name", "type", "role", "region", "status", "preview")
        self.table = ttk.Treeview(step3, columns=columns, show="headings",
                                  height=7)
        for col, width in zip(columns, (160, 70, 60, 170, 130, 220)):
            self.table.heading(col, text=col.upper())
            self.table.column(col, width=width)
        self.table.pack(fill="both", expand=True, pady=6)
        self.table.bind("<<TreeviewSelect>>",
                        lambda _e: self._refresh_setup_details())

        self.table.bind("<Double-1>", lambda _e: self._edit_source())
        row = ttk.Frame(step3)
        row.pack(fill="x")
        ttk.Button(row, text="Edit selected…",
                  command=self._edit_source).pack(side="left")
        self.draw_region_btn = ttk.Button(row, text="Draw region…",
                                          command=self._draw_region)
        self.draw_region_btn.pack(side="left", padx=6)
        ttk.Button(row, text="Remove selected",
                  command=self._remove_source).pack(side="left", padx=6)
        ttk.Button(row, text="Review selected regions…",
                  command=self._review_regions).pack(side="left", padx=6)
        ttk.Label(row, text="1. Keep the target visible.  2. Draw region.  "
                           "3. Drag a rectangle around the value only.",
                 foreground="#444444").pack(side="left", padx=12)
        ttk.Button(row, text="Step 4 — Preview all fields →",
                  command=self._preview).pack(side="right")

        # -- retained crop/OCR preview for the selected field (§4: the
        # setup table must keep a visible preview after the picker closes,
        # not only transiently inside it) ------------------------------
        details = ttk.LabelFrame(step3, text="Selected field preview",
                                 padding=6)
        details.pack(fill="x", pady=(4, 0))
        self.setup_detail_thumb = tk.Label(
            details, text="(no preview yet)", width=12, height=4,
            bg="#eeeeee", relief="groove")
        self.setup_detail_thumb.pack(side="left", padx=(0, 8))
        detail_text = ttk.Frame(details)
        detail_text.pack(side="left", fill="x", expand=True)
        self.setup_detail_var = tk.StringVar(
            value="Select a field to see its last captured region here.")
        ttk.Label(detail_text, textvariable=self.setup_detail_var,
                 wraplength=760, justify="left").pack(anchor="w")

        self.status = tk.StringVar(
            value="Add 1–8 fields, edit each (double-click), draw regions, "
                  "then preview.")
        ttk.Label(outer, textvariable=self.status).pack(fill="x", pady=4)
        # source_id -> {"thumb": PhotoImage, "raw_ocr", "normalized",
        # "content_status", "captured_utc", "override"} - the only place
        # setup-time crop/OCR previews live once the picker/review dialog
        # closes.
        self._setup_previews: dict[str, dict[str, Any]] = getattr(
            self, "_setup_previews", {})
        self._refresh_table()

    def _on_backend_changed(self) -> None:
        self.backend_explain_var.set(
            backend_explanation(self.backend_var.get(),
                                self.controller.effective_backend
                                if self.controller else None))
        self.test_verdict_var.set("Not tested yet")
        self.test_detail_var.set("")
        self.test_explain_var.set("")
        self._refresh_next_step()

    def _on_cursor_toggled(self) -> None:
        """Keep the cursor-position checkbox label in step with its state."""
        if hasattr(self, "cursor_check"):
            self.cursor_check.configure(
                text=f"Cursor position: "
                     f"{'on' if self.cursor_var.get() else 'off'}")

    def _ensure_controller(self) -> LiveSessionController | None:
        """Build the controller on first use, or update it in place - never
        silently replace one that already owns a live worker (that used to
        leak the old worker process)."""

        if self.scope is None:
            self.status.set("Select a target first.")
            return None
        backend = self.backend_var.get()
        if self.controller is None:
            env = environment_snapshot(self.scope, backend)
            self.controller = LiveSessionController(
                scope=self.scope, backend=backend, sources=self.sources,
                defaults=self.defaults, environment_snapshot=env)
            self.controller.machine.select_target()
            self.controller.machine.sources_configured()
        else:
            self.controller.sources = self.sources
            self.controller.backend = backend
        return self.controller

    def _select_window(self) -> None:
        windows = list_windows()
        chooser = tk.Toplevel(self.root)
        chooser.title("Select target window")
        # Independent audit MAJOR: without transient+grab_set, this
        # chooser could be raised then lost behind the main window (e.g.
        # after Alt-Tab or any of the app's own topmost windows stealing
        # focus), and the main setup screen stayed fully clickable/
        # editable while a target selection was still pending.
        chooser.transient(self.root)
        chooser.grab_set()
        listbox = tk.Listbox(chooser, width=90, height=20)
        for win in windows:
            listbox.insert("end", f"{win.title}  ·  pid {win.pid}")
        listbox.pack(padx=8, pady=8)

        def choose() -> None:
            index = listbox.curselection()
            if not index:
                return
            win = windows[index[0]]
            info = window_client_info(win.hwnd)
            self.scope = {"type": "window", "hwnd": win.hwnd, "pid": win.pid,
                          "title": win.title, "client_w": info["client_w"],
                          "client_h": info["client_h"],
                          "origin_x": info["origin_x"],
                          "origin_y": info["origin_y"]}
            visible = ("minimized" if info["iconic"] else
                      ("visible" if info["exists"] else "not found"))
            self.scope_label.set(
                f"{win.title}  ·  pid {win.pid}  ·  "
                f"{info['client_w']}×{info['client_h']}  ·  "
                f"DPI {info['dpi']}  ·  {visible}  ·  requested backend: "
                f"{backend_label(self.backend_var.get())}")
            self._drop_controller()  # a new target needs a fresh controller
            # A new target has not been tested yet - a stale PASS/FAIL from
            # the PREVIOUS target must never keep showing here (§10).
            self.test_verdict_var.set("Not tested yet")
            self.test_detail_var.set("")
            self.test_explain_var.set("")
            # BLOCKER (independent audit): every field's rect was drawn
            # against the PREVIOUS target's pixel layout. Without clearing
            # this, the setup table kept showing "region set" plus the old
            # target's thumbnail, and nothing stopped Preview/Arm/Start from
            # silently running against a completely wrong window using
            # leftover coordinates - the picker's own blank/near-uniform
            # safeguards are bypassed entirely since preview() is never
            # re-run against the new target. Force every field back to
            # "no region drawn" so each must be redrawn/reconfirmed here.
            self._confirmed_regions = set()
            self._setup_previews = {}
            self._refresh_table()
            self._refresh_next_step()
            chooser.grab_release()
            chooser.destroy()

        def cancel() -> None:
            chooser.grab_release()
            chooser.destroy()

        # Second independent audit MINOR: making this dialog modal
        # (grab_set above) means the only way out used to be the OS
        # window-close button - an explicit Cancel matches _draw_region's
        # countdown bar and the Preview gate's "Back to setup".
        chooser.protocol("WM_DELETE_WINDOW", cancel)
        buttons = ttk.Frame(chooser)
        buttons.pack(pady=4)
        ttk.Button(buttons, text="Select", command=choose).pack(
            side="left", padx=4)
        ttk.Button(buttons, text="Cancel", command=cancel).pack(
            side="left", padx=4)

    def _select_monitor(self) -> None:
        # §5: actually show a chooser (the "…" label promised one) so a
        # multi-monitor user can target any monitor, not silently monitor 0;
        # and give explicit feedback when none are found.
        monitors = list_monitors()
        if not monitors:
            self.status.set("No monitors were detected.")
            return

        def commit(m) -> None:
            self.scope = {"type": "monitor",
                          "monitor": {"x": m.x, "y": m.y, "w": m.w, "h": m.h},
                          "monitor_id": m.index}
            self.scope_label.set(
                f"Monitor {m.index} ({m.w}×{m.h})  ·  requested backend: "
                f"{backend_label(self.backend_var.get())}  ·  occluding "
                f"windows WILL be captured (CopyFromScreen sees whatever is "
                f"on screen)")
            self._drop_controller()
            self.test_verdict_var.set("Not tested yet")
            self.test_detail_var.set("")
            self.test_explain_var.set("")
            # Independent audit (adversarial recovery pass): the sibling of
            # the fix already applied to _select_window's choose() - every
            # field's rect was drawn against the PREVIOUS target's pixel
            # layout, so it must be cleared here too, not just for the
            # window-picker path.
            self._confirmed_regions = set()
            self._setup_previews = {}
            self._refresh_table()
            self._refresh_next_step()

        if len(monitors) == 1:
            commit(monitors[0])
            return
        chooser = tk.Toplevel(self.root)
        chooser.title("Select monitor")
        chooser.transient(self.root)
        chooser.grab_set()  # independent audit MAJOR - see _select_window
        listbox = tk.Listbox(chooser, width=60, height=min(12,
                                                           len(monitors)))
        for m in monitors:
            listbox.insert("end", f"Monitor {m.index}  ·  {m.w}×{m.h}  ·  "
                                  f"at ({m.x}, {m.y})")
        listbox.pack(padx=8, pady=8)

        def choose() -> None:
            sel = listbox.curselection()
            if not sel:
                return
            commit(monitors[sel[0]])
            chooser.grab_release()
            chooser.destroy()

        def cancel() -> None:
            chooser.grab_release()
            chooser.destroy()

        chooser.protocol("WM_DELETE_WINDOW", cancel)  # see _select_window
        buttons = ttk.Frame(chooser)
        buttons.pack(pady=4)
        ttk.Button(buttons, text="Select", command=choose).pack(
            side="left", padx=4)
        ttk.Button(buttons, text="Cancel", command=cancel).pack(
            side="left", padx=4)

    def _add_source(self) -> None:
        if len([s for s in self.sources if s.enabled]) >= C.SOURCE_COUNT_MAX:
            self.status.set("Maximum of 8 fields.")
            return
        source = SourceConfig(source_id=new_source_id(),
                              display_name=f"Field {len(self.sources) + 1}",
                              rect=(10, 10 + 40 * len(self.sources), 180, 28))
        self.sources.append(source)
        self._refresh_table()
        # Auto-select the new row so "Draw region…"/"Edit…"/"Remove" act on
        # the obvious target immediately (usability: with nothing selected,
        # those buttons only set the easily-missed status line and looked
        # broken to an impatient owner).
        children = self.table.get_children()
        if children:
            self.table.selection_set(children[-1])
            self.table.focus(children[-1])
            self._refresh_setup_details()
        self.status.set(f"Added {source.display_name}. Now click "
                       f"“Draw region…” to mark where its value is.")

    def _remove_source(self) -> None:
        index = self.table.index(self.table.focus()) \
            if self.table.focus() else None
        if index is None or not (0 <= index < len(self.sources)):
            # Give feedback rather than a completely silent no-op.
            self.status.set("Select a field row first.")
            return
        removed = self.sources[index]
        self._confirmed_regions.discard(removed.source_id)
        self._setup_previews.pop(removed.source_id, None)
        del self.sources[index]
        self._refresh_table()

    def _refresh_table(self) -> None:
        # Adversarial review finding (2026-07-21, pre-existing but exposed
        # by this session's own new offer_type_fix() call site): once
        # _build_recording() has destroyed the setup screen's Treeview
        # (e.g. via _disarm_and_repreview() re-opening the preview gate),
        # this used to be an unconditional TclError - the same "off the
        # setup screen" no-op guard _refresh_next_step already documents
        # and applies for exactly this reason.
        if not hasattr(self, "table") or not self.table.winfo_exists():
            return
        self.table.delete(*self.table.get_children())
        for source in self.sources:
            has_region = source.source_id in self._confirmed_regions
            preview = self._setup_previews.get(source.source_id)
            if preview:
                preview_text = (f"{preview.get('normalized', '—')} · "
                               f"{preview.get('content_status', '')}")
            else:
                preview_text = "(no preview yet)"
            # The REGION cell used to show the placeholder rect even before a
            # region was drawn, contradicting the STATUS cell ("no region
            # drawn") - a first-timer saw concrete coordinates and a "nothing
            # drawn" status at once. Show the coordinates only once the region
            # is actually confirmed.
            region_text = (f"{source.rect[0]},{source.rect[1]} "
                          f"{source.rect[2]}×{source.rect[3]}"
                          if has_region else "(not drawn)")
            self.table.insert("", "end", values=(
                source.display_name, source.data_type, source.semantic_role,
                region_text,
                "region set" if has_region else "no region drawn",
                preview_text))
        self._refresh_setup_details()
        self._refresh_next_step()

    def _refresh_next_step(self) -> None:
        """Recompute and render the persistent next-step card + Test
        capture/Retest enablement (§8/§9/§11) from the single pure
        `derive_next_step`/`can_test_capture` source of truth. A no-op if
        the setup screen's widgets are not the current screen (e.g. a
        Toplevel dialog is refreshing the table in the background)."""

        # The StringVars survive a screen swap, so hasattr() alone would
        # pass after _build_ready/_build_recording destroyed the setup
        # widgets and then configure a destroyed test_capture_btn (a
        # TclError). Gate on the actual widget still existing so the
        # docstring's "no-op off the setup screen" promise genuinely holds.
        if not hasattr(self, "test_capture_btn") or \
                not self.test_capture_btn.winfo_exists():
            return
        controller_state = self.controller.machine.state \
            if self.controller is not None else None
        enabled_fields = [s for s in self.sources if s.enabled]
        all_confirmed = bool(enabled_fields) and all(
            s.source_id in self._confirmed_regions for s in enabled_fields)
        view = derive_next_step(
            has_target=self.scope is not None,
            controller_state=controller_state,
            capture_tested=getattr(self, "test_verdict_var", None) is not None
            and self.test_verdict_var.get() != "Not tested yet",
            capture_verdict=(self.test_verdict_var.get()
                            if getattr(self, "test_verdict_var", None)
                            is not None
                            and self.test_verdict_var.get() != "Not tested yet"
                            else None),
            enabled_field_count=len(enabled_fields),
            all_regions_confirmed=all_confirmed,
            preview_confirmed=(
                self.controller is not None
                and self.controller.machine.preview_confirmed_revision
                == self.controller.machine.configuration_revision))
        self.next_step_headline_var.set(view["headline"])
        self.next_step_detail_var.set(
            f"{view['detail']} Next: {view['primary_action']}.")
        blocked = bool(self.controller is not None
                      and self.controller.machine.setup_worker_blocked)
        allowed, reason = can_test_capture(
            controller_state, self.scope is not None,
            setup_worker_blocked=blocked)
        state = "normal" if allowed else "disabled"
        self.test_capture_btn.configure(state=state)
        self.retest_btn.configure(state=state)
        self.test_capture_disabled_reason_var.set("" if allowed else reason)
        self.retry_worker_btn.configure(
            state="normal" if blocked else "disabled")
        # region_snapshot is worker-dependent (statemachine._WORKER_DEPENDENT)
        # exactly like Test capture/Retest - Draw region was the one caller
        # of it that never reflected the blocked latch, so it kept looking
        # clickable and kept leading into the same dead end.
        if hasattr(self, "draw_region_btn") and \
                self.draw_region_btn.winfo_exists():
            self.draw_region_btn.configure(
                state="disabled" if blocked else "normal")

    def _record_setup_preview(self, source_id: str, *, thumb_b64: str | None,
                              raw_ocr: str, normalized: Any,
                              content_status: str, capture_status: str,
                              ocr_status: str, override: str | None = None
                              ) -> None:
        """The single place a field's setup-time crop/OCR preview is stored
        so it survives after the picker/preview-gate/review dialog closes -
        called from the picker's one-shot preview, the Step 4 preview gate,
        and Re-test all regions."""

        from datetime import datetime, timezone
        entry: dict[str, Any] = {
            "raw_ocr": raw_ocr, "normalized": normalized,
            "content_status": content_status,
            "capture_status": capture_status, "ocr_status": ocr_status,
            "captured_utc": datetime.now(timezone.utc).isoformat(),
        }
        if override:
            entry["override"] = override
        if thumb_b64:
            try:
                entry["thumb"] = tk.PhotoImage(
                    master=self.root, data=base64.b64decode(thumb_b64))
            except tk.TclError:
                pass
        self._setup_previews[source_id] = entry

    def _refresh_setup_details(self) -> None:
        if not hasattr(self, "setup_detail_var"):
            return
        index = self._selected_index()
        if index is None or index >= len(self.sources):
            self.setup_detail_var.set(
                "Select a field to see its last captured region here.")
            self.setup_detail_thumb.configure(image="", text="(no preview "
                                                              "yet)")
            return
        source = self.sources[index]
        preview = self._setup_previews.get(source.source_id)
        if not preview:
            self.setup_detail_var.set(
                f"{source.display_name}: no preview yet - Draw region or "
                f"run Preview to capture one.")
            self.setup_detail_thumb.configure(image="", text="(no preview "
                                                              "yet)")
            return
        thumb = preview.get("thumb")
        if thumb is not None:
            self.setup_detail_thumb.configure(image=thumb, text="",
                                             width=0, height=0)
        else:
            self.setup_detail_thumb.configure(image="", text="(no crop)",
                                             width=12, height=4)
        override_note = (f" · CONFIRMED VIA ADVANCED OVERRIDE: "
                        f"{preview['override']}"
                        if preview.get("override") else "")
        self.setup_detail_var.set(
            f"{source.display_name} · last captured "
            f"{preview.get('captured_utc', '')}\n"
            f"Raw OCR: {preview.get('raw_ocr', '')!r}\n"
            f"Normalized: {preview.get('normalized')}\n"
            f"Capture: {preview.get('capture_status')} · OCR: "
            f"{preview.get('ocr_status')} · Content: "
            f"{preview.get('content_status')}{override_note}")

    def _selected_index(self) -> int | None:
        focus = self.table.focus()
        if not focus:
            return None
        index = self.table.index(focus)
        return index if 0 <= index < len(self.sources) else None

    def _edit_source(self) -> None:
        index = self._selected_index()
        if index is None:
            self.status.set("Select a field row first.")
            return
        source = self.sources[index]
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit field")
        name_var = tk.StringVar(value=source.display_name)
        type_var = tk.StringVar(value=source.data_type)
        role_var = tk.StringVar(value=source.semantic_role)
        rect_var = tk.StringVar(
            value=f"{source.rect[0]},{source.rect[1]},"
                  f"{source.rect[2]},{source.rect[3]}")
        # Phase 2: several fields can share ONE drawn region over a combined
        # overlay line (e.g. lat+long+elev on one thin readout line) by each
        # picking a different whitespace-separated "part" of that region's
        # OCR text. Blank means "parse the whole region" - unchanged, single
        # -value behavior.
        line_part_var = tk.StringVar(
            value="" if source.line_part is None else str(source.line_part))
        other_names = [s.display_name for s in self.sources
                      if s.source_id != source.source_id]
        copy_from_var = tk.StringVar(value="")
        for label, widget in (
                ("Name", ttk.Entry(dialog, textvariable=name_var, width=24)),
                ("Type", ttk.OptionMenu(dialog, type_var, source.data_type,
                                        *C.DATA_TYPES)),
                ("Role", ttk.OptionMenu(dialog, role_var, source.semantic_role,
                                        *C.SEMANTIC_ROLES)),
                ("Rect x,y,w,h", ttk.Entry(dialog, textvariable=rect_var,
                                           width=24)),
                ("Copy region from", ttk.OptionMenu(
                    dialog, copy_from_var, "", *other_names)),
                ("Line part (optional)", ttk.Entry(
                    dialog, textvariable=line_part_var, width=6))):
            line = ttk.Frame(dialog)
            line.pack(fill="x", padx=8, pady=3)
            ttk.Label(line, text=label, width=14).pack(side="left")
            widget.pack(side="left")
        ttk.Label(dialog, foreground="#666666", wraplength=320, justify="left",
                 text="Same-line values (e.g. latitude and longitude on one "
                      "readout): draw the region around the WHOLE line once, "
                      "then give each field the same rect and a different "
                      "line part - 0 for the first value, 1 for the second, "
                      "and so on. \"Copy region from\" fills the rect from "
                      "another field for you."
                 ).pack(fill="x", padx=8, pady=(0, 4))

        def on_copy_from(*_args) -> None:
            chosen = copy_from_var.get()
            for other in self.sources:
                if other.display_name == chosen:
                    rect_var.set(f"{other.rect[0]},{other.rect[1]},"
                                 f"{other.rect[2]},{other.rect[3]}")
                    break
        copy_from_var.trace_add("write", on_copy_from)

        def apply() -> None:
            source.display_name = name_var.get().strip()
            source.data_type = type_var.get()
            source.semantic_role = role_var.get()
            try:
                x, y, w, h = (int(v) for v in rect_var.get().split(","))
                source.rect = (x, y, w, h)
                # An explicit manual rect entry counts as a confirmed region
                # (the user typed real coordinates), so Preview is unblocked.
                if w > 0 and h > 0:
                    self._confirmed_regions.add(source.source_id)
            except ValueError:
                messagebox.showwarning("Invalid rect",
                                       "Use x,y,w,h integers.")
                return
            part_text = line_part_var.get().strip()
            if not part_text:
                source.line_part = None
            else:
                try:
                    part = int(part_text)
                    if part < 0:
                        raise ValueError
                    source.line_part = part
                except ValueError:
                    messagebox.showwarning(
                        "Invalid line part",
                        "Line part must be blank or a whole number "
                        "(0, 1, 2, ...).")
                    return
            # `coordinate` (Phase 1) is a number-shaped value - lat/long
            # fields need it to survive OCR's degree-symbol corruption and
            # still be eligible for X/Y/Z, so only clear the role for
            # data types that are genuinely non-numeric (text/auto).
            if source.data_type not in ("number", "coordinate") and \
                    source.semantic_role in ("x", "y", "z"):
                source.semantic_role = "none"
                messagebox.showinfo(
                    "Role cleared",
                    "X/Y/Z require a number or coordinate field.")
            dialog.destroy()
            self._refresh_table()

        ttk.Button(dialog, text="Apply", command=apply).pack(pady=8)

    # -- test capture (Step 2) --------------------------------------------

    def _retry_worker(self) -> None:
        """Clears setup_worker_blocked after 3 consecutive setup failures
        (independent audit BLOCKER: this was previously unreachable from
        the UI, so a triple-failure permanently bricked Test capture with
        no way out other than reselecting the target)."""

        if self.controller is None:
            return
        self.status.set("Retrying capture worker…")
        self.root.update_idletasks()
        try:
            self.controller.retry_worker()
            self.status.set("Worker retry succeeded - test capture again.")
        except WorkerError as exc:
            self.status.set(f"Retry failed: {exc.detail}")
        except IllegalAction:
            pass
        self._refresh_next_step()

    def _test_capture(self) -> None:
        controller = self._ensure_controller()
        if controller is None:
            return
        self.status.set("Testing capture…")
        self.root.update_idletasks()
        try:
            controller.ensure_worker()
            reply = controller.test_capture()
        except WorkerError as exc:
            self.test_verdict_var.set("FAIL")
            self.test_verdict_label.configure(foreground="#b42318")
            self.test_explain_var.set(f"Worker error: {exc.detail}")
            self.status.set("Test capture failed.")
            self._refresh_next_step()
            return
        verdict, explanation = classify_capture_test(
            reply.get("capture_status", ""),
            reply.get("frame_content_status", ""),
            bool(reply.get("no_backend_usable")))
        color = {"PASS": "#1a7f37", "WARNING": "#b58900",
                "FAIL": "#b42318"}[verdict]
        self.test_verdict_var.set(verdict)
        self.test_verdict_label.configure(foreground=color)
        window = reply.get("window") or {}
        self.test_detail_var.set(
            f"{window.get('client_w')}×{window.get('client_h')} · "
            f"DPI {window.get('dpi')} · captured in "
            f"{reply.get('capture_ms', '?')} ms · effective backend: "
            f"{backend_label(reply.get('effective_backend'))}")
        self.test_explain_var.set(explanation)
        self.backend_explain_var.set(
            backend_explanation(self.backend_var.get(),
                                controller.effective_backend))
        b64 = reply.get("frame_png_b64")
        if b64:
            try:
                image = tk.PhotoImage(master=self.root, data=base64.b64decode(b64))
                factor = picker_scale_factor(image.width(), image.height(),
                                            260, 140)
                if factor > 1:
                    image = image.subsample(factor, factor)
                self._test_thumb_image = image
                self.test_thumb_label.configure(image=image, text="",
                                                width=0, height=0)
            except tk.TclError:
                self.test_thumb_label.configure(text="(preview unavailable)")
        self.status.set(f"Test capture: {verdict}.")
        self._refresh_next_step()

    def _save_diagnostic_setup(self) -> None:
        controller = self.controller
        if controller is None or controller.effective_backend is None:
            messagebox.showinfo("Nothing to save",
                                "Run Test capture first.")
            return
        try:
            reply = controller.region_snapshot(probe_backend=False)
        except WorkerError as exc:
            messagebox.showwarning("Snapshot failed", exc.detail)
            return
        b64 = reply.get("frame_png_b64")
        if not b64:
            messagebox.showinfo("Nothing to save", "No frame captured.")
            return
        out_dir = diagnostics_root()
        out_dir.mkdir(parents=True, exist_ok=True)
        from ..paths import new_diagnostic_id, resolve_under
        snap_dir = resolve_under(out_dir, new_diagnostic_id())
        snap_dir.mkdir(parents=True, exist_ok=True)
        (snap_dir / "setup_frame.png").write_bytes(base64.b64decode(b64))
        messagebox.showinfo("Saved", f"Saved locally to:\n{snap_dir}\n\n"
                                     "This is never uploaded.")

    def _open_diagnostics_folder(self) -> None:
        path = diagnostics_root()
        path.mkdir(parents=True, exist_ok=True)
        self._open_folder(path)

    def _open_folder(self, path) -> None:
        try:
            os.startfile(str(path))  # noqa: S606 - Windows-only, no shell
        except OSError as exc:
            messagebox.showwarning("Could not open folder", str(exc))

    # -- region drawing -----------------------------------------------------

    def _draw_region(self) -> None:
        """Region snapshot picker with a NON-BLOCKING countdown (§4). The old
        blocking 3 s sleep froze the whole UI (window unmovable, no
        countdown, no cancel - it looked hung). Now a root.after countdown
        ticks the status label each second and offers Cancel, then takes the
        snapshot in the final callback."""

        index = self._selected_index()
        if index is None:
            self.status.set("Select a field row first.")
            return
        controller = self._ensure_controller()
        if controller is None:
            return
        if getattr(self, "_draw_countdown_active", False):
            return  # ignore re-entrant clicks during a countdown
        self._draw_countdown_active = True
        source = self.sources[index]

        bar = tk.Toplevel(self.root)
        bar.title("Draw region")
        bar.transient(self.root)
        bar.attributes("-topmost", True)
        # Independent audit MAJOR: without a grab, the main setup screen
        # stayed fully clickable during the 3s countdown - selecting a
        # different target or removing this field mid-countdown left the
        # final tick(0) callback operating on the `source`/`controller`/
        # `index` this closure captured at the START of the countdown,
        # silently stale by the time it actually fires.
        bar.grab_set()
        msg = tk.StringVar()
        ttk.Label(bar, textvariable=msg, padding=12,
                 font=("Segoe UI", 11)).pack()
        cancelled = {"v": False}

        def cancel() -> None:
            cancelled["v"] = True
            self._draw_countdown_active = False
            bar.grab_release()
            bar.destroy()
            self.status.set("Draw region cancelled.")

        ttk.Button(bar, text="Cancel", command=cancel).pack(pady=(0, 10))
        bar.protocol("WM_DELETE_WINDOW", cancel)

        def tick(remaining: int) -> None:
            if cancelled["v"]:
                return
            if remaining > 0:
                msg.set(f"Move the pointer to the target for field "
                       f"'{source.display_name}'.\nCapturing the snapshot in "
                       f"{remaining} s…  (Cancel to abort)")
                self.root.after(1000, lambda: tick(remaining - 1))
                return
            bar.grab_release()
            bar.destroy()
            self._draw_countdown_active = False
            try:
                controller.ensure_worker()
                reply = controller.region_snapshot()
            except WorkerError as exc:
                self.status.set(f"Snapshot failed ({exc.detail}); set the "
                               f"rect via Edit selected instead.")
                return
            except IllegalAction:
                # Repeated real-worker failures against the live target can
                # latch setup_worker_blocked between the click and this
                # callback firing - region_snapshot() then raises
                # IllegalAction, not WorkerError, and previously fell
                # through to the generic top-level handler with no mention
                # of Retry (same class of gap already fixed for
                # pause/resume's IllegalAction branches).
                self.status.set(
                    "Snapshot blocked - the capture worker needs a Retry "
                    "(Step 2, next to Test capture) before drawing can "
                    "continue."
                    if controller.machine.setup_worker_blocked else
                    "Snapshot could not run right now; check the setup "
                    "and try again.")
                self._refresh_next_step()
                return
            self._show_snapshot_picker(index, reply)

        tick(3)

    def _flash_row(self, index: int) -> None:
        children = self.table.get_children()
        if index >= len(children):
            return
        item = children[index]
        self.table.tag_configure("flash", background="#fff3b0")
        self.table.item(item, tags=("flash",))

        def clear() -> None:
            if item in self.table.get_children():
                self.table.item(item, tags=())

        self.root.after(1200, clear)

    def _show_snapshot_picker(self, index: int, reply: dict) -> None:
        """REGION SELECTION MODE: an explicit, unmistakable modal picker.

        State model: NO_SELECTION -> DRAGGING -> SELECTION_READY ->
        CONFIRMED / CANCELLED (layout.region_on_*). A simple click never
        creates a region; Confirm stays disabled until a real drag, in
        bounds, produced a non-blank crop; Esc cancels without touching the
        field's previously confirmed rect.
        """

        source = self.sources[index]
        window = reply.get("window") or {}
        native_w = window.get("client_w", 800)
        native_h = window.get("client_h", 400)
        b64 = reply.get("frame_png_b64")

        # §6: cap the canvas to the ACTUAL screen (minus ~300px of picker
        # chrome: banner, status, zoom row, preview panel, button row) so the
        # snapshot never grows the picker taller/wider than the display and
        # pushes Confirm/Redraw/Cancel off the bottom edge on a small or
        # high-DPI laptop.
        pmax_w = max(400, self.root.winfo_screenwidth() - 60)
        pmax_h = max(300, self.root.winfo_screenheight() - 300)

        def _picker_scale() -> int:
            return picker_scale_factor(native_w, native_h, pmax_w, pmax_h)

        picker = tk.Toplevel(self.root)
        picker.title("Region selection mode")
        picker.transient(self.root)
        picker.grab_set()

        banner = tk.Frame(picker, bg="#7a1f1f")
        banner.pack(fill="x")
        tk.Label(banner, bg="#7a1f1f", fg="white",
                font=("Segoe UI", 14, "bold"), pady=6,
                text=f"REGION SELECTION MODE — Field: "
                     f"{source.display_name}").pack()
        tk.Label(banner, bg="#7a1f1f", fg="white", font=("Segoe UI", 10),
                text="Drag a rectangle around the value Screen2XYZ should "
                     "read. Press Esc to cancel.").pack(pady=(0, 6))

        status_var = tk.StringVar()
        ttk.Label(picker, textvariable=status_var,
                 foreground="#444444").pack(anchor="w", padx=6, pady=(4, 0))

        state: dict[str, Any] = {
            "mode": REGION_NO_SELECTION,
            "scale": _picker_scale(),
            "rect": None,
            # The exact client size/DPI this screenshot was taken against -
            # used to block Confirm if the target resizes/DPI-changes while
            # the picker is open (§4 "stale screenshot").
            "snapshot_w": native_w, "snapshot_h": native_h,
            "snapshot_dpi": window.get("dpi"),
        }
        override_var = tk.BooleanVar(value=False)
        full_image = None
        if b64:
            try:
                full_image = tk.PhotoImage(master=picker,
                                          data=base64.b64decode(b64))
            except tk.TclError:
                full_image = None
        image_holder: dict[str, Any] = {}
        thumb_ref: dict[str, Any] = {}

        def target_name() -> str:
            return (self.scope or {}).get("title") or \
                ("Monitor" if self.scope and
                 self.scope.get("type") == "monitor" else "target")

        def update_status() -> None:
            eff = self.controller.effective_backend if self.controller \
                else None
            zoom_pct = round(100 / state["scale"])
            label = {REGION_NO_SELECTION: "Selection mode active - drag "
                                          "to select",
                    REGION_DRAGGING: "Selection mode active - dragging…",
                    REGION_SELECTION_READY: "Selection mode active - "
                                            "region ready to confirm"}
            status_var.set(
                f"{label.get(state['mode'], 'Selection mode active')} · "
                f"target: {target_name()} · effective backend: {eff} · "
                f"zoom: {zoom_pct}%")

        controls = ttk.Frame(picker)
        controls.pack(fill="x", padx=6)

        def redraw_base() -> None:
            canvas.delete("all")
            if full_image is None:
                canvas.configure(width=min(native_w, 1200),
                                height=min(native_h, 700))
                canvas.create_text(
                    10, 10, anchor="nw", fill="white",
                    text="(snapshot preview unavailable; drag to set the "
                         "rectangle at native size)")
                return
            factor = state["scale"]
            shown = full_image.subsample(factor, factor) if factor > 1 \
                else full_image
            image_holder["image"] = shown
            canvas.configure(width=shown.width(), height=shown.height())
            canvas.create_image(0, 0, anchor="nw", image=shown,
                               tags=("base",))
            redraw_overlay()

        def redraw_overlay() -> None:
            canvas.delete("overlay")
            rect = state["rect"]
            if not rect or full_image is None:
                return
            img = image_holder.get("image")
            cw = img.width() if img else min(native_w, 1200)
            ch = img.height() if img else min(native_h, 700)
            factor = state["scale"]
            x, y, w, h = rect
            sx0, sy0 = x / factor, y / factor
            sx1, sy1 = (x + w) / factor, (y + h) / factor
            # Dim everything outside the selection with four stippled
            # rectangles (a real spotlight effect without an imaging lib).
            for cx0, cy0, cx1, cy1 in ((0, 0, cw, sy0), (0, sy1, cw, ch),
                                      (0, sy0, sx0, sy1),
                                      (sx1, sy0, cw, sy1)):
                if cx1 > cx0 and cy1 > cy0:
                    canvas.create_rectangle(cx0, cy0, cx1, cy1, fill="black",
                                           stipple="gray50", outline="",
                                           tags=("overlay",))
            canvas.create_rectangle(sx0, sy0, sx1, sy1, outline="#00e5ff",
                                   width=2, fill="#00e5ff", stipple="gray12",
                                   tags=("overlay",))

        def set_scale(new_scale: int) -> None:
            state["scale"] = max(1, new_scale)
            redraw_base()
            update_status()

        ttk.Button(controls, text="Zoom in",
                  command=lambda: set_scale(state["scale"] - 1)).pack(
            side="left", padx=2, pady=4)
        ttk.Button(controls, text="Zoom out",
                  command=lambda: set_scale(state["scale"] + 1)).pack(
            side="left", padx=2)
        ttk.Button(controls, text="Fit to window",
                  command=lambda: set_scale(_picker_scale())).pack(
            side="left", padx=2)
        ttk.Button(controls, text="100%",
                  command=lambda: set_scale(1)).pack(side="left", padx=2)
        dims_var = tk.StringVar(value="")
        ttk.Label(controls, textvariable=dims_var,
                 font=("Consolas", 10)).pack(side="left", padx=12)

        canvas = tk.Canvas(picker, bg="grey", cursor="crosshair")
        canvas.pack(fill="both", expand=True, padx=6, pady=4)

        preview_frame = ttk.Frame(picker)
        preview_frame.pack(fill="x", padx=6, pady=(0, 4))

        def clear_preview_panel() -> None:
            for widget in preview_frame.winfo_children():
                widget.destroy()

        def run_one_shot_preview(rect: tuple[int, int, int, int]) -> None:
            temp_source = SourceConfig(
                source_id=source.source_id,
                display_name=source.display_name,
                data_type=source.data_type,
                semantic_role=source.semantic_role,
                unit=source.unit,
                decimal_separator=source.decimal_separator,
                rect=rect, upscale_factor=source.upscale_factor)
            try:
                reply2 = self.controller.preview_single_region(temp_source)
            except WorkerError as exc:
                clear_preview_panel()
                ttk.Label(preview_frame, text=f"Preview failed: "
                                              f"{exc.detail}",
                         foreground="#b42318").pack(anchor="w")
                confirm_btn.configure(state="disabled")
                return
            region_obs = reply2.get("region_preview") or {}
            clear_preview_panel()
            thumb_label = tk.Label(preview_frame, text="(no crop)",
                                   width=10, height=3, bg="#eeeeee",
                                   relief="groove")
            crop_b64 = region_obs.get("crop_png_b64")
            if crop_b64:
                try:
                    thumb_ref["image"] = tk.PhotoImage(
                        master=picker, data=base64.b64decode(crop_b64))
                    thumb_label.configure(image=thumb_ref["image"], text="",
                                         width=0, height=0)
                except tk.TclError:
                    pass
            thumb_label.pack(side="left", padx=6)
            detail = ttk.Frame(preview_frame)
            detail.pack(side="left", fill="x", expand=True)
            ttk.Label(detail, text=f"Region: x={rect[0]} y={rect[1]} "
                                   f"w={rect[2]} h={rect[3]}").pack(
                anchor="w")
            ttk.Label(detail, text=f"Raw OCR: "
                                   f"{region_obs.get('raw_text', '')!r}"
                      ).pack(anchor="w")
            ttk.Label(detail, text=f"Normalized: "
                                   f"{region_obs.get('normalized_value')}"
                      ).pack(anchor="w")
            content_status = region_obs.get("crop_content_status",
                                            "NOT_EVALUATED")
            ttk.Label(detail, text=f"Capture: "
                                   f"{region_obs.get('capture_status')} · "
                                   f"OCR: {region_obs.get('ocr_status')} · "
                                   f"Parse: "
                                   f"{region_obs.get('parse_status')} · "
                                   f"Content: {content_status}").pack(
                anchor="w")
            state["rect"] = rect
            state["content_status"] = content_status
            state["has_crop"] = bool(crop_b64)
            self._record_setup_preview(
                source.source_id, thumb_b64=crop_b64,
                raw_ocr=region_obs.get("raw_text", ""),
                normalized=region_obs.get("normalized_value"),
                content_status=content_status,
                capture_status=region_obs.get("capture_status", ""),
                ocr_status=region_obs.get("ocr_status", ""))
            override_var.set(False)
            if content_status == "NEAR_UNIFORM_OTHER":
                ttk.Checkbutton(
                    detail, text="Use anyway (advanced) - this crop looks "
                                "like a single flat color; only choose "
                                "this if you know that is correct",
                    variable=override_var,
                    command=update_confirm_gate).pack(anchor="w", pady=(2, 0))
            update_confirm_gate()
            if not region_confirm_allowed(
                    rect[0], rect[1], rect[2], rect[3], native_w, native_h,
                    C.REGION_MIN_PX, bool(crop_b64), content_status,
                    allow_near_uniform_other=True):
                ttk.Label(detail, text="⚠ This crop looks blank/near-"
                                       "uniform - drag again over the "
                                       "visible value.",
                         foreground="#b58900").pack(anchor="w")

        def update_confirm_gate() -> None:
            rect = state.get("rect")
            if not rect:
                confirm_btn.configure(state="disabled")
                return
            allowed = region_confirm_allowed(
                rect[0], rect[1], rect[2], rect[3], native_w, native_h,
                C.REGION_MIN_PX, state.get("has_crop", False),
                state.get("content_status", "NOT_EVALUATED"),
                allow_near_uniform_other=override_var.get())
            confirm_btn.configure(state=("normal" if allowed else
                                        "disabled"))

        drag = {"x0": 0, "y0": 0}

        def press(event) -> None:
            if state["mode"] == REGION_CONFIRMED:
                return
            state["mode"] = region_on_press(state["mode"])
            drag["x0"], drag["y0"] = event.x, event.y
            state["rect"] = None
            clear_preview_panel()
            confirm_btn.configure(state="disabled")
            redraw_overlay()
            update_status()

        def clamped_canvas_xy(event) -> tuple[int, int]:
            img = image_holder.get("image")
            max_x = img.width() if img else native_w // state["scale"]
            max_y = img.height() if img else native_h // state["scale"]
            return (min(max(event.x, 0), max_x),
                    min(max(event.y, 0), max_y))

        def move(event) -> None:
            if state["mode"] != REGION_DRAGGING:
                return
            cx, cy = clamped_canvas_xy(event)
            rect = region_drag_rect(drag["x0"], drag["y0"], cx, cy,
                                   state["scale"], native_w, native_h)
            state["rect"] = rect
            dims_var.set(f"x={rect[0]} y={rect[1]} w={rect[2]} "
                        f"h={rect[3]} (physical px)")
            redraw_overlay()

        def release(event) -> None:
            if state["mode"] != REGION_DRAGGING:
                return
            move(event)
            rect = state["rect"] or (0, 0, 0, 0)
            state["mode"] = region_on_release(rect[2], rect[3],
                                             C.REGION_MIN_PX)
            update_status()
            if state["mode"] == REGION_SELECTION_READY:
                run_one_shot_preview(rect)
            else:
                state["rect"] = None
                redraw_overlay()

        canvas.bind("<ButtonPress-1>", press)
        canvas.bind("<B1-Motion>", move)
        canvas.bind("<ButtonRelease-1>", release)

        buttons = ttk.Frame(picker)
        buttons.pack(fill="x", pady=8, padx=6)

        def do_redraw() -> None:
            state["mode"] = region_on_redraw(state["mode"])
            state["rect"] = None
            clear_preview_panel()
            redraw_overlay()
            confirm_btn.configure(state="disabled")
            update_status()

        def do_cancel() -> None:
            state["mode"] = region_on_cancel(state["mode"])
            picker.grab_release()
            picker.destroy()
            self.status.set(f"Selection cancelled; kept the previous "
                           f"region for {source.display_name}.")

        def do_confirm() -> None:
            if state["mode"] != REGION_SELECTION_READY or not state["rect"]:
                return
            if self.scope and self.scope.get("type") == "window":
                try:
                    live = window_client_info(int(self.scope["hwnd"]))
                    if region_stale(state["snapshot_w"], state["snapshot_h"],
                                    state["snapshot_dpi"],
                                    live.get("client_w", state["snapshot_w"]),
                                    live.get("client_h", state["snapshot_h"]),
                                    live.get("dpi")):
                        messagebox.showwarning(
                            "Target changed",
                            "The target's size or DPI changed since this "
                            "snapshot was taken. Cancel and click Draw "
                            "region again for a fresh snapshot before "
                            "confirming.")
                        return
                except (OSError, ValueError):
                    pass
            content_status = state.get("content_status", "NOT_EVALUATED")
            override_note = None
            if content_status == "NEAR_UNIFORM_OTHER" and override_var.get():
                if not messagebox.askyesno(
                        "Confirm advanced override",
                        "This crop looks like a single flat color, which "
                        "usually means the wrong region or a genuinely "
                        "blank field. Are you sure you want to confirm it "
                        "anyway?"):
                    return
                from datetime import datetime, timezone
                override_note = (
                    f"region confirmed via advanced override "
                    f"(NEAR_UNIFORM_OTHER) at "
                    f"{datetime.now(timezone.utc).isoformat()}")
            state["mode"] = region_on_confirm(state["mode"])
            x, y, w, h = state["rect"]
            source.rect = (x, y, w, h)
            self._confirmed_regions.add(source.source_id)
            if override_note:
                source.notes = (f"{source.notes}\n{override_note}"
                               if source.notes else override_note)
                preview = self._setup_previews.get(source.source_id)
                if preview is not None:
                    preview["override"] = override_note
            picker.grab_release()
            picker.destroy()
            self._refresh_table()
            self._flash_row(index)
            self.status.set(f"Region saved for {source.display_name}: "
                           f"x={x}, y={y}, w={w}, h={h}"
                           + (" (advanced override)" if override_note
                              else ""))

        ttk.Button(buttons, text="Redraw", command=do_redraw).pack(
            side="left")
        confirm_btn = ttk.Button(buttons, text="Confirm this region",
                                command=do_confirm, state="disabled")
        confirm_btn.pack(side="left", padx=6)
        ttk.Button(buttons, text="Cancel", command=do_cancel).pack(
            side="left")

        picker.bind("<Escape>", lambda _e: do_cancel())
        picker.protocol("WM_DELETE_WINDOW", do_cancel)
        redraw_base()
        update_status()

    def _review_regions(self) -> None:
        """One screenshot with every configured region overlaid, numbered,
        clickable to select that field, with Edit/Redraw/Remove actions."""

        controller = self._ensure_controller()
        if controller is None:
            return
        try:
            controller.ensure_worker()
            reply = controller.region_snapshot()
        except WorkerError as exc:
            messagebox.showwarning("Snapshot failed", exc.detail)
            return
        window = reply.get("window") or {}
        native_w = window.get("client_w", 800)
        native_h = window.get("client_h", 400)
        b64 = reply.get("frame_png_b64")
        scale = picker_scale_factor(
            native_w, native_h,
            max(400, self.root.winfo_screenwidth() - 60),
            max(300, self.root.winfo_screenheight() - 220))

        review = tk.Toplevel(self.root)
        review.title("Review selected regions")
        full_image = None
        if b64:
            try:
                full_image = tk.PhotoImage(master=review,
                                          data=base64.b64decode(b64))
                if scale > 1:
                    full_image = full_image.subsample(scale, scale)
            except tk.TclError:
                full_image = None
        self._review_image_ref = full_image  # keep alive
        canvas = tk.Canvas(
            review, bg="grey",
            width=(full_image.width() if full_image
                  else min(native_w, 1200)),
            height=(full_image.height() if full_image
                   else min(native_h, 700)))
        canvas.pack(fill="both", expand=True)
        if full_image is not None:
            canvas.create_image(0, 0, anchor="nw", image=full_image)

        hit_boxes: list[tuple[float, float, float, float, int]] = []
        for i, src in enumerate(self.sources):
            if src.source_id not in self._confirmed_regions \
                    or src.rect[2] <= 0 or src.rect[3] <= 0:
                continue  # only show actually-confirmed regions (§3)
            x, y, w, h = src.rect
            sx0, sy0 = x / scale, y / scale
            sx1, sy1 = (x + w) / scale, (y + h) / scale
            canvas.create_rectangle(sx0, sy0, sx1, sy1, outline="#00e5ff",
                                   width=2)
            canvas.create_text(sx0 + 4, sy0 + 4, anchor="nw",
                              fill="#00e5ff", font=("Segoe UI", 10, "bold"),
                              text=f"{i + 1}. {src.display_name}")
            hit_boxes.append((sx0, sy0, sx1, sy1, i))

        detail_var = tk.StringVar(
            value="Click a numbered region to see its latest crop/OCR.")
        detail_frame = ttk.LabelFrame(review, text="Selected region details",
                                      padding=6)
        detail_frame.pack(fill="x", padx=4, pady=(4, 0))
        detail_thumb = tk.Label(detail_frame, text="(no preview)", width=12,
                                height=4, bg="#eeeeee", relief="groove")
        detail_thumb.pack(side="left", padx=(0, 8))
        ttk.Label(detail_frame, textvariable=detail_var, wraplength=760,
                 justify="left").pack(side="left", fill="x", expand=True)

        def show_detail(i: int) -> None:
            if i >= len(self.sources):
                return
            src = self.sources[i]
            preview = self._setup_previews.get(src.source_id)
            if not preview:
                detail_var.set(f"{i + 1}. {src.display_name}: no preview "
                               f"yet - use Re-test all regions.")
                detail_thumb.configure(image="", text="(no preview)")
                return
            thumb = preview.get("thumb")
            if thumb is not None:
                detail_thumb.configure(image=thumb, text="", width=0,
                                      height=0)
            else:
                detail_thumb.configure(image="", text="(no crop)", width=12,
                                      height=4)
            detail_var.set(
                f"{i + 1}. {src.display_name} · last captured "
                f"{preview.get('captured_utc', '')}\n"
                f"Raw OCR: {preview.get('raw_ocr', '')!r} -> "
                f"{preview.get('normalized')}\n"
                f"Capture: {preview.get('capture_status')} · OCR: "
                f"{preview.get('ocr_status')} · Content: "
                f"{preview.get('content_status')}")

        def on_click(event) -> None:
            for x0, y0, x1, y1, i in hit_boxes:
                if x0 <= event.x <= x1 and y0 <= event.y <= y1:
                    children = self.table.get_children()
                    if i < len(children):
                        self.table.selection_set(children[i])
                        self.table.focus(children[i])
                    show_detail(i)
                    break

        canvas.bind("<Button-1>", on_click)

        status_var = tk.StringVar(value="")
        ttk.Label(review, textvariable=status_var,
                 foreground="#444444").pack(anchor="w", padx=4)

        def retest_all() -> None:
            # Independent audit MAJOR: this loop re-captures every field
            # one at a time with no acknowledgement until it's all done -
            # the more fields, the longer the review dialog looked frozen.
            status_var.set("Re-testing…")
            self.root.update_idletasks()
            tested = 0
            failed = 0
            for src in self.sources:
                if src.rect[2] <= 0 or src.rect[3] <= 0:
                    continue
                try:
                    reply2 = controller.preview_single_region(src)
                except WorkerError:
                    failed += 1
                    continue
                obs = reply2.get("region_preview") or {}
                self._record_setup_preview(
                    src.source_id, thumb_b64=obs.get("crop_png_b64"),
                    raw_ocr=obs.get("raw_text", ""),
                    normalized=obs.get("normalized_value"),
                    content_status=obs.get("crop_content_status",
                                          "NOT_EVALUATED"),
                    capture_status=obs.get("capture_status", ""),
                    ocr_status=obs.get("ocr_status", ""))
                tested += 1
            self._refresh_table()
            status_var.set(f"Re-tested {tested} region(s)"
                          + (f", {failed} failed" if failed else "") + ".")

        actions = ttk.Frame(review)
        actions.pack(fill="x", pady=6)
        ttk.Button(actions, text="Re-test all regions",
                  command=retest_all).pack(side="left")
        ttk.Button(actions, text="Edit selected…",
                  command=lambda: (review.destroy(),
                                  self._edit_source())).pack(
            side="left", padx=4)
        ttk.Button(actions, text="Redraw selected…",
                  command=lambda: (review.destroy(),
                                  self._draw_region())).pack(
            side="left", padx=4)
        ttk.Button(actions, text="Remove selected",
                  command=lambda: (self._remove_source(),
                                  review.destroy())).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Close", command=review.destroy).pack(
            side="right", padx=4)

    # -- preview ------------------------------------------------------------

    def _preview(self) -> None:
        if self.scope is None:
            self.status.set("Select a target first.")
            return
        try:
            validate_source_set(self.sources)
        except ValidationError as exc:
            self.status.set(f"Field error: {exc}")
            return
        # §3: block Preview until every enabled field has a CONFIRMED region,
        # so the placeholder rectangle can never be captured as if it were a
        # real selection.
        undrawn = [s.display_name for s in self.sources
                   if s.enabled and s.source_id not in self._confirmed_regions]
        if undrawn:
            self.status.set(
                f"Draw a region for: {', '.join(undrawn)} — a field with no "
                f"confirmed region cannot be previewed.")
            return
        try:
            interval_ms = int(self.interval_var.get())
        except (tk.TclError, ValueError):
            self.status.set("Interval must be a whole number of "
                           "milliseconds (250–10000).")
            return
        self.defaults = SessionDefaults(
            interval_ms=interval_ms,
            retention_mode=self.retention_var.get(),
            cursor_metadata=bool(self.cursor_var.get()))
        try:
            self.defaults.validate()
        except ValidationError as exc:
            self.status.set(f"Setting error: {exc}")
            return
        controller = self._ensure_controller()
        if controller is None:
            return
        controller.environment_snapshot = environment_snapshot(
            self.scope, self.backend_var.get())
        controller.on_pause = self._handle_pause
        # Independent audit MAJOR: Preview captures every configured field
        # (up to 8) - likely SLOWER than a single Test capture - yet gave
        # no "Working…" acknowledgement at all before this synchronous,
        # main-thread-blocking call. The window simply stopped responding
        # with zero on-screen sign the click had registered.
        self.status.set("Previewing…")
        self.root.update_idletasks()
        try:
            controller.ensure_worker()
            reply = controller.preview()
        except WorkerError as exc:
            self.status.set(f"Worker error: {exc.detail}")
            return
        self.status.set("Preview ready.")
        self._show_preview_gate(reply)

    def _show_preview_gate(self, reply: dict[str, Any]) -> None:
        gate = tk.Toplevel(self.root)
        gate.title("Step 4 — Preview and verify")
        # Independent audit (MAJOR): this is the final review gate before
        # arming - the app's own onboarding text promises "review the
        # highlighted region and its crop/OCR preview" before recording.
        # Without transient+grab_set, the setup screen behind it stayed
        # fully clickable, so a field could be edited/added/removed while
        # this exact gate was still open and referencing the pre-edit
        # `reply`, and clicking Confirm here would arm against fields/
        # regions that were never actually the ones reviewed.
        gate.transient(self.root)
        gate.grab_set()
        window = reply.get("window") or {}
        ttk.Label(gate, text=f"Backend: "
                             f"{backend_label(self.controller.effective_backend)}"
                             f" (requested {backend_label(self.backend_var.get())})"
                             f" · {window.get('client_w')}×"
                             f"{window.get('client_h')} · DPI "
                             f"{window.get('dpi')} · frame shows "
                             f"{content_status_label(reply.get('frame_content_status'))}"
                             ).pack(padx=8, pady=6)
        names = {s.source_id: s.display_name for s in self.sources}
        by_id = {s.source_id: s for s in self.sources}
        confirm_vars: dict[str, tk.BooleanVar] = {}
        thumbs: list[tk.PhotoImage] = []
        # (field, suggested_type) pairs for the one-click fix dialog below.
        type_suggestions: list[tuple[Any, str]] = []
        for obs in reply.get("observations", []):
            row = ttk.Frame(gate)
            row.pack(fill="x", padx=8, pady=2)
            thumb_label = tk.Label(row, text="", width=8, height=2,
                                   bg="#eeeeee", relief="groove")
            b64 = obs.get("crop_png_b64")
            if b64:
                try:
                    image = tk.PhotoImage(master=gate,
                                         data=base64.b64decode(b64))
                    thumbs.append(image)
                    thumb_label.configure(image=image, width=0, height=0)
                except tk.TclError:
                    pass
            thumb_label.pack(side="left", padx=4)
            ttk.Label(row, text=names.get(obs["source_id"], ""),
                      width=16).pack(side="left")
            ttk.Label(row, text=f"{obs.get('crop_w')}×{obs.get('crop_h')}",
                      width=10).pack(side="left")
            ttk.Label(row, text=f"OCR: {obs.get('raw_text', '')[:40]!r} -> "
                                f"{obs.get('normalized_value')}",
                     width=55).pack(side="left")
            var = tk.BooleanVar(value=False)
            confirm_vars[obs["source_id"]] = var
            ttk.Checkbutton(row, text="aligned with the intended value",
                           variable=var).pack(side="left")
            # Preview-time guidance (Phase 4.1 extended): the recording
            # screen already got a per-status hint here; this gate had
            # none at all, so a field stuck on a parse failure gave no
            # clue why - even though this is the very first place an
            # owner could see and fix it, before ever starting a real
            # recording. Computed the same way derive_value_status is
            # (stability isn't evaluated at preview time, so a neutral
            # NOT_EVALUATED is passed - it never resolves to REJECTED).
            preview_source = by_id.get(obs["source_id"])
            preview_value_status = C.derive_value_status(
                obs.get("capture_status", "OK"), obs.get("ocr_status", "OK"),
                obs.get("parse_status", "NOT_RUN"), "NOT_EVALUATED")
            preview_guidance = value_status_guidance(
                preview_value_status, raw_text=obs.get("raw_text", ""),
                data_type=preview_source.data_type if preview_source else "")
            if preview_guidance:
                ttk.Label(row, text=f"⚠ {preview_guidance}",
                         foreground="#b42318", wraplength=520,
                         justify="left").pack(side="left", padx=(8, 0))
            if preview_source is not None:
                suggested = suggest_field_type(
                    obs.get("raw_text", ""), obs.get("parse_status", ""),
                    preview_source.data_type)
                if suggested:
                    type_suggestions.append((preview_source, suggested))
            self._record_setup_preview(
                obs["source_id"], thumb_b64=b64,
                raw_ocr=obs.get("raw_text", ""),
                normalized=obs.get("normalized_value"),
                content_status=obs.get("crop_content_status",
                                      "NOT_EVALUATED"),
                capture_status=obs.get("capture_status", ""),
                ocr_status=obs.get("ocr_status", ""))
        self._refresh_table()
        self._preview_thumbs = thumbs  # keep references alive
        buttons = ttk.Frame(gate)
        buttons.pack(pady=8)

        # Adversarial review finding (2026-07-21): `gate.after(200, ...)`
        # below is NOT cancelled by `gate.destroy()` - Tk deletes the
        # callback's registered Tcl command but the timer stays armed, so
        # 200ms after opening, clicking either button before then made Tk
        # try to invoke a deleted command (a background Tcl error, and the
        # Python callback body never runs - a `winfo_exists()` guard
        # inside it is dead code, since Tk errors out before that body is
        # ever reached). The real fix is tracking the job id and
        # `after_cancel()`-ing it explicitly on every path that destroys
        # the gate first.
        pending_hint_id: list[str | None] = [None]

        def cancel_pending_hint() -> None:
            if pending_hint_id[0] is not None:
                try:
                    gate.after_cancel(pending_hint_id[0])
                except tk.TclError:
                    pass
                pending_hint_id[0] = None

        def back_to_setup() -> None:
            cancel_pending_hint()
            gate.destroy()

        ttk.Button(buttons, text="← Back to setup",
                   command=back_to_setup).pack(side="left", padx=4)

        def confirm() -> None:
            if not all(var.get() for var in confirm_vars.values()):
                messagebox.showwarning(
                    "Not confirmed",
                    "Confirm every field is aligned with the intended "
                    "value before arming.")
                return
            cancel_pending_hint()
            gate.destroy()
            try:
                self.controller.confirm_preview_and_arm()
            except WorkerError as exc:
                self.status.set(f"Arm error: {exc.detail}")
                return
            self._build_ready()

        ttk.Button(buttons, text="Confirm preview ✓ → Step 5",
                   command=confirm).pack(side="left", padx=4)

        # One-click type fix (2026-07-21): the per-row text hints above
        # existed for two full real owner sessions and were never acted
        # on - a hint the owner has to read, translate, and manually apply
        # via Edit selected is not enough at this gate. When the REAL
        # preview shows a field whose type demonstrably cannot parse its
        # own captured text (suggest_field_type), the app now OFFERS the
        # fix itself: one modal yes/no, applied only on an explicit yes,
        # then the preview re-runs with a fresh capture so the owner
        # immediately sees the corrected result. Never silent: declining
        # changes nothing.
        if type_suggestions:
            def offer_type_fix() -> None:
                pending_hint_id[0] = None
                lines = "\n".join(
                    f"  {source.display_name}: {source.data_type} → "
                    f"{suggested}"
                    for source, suggested in type_suggestions)
                # Adversarial review finding: X/Y/Z-role clearing is a
                # real side effect of accepting some suggestions (a
                # non-numeric type can't hold that role) - it must be
                # disclosed BEFORE the owner answers yes/no, not only
                # after, and not only in this session's own commit log.
                would_clear = [
                    source.display_name
                    for source, suggested in type_suggestions
                    if suggested not in ("number", "coordinate")
                    and source.semantic_role in ("x", "y", "z")]
                role_note = (
                    "\n\nThis will also clear the X/Y/Z role on: "
                    f"{', '.join(would_clear)} (that role needs a "
                    "number or coordinate field)." if would_clear else "")
                ok = messagebox.askyesno(
                    "Fix field types?",
                    "These fields cannot read their captured text with "
                    "their current Type, but a different Type would work:"
                    f"\n\n{lines}{role_note}\n\n"
                    "Switch them automatically and re-run the preview?",
                    parent=gate)
                if not ok:
                    return
                cleared_roles: list[str] = []
                for source, suggested in type_suggestions:
                    source.data_type = suggested
                    # X/Y/Z roles require a number-shaped type; "auto" can
                    # yield text, so the role must be released (same rule
                    # the Edit dialog enforces) - announced, never silent.
                    if suggested not in ("number", "coordinate") and \
                            source.semantic_role in ("x", "y", "z"):
                        source.semantic_role = "none"
                        cleared_roles.append(source.display_name)
                summary = ", ".join(
                    f"{s.display_name}→{t}" for s, t in type_suggestions)
                cancel_pending_hint()
                gate.destroy()
                if cleared_roles:
                    # Adversarial review finding: a status-bar message set
                    # here is provably never painted - _preview() below
                    # overwrites the same StringVar with "Previewing…"
                    # before the event loop ever processes an idle redraw
                    # for this one. A blocking dialog (the Edit-field
                    # dialog's own existing pattern for this exact rule)
                    # is the only way the owner actually sees it.
                    messagebox.showinfo(
                        "Role cleared",
                        f"Field types switched: {summary}.\n\nX/Y/Z role "
                        "cleared (that role needs a number or coordinate "
                        f"field): {', '.join(cleared_roles)}.")
                else:
                    self.status.set(f"Field types switched: {summary} — "
                                   f"re-running preview…")
                self._refresh_table()
                self._preview()
            pending_hint_id[0] = gate.after(200, offer_type_fix)

    # -- ready + recording ------------------------------------------------

    def _build_ready(self) -> None:
        for widget in self.root.winfo_children():
            widget.destroy()
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill="both", expand=True)
        elig = self.controller.session_json()["xyz_eligibility"]
        ttk.Label(frame, text="Step 5 — Ready to record",
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(frame, text=self.scope_label.get()).pack(anchor="w")
        ttk.Label(frame, text=f"Effective backend: "
                             f"{backend_label(self.controller.effective_backend)}"
                  ).pack(anchor="w")
        ttk.Label(frame, text=f"{len(self.sources)} fields · "
                             f"{self.defaults.interval_ms} ms · "
                             f"retention: "
                             f"{retention_label(self.defaults.retention_mode)}"
                  ).pack(anchor="w")
        ttk.Label(frame, text=xyz_status_sentence(
            elig["eligible"], xyz_missing_axes(self.sources))).pack(anchor="w")
        visibility = (self.controller.environment_snapshot or {}).get(
            "window_visibility")
        if visibility and not visibility.get("fully_visible", True) and \
                self.controller.effective_backend == C.BACKEND_COPYFROMSCREEN:
            ttk.Label(frame, text="⚠ Part of the target is off-screen; "
                                 "CopyFromScreen cannot capture that part.",
                     foreground="#b58900").pack(anchor="w")
        ttk.Button(frame, text="● START RECORDING",
                   command=self._start_recording).pack(pady=10)
        # Independent audit MAJOR: Start recording's own worker round-trip
        # (RECORD_START) had no "Working…" acknowledgement anywhere on
        # this screen - there was no status label here at all to hold one.
        self.ready_status_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.ready_status_var,
                 foreground="#444444").pack(anchor="w")

    def _start_recording(self) -> None:
        if hasattr(self, "ready_status_var"):
            self.ready_status_var.set("Starting…")
            self.root.update_idletasks()
        try:
            self.controller.start_recording()
        except WorkerError as exc:
            if hasattr(self, "ready_status_var"):
                self.ready_status_var.set(f"Could not start: {exc.detail}")
            messagebox.showwarning("Cannot start recording", exc.detail)
            return
        # §33: stop any prior scheduler before creating a new one, so a
        # disarm -> re-preview -> re-record recovery cycle does not orphan
        # (leak) the previous paused daemon thread.
        if self.scheduler is not None:
            self.scheduler.stop(drain_timeout=0.25)
            self.scheduler = None
        # Live-feed state: a bounded ring buffer (never rereads a CSV/journal
        # file - every row comes straight from the TickResult/on_event data
        # already flowing through the controller) plus per-source last-value
        # tracking for the "changed" column.
        self._feed_buffer: "deque[dict[str, Any]]" = deque(maxlen=FEED_MAX_ROWS)
        self._csv_rows_buffer: "deque[dict[str, Any]]" = deque(
            maxlen=FEED_MAX_ROWS)
        self._feed_last_value: dict[str, str | None] = {}
        self._feed_counters = {"captures": 0, "live_observations": 0,
                              "changes": 0, "errors": 0}
        self._last_capture_time = ""
        self._last_csv_write_time = ""
        self._build_recording()
        self._start_time = time.monotonic()
        self._result_queue: "queue.Queue" = queue.Queue()
        # on_tick runs the REAL capture on a dedicated per-tick worker thread
        # that holds the scheduler's in-flight lock for the whole tick, so
        # deadlines arriving mid-capture are skipped, never queued. Ticks never
        # overlap (single outstanding), so controller.tick() is never entered
        # concurrently. Only the UI refresh is marshalled back to Tk via a
        # queue polled by after().
        self.scheduler = TickScheduler(
            self.defaults.interval_ms,
            on_tick=self._scheduler_tick,
            on_skip=self.controller.note_skipped_tick)
        self.scheduler.start()
        self.root.after(100, self._drain_results)
        self._open_mini_controller()

    def _scheduler_tick(self) -> None:
        try:
            result = self.controller.tick()
        except Exception as exc:  # never kill the scheduler thread
            self.controller.journal and self.controller.journal.log_error(
                f"tick error: {exc}")
            return
        self._result_queue.put(result)

    def _drain_results(self) -> None:
        try:
            while True:
                result = self._result_queue.get_nowait()
                self._render_tick(result)
        except queue.Empty:
            pass
        if self.scheduler is not None:
            self.root.after(100, self._drain_results)

    def _build_recording(self) -> None:
        for widget in self.root.winfo_children():
            widget.destroy()
        frame = ttk.Frame(self.root, padding=8)
        frame.pack(fill="both", expand=True)
        header = ttk.Frame(frame)
        header.pack(fill="x")
        self.rec_banner = tk.StringVar(value="● REC")
        ttk.Label(header, textvariable=self.rec_banner, foreground="red",
                 font=("Segoe UI", 14, "bold")).pack(side="left")
        self.capture_flash_var = tk.StringVar(value="")
        ttk.Label(header, textvariable=self.capture_flash_var,
                 foreground="#1a7f37",
                 font=("Segoe UI", 11, "bold")).pack(side="left", padx=12)
        self.rec_stats = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.rec_stats).pack(anchor="w")
        self.rec_stats2 = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.rec_stats2).pack(anchor="w")
        self.rec_counters_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.rec_counters_var,
                 foreground="#444444").pack(anchor="w")
        # A plain "what to do first" line for pauses that do NOT need a
        # re-preview (minimized / covered / disk full / worker failure).
        # Without it, those pauses showed only a Resume button that
        # immediately re-paused - a silent no-op to the owner.
        self.pause_guidance_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.pause_guidance_var,
                 foreground="#7a5b00", wraplength=980,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")

        # -- Recovery bar (resize/DPI pause). Placed at the TOP, right under
        # the pause banner, and hidden until a repreview-required pause needs
        # it - so the ONLY control that recovers such a pause can never be
        # clipped below the fold (it previously sat under the fill/expand
        # notebook and squeezed to a 9px unreadable sliver on the default
        # window). Kept in a highlighted bar so it reads as an action, and
        # `before=`-anchored above the field cards so it always shows here.
        self._cards_label = ttk.Label(frame, text="Field cards")
        self.recovery_frame = tk.Frame(frame, bg="#fff3cd", bd=1,
                                       relief="solid")
        self.recovery_var = tk.StringVar(value="")
        tk.Label(self.recovery_frame, textvariable=self.recovery_var,
                bg="#fff3cd", fg="#7a5b00", font=("Segoe UI", 10, "bold"),
                anchor="w", justify="left", wraplength=980).pack(
            side="left", fill="x", expand=True, padx=8, pady=6)
        self.recovery_btn = ttk.Button(
            self.recovery_frame, text="Disarm and re-preview…",
            command=self._disarm_and_repreview, state="disabled")
        self.recovery_btn.pack(side="right", padx=8, pady=6)
        # Constructed but not shown yet (no wasted space in the normal case).

        # -- Field cards: one compact card per field, always visible -------
        self._cards_label.pack(anchor="w", pady=(8, 0))
        cards_outer = ttk.Frame(frame)
        cards_outer.pack(fill="x")
        # §17: scale the fixed card/canvas pixel sizes by the display DPI so
        # the lower card lines are not clipped at 125-200% scaling.
        card_w = self._dpi_scale(170)
        # +40 over the prior 176 (Phase 4.1): the warn_var label now shows a
        # specific, actionable per-status message (layout.
        # value_status_guidance) instead of one fixed generic phrase, and
        # needs room to wrap to 2-3 lines without being clipped.
        card_h = self._dpi_scale(216)
        cards_canvas = tk.Canvas(cards_outer, height=card_h + 8,
                                 highlightthickness=0)
        cards_hscroll = ttk.Scrollbar(cards_outer, orient="horizontal",
                                      command=cards_canvas.xview)
        cards_canvas.configure(xscrollcommand=cards_hscroll.set)
        cards_canvas.pack(side="top", fill="x")
        cards_hscroll.pack(side="top", fill="x")
        cards_inner = ttk.Frame(cards_canvas)
        cards_canvas.create_window((0, 0), window=cards_inner, anchor="nw")

        def on_cards_configure(_e) -> None:
            cards_canvas.configure(scrollregion=cards_canvas.bbox("all"))

        cards_inner.bind("<Configure>", on_cards_configure)
        # source_id -> widget refs, kept here (not layout.py) since Tk
        # widgets aren't testable headlessly; supports 1-8 fields without
        # clipping via the horizontal scrollbar above.
        self.field_cards: dict[str, dict[str, Any]] = {}
        for source in self.sources:
            if not source.enabled:
                continue
            card = ttk.LabelFrame(cards_inner, text=source.display_name,
                                  width=card_w, height=card_h)
            card.pack(side="left", padx=4, pady=2)
            card.pack_propagate(False)
            thumb = tk.Label(card, text="(no crop yet)", width=16, height=3,
                             bg="#eeeeee", relief="groove")
            thumb.pack(pady=(2, 2))
            value_var = tk.StringVar(value="—")
            ttk.Label(card, textvariable=value_var,
                     font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=4)
            status_var = tk.StringVar(value="(not observed yet)")
            ttk.Label(card, textvariable=status_var,
                     font=("Segoe UI", 8)).pack(anchor="w", padx=4)
            times_var = tk.StringVar(value="changed: — · persisted: —")
            ttk.Label(card, textvariable=times_var, font=("Segoe UI", 8),
                     foreground="#444444").pack(anchor="w", padx=4)
            rect_var = tk.StringVar(
                value=f"{source.rect[0]},{source.rect[1]} "
                     f"{source.rect[2]}×{source.rect[3]}")
            ttk.Label(card, textvariable=rect_var, font=("Segoe UI", 8),
                     foreground="#666666").pack(anchor="w", padx=4)
            warn_var = tk.StringVar(value="")
            ttk.Label(card, textvariable=warn_var, foreground="#b42318",
                     font=("Segoe UI", 8, "bold"),
                     wraplength=card_w - 12).pack(anchor="w", padx=4)
            self.field_cards[source.source_id] = {
                "thumb": thumb, "value_var": value_var,
                "status_var": status_var, "times_var": times_var,
                "warn_var": warn_var, "last_changed": "",
                "last_persisted": "", "image": None, "missing_streak": 0,
                "last_raw_text": "",
            }

        # -- Live capture and CSV feed / Saved CSV rows ---------------------
        ttk.Label(frame, text="Live capture and CSV feed").pack(
            anchor="w", pady=(8, 0))
        feed_controls = ttk.Frame(frame)
        feed_controls.pack(fill="x")
        self.feed_saved_only_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(feed_controls, text="Show saved rows only",
                       variable=self.feed_saved_only_var,
                       command=self._rebuild_feed_view).pack(side="left")
        self.feed_warnings_only_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(feed_controls, text="Show warnings only",
                       variable=self.feed_warnings_only_var,
                       command=self._rebuild_feed_view).pack(side="left",
                                                             padx=8)
        self.feed_paused_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(feed_controls, text="Pause auto-scroll",
                       variable=self.feed_paused_var).pack(side="left",
                                                          padx=8)
        ttk.Label(feed_controls, text="Columns:").pack(side="left",
                                                       padx=(12, 2))
        self.feed_preset_var = tk.StringVar(value="Simple")
        ttk.OptionMenu(feed_controls, self.feed_preset_var, "Simple",
                      *FEED_PRESET_NAMES,
                      command=lambda _v: self._apply_feed_preset()).pack(
            side="left")
        ttk.Button(feed_controls, text="Clear screen feed",
                  command=self._clear_screen_feed).pack(side="left", padx=8)
        # One button: the CSV files live directly in the run folder, so a
        # separate "Open CSV folder" (§32) only implied a location that does
        # not exist.
        ttk.Button(feed_controls, text="Open run folder (CSV + journal)",
                  command=self._open_run_folder).pack(side="left", padx=8)

        # On-screen colour legend, right next to the coloured rows it
        # explains (previously the colours were documented only in Help, and
        # yellow was omitted there entirely).
        legend = ttk.Frame(frame)
        legend.pack(fill="x", pady=(2, 0))
        ttk.Label(legend, text="Row colours:").pack(side="left")
        _legend_bg = {"gray": "#f2f2f2", "blue": "#dbeeff", "green": "#dff5df",
                      "orange": "#ffe0b3", "yellow": "#fff6d6",
                      "red": "#fbdede"}
        for color, meaning in FEED_COLOR_LEGEND:
            tk.Label(legend, text=f" {meaning} ", bg=_legend_bg[color],
                     relief="groove", font=("Segoe UI", 8)).pack(
                side="left", padx=2)

        notebook = ttk.Notebook(frame)
        notebook.pack(fill="both", expand=True, pady=(4, 0))

        feed_tab = ttk.Frame(notebook)
        notebook.add(feed_tab, text="Live feed")
        feed_tree_frame = ttk.Frame(feed_tab)
        feed_tree_frame.pack(fill="both", expand=True)
        self.feed_tree = ttk.Treeview(feed_tree_frame, columns=FEED_COLUMNS,
                                     displaycolumns=FEED_PRESETS["Simple"],
                                     show="headings", height=10)
        for col in FEED_COLUMNS:
            self.feed_tree.heading(col, text=feed_column_title(col))
            self.feed_tree.column(col, width=FEED_COLUMN_WIDTHS[col])
        for color, bg in (("gray", "#f2f2f2"), ("blue", "#dbeeff"),
                          ("green", "#dff5df"), ("orange", "#ffe0b3"),
                          ("red", "#fbdede"), ("yellow", "#fff6d6")):
            self.feed_tree.tag_configure(color, background=bg)
        feed_vscroll = ttk.Scrollbar(feed_tree_frame, orient="vertical",
                                     command=self.feed_tree.yview)
        feed_hscroll = ttk.Scrollbar(feed_tab, orient="horizontal",
                                     command=self.feed_tree.xview)
        self.feed_tree.configure(yscrollcommand=feed_vscroll.set,
                                 xscrollcommand=feed_hscroll.set)
        self.feed_tree.grid(row=0, column=0, sticky="nsew")
        feed_vscroll.grid(row=0, column=1, sticky="ns")
        feed_tree_frame.rowconfigure(0, weight=1)
        feed_tree_frame.columnconfigure(0, weight=1)
        feed_hscroll.pack(side="bottom", fill="x")

        csv_tab = ttk.Frame(notebook)
        notebook.add(csv_tab, text="Saved CSV rows")
        self.csv_mode_var = tk.StringVar(
            value="Showing the LIVE CSV snapshot (events_wide.live.csv) - "
                 "updates during recording. After Stop, the Finalized "
                 "screen shows the verified final CSV row count.")
        ttk.Label(csv_tab, textvariable=self.csv_mode_var,
                 foreground="#444444", wraplength=980).pack(anchor="w",
                                                            padx=4, pady=2)
        self.csv_placeholder_var = tk.StringVar(
            value="No rows have been written yet. Live captures are "
                 "visible in the Live feed.")
        self.csv_placeholder_label = ttk.Label(
            csv_tab, textvariable=self.csv_placeholder_var,
            foreground="#444444", padding=8)
        self.csv_placeholder_label.pack(anchor="w")
        csv_controls = ttk.Frame(csv_tab)
        csv_controls.pack(fill="x")
        ttk.Button(csv_controls, text="Copy selected row",
                  command=self._copy_selected_csv_row).pack(side="left")
        ttk.Button(csv_controls, text="Open containing folder",
                  command=self._open_run_folder).pack(side="left", padx=6)
        self.csv_file_label_var = tk.StringVar(value="")
        ttk.Label(csv_controls, textvariable=self.csv_file_label_var,
                 foreground="#444444").pack(side="left", padx=12)
        csv_tree_frame = ttk.Frame(csv_tab)
        csv_tree_frame.pack(fill="both", expand=True)
        self.csv_tree = ttk.Treeview(csv_tree_frame, columns=(),
                                    show="headings", height=10)
        csv_vscroll = ttk.Scrollbar(csv_tree_frame, orient="vertical",
                                    command=self.csv_tree.yview)
        csv_hscroll = ttk.Scrollbar(csv_tab, orient="horizontal",
                                    command=self.csv_tree.xview)
        self.csv_tree.configure(yscrollcommand=csv_vscroll.set,
                                xscrollcommand=csv_hscroll.set)
        self.csv_tree.grid(row=0, column=0, sticky="nsew")
        csv_vscroll.grid(row=0, column=1, sticky="ns")
        csv_tree_frame.rowconfigure(0, weight=1)
        csv_tree_frame.columnconfigure(0, weight=1)
        csv_hscroll.pack(side="bottom", fill="x")
        self._csv_columns: tuple[str, ...] = ()

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=6)
        self.pause_btn = ttk.Button(buttons, text="⏸ Pause",
                                    command=self._pause)
        self.pause_btn.pack(side="left")
        self.resume_btn = ttk.Button(buttons, text="▶ Resume",
                                     command=self._resume)
        self.resume_btn.pack(side="left", padx=4)
        self._resume_needs_recovery = False
        self._refresh_pause_resume_buttons()
        ttk.Button(buttons, text="■ Stop",
                   command=self._stop).pack(side="left", padx=4)
        ttk.Button(buttons, text="Diagnostic snapshot",
                  command=self._diagnostic_snapshot_recording).pack(
            side="left", padx=4)
        ttk.Label(buttons, text="(Esc = emergency stop)").pack(side="left",
                                                              padx=8)

    def _dpi_scale(self, px: int) -> int:
        """Scale a baseline (96-DPI) pixel constant by the current display
        scaling (§17), so fixed-size containers grow with Windows 125-200%
        scaling instead of clipping their text. Falls back to px on error."""
        try:
            return int(px * self.root.winfo_fpixels("1i") / 96.0)
        except Exception:
            return px

    def _show_recovery_bar(self, show: bool, message: str = "", *,
                           action_label: str = "Disarm and re-preview…",
                           action_command=None) -> None:
        """Show/hide the top recovery bar. Shown for a pause that needs an
        explicit fix (a resize/DPI re-preview, or a closed-window target
        re-selection), anchored above the field cards so it is always
        visible near the pause banner and never clipped by the notebook.
        The button's label/command is set per pause reason: a closed window
        (requires_reresolve) offers 'Choose target window…', not the
        re-preview action that provably cannot recover a dead window."""

        if not hasattr(self, "recovery_frame"):
            return
        # §15: this flag also gates the main Resume button (via
        # _refresh_pause_resume_buttons) so the UI never contradicts
        # "Resume is disabled until you fix the reported issue".
        self._resume_needs_recovery = show
        if show:
            self.recovery_var.set(message)
            self.recovery_btn.configure(
                state="normal", text=action_label,
                command=action_command or self._disarm_and_repreview)
            if not self.recovery_frame.winfo_ismapped():
                self.recovery_frame.pack(fill="x", pady=(6, 0),
                                        before=self._cards_label)
        else:
            self.recovery_var.set("")
            self.recovery_btn.configure(state="disabled")
            self.recovery_frame.pack_forget()
        self._refresh_pause_resume_buttons()

    def _disarm_and_repreview(self) -> None:
        """The recovery action a resize/DPI-change pause requires (§3/§C):
        reconfigure, re-snapshot the environment, and reopen the real
        preview gate. Confirming there re-arms and returns to Step 6,
        where Start Recording resumes the SAME journal/run (start_recording
        is a no-op on an already-open journal) - no data is lost, only the
        live-feed UI buffers reset to empty."""

        try:
            self.controller.machine.reconfigure()
        except Exception as exc:
            messagebox.showwarning("Cannot reconfigure", str(exc))
            return
        self.controller.environment_snapshot = environment_snapshot(
            self.scope, self.backend_var.get())
        # Independent audit MAJOR: this synchronous re-preview call had no
        # acknowledgement either - the recovery bar (the widget visible on
        # this screen) is repurposed briefly to show it is working.
        if hasattr(self, "recovery_var"):
            self.recovery_var.set("Reconfiguring and re-previewing…")
            self.root.update_idletasks()
        try:
            self.controller.ensure_worker()
            reply = self.controller.preview()
        except WorkerError as exc:
            messagebox.showwarning("Re-preview failed", exc.detail)
            return
        self._show_preview_gate(reply)

    def _reselect_target_for_recovery(self) -> None:
        """Recovery for a closed/renamed target window (requires_reresolve):
        pick the window again and rebind the SAME run to it, then re-preview.
        Regions are client-relative so they still apply to the reopened
        window. Unlike Step-1 target selection this KEEPS the controller,
        journal and confirmed regions - it only points the existing run at a
        live window, so no captured data is lost. Usability MAJOR: a closed
        window used to offer only 'Disarm and re-preview', which re-previews
        the dead window and cannot recover - a dead-end into Stop."""

        if self.controller is None:
            return
        windows = list_windows()
        chooser = tk.Toplevel(self.root)
        chooser.title("Choose the target window again")
        chooser.transient(self.root)
        chooser.grab_set()
        ttk.Label(chooser,
                 text="The previous target window is gone. Pick the window "
                      "to continue this recording against - the fields and "
                      "regions you set up are kept.",
                 wraplength=560).pack(padx=8, pady=(8, 0))
        listbox = tk.Listbox(chooser, width=90, height=18)
        for win in windows:
            listbox.insert("end", f"{win.title}  ·  pid {win.pid}")
        listbox.pack(padx=8, pady=8)

        def choose() -> None:
            index = listbox.curselection()
            if not index:
                return
            win = windows[index[0]]
            info = window_client_info(win.hwnd)
            new_scope = {"type": "window", "hwnd": win.hwnd, "pid": win.pid,
                         "title": win.title, "client_w": info["client_w"],
                         "client_h": info["client_h"],
                         "origin_x": info["origin_x"],
                         "origin_y": info["origin_y"]}
            self.scope = new_scope
            self.controller.scope = new_scope
            # The worker was bound to the OLD hwnd at spawn; force a respawn
            # against the new window before the re-preview captures anything.
            if self.controller.worker is not None:
                try:
                    self.controller.worker.teardown()
                except Exception:
                    pass
                self.controller.worker = None
            chooser.grab_release()
            chooser.destroy()
            self._disarm_and_repreview()

        def cancel() -> None:
            chooser.grab_release()
            chooser.destroy()

        chooser.protocol("WM_DELETE_WINDOW", cancel)
        buttons = ttk.Frame(chooser)
        buttons.pack(pady=4)
        ttk.Button(buttons, text="Choose", command=choose).pack(
            side="left", padx=4)
        ttk.Button(buttons, text="Cancel", command=cancel).pack(
            side="left", padx=4)

    # -- live feed / Saved CSV rows ----------------------------------------

    def _render_tick(self, result) -> None:
        if self.controller is None:
            return
        # Capture indicator: flash on every tick that actually ran, so the
        # owner can see the program is working even when nothing changed.
        self._capture_flash_state = not self._capture_flash_state
        marker = "● captured" if self._capture_flash_state else "○ captured"
        self.capture_flash_var.set(marker)
        now_str = time.strftime("%H:%M:%S")
        self._feed_counters["captures"] += 1
        frame = result.frame or {}
        if frame.get("capture_status") == "OK" or result.observations:
            self._last_capture_time = now_str
        event = result.event or {}
        journal_ok = result.event is not None
        snapshot = event.get("live_csv_snapshot") if journal_ok else None
        live_csv_ok = snapshot.get("ok") if snapshot else None
        changed_ids = set(event.get("changed_source_ids") or [])
        is_retained_error = journal_ok and \
            event.get("event_status") == "RETAINED_ERROR"
        retention_reason = ", ".join(event.get("retention_reason_codes")
                                     or [])
        cursor = frame.get("cursor") or {}
        cursor_str = (f"{cursor.get('screen_x')},{cursor.get('screen_y')}"
                     if self.defaults.cursor_metadata and cursor else "")
        names = {s.source_id: s.display_name for s in self.sources}
        crop_bytes = getattr(self.controller, "last_crop_bytes", {})
        for sid, obs in result.observations.items():
            self._feed_counters["live_observations"] += 1
            current = obs.normalized_value if obs.normalized_value \
                is not None else (obs.raw_text or None)
            changed = value_changed(self._feed_last_value.get(sid), current)
            self._feed_last_value[sid] = current
            if changed:
                self._feed_counters["changes"] += 1
            retained = journal_ok and sid in changed_ids
            color = feed_row_color(
                value_status=obs.value_status, ocr_status=obs.ocr_status,
                capture_status=obs.capture_status,
                stability_status=obs.stability_status,
                journal_persisted=retained,
                is_retained_error=(is_retained_error and sid in changed_ids),
                live_csv_ok=live_csv_ok if retained else None)
            if color in ("red", "orange", "yellow"):
                self._feed_counters["errors"] += 1
            self._append_feed_row({
                "time": now_str, "tick": self.controller.frame_seq,
                "cursor": cursor_str, "field": names.get(sid, sid),
                "raw_ocr": obs.raw_text, "normalized":
                    obs.normalized_value, "capture": obs.capture_status,
                "ocr": obs.ocr_status,
                "value_status": value_status_label(obs.value_status),
                "changed": changed, "retained": retained,
                "journal": retained, "live_csv": bool(retained and
                                                       live_csv_ok),
                "reason": retention_reason if retained else "",
                "backend": backend_label(self.controller.effective_backend),
                "ms": result.tick_ms, "color": color,
            })
            self._update_field_card(sid, obs, now_str, changed, retained,
                                    color, crop_bytes.get(sid))
        if journal_ok:
            self._last_csv_write_time = now_str
            self._append_csv_row(event)
        elapsed = time.monotonic() - self._start_time
        diag = self.controller.diagnostics
        journal = self.controller.journal
        events_count = journal.counters['events'] if journal else 0
        self.rec_stats.set(
            f"{format_elapsed(elapsed)} · tick {self.controller.frame_seq} "
            f"· last {diag['last_tick_ms']} ms · skipped "
            f"{diag['skipped_ticks']} · OCR err {diag['ocr_errors']} · "
            f"events {events_count}")
        run_dir = journal.run_dir if journal else None
        disk_bytes = journal.disk_bytes if journal else 0
        pause_reason = (pause_message(self.controller.pause_state.reason,
                                      self.controller.pause_state.detail)[0]
                        if self.controller.pause_state else "")
        self.rec_stats2.set(
            f"backend {backend_label(self.controller.effective_backend)} · "
            f"target visibility: {'ok' if not pause_reason else pause_reason} · "
            f"storage {disk_bytes // 1024} KiB · run: "
            f"{run_dir.name if run_dir else '(none)'}")
        live_rows = journal.live_snapshot_row_count if journal else 0
        self.rec_counters_var.set(
            f"Captures {self._feed_counters['captures']} · Live obs "
            f"{self._feed_counters['live_observations']} · Changes "
            f"{self._feed_counters['changes']} · Retained (attempted) "
            f"{diag['retained_events_attempted']} · Journal events "
            f"{events_count} · Live CSV rows {live_rows} · Errors "
            f"{self._feed_counters['errors']} (capture "
            f"{diag['capture_errors']} · OCR {diag['ocr_errors']} · export "
            f"{diag['export_errors']}) · Skipped {diag['skipped_ticks']} · "
            f"Last capture {self._last_capture_time or '(none)'} · Last "
            f"journal write {diag['last_journal_write_utc'] or '(none)'} · "
            f"Last live CSV update "
            f"{diag['last_live_csv_utc'] or '(none)'}")
        # An automatic pause entered during THIS tick (result.pause is the
        # exact PauseState _enter_pause set) - update the banner/recovery
        # bar here, on the main thread via the already-safe result queue,
        # rather than from _handle_pause on the tick thread (§ MINOR fix).
        self._render_pause_state(result.pause)

    def _render_pause_state(self, pause) -> None:
        """Reflect an automatic pause (or its absence) on the recording
        screen: banner, recovery bar, and the plain 'what to do first'
        guidance line. Extracted from _render_tick so the recovery routing
        is unit-testable. Three distinct pause classes get three distinct
        recoveries:
          - requires_reresolve (target window gone): a 'Choose target
            window…' action that rebinds the SAME run - NOT the re-preview
            action, which cannot recover a dead window;
          - requires_repreview (resize/DPI): the Disarm-and-re-preview bar;
          - anything else (minimized/covered/disk/worker): keep Resume, but
            show the concrete first step so Resume is never a silent no-op.
        """
        if pause is None:
            if hasattr(self, "pause_guidance_var"):
                self.pause_guidance_var.set("")
            return
        sentence, _actions = pause_message(pause.reason, pause.detail)
        if hasattr(self, "rec_banner"):
            self.rec_banner.set(f"⏸ PAUSED — {sentence}")
        if pause.requires_reresolve:
            self._show_recovery_bar(
                True,
                f"{sentence}  Choose the window again if it reopened, or "
                f"Stop to save what you have.",
                action_label="Choose target window…",
                action_command=self._reselect_target_for_recovery)
            if hasattr(self, "pause_guidance_var"):
                self.pause_guidance_var.set("")
        elif pause.requires_repreview:
            self._show_recovery_bar(
                True,
                f"{sentence}  Resume is disabled until you Disarm and "
                f"re-preview.")
            if hasattr(self, "pause_guidance_var"):
                self.pause_guidance_var.set("")
        else:
            self._show_recovery_bar(False)
            if hasattr(self, "pause_guidance_var"):
                self.pause_guidance_var.set(pause_guidance(pause.reason))

    def _update_field_card(self, sid: str, obs, now_str: str, changed: bool,
                           retained: bool, color: str,
                           crop_png: bytes | None) -> None:
        card = self.field_cards.get(sid)
        if card is None:
            return
        shown = obs.normalized_value if obs.normalized_value is not None \
            else (obs.raw_text or "—")
        card["value_var"].set(str(shown))
        state_label = persistence_state(
            retained=retained, journal_ok=retained,
            live_csv_ok=(color == "green") if retained else None)
        card["status_var"].set(field_card_status(
            obs.value_status, obs.stability_status, state_label))
        if changed:
            card["last_changed"] = now_str
        if retained:
            card["last_persisted"] = now_str
        card["times_var"].set(f"changed: {card['last_changed'] or '—'} · "
                             f"persisted: {card['last_persisted'] or '—'}")
        # A brief "No value yet" while the owner hovers elsewhere is normal
        # (§5k Phase 2.3) and shows no warning; only a value that STAYS
        # missing for many consecutive ticks escalates to an actionable
        # message (Phase 4.2) - a transient blip must never look like an
        # error, and a genuinely stuck field must never stay silent forever.
        if obs.value_status == "MISSING_SOURCE_VALUE":
            card["missing_streak"] += 1
        else:
            card["missing_streak"] = 0
        # Remember the last REAL OCR text per card: a pixel-hash-cached
        # tick deliberately blanks obs.raw_text (contract - a cached
        # confirmation is never presented as fresh OCR), which used to
        # starve the content-aware guidance below of its input, so a
        # static (unmoving) reading showed the GENERIC advice even when
        # the coordinate/code-specific hint applied - exactly what the
        # owner's 2026-07-21 screenshots showed. Display-guidance-only.
        if obs.raw_text:
            card["last_raw_text"] = obs.raw_text
        if obs.value_status == "MISSING_SOURCE_VALUE":
            escalation = missing_value_guidance(card["missing_streak"])
            card["warn_var"].set(f"⚠ {escalation}" if escalation else "")
        elif color in ("red", "orange", "yellow"):
            source = next((s for s in self.sources if s.source_id == sid),
                          None)
            guidance = value_status_guidance(
                obs.value_status,
                raw_text=obs.raw_text or card.get("last_raw_text", ""),
                data_type=source.data_type if source else "")
            card["warn_var"].set(f"⚠ {guidance}" if guidance
                                else "⚠ capture/OCR issue")
        else:
            card["warn_var"].set("")
        if crop_png:
            try:
                image = tk.PhotoImage(master=self.root, data=crop_png)
                factor = picker_scale_factor(image.width(), image.height(),
                                            150, 55)
                if factor > 1:
                    image = image.subsample(factor, factor)
                card["image"] = image
                card["thumb"].configure(image=image, text="", width=0,
                                       height=0)
            except tk.TclError:
                pass

    def _apply_feed_preset(self) -> None:
        preset = FEED_PRESETS.get(self.feed_preset_var.get(),
                                  FEED_PRESETS["Simple"])
        self.feed_tree.configure(displaycolumns=preset)

    def _append_feed_row(self, row: dict[str, Any]) -> None:
        self._feed_buffer.append(row)
        if self.feed_saved_only_var.get() and not row["journal"]:
            return
        if self.feed_warnings_only_var.get() and row["color"] not in (
                "red", "orange", "yellow"):
            return
        self._insert_feed_row(row)

    def _insert_feed_row(self, row: dict[str, Any]) -> None:
        values = (row["time"], row["tick"], row["cursor"], row["field"],
                 row["raw_ocr"],
                 row["normalized"] if row["normalized"] is not None
                 else "—",
                 row["capture"], row["ocr"], row["value_status"],
                 "yes" if row["changed"] else "no",
                 "yes" if row["retained"] else "no",
                 "yes" if row["journal"] else "no",
                 "yes" if row["live_csv"] else "no", row["reason"],
                 row["backend"], row["ms"])
        self.feed_tree.insert("", "end", values=values, tags=(row["color"],))
        children = self.feed_tree.get_children()
        if len(children) > FEED_MAX_ROWS:
            self.feed_tree.delete(children[0])
        if not self.feed_paused_var.get():
            self.feed_tree.yview_moveto(1.0)

    def _rebuild_feed_view(self) -> None:
        self.feed_tree.delete(*self.feed_tree.get_children())
        saved_only = self.feed_saved_only_var.get()
        warnings_only = self.feed_warnings_only_var.get()
        for row in self._feed_buffer:
            if saved_only and not row["journal"]:
                continue
            if warnings_only and row["color"] not in ("red", "orange",
                                                       "yellow"):
                continue
            self._insert_feed_row(row)

    def _clear_screen_feed(self) -> None:
        # UI buffer only - never touches the journal, CSVs, or Saved CSV
        # rows (those reflect data that is already durably persisted).
        self._feed_buffer.clear()
        self.feed_tree.delete(*self.feed_tree.get_children())

    def _append_csv_row(self, event: dict[str, Any]) -> None:
        from ..exports import wide_csv_header, wide_csv_row
        if not self._csv_columns:
            self._csv_columns = wide_csv_header(
                self.sources, self.defaults.cursor_metadata)
            self.csv_tree.configure(columns=self._csv_columns)
            for col in self._csv_columns:
                self.csv_tree.heading(col, text=csv_preview_title(col))
                self.csv_tree.column(col, width=110)
            self.csv_placeholder_label.pack_forget()
            run_dir = self.controller.journal.run_dir \
                if self.controller.journal else None
            self.csv_file_label_var.set(
                "LIVE snapshot: events_wide.live.csv · "
                "observations_long.live.csv"
                + (f" · points.live.xyz (if eligible) · {run_dir}"
                   if run_dir else ""))
        row = wide_csv_row(event, self.sources, self.defaults.cursor_metadata)
        self._csv_rows_buffer.append(row)
        self.csv_tree.insert("", 0, values=tuple(row.get(c, "")
                                                 for c in self._csv_columns))
        children = self.csv_tree.get_children()
        if len(children) > FEED_MAX_ROWS:
            self.csv_tree.delete(children[-1])

    def _copy_selected_csv_row(self) -> None:
        focus = self.csv_tree.focus()
        if not focus:
            return
        values = self.csv_tree.item(focus, "values")
        text = "\t".join(str(v) for v in values)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def _diagnostic_snapshot_recording(self) -> None:
        result = self.controller.diagnostic_snapshot()
        if result.get("dir"):
            messagebox.showinfo(
                "Diagnostic snapshot saved",
                f"{result['source_count']} field crop(s) saved locally "
                f"to:\n{result['dir']}\n\nNever uploaded.")
        else:
            messagebox.showinfo("Nothing to save", result.get("note", ""))

    def _open_run_folder(self) -> None:
        if self.controller and self.controller.journal:
            self._open_folder(self.controller.journal.run_dir)

    def _open_mini_controller(self) -> None:
        self.mini = tk.Toplevel(self.root)
        self.mini.overrideredirect(True)
        self.mini.attributes("-topmost", True)
        regions = [(s.rect[0], s.rect[1], s.rect[2], s.rect[3])
                   for s in self.sources if s.enabled]
        # Map field-relative region rects to screen coordinates using the
        # live client origin so the controller never covers a capture region.
        if self.scope.get("type") == "window":
            live = window_client_info(int(self.scope["hwnd"]))
            origin = (live.get("origin_x", 0), live.get("origin_y", 0))
        else:
            monitor = self.scope.get("monitor", {})
            origin = (monitor.get("x", 0), monitor.get("y", 0))
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        position = mini_controller_position(
            [(r[0] + origin[0], r[1] + origin[1], r[2], r[3])
             for r in regions], screen_w, screen_h)
        if position is None:
            position = (screen_w - 280, 12)
        # §17: scale the mini controller so its Stop/Emergency buttons are
        # not clipped past a fixed 260px width at higher DPI scaling.
        mini_w, mini_h = self._dpi_scale(260), self._dpi_scale(60)
        self.mini.geometry(f"{mini_w}x{mini_h}+{position[0]}+{position[1]}")
        frame = tk.Frame(self.mini, bg="black")
        frame.pack(fill="both", expand=True)
        self.mini_label = tk.Label(frame, text="● REC 00:00:00", fg="red",
                                   bg="black", font=("Segoe UI", 11, "bold"))
        self.mini_label.pack(side="left", padx=6)
        pause_b = tk.Button(frame, text="⏸", command=self._pause)
        pause_b.pack(side="left")
        stop_b = tk.Button(frame, text="■", command=self._stop)
        stop_b.pack(side="left")
        # The red "!" is the one destructive control here (it kills the
        # capture worker immediately); unlabeled it reads as an alert icon,
        # not a button. Give all three hover tooltips so the floating
        # controller is self-explanatory.
        emergency_b = tk.Button(frame, text="!", fg="red",
                                command=self._emergency_stop)
        emergency_b.pack(side="left")
        self._add_tooltip(pause_b, "Pause")
        self._add_tooltip(stop_b, "Stop and save")
        self._add_tooltip(emergency_b, "Emergency stop (kills capture now)")
        self._update_mini()

    def _add_tooltip(self, widget, text: str) -> None:
        """Minimal hover tooltip (Tk has none built in). Self-contained: one
        Toplevel shown on <Enter>, destroyed on <Leave>/<Destroy>."""
        state = {"win": None}

        def show(_event=None) -> None:
            if state["win"] is not None:
                return
            x = widget.winfo_rootx()
            y = widget.winfo_rooty() + widget.winfo_height() + 2
            win = tk.Toplevel(widget)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.geometry(f"+{x}+{y}")
            tk.Label(win, text=text, bg="#ffffe0", fg="black", relief="solid",
                     borderwidth=1, font=("Segoe UI", 8), padx=4).pack()
            state["win"] = win

        def hide(_event=None) -> None:
            if state["win"] is not None:
                state["win"].destroy()
                state["win"] = None

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)
        widget.bind("<Destroy>", hide)

    def _update_mini(self) -> None:
        if self.mini is None or self.controller is None:
            return
        state = self.controller.machine.state
        elapsed = time.monotonic() - self._start_time
        prefix = "● REC" if state == "RECORDING" else "⏸ PAUSED"
        color = "red" if state == "RECORDING" else "yellow"
        self.mini_label.configure(text=f"{prefix} {format_elapsed(elapsed)}",
                                  fg=color)
        self.mini.after(500, self._update_mini)

    def _refresh_pause_resume_buttons(self) -> None:
        """Three independent audits converged on the same MAJOR: Pause is
        legal only in RECORDING and Resume only in PAUSED (statemachine.py),
        but neither button was ever disabled outside its legal state, so a
        natural double-click (or clicking Pause right after an automatic
        pause already fired) raised an uncaught IllegalAction - a different
        exception type than the `except WorkerError` these handlers already
        had, invisible until the last-resort callback-exception net caught
        it as a scary generic popup. Gate both buttons the same way Test
        capture/Retest already are, so the illegal click is never offered
        in the first place."""

        if not hasattr(self, "pause_btn") or self.controller is None:
            return
        state = self.controller.machine.state
        self.pause_btn.configure(
            state="normal" if state == "RECORDING" else "disabled")
        if hasattr(self, "resume_btn"):
            can_resume = state == "PAUSED" and not self._resume_needs_recovery
            self.resume_btn.configure(
                state="normal" if can_resume else "disabled")

    def _pause(self) -> None:
        # Independent audit MAJOR: stop future dispatch and drain any
        # in-flight tick BEFORE touching the controller. Previously
        # user_pause() ran first, so a concurrently in-flight tick's own
        # worker request could race it - the loser's WorkerError made
        # user_pause() tear the worker down out from under the still-
        # running tick (extra worker restarts, a dropped capture, or the
        # deliberate "USER_REQUEST" pause reason getting silently
        # overwritten by a bogus "WORKER_FAILURE_STREAK" one). Mirrors the
        # ordering _stop()/_emergency_stop() already used correctly.
        #
        # Second independent audit MAJOR: a hardcoded 2.0s drain timeout
        # can be shorter than a real, legal in-flight tick's own round-
        # trip budget (controller.drain_budget_s(), which scales with the
        # configured interval up to ~20s) - and the earlier code discarded
        # drain()'s outcome, proceeding into user_pause() regardless. That
        # reopened the exact race this drain call exists to close. Now:
        # size the wait from the real budget, and if it's still not
        # enough, refuse instead of racing the still-running tick.
        #
        # self.status is the SETUP screen's status line - it has no
        # widget on the recording screen, so an acknowledgement here must
        # use rec_banner (the label the owner is actually looking at).
        self.rec_banner.set("Pausing…")
        self.root.update_idletasks()
        if self.scheduler:
            self.scheduler.pause()
            budget = self.controller.drain_budget_s() if self.controller \
                else 2.0
            if not self.scheduler.drain(timeout=budget + 0.5):
                self.rec_banner.set(
                    "⏸ Still capturing — click Pause again in a moment.")
                self._refresh_pause_resume_buttons()
                return
        try:
            self.controller.user_pause()
            self.rec_banner.set("⏸ PAUSED")
        except WorkerError:
            self.rec_banner.set("⏸ PAUSED (could not confirm with worker)")
        except IllegalAction:
            # Benign re-entrant call (e.g. a double-click while already
            # PAUSED) - not a worker problem, so don't claim one. Restore
            # the banner from ground truth rather than assuming why it
            # was illegal.
            self.rec_banner.set(
                "⏸ PAUSED"
                if self.controller.machine.state == "PAUSED" else "● REC")
        finally:
            self._refresh_pause_resume_buttons()

    def _resume(self) -> None:
        # Symmetric drain (see _pause): a no-op in the normal click-Pause-
        # then-click-Resume flow (nothing can be in-flight while paused),
        # but cheap insurance against any future path that calls resume
        # without a preceding drain. Same real-budget sizing as _pause.
        self.rec_banner.set("Resuming…")
        self.root.update_idletasks()
        if self.scheduler:
            budget = self.controller.drain_budget_s() if self.controller \
                else 2.0
            if not self.scheduler.drain(timeout=budget + 0.5):
                self.rec_banner.set(
                    "⏸ PAUSED — still busy, click Resume again in a "
                    "moment.")
                self._refresh_pause_resume_buttons()
                return
        try:
            self.controller.user_resume()
            if self.scheduler:
                self.scheduler.resume()
            self.rec_banner.set("● REC")
            self._show_recovery_bar(False)
            if hasattr(self, "pause_guidance_var"):
                self.pause_guidance_var.set("")
        except WorkerError as exc:
            self.rec_banner.set("⏸ PAUSED")
            messagebox.showwarning("Cannot resume", exc.detail)
        except IllegalAction:
            # Same reasoning as _pause's IllegalAction branch: don't leave
            # "Resuming…" stuck forever - restore from ground truth.
            self.rec_banner.set(
                "● REC"
                if self.controller.machine.state == "RECORDING"
                else "⏸ PAUSED")
        finally:
            self._refresh_pause_resume_buttons()

    def _handle_pause(self, pause: PauseState) -> None:
        """Set as controller.on_pause; runs on the SCHEDULER's tick thread
        (every _enter_pause call happens inside the same call stack as
        tick()). Independent audit MINOR: this used to also call
        `self.root.after(0, update_ui)` directly from that background
        thread to update rec_banner/the recovery bar - outside Tkinter's
        documented single-thread contract, and inconsistent with every
        other UI update in this file, which is marshalled back to Tk only
        via the _result_queue that _drain_results polls. Since
        TickResult.pause carries the exact same PauseState object this
        callback receives, the actual widget updates now happen in
        _render_tick instead (§ pause branch below) - reached only via
        that already-thread-safe queue. Only a plain, already thread-safe
        threading.Event operation remains here."""

        if self.scheduler:
            self.scheduler.pause()

    def _stop(self) -> None:
        # Independent cycle-4 verification audit caught that this was
        # claimed fixed in an earlier commit message but the code was
        # never actually changed: this call used the scheduler's default
        # 5s drain_timeout, unlike _emergency_stop/_on_close's bounded
        # 0.25s. If the worker died mid-tick, clicking the ordinary Stop
        # button (not just Emergency stop) could freeze the whole UI for
        # up to 5 seconds. The subsequent controller.stop() below tears
        # the worker down regardless, which is what actually unblocks a
        # stuck tick - waiting the full 5s here serves no purpose.
        if self.scheduler:
            self.scheduler.stop(drain_timeout=0.25)
        # If finalize() (called inside controller.stop()) raises, the
        # session-state-machine has ALREADY moved to STOPPING (stop()
        # transitions the state before finalizing) - and STOPPING is not a
        # legal state for "stop" to run again, so an uncaught exception here
        # would strand the recording screen forever with every further Stop
        # click raising the same IllegalAction (caught only by the
        # last-resort callback-exception net, never reaching the Finalized
        # screen or its "run recover <run_id>" recovery hint). Mirror
        # _emergency_stop's own try/except so the owner always reaches a
        # real screen: the journal itself is already durably safe on disk
        # by this point regardless of whether finalize's export step failed.
        try:
            summary = self.controller.stop()
        except Exception:
            summary = {}
        self._close_mini()
        self._build_finalized(summary)

    def _emergency_stop(self) -> None:
        # Esc = emergency stop ONLY while actually recording (§2). Binding it
        # for the whole app meant that after any Test capture created a
        # controller, a stray Esc on the setup screen - the universal
        # cancel/back reflex - tore the worker down and dumped the user to a
        # bogus "Finalized" screen, losing all field/region setup. Gate on a
        # live scheduler (recording/paused), not merely a controller existing.
        if self.controller is None or self.scheduler is None:
            return
        if self.controller.machine.state not in ("RECORDING", "PAUSED"):
            return
        # Bounded drain: stay within the emergency budget. A tick stuck on a
        # slow capture is unblocked by the worker kill in emergency_stop().
        self.scheduler.stop(drain_timeout=0.25)
        try:
            summary = self.controller.emergency_stop()
        except Exception:
            summary = {}
        self._close_mini()
        self._build_finalized(summary)

    def _close_mini(self) -> None:
        if self.mini is not None:
            self.mini.destroy()
            self.mini = None

    def _drop_controller(self) -> None:
        """Tear down any live worker before dropping the controller
        reference (independent audit MAJOR: every '...needs a fresh
        controller' site - target reselect, guided demo, New session -
        previously just discarded self.controller, leaking its
        PowerShell/GDI capture-worker subprocess for the rest of the app's
        life. The job-object kill-on-close safety net (worker.py) only
        fires when the whole UI process exits, not when a Python reference
        is merely dropped)."""

        if self.controller is not None and self.controller.worker is not None:
            self.controller.worker.teardown()
        self.controller = None

    def _build_finalized(self, summary: dict[str, Any]) -> None:
        for widget in self.root.winfo_children():
            widget.destroy()
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill="both", expand=True)
        run_dir = (self.controller.journal.run_dir
                   if self.controller and self.controller.journal else None)
        # §16: only claim success when a summary actually came back AND the
        # final CSV verified against the journal. An emergency stop can
        # return {} (finalize raised/never ran), and a verified=False summary
        # means captured rows are missing from the deliverable - the headline
        # must not read "Final CSV finalized" in either case (usability MAJOR:
        # the success wording used to show even on a verify mismatch).
        verified = bool(summary) and summary.get("final_csv_row_count_verified")
        if summary and verified:
            header, colour = "Run finalized — Final CSV finalized", "#1a7f37"
        elif summary and not verified:
            header, colour = ("Run stopped — the final CSV could NOT be "
                             "verified", "#b42318")
        else:
            header, colour = ("Stopped — finalization did not complete",
                             "#b42318")
        ttk.Label(frame, text=header, foreground=colour,
                  font=("Segoe UI", 14, "bold")).pack(anchor="w")
        if not summary:
            ttk.Label(
                frame, wraplength=900, foreground="#b58900",
                text=("The run was stopped without a completed finalize (e.g. "
                     "an emergency stop). Your captured data is safe in the "
                     "recording journal on disk" +
                     (f" at {run_dir}" if run_dir else "") +
                     " — click “Rebuild exports now” below to turn it into "
                     "the CSV/XYZ files.")).pack(anchor="w", pady=4)
        if summary:
            ttk.Label(frame, text=f"Journal events: "
                                 f"{summary.get('event_count')}"
                      ).pack(anchor="w")
            ttk.Label(
                frame,
                text=f"Final CSV rows: {summary.get('final_csv_row_count')} "
                    f"({'verified against journal' if verified else 'NOT '
                       'VERIFIED - see warnings below'})",
                foreground=("#1a7f37" if verified else "#b42318")
            ).pack(anchor="w")
            # Explicit XYZ outcome - the owner never has to open the folder to
            # learn whether their point cloud was produced (usability MAJOR).
            xyz = summary.get("xyz")
            if xyz:
                sentence, xyz_colour = xyz_outcome_sentence(xyz)
                ttk.Label(frame, text=sentence, foreground=xyz_colour,
                         wraplength=900).pack(anchor="w")
            live_rows = summary.get('live_csv_snapshot_row_count', 0)
            ttk.Label(frame, text=f"Live CSV snapshot rows seen while "
                                 f"recording: {live_rows}").pack(anchor="w")
            if summary.get("warnings"):
                plain = "; ".join(warning_sentence(w)
                                  for w in summary["warnings"])
                ttk.Label(frame, text=f"Warnings: {plain}",
                         foreground="#b58900", wraplength=900).pack(
                    anchor="w")
            if run_dir:
                ttk.Label(frame, text=f"Output: {run_dir}").pack(anchor="w")
                ttk.Label(
                    frame,
                    text="Files: events_wide.csv · observations_long.csv · "
                        "points.xyz · points_xyz_metadata.json · "
                        "run_summary.json · manifest.sha256.json").pack(
                    anchor="w")
                ttk.Label(
                    frame, foreground="#444444", wraplength=900,
                    text="Tip: the files ending in .live.csv are recording "
                         "previews — use the files WITHOUT .live as your "
                         "final data.").pack(anchor="w", pady=(2, 0))
        button_row = ttk.Frame(frame)
        button_row.pack(pady=10)
        if run_dir:
            ttk.Button(button_row, text="Open run folder",
                      command=lambda: self._open_folder(run_dir)).pack(
                side="left", padx=4)
        # One-click in-process rebuild for a failed/unverified finalize, so a
        # non-developer never has to run "python -m screen2xyz_m2 recover
        # <run_id>" in a terminal (usability MAJOR).
        if run_dir and (not summary or not verified):
            ttk.Button(button_row, text="Rebuild exports now",
                      command=lambda: self._rebuild_exports(run_dir)).pack(
                side="left", padx=4)
        ttk.Button(button_row, text="New session",
                   command=self._reset).pack(side="left", padx=4)

    def _rebuild_exports(self, run_dir) -> None:
        """Rebuild CSV/XYZ exports from the durable journal in-process (the
        same work the 'recover' CLI does), so an owner recovers a failed or
        unverified finalize with one click instead of a terminal command."""
        from ..recovery import recover_run
        try:
            result = recover_run(run_dir)
        except Exception as exc:  # noqa: BLE001 - shown to the owner
            messagebox.showwarning("Could not rebuild exports", str(exc))
            return
        messagebox.showinfo(
            "Exports rebuilt",
            f"Rebuilt from {result['events']} journal events.")
        self._build_finalized(result["summary"])

    def _reset(self) -> None:
        self.scope = None
        self.sources = []
        self._drop_controller()
        self.scheduler = None
        self.scope_label = tk.StringVar(value="No target selected")
        self._setup_previews = {}
        self._confirmed_regions = set()
        self._build_setup()

    def _on_close(self) -> None:
        if self.scheduler:
            # Don't hang window close on a stuck tick; the worker teardown
            # below unblocks any in-flight capture.
            self.scheduler.stop(drain_timeout=0.25)
        if self.controller and self.controller.worker:
            self.controller.worker.teardown()
        if self._demo_session is not None:
            self._demo_session.quit()
        self._close_mini()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def launch() -> None:
    M2App().run()
