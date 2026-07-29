"""Pure UI-logic helpers (no Tk) so they can be unit-tested headlessly."""

from __future__ import annotations

from typing import Any

from ..parsing import looks_like_alphanumeric_code, looks_like_coordinate


def format_elapsed(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def mini_controller_position(regions: list[tuple[int, int, int, int]],
                             screen_w: int, screen_h: int,
                             controller_w: int = 260,
                             controller_h: int = 60,
                             margin: int = 12) -> tuple[int, int] | None:
    """Pick a screen corner for the always-on-top mini controller that does
    not intersect any configured capture region. Returns None if no corner
    is free (the UI then requires manual placement)."""

    corners = [
        (margin, margin),
        (screen_w - controller_w - margin, margin),
        (margin, screen_h - controller_h - margin),
        (screen_w - controller_w - margin, screen_h - controller_h - margin),
    ]
    controller_area = (controller_w, controller_h)
    for cx, cy in corners:
        rect = (cx, cy, controller_area[0], controller_area[1])
        if not any(_intersects(rect, region) for region in regions):
            return (cx, cy)
    return None


def _intersects(a: tuple[int, int, int, int],
                b: tuple[int, int, int, int]) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw <= bx or bx + bw <= ax
                or ay + ah <= by or by + bh <= ay)


def pause_message(reason: str, detail: str = "") -> tuple[str, list[str]]:
    """Return a plain-language pause sentence + legal primary actions."""

    table = {
        "USER_REQUEST": ("You pressed Pause.", ["Resume"]),
        "TARGET_UNAVAILABLE": ("The target window closed.",
                               ["Disarm and choose window…"]),
        "TARGET_MINIMIZED_STREAK": ("The target window is minimized.",
                                    ["Resume"]),
        "DISPLAY_INVALIDATED": ("The target size or DPI changed.",
                                ["Disarm and re-preview"]),
        "BACKEND_BLANK_STREAK": ("The capture backend cannot see the window "
                                 "content.",
                                 ["Try fallback backend", "Resume anyway"]),
        "WORKER_FAILURE_STREAK": ("The capture worker failed three times.",
                                  ["Resume", "Stop"]),
        "DISK_LIMIT": ("The session disk limit was reached.",
                       ["Open folder", "Stop"]),
        "CROP_WRITE_FAILURE": ("A crop could not be written.",
                               ["Resume", "Stop"]),
        "EVIDENCE_BUFFER_LIMIT": ("The evidence buffer is full.",
                                  ["Resume", "Stop"]),
        "MANUAL_RECONFIGURATION": ("Reconfiguration is required.",
                                   ["Disarm and re-preview"]),
    }
    sentence, actions = table.get(reason, (reason, ["Resume", "Stop"]))
    if detail:
        sentence = f"{sentence} ({detail})"
    return sentence, actions


# A plain "what to do first" line per pause reason. Usability finding: the
# recording screen discarded pause_message's recommended actions and, for
# every pause that is not a resize/DPI change, offered only a Resume button
# that immediately re-paused - reading as a silent no-op with no on-screen
# fix. This surfaces the concrete first step so Resume is never a mystery.
def pause_guidance(reason: str) -> str:
    return {
        "USER_REQUEST": "",
        "TARGET_UNAVAILABLE":
            "The target window is gone. If it reopened, choose it again; "
            "otherwise click Stop to save what you have.",
        "TARGET_MINIMIZED_STREAK":
            "Restore (un-minimize) the target window, then click Resume.",
        "DISPLAY_INVALIDATED": "",  # the recovery bar already guides this
        "MANUAL_RECONFIGURATION": "",
        "BACKEND_BLANK_STREAK":
            "Uncover the target window (or switch the backend to "
            "CopyFromScreen), then click Resume.",
        "WORKER_FAILURE_STREAK":
            "Click Resume to try the capture worker again, or Stop to save "
            "what you have.",
        "DISK_LIMIT":
            "Free up disk space, or click Stop to save what you have "
            "(your captured data is already on disk).",
        "CROP_WRITE_FAILURE":
            "A crop image could not be saved. Free up disk space, then "
            "Resume, or Stop to save what you have.",
        "EVIDENCE_BUFFER_LIMIT":
            "The evidence buffer is full. Click Resume to continue, or Stop "
            "to save what you have.",
    }.get(reason, "Click Resume to continue, or Stop to save what you have.")


def value_row(display_name: str, obs: dict[str, Any]) -> tuple[str, str, str]:
    """Row for the live grid: name, value-or-dash, human status."""

    value = obs.get("normalized_value")
    shown = value if value is not None else "—"
    status = obs.get("value_status", "")
    return display_name, str(shown), status


def classify_capture_test(capture_status: str, frame_content_status: str,
                          no_backend_usable: bool) -> tuple[str, str]:
    """Test-capture verdict: (PASS|WARNING|FAIL, plain-English explanation).

    Never reports PASS for a black/blank frame - that is the exact failure
    class this check exists to catch."""

    if capture_status == "TARGET_UNAVAILABLE":
        return "FAIL", "The target window is not available (closed or moved off-screen)."
    if capture_status == "TARGET_MINIMIZED":
        return "FAIL", "The target window is minimized. Restore it and test again."
    if capture_status != "OK":
        # Every remaining hard-failure status gets a plain sentence plus a
        # concrete remedy, so the owner is never shown a bare code with the
        # only advice being "Retest" (which would just reproduce it). The
        # raw code stays as a parenthetical for support.
        remedy = {
            "REGION_OUT_OF_BOUNDS":
                "A field's region falls outside the window. Redraw the "
                "region so it sits inside the target.",
            "BACKEND_FAILURE":
                "The capture backend could not read this window. Try the "
                "CopyFromScreen backend, and keep the window uncovered and "
                "on screen.",
            "PAYLOAD_TOO_LARGE":
                "The window is too large to capture at full size. Try a "
                "smaller window, or capture a single monitor instead.",
            "DISPLAY_INVALIDATED":
                "The screen layout or scaling changed. Reselect the target "
                "and test capture again.",
        }.get(capture_status,
              "Capture could not complete. Check the target window and try "
              "again.")
        return "FAIL", f"{remedy} ({capture_status})"
    if no_backend_usable:
        return "FAIL", ("Neither PrintWindow nor CopyFromScreen produced "
                        "usable content for this window.")
    if frame_content_status == "CONTENT_DETECTED":
        return "PASS", "The captured frame shows real content."
    if frame_content_status == "NEAR_UNIFORM_OTHER":
        return "WARNING", ("The frame is a single flat color/near-blank. "
                           "This may be correct (e.g. a blank field) or may "
                           "mean the wrong window/region is selected.")
    if frame_content_status in ("NEAR_UNIFORM_DARK", "NEAR_UNIFORM_LIGHT"):
        return "FAIL", ("The frame is solid dark/light with no visible "
                        "content - this backend cannot see this window.")
    return "WARNING", "Unable to classify this frame confidently."


def backend_explanation(requested_backend: str,
                        effective_backend: str | None) -> str:
    """One or two plain-English sentences explaining the backend choice."""

    if requested_backend != "auto":
        return (f"Using {requested_backend} directly, as explicitly chosen. "
               f"It is never re-tested automatically.")
    if effective_backend is None:
        return "Auto: not yet resolved - run Test capture to find out."
    if effective_backend == "printwindow_clientonly":
        return ("Auto resolved to PrintWindow: it can read this window's "
               "content directly, even if another window covers it.")
    return ("Auto resolved to CopyFromScreen (PrintWindow could not see "
           "this window's content). This backend can only capture pixels "
           "that are actually visible on screen: keep the target uncovered "
           "and fully on-screen.")


def picker_scale_factor(source_w: int, source_h: int,
                        max_w: int = 1200, max_h: int = 700) -> int:
    """Integer subsample factor (>=1) so a screenshot fits within the given
    display bounds. tk.PhotoImage only scales by whole-number ratios, so the
    picker displays at 1/factor while region picks are multiplied back by
    factor to recover the original physical-pixel coordinates."""

    import math
    if source_w <= 0 or source_h <= 0:
        return 1
    needed = max(source_w / max_w, source_h / max_h, 1.0)
    return max(1, math.ceil(needed))


# -- region selection mode (Draw region…) ------------------------------------
#
# An explicit state model so the picker can never leave the owner guessing
# whether it is in selection mode, whether a drag did anything, or which
# rectangle is currently selected.

REGION_NO_SELECTION = "NO_SELECTION"
REGION_DRAGGING = "DRAGGING"
REGION_SELECTION_READY = "SELECTION_READY"
REGION_CONFIRMED = "CONFIRMED"
REGION_CANCELLED = "CANCELLED"


def region_on_press(_state: str) -> str:
    """Pressing the mouse (re)starts a drag from any state - including
    re-dragging after a prior SELECTION_READY, which discards it cleanly
    rather than stacking controls."""

    return REGION_DRAGGING


def region_on_release(width: int, height: int, min_px: int) -> str:
    """A simple click (no meaningful movement) must never create a region -
    it returns to NO_SELECTION instead of SELECTION_READY."""

    if width >= min_px and height >= min_px:
        return REGION_SELECTION_READY
    return REGION_NO_SELECTION


def region_on_redraw(_state: str) -> str:
    """Clears the temporary selection so the owner can drag again."""

    return REGION_NO_SELECTION


def region_on_cancel(_state: str) -> str:
    return REGION_CANCELLED


def region_on_confirm(state: str) -> str:
    if state != REGION_SELECTION_READY:
        return state
    return REGION_CONFIRMED


def region_drag_rect(x0: float, y0: float, x1: float, y1: float,
                     scale: int, bounds_w: int, bounds_h: int
                     ) -> tuple[int, int, int, int]:
    """Canvas-space drag (any direction, any zoom) -> a clamped, normalized
    physical-pixel rect (x, y, w, h). Clamping happens in physical-pixel
    space so the result is always within [0, bounds_w] x [0, bounds_h]
    regardless of how far the drag went outside the visible canvas."""

    cx0, cx1 = sorted((x0, x1))
    cy0, cy1 = sorted((y0, y1))
    px0 = max(0, min(cx0 * scale, bounds_w))
    px1 = max(0, min(cx1 * scale, bounds_w))
    py0 = max(0, min(cy0 * scale, bounds_h))
    py1 = max(0, min(cy1 * scale, bounds_h))
    return int(px0), int(py0), int(max(0, px1 - px0)), int(max(0, py1 - py0))


def region_confirm_allowed(x: int, y: int, w: int, h: int,
                           bounds_w: int, bounds_h: int, min_px: int,
                           has_crop: bool, content_status: str,
                           *, allow_near_uniform_other: bool = False) -> bool:
    """Every condition must hold before 'Confirm this region' may be used:
    a real drag occurred, the region is within bounds, a crop preview
    exists, and the crop is not blank/near-uniform.

    NEAR_UNIFORM_DARK/LIGHT (solid black/white - almost always a wrong
    region or an unusable backend) can never be confirmed. NEAR_UNIFORM_OTHER
    (a single flat non-black/white color - sometimes a genuinely blank field)
    is blocked by default too, but may be confirmed via an explicit advanced
    override (`allow_near_uniform_other=True`), which the caller must gate
    behind a second, explicit confirmation and record in session metadata -
    it is never silently accepted (§4)."""

    if w < min_px or h < min_px:
        return False
    if x < 0 or y < 0 or x + w > bounds_w or y + h > bounds_h:
        return False
    if not has_crop:
        return False
    if content_status in ("NEAR_UNIFORM_DARK", "NEAR_UNIFORM_LIGHT"):
        return False
    if content_status == "NEAR_UNIFORM_OTHER" and not allow_near_uniform_other:
        return False
    return True


def region_stale(screenshot_client_w: int, screenshot_client_h: int,
                 screenshot_dpi: int | None,
                 live_client_w: int, live_client_h: int,
                 live_dpi: int | None) -> bool:
    """True if the target's client size or DPI changed since the picker's
    screenshot was taken - the picker must then block confirmation until a
    fresh Redraw/Retest, rather than let the owner confirm a rectangle
    against pixels that no longer correspond to the live window (§4 "stale
    screenshot after target resize/DPI change")."""

    if screenshot_client_w != live_client_w or \
            screenshot_client_h != live_client_h:
        return True
    if screenshot_dpi is not None and live_dpi is not None and \
            screenshot_dpi != live_dpi:
        return True
    return False


# -- live capture / CSV feed --------------------------------------------------

def value_changed(previous: str | None, current: str | None) -> bool:
    """Seeding (nothing to compare against yet) is never a change."""

    return previous is not None and previous != current


_WARNING_VALUE_STATUSES = frozenset({
    "OCR_FAILURE", "NO_NUMBER", "AMBIGUOUS_MULTIPLE_NUMBERS",
    "MALFORMED_NUMBER", "OUT_OF_RANGE", "INPUT_TRUNCATED",
    "SOURCE_NOT_VISIBLE", "TARGET_UNAVAILABLE", "CAPTURE_FAILURE",
    "UNSTABLE_READING", "SUSPECT_GLYPH_CONFUSION",
})


def feed_row_color(*, value_status: str, ocr_status: str,
                   capture_status: str, stability_status: str,
                   journal_persisted: bool, is_retained_error: bool,
                   live_csv_ok: bool | None = None) -> str:
    """gray (observed live only) / blue (candidate awaiting stability) /
    green (persisted to journal AND the live CSV snapshot updated) / orange
    (persisted to journal but the live CSV snapshot update failed) / red
    (retained error) / yellow (warning, empty OCR, or a temporary capture
    issue that was not retained).

    `journal_persisted` means exactly what it says - the durable
    events.jsonl append actually succeeded (§2) - never "will become a CSV
    row", since official CSV files exist only after Stop/finalize."""

    if is_retained_error:
        return "red"
    if journal_persisted:
        return "green" if live_csv_ok is not False else "orange"
    warning = (capture_status != "OK" or ocr_status == "ENGINE_FAILURE"
              or ocr_status == "EMPTY_TEXT"
              or value_status in _WARNING_VALUE_STATUSES)
    if warning:
        return "yellow"
    if stability_status == "PENDING_CONFIRMATION":
        return "blue"
    return "gray"


# -- truthful persistence states (§2) ----------------------------------------
#
# Four explicit, plain-language states so the UI never conflates "durably
# journaled" with "a CSV file exists" - official CSV files exist only after
# Stop/finalize.

PERSISTENCE_OBSERVED_LIVE = "Observed live"
PERSISTENCE_JOURNAL = "Persisted to journal"
PERSISTENCE_LIVE_CSV = "Live CSV snapshot updated"
PERSISTENCE_FINAL_CSV = "Final CSV finalized"


def persistence_state(*, retained: bool, journal_ok: bool,
                      live_csv_ok: bool | None,
                      finalized: bool = False) -> str:
    """One of the four states above for a single field/event, in order."""

    if finalized:
        return PERSISTENCE_FINAL_CSV
    if retained and journal_ok and live_csv_ok:
        return PERSISTENCE_LIVE_CSV
    if retained and journal_ok:
        return PERSISTENCE_JOURNAL
    return PERSISTENCE_OBSERVED_LIVE


# -- persistent "next recommended step" card + progressive control gating ---
#
# One pure function is the single source of truth for: what the next-step
# card says, and whether Test capture/Retest may be clicked right now. Every
# other widget's enabled/disabled state already has its own dedicated check
# elsewhere (undrawn-region gating on Preview, ARMED-only gating on Start,
# etc.) - this one exists specifically to close the class of bug where a
# setup-only action (Test capture / Retest) is clicked after the session has
# moved past setup (ARMED/RECORDING/PAUSED/STOPPING/FINALIZED) and silently
# raises IllegalAction with no visible acknowledgement.

NEXT_STEP_NO_TARGET = "NO_TARGET"
NEXT_STEP_TARGET_SELECTED = "TARGET_SELECTED"
NEXT_STEP_FIELDS_REQUIRED = "FIELDS_REQUIRED"
NEXT_STEP_REGIONS_REQUIRED = "REGIONS_REQUIRED"
NEXT_STEP_READY_TO_PREVIEW = "READY_TO_PREVIEW"
NEXT_STEP_READY_TO_ARM = "READY_TO_ARM"
NEXT_STEP_ARMED = "ARMED"
NEXT_STEP_RECORDING = "RECORDING"
NEXT_STEP_PAUSED = "PAUSED"
NEXT_STEP_FINALIZED = "FINALIZED"

# Once the controller has moved past these two states, Step 2's Test
# capture/Retest is no longer a legal action (LiveSessionController.
# region_snapshot requires TARGET_SELECTED or REGIONS_CONFIGURED) - it must
# be disabled, not left clickable-but-silently-broken.
_TEST_CAPTURE_LEGAL_STATES = frozenset({None, "TARGET_SELECTED",
                                        "REGIONS_CONFIGURED"})


def can_test_capture(controller_state: str | None, has_target: bool,
                     setup_worker_blocked: bool = False) -> tuple[bool, str]:
    """(allowed, reason-if-not). reason is '' when allowed.

    setup_worker_blocked (independent audit finding): after three
    consecutive capture-worker setup failures the controller latches
    setup_worker_blocked=True, and Test capture/Retest can never succeed
    again (ensure_worker fails fast on the block before even attempting a
    respawn) until retry_worker() explicitly clears it. Before this fix the
    UI never distinguished this from an ordinary FAIL verdict, so the
    "Next step" card kept recommending "Retest" - advice that could never
    work - with no visible way out."""

    if not has_target:
        return False, "Select a target before testing capture."
    if setup_worker_blocked:
        return False, (
            "The capture worker failed three times in a row and is "
            "blocked. Click Retry to clear this and try again.")
    if controller_state not in _TEST_CAPTURE_LEGAL_STATES:
        return False, (
            "Test capture is only available during setup. This session is "
            f"past setup ({controller_state}) - use Disarm/Stop or start a "
            "new session to test capture again.")
    return True, ""


def derive_next_step(*, has_target: bool, controller_state: str | None,
                     capture_tested: bool, capture_verdict: str | None,
                     enabled_field_count: int, all_regions_confirmed: bool,
                     preview_confirmed: bool) -> dict[str, Any]:
    """Single source of truth for the persistent next-step card. Pure/no Tk
    so it is fully unit-testable without a display. Returns a dict with:
    state, step, total, headline, detail, primary_action."""

    total = 6
    if not has_target:
        return {"state": NEXT_STEP_NO_TARGET, "step": 1, "total": total,
                "headline": "Step 1 of 6 — Select a target",
                "detail": "No target is selected.",
                "primary_action": "Select target window or monitor"}
    if controller_state in ("RECORDING",):
        return {"state": NEXT_STEP_RECORDING, "step": 6, "total": total,
                "headline": "Step 6 of 6 — Recording",
                "detail": "Screen2XYZ is capturing on schedule.",
                "primary_action": "Watch the live feed, or Pause/Stop"}
    if controller_state in ("PAUSED",):
        return {"state": NEXT_STEP_PAUSED, "step": 6, "total": total,
                "headline": "Step 6 of 6 — Paused",
                "detail": "Recording is paused.",
                "primary_action": "Resume, or fix the reported issue first"}
    if controller_state in ("STOPPING", "FINALIZED"):
        return {"state": NEXT_STEP_FINALIZED, "step": 6, "total": total,
                "headline": "Session finished",
                "detail": "This session has stopped.",
                "primary_action": "Open the run folder, or start a new "
                                  "session"}
    if controller_state == "ARMED":
        return {"state": NEXT_STEP_ARMED, "step": 5, "total": total,
                "headline": "Step 5 of 6 — Start recording",
                "detail": "Preview confirmed. Ready to record.",
                "primary_action": "Start recording"}
    if not capture_tested:
        return {"state": NEXT_STEP_TARGET_SELECTED, "step": 2,
                "total": total,
                "headline": "Step 2 of 6 — Test capture",
                "detail": "Target selected. Capture has not been verified.",
                "primary_action": "Test capture now"}
    if capture_verdict == "FAIL":
        return {"state": NEXT_STEP_TARGET_SELECTED, "step": 2,
                "total": total,
                "headline": "Step 2 of 6 — Test capture: FAILED",
                "detail": "The last capture test failed. Fix the target or "
                          "backend, then retest.",
                "primary_action": "Retest"}
    if enabled_field_count == 0:
        return {"state": NEXT_STEP_FIELDS_REQUIRED, "step": 3,
                "total": total,
                "headline": "Step 3 of 6 — Add fields",
                "detail": "Capture works. Now add the field(s) you want to "
                          "record.",
                "primary_action": "+ Add field"}
    if not all_regions_confirmed:
        return {"state": NEXT_STEP_REGIONS_REQUIRED, "step": 3,
                "total": total,
                "headline": "Step 3 of 6 — Draw regions",
                "detail": "Every enabled field needs a confirmed region "
                          "before Preview.",
                "primary_action": "Select a field, then Draw region"}
    if not preview_confirmed:
        return {"state": NEXT_STEP_READY_TO_PREVIEW, "step": 4,
                "total": total,
                "headline": "Step 4 of 6 — Preview and arm",
                "detail": "All fields have confirmed regions.",
                # Match the real button label ("Step 4 — Preview all fields")
                # so "Next: Preview all fields" points at a findable control.
                "primary_action": "Preview all fields"}
    return {"state": NEXT_STEP_READY_TO_ARM, "step": 5, "total": total,
            "headline": "Step 5 of 6 — Arm", "detail": "Preview confirmed.",
            "primary_action": "Confirm preview and arm"}


# -- live feed: columns, presets ----------------------------------------------

FEED_COLUMNS = ("time", "tick", "cursor", "field", "raw_ocr", "normalized",
               "capture", "ocr", "value_status", "changed", "retained",
               "journal", "live_csv", "reason", "backend", "ms")

FEED_COLUMN_WIDTHS = {
    "time": 70, "tick": 50, "cursor": 90, "field": 110, "raw_ocr": 140,
    "normalized": 90, "capture": 60, "ocr": 90, "value_status": 140,
    "changed": 60, "retained": 60, "journal": 60, "live_csv": 65,
    "reason": 110, "backend": 130, "ms": 45,
}

# The default "Simple" preset is the exact 8 columns the owner asked for;
# every preset is a subset of FEED_COLUMNS so ttk.Treeview's `displaycolumns`
# can select it without touching the underlying data columns.
FEED_PRESETS: dict[str, tuple[str, ...]] = {
    "Simple": ("time", "tick", "field", "normalized", "value_status",
              "changed", "journal", "live_csv"),
    "OCR": ("time", "tick", "field", "raw_ocr", "normalized", "capture",
           "ocr", "value_status"),
    "Persistence": ("time", "tick", "field", "changed", "retained",
                   "journal", "live_csv", "reason"),
    "Diagnostics": ("time", "tick", "cursor", "field", "capture", "ocr",
                   "backend", "ms", "reason"),
    "All": FEED_COLUMNS,
}
FEED_PRESET_NAMES = tuple(FEED_PRESETS)


# -- plain-language labels for everything shown to a non-developer owner ------
#
# The app tries hard to speak plain language, but several controls still put
# raw internal tokens (snake_case enum values, SCREAMING_SNAKE status codes)
# straight in front of the user. Every such token gets ONE human-readable
# label here - pure and testable, so a single guard test can assert no raw
# code leaks to a user-facing surface. The raw code is preserved in the
# exported CSV/JSON (never changed) and, where useful for support, shown only
# as a parenthetical - never as the whole message.

BACKEND_LABELS = {
    "auto": "Auto (recommended)",
    "printwindow_clientonly": "PrintWindow",
    "copyfromscreen": "CopyFromScreen",
}


_BACKEND_LABEL_TO_VALUE = {label: value
                           for value, label in BACKEND_LABELS.items()}


def backend_label(value: str | None) -> str:
    """Friendly name for a backend token, matching the Help text's
    'Auto / PrintWindow / CopyFromScreen' wording. Unknown/None -> as-is."""
    if value is None:
        return "not resolved yet"
    return BACKEND_LABELS.get(value, value)


def backend_value(label: str) -> str:
    """Map a friendly backend label back to its stored enum token (identity
    if already a token, so a round-trip through the dropdown is always
    safe)."""
    return _BACKEND_LABEL_TO_VALUE.get(label, label)


RETENTION_LABELS = {
    "changed_and_errors": "Changes + errors (default)",
    "changed_only": "Changed values only",
    "every_tick_diagnostic": "Every tick (diagnostic)",
    "values_only": "Values only",
}
_RETENTION_LABEL_TO_KEY = {label: key for key, label in RETENTION_LABELS.items()}


def retention_label(key: str) -> str:
    return RETENTION_LABELS.get(key, key)


def retention_key(label: str) -> str:
    """Map a menu label back to the stored enum key (identity if already a
    key, so a round-trip is always safe)."""
    return _RETENTION_LABEL_TO_KEY.get(label, label)


# value_status codes -> a short plain sentence a non-developer can act on.
VALUE_STATUS_LABELS = {
    "OK": "OK",
    "MISSING_SOURCE_VALUE": "No value yet",
    "OCR_FAILURE": "Could not read the text",
    "NO_NUMBER": "No number found",
    "AMBIGUOUS_MULTIPLE_NUMBERS": "More than one number in the region",
    "MALFORMED_NUMBER": "Number not readable",
    "OUT_OF_RANGE": "Number outside the allowed range",
    "INPUT_TRUNCATED": "Text too long — shortened",
    "UNSTABLE_READING": "Still settling",
    "SOURCE_NOT_VISIBLE": "This field is not visible",
    "TARGET_UNAVAILABLE": "The window is unavailable",
    "CAPTURE_FAILURE": "Capture failed",
    "SUSPECT_GLYPH_CONFUSION":
        "Reading looks miskeyed — a coordinate part is out of range",
}


def value_status_label(code: str) -> str:
    return VALUE_STATUS_LABELS.get(code, code)


# Phase 4.1 (2026-07-19): the recording screen's field cards showed the
# SAME generic "capture/OCR issue" text for every warning colour, whatever
# the actual value_status was - a non-technical owner had no way to tell a
# too-tight region from a wrong decimal separator from a genuinely gone
# window. This gives each reachable failure status its own concrete next
# step, the same pattern pause_guidance already established for pause
# reasons. "" means the short status label above it is already enough.
#
# Real-owner finding (same day, after this shipped): a field still typed
# "number" (never auto-changed - by design) hit the exact danger case the
# `coordinate` type exists for, and got the generic AMBIGUOUS_MULTIPLE_
# NUMBERS/MALFORMED_NUMBER advice below - "redraw a tighter region" - which
# is actively WRONG here: the text is already scoped to one coordinate: no
# amount of redrawing fixes a degree-symbol misread. `raw_text`/`data_type`
# are optional (default "") so every existing call site keeps working
# unchanged; when both are supplied AND the text looks coordinate-shaped
# AND the field isn't already typed `coordinate`, this specific, correct
# hint pre-empts the generic (and here wrong) one.
# Owner escalation (2026-07-21, competition deadline): the text hints
# below existed but the owner never acted on them across two full real
# sessions - the app has to offer the fix itself, one click, at the
# mandatory Step 4 Preview gate. This is the pure decision function (Tk-
# free, so it is headlessly testable and shared by the dialog and any
# future call site): given one field's REAL preview outcome, which type
# would actually work? Returns the suggested data_type string, or None
# when the current type is fine / no better suggestion exists. Suggestion
# only - the caller must still get an explicit owner yes before changing
# anything.
def suggest_field_type(raw_text: str, parse_status: str,
                       data_type: str) -> str | None:
    if parse_status not in ("AMBIGUOUS_MULTIPLE_NUMBERS", "MALFORMED_NUMBER",
                            "NO_NUMBER"):
        return None
    if not raw_text:
        return None
    if data_type == "number":
        if looks_like_coordinate(raw_text):
            return "coordinate"
        if looks_like_alphanumeric_code(raw_text):
            return "auto"
        if parse_status == "NO_NUMBER" and any(
                c.isalpha() for c in raw_text):
            return "auto"
    return None


def value_status_guidance(code: str, *, raw_text: str = "",
                          data_type: str = "") -> str:
    if (code in ("AMBIGUOUS_MULTIPLE_NUMBERS", "MALFORMED_NUMBER",
                "NO_NUMBER")
            and data_type != "coordinate" and looks_like_coordinate(raw_text)):
        return ('Looks like a coordinate value, not a plain number. '
               'Change this field\'s Type to "coordinate" (Edit '
               'selected) for safe parsing.')
    # Same generalization for a number field over genuinely non-numeric
    # content: an alphanumeric code/serial number, or - for NO_NUMBER
    # specifically - any text that contains a letter at all (NO_NUMBER
    # already means "some text was found, but zero numeric candidates in
    # it", so a letter's presence is a reliable signal the field isn't
    # numeric, not just a decimal-separator/redraw problem).
    if data_type in ("number", "coordinate") and raw_text:
        if code == "MALFORMED_NUMBER" and looks_like_alphanumeric_code(
                raw_text):
            return ('Looks like it has letters as well as digits (e.g. an '
                   'ID or code), not a plain number. Change this '
                   'field\'s Type to "text" or "auto" (Edit selected) if '
                   'that\'s expected.')
        if code == "NO_NUMBER" and any(c.isalpha() for c in raw_text):
            return ('No number found, but there is text here. If this '
                   'field isn\'t meant to be a pure number, change its '
                   'Type to "text" or "auto" (Edit selected).')
    return {
        "OK": "",
        "MISSING_SOURCE_VALUE": "",  # live-only; see the guide's hover note
        "OCR_FAILURE":
            "Could not read the text. Try Retest, or raise the upscale "
            "factor via Edit selected.",
        "NO_NUMBER":
            "No number found. Redraw the region around just the value, "
            "or check the field's type.",
        "AMBIGUOUS_MULTIPLE_NUMBERS":
            "More than one number found. Redraw a tighter region around "
            "just this value.",
        "MALFORMED_NUMBER":
            "Not a valid number. Redraw around just the digits, or check "
            "the decimal separator.",
        "OUT_OF_RANGE":
            "Number is outside the allowed range. Confirm the region, or "
            "adjust the range.",
        "INPUT_TRUNCATED":
            "Recognized text was too long and got cut off. Redraw a "
            "smaller region.",
        "UNSTABLE_READING":
            "Still settling across repeated captures - usually resolves "
            "on its own.",
        "SOURCE_NOT_VISIBLE":
            "This region is outside the visible window. Move/resize the "
            "window, or redraw.",
        "TARGET_UNAVAILABLE":
            "The window is gone. If it reopened, choose it again from "
            "the recovery bar.",
        "CAPTURE_FAILURE":
            "Capture failed this tick. If this repeats, try Retest, or "
            "switch backend.",
        "SUSPECT_GLYPH_CONFUSION":
            "A coordinate part looks impossible (likely a misread "
            "symbol). Widen the region, or Retest.",
    }.get(code, "")


# Phase 4.2 (2026-07-19): a field that briefly shows "No value yet" while
# the owner hovers elsewhere is normal (§5k Phase 2.3) and needs no
# guidance - but a field that NEVER gets a value across many consecutive
# ticks is a genuine setup problem (empty region, wrong location) with no
# actionable hint today; it would otherwise show "No value yet" silently
# for the rest of the session. This is a UI-presentation threshold only -
# it never changes value_status, never pauses recording, never touches
# the journal - purely how long the field card waits before upgrading its
# own display from the plain label to an actionable message.
MISSING_VALUE_HINT_TICKS = 10


def missing_value_guidance(streak: int) -> str:
    if streak < MISSING_VALUE_HINT_TICKS:
        return ""
    return (f"No value in the last {streak} captures. Confirm the region "
            f"is drawn over the value's exact on-screen location (Edit "
            f"selected), or Retest.")


STABILITY_LABELS = {
    "IMMEDIATE": "recorded",
    "PENDING_CONFIRMATION": "confirming…",
    "CONFIRMED": "confirmed",
    "REJECTED": "not kept",
    "NOT_EVALUATED": "",
}


def stability_label(code: str) -> str:
    return STABILITY_LABELS.get(code, code)


CONTENT_STATUS_LABELS = {
    "CONTENT_DETECTED": "real content",
    "NEAR_UNIFORM_DARK": "solid dark (nothing visible)",
    "NEAR_UNIFORM_LIGHT": "solid light (nothing visible)",
    "NEAR_UNIFORM_OTHER": "single flat colour (near-blank)",
    "NOT_EVALUATED": "not checked",
}


def content_status_label(code: str) -> str:
    return CONTENT_STATUS_LABELS.get(code, code)


def xyz_status_sentence(eligible: bool, missing_axes: list[str]) -> str:
    """Plain, optional-framed XYZ status for the Ready screen. The old text
    ('exactly one enabled number source must hold role x') read like a hard
    error, used the internal word 'source', and revealed only the first
    missing axis. XYZ is optional, so say so, use 'field', and list every
    missing axis at once."""
    if eligible:
        return ("XYZ export: ELIGIBLE — one number field is assigned to "
                "each of X, Y and Z.")
    axes = ", ".join(missing_axes) if missing_axes else "X, Y, Z"
    return ("XYZ export (optional): not enabled — assign one number field "
            f"to each of X, Y and Z. Missing: {axes}.")


_WARNING_LABELS = {
    "JOURNAL_MISSING": "The recording journal file was missing",
    "JOURNAL_SEQUENCE_BREAK": "A gap was found in the recorded events",
    "MALFORMED_JOURNAL_LINE": "A recorded event line was unreadable",
    "PARTIAL_FINAL_LINE": "The last recorded line was incomplete and skipped",
    "FINAL_CSV_ROW_COUNT_MISMATCH":
        "Some captured rows are missing from the final CSV",
    "FINAL_CSV_UNREADABLE": "The final CSV could not be read back to verify",
    "CHECKPOINT_DIVERGENCE":
        "The recovery checkpoint did not match the journal",
    "MISSING_CROP": "A crop image was missing",
    "ORPHAN_CROP": "A crop image had no matching event",
    "CROP_HASH_MISMATCH": "A crop image did not match its recorded checksum",
}


def warning_sentence(code: str) -> str:
    """Turn a raw finalize/recovery warning code (optionally 'CODE: detail')
    into a plain sentence, keeping any detail as a parenthetical. Unknown
    codes fall back to a de-underscored, capitalized form so no raw
    SCREAMING_SNAKE token is ever shown."""
    prefix, _, detail = code.partition(":")
    prefix = prefix.strip()
    label = _WARNING_LABELS.get(prefix)
    if label is None:
        label = prefix.replace("_", " ").capitalize()
    detail = detail.strip()
    return f"{label} ({detail})" if detail else label


def xyz_outcome_sentence(xyz: dict) -> tuple[str, str]:
    """(sentence, colour) for the Finalized screen's XYZ line, from the
    finalize summary's 'xyz' block. Green when the point cloud was actually
    written; amber with a plain reason when it was not - the owner never has
    to open the folder to learn whether they got their point cloud."""
    if xyz.get("written"):
        excluded = xyz.get("excluded_event_count", 0)
        extra = (f" ({excluded} event(s) had a non-OK axis and were "
                 f"excluded)" if excluded else "")
        return (f"XYZ export: WRITTEN — {xyz.get('row_count', 0)} points to "
                f"points.xyz{extra}.", "#1a7f37")
    reason = xyz.get("reason") or "not eligible"
    # Turn the internal eligibility reason into plain, optional-framed text.
    if "role" in reason:
        reason = ("assign one number field to each of X, Y and Z to enable "
                  "it")
    return (f"XYZ export (optional): not produced — {reason}.", "#b58900")


def field_card_status(value_status: str, stability_status: str,
                      persistence_label: str) -> str:
    """The one-line status under a field card, fully humanized. Drops empty
    parts so a healthy field reads e.g. 'OK · recorded · Persisted to
    journal' rather than leaking 'OK · IMMEDIATE · …'."""
    parts = [value_status_label(value_status),
             stability_label(stability_status), persistence_label]
    return " · ".join(p for p in parts if p)


# Live-feed and Saved-CSV-preview column headers: friendly titles instead of
# the raw column ids upper-cased (which leaked VALUE_STATUS / LIVE_CSV /
# RAW_OCR / MONOTONIC_OFFSET_MS to the user). displaycolumns still uses the
# raw ids, so only the visible heading text changes.
FEED_COLUMN_TITLES = {
    "time": "Time", "tick": "Tick", "cursor": "Cursor", "field": "Field",
    "raw_ocr": "Raw OCR", "normalized": "Value", "capture": "Capture",
    "ocr": "OCR", "value_status": "Status", "changed": "Changed",
    "retained": "Kept", "journal": "Saved", "live_csv": "Live CSV",
    "reason": "Reason", "backend": "Backend", "ms": "ms",
}


def feed_column_title(col: str) -> str:
    return FEED_COLUMN_TITLES.get(col, col.replace("_", " ").title())


# Fixed leading columns of the wide CSV, humanized for the on-screen preview
# only (the written file keeps the exact snake_case header).
CSV_PREVIEW_TITLES = {
    "event_seq": "Event #", "event_id": "Event ID",
    "event_status": "Status", "capture_utc": "Captured at (UTC)",
    "monotonic_offset_ms": "Offset (ms)",
}


def csv_preview_title(col: str) -> str:
    if col in CSV_PREVIEW_TITLES:
        return CSV_PREVIEW_TITLES[col]
    # Dynamic per-field columns look like "<Field> [VALUE]" already - keep
    # them, only tidy any residual snake_case token.
    return col if "[" in col or " " in col else col.replace("_", " ").title()


# The recording feed's six row colours, as a compact on-screen legend (Help
# has the full prose; this lives next to the colours themselves). Yellow was
# previously undocumented on screen AND missing from Help.
FEED_COLOR_LEGEND = (
    ("gray", "seen"), ("blue", "confirming"), ("green", "saved"),
    ("orange", "saved, live CSV lagged"), ("yellow", "problem, not kept"),
    ("red", "error kept"),
)
