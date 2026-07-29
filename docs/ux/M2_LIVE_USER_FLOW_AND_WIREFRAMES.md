# M2-Live User Flow and Wireframes

**Status: OWNER APPROVAL GATE — implementation must not begin until the
owner confirms this journey matches the intended application.** (M1 was
technically correct but missed the intended workflow; this document exists
to prevent a repeat.) Legal-action table §3 is the single source of truth
for the UI state machine referenced by the architecture.

## 1. User journey (happy path)

1. Launch `python -m screen2xyz_m2` → **SETUP** screen.
2. Click **Select target window** → live list of visible windows (title +
   process); pick the viewer application; its identity appears in the
   header. (Fallback tab: pick a monitor instead.)
3. Click **Add source** (repeat 3+ times): type a name ("Longitude"),
   choose Number/Text/Auto, optionally choose role X/Y/Z/metadata.
4. For each source click **Draw region** → a **countdown** (default 3 s,
   configurable 3–5 s) lets the user return the pointer to the target so
   hover-dependent fields show real values → exactly one
   `REGION_SNAPSHOT` frame is
   captured and opens in a picker canvas (the backend that produced it is
   shown; a near-uniform whole frame offers **Compare fallback**, which
   requires a new countdown and one separate snapshot) → drag a rectangle
   around the value field → the crop preview appears next to the source
   row.
5. Click **Preview all** → **PREVIEW GATE**: same countdown, then exactly
   one distinct `PREVIEW` operation and
   fresh synchronized frame; every source shows its crop image, pixel
   size, coordinates, and OCR preview text. Empty OCR on a
   hover-dependent field is allowed and never treated as capture failure —
   the user judges alignment. Fix any
   misaligned rectangle and re-preview.
6. Click **Confirm preview** → this **arms the session** and shows the
   **READY** summary (target, sources, interval, retention mode, output
   folder, disk estimate). Optionally **Save profile**.
7. Click **● Start recording** → **RECORDING**: red REC banner, live grid
   updating every second, history table gaining rows only for configured
   retained value changes/errors/recoveries, and a **compact always-on-top mini controller** (REC/PAUSED,
   elapsed, Pause/Resume, Stop, emergency Stop)
   that stays visible even when the target application covers the main
   window and is placed away from every configured region. The user goes to
   the target application and moves the mouse;
   Screen2XYZ needs no further interaction.
8. **Pause** any time (banner turns yellow PAUSED); **Resume** continues.
9. Click **■ Stop** → **FINALIZED**: run summary, output paths, export buttons
   (wide/long CSV always; XYZ button enabled only when the X/Y/Z gate passes,
   with the reason shown when disabled). Esc is **Emergency Stop**: it ends
   capture within the hard bound and attempts finalization, but may leave the
   run recoverable rather than finalized.
10. Recovery path: after an emergency stop or crash with incomplete
    finalization, next launch offers
    "Recover unfinalized run <id>" which rebuilds exports from the journal.

## 2. Wireframes (low-fidelity, annotated)

### SETUP

```
┌─ Screen2XYZ M2 — Live Region Watch ────────────────────────────────────┐
│ Target: [ (none selected) ▼ Select window… ] [ Monitor tab ]           │
│         → after selection: "Target Viewer — viewer.exe (hwnd 0x51A2)" │
│ ─────────────────────────────────────────────────────────────────────  │
│ Sources                     [+ Add source]                             │
│ ┌──┬──────────┬────────┬──────┬────────────┬───────────┬────────────┐  │
│ │# │ Name     │ Type   │ Role │ Region     │ Preview   │            │  │
│ ├──┼──────────┼────────┼──────┼────────────┼───────────┼────────────┤  │
│ │1 │Longitude │ Number │  X   │ 812,64 180×28 │ [crop] │[Draw][Del] │  │
│ │2 │Latitude  │ Number │  Y   │ 812,96 180×28 │ [crop] │[Draw][Del] │  │
│ │3 │Elevation │ Number │  Z   │ 812,128 180×28│ [crop] │[Draw][Del] │  │
│ └──┴──────────┴────────┴──────┴────────────┴───────────┴────────────┘  │
│ Interval [1.0 s ▾]  Retention [Changes + errors ▾]  ☐ cursor metadata  │
│ Stability [fast: confirm=1 ▾]   Profile: [Load…] [Save…]               │
│                                            [ Preview all → ]           │
└────────────────────────────────────────────────────────────────────────┘
```
Notes: "Draw region" opens a frozen snapshot (never a live always-on-top
overlay); rectangles are drawn on the snapshot, stored client-relative.
Role dropdown refuses a second X/Y/Z with "already assigned to
<name> — move it here?".

### PREVIEW GATE (modal, mandatory)

```
┌─ Preview — confirm every field is aligned ─────────────────────────────┐
│ Frame: 2026-07-18 04:12:03Z · client 1280×720 @ (208,231) · DPI 96     │
│ Backend candidate: PrintWindow(PW_CLIENTONLY)  [whole frame: content]  │
│ ┌───────────┬───────────────┬──────────┬──────────────────────────┐    │
│ │ Longitude │ [crop image]  │ 180×28   │ OCR: "-123.654321"       │    │
│ │ Latitude  │ [crop image]  │ 180×28   │ OCR: "49.123456"         │    │
│ │ Elevation │ [crop image]  │ 180×28   │ OCR: "87.05"             │    │
│ └───────────┴───────────────┴──────────┴──────────────────────────┘    │
│ ⚠ shown here when backend fell back to CopyFromScreen:                 │
│   "Keep the target window visible and uncovered while recording."      │
│                       [ ← Back to setup ]  [ Confirm preview ✓ ]       │
└────────────────────────────────────────────────────────────────────────┘
```

### READY

```
│ Target … · 3 sources · 1.0 s · Changes + errors · .lab_work/m2_runs/   │
│ Estimated disk: ~4 KiB/event · caps: warn 200 MiB stop 500 MiB         │
│ XYZ export: ELIGIBLE (X=Longitude, Y=Latitude, Z=Elevation)            │
│                     [ ● Start recording ]                              │
```

### RECORDING

```
┌─ ● REC  Target Viewer — 00:04:12 · tick 252 (1.00 s actual) ───────────┐
│ last tick 24 ms · skipped 0 · OCR errors 1 · events 87 · disk 3.1 MiB  │
│ ┌ Current values (updates EVERY tick) ────────────────────────────┐    │
│ │ Longitude  -123.660102   OK          Latitude  49.120441   OK   │    │
│ │ Elevation  86.90         OK                                     │    │
│ └─────────────────────────────────────────────────────────────────┘    │
│ ┌ History (retained changes/errors) ── newest first ──────────────┐    │
│ │ #87 04:16:15Z  -123.660102  49.120441  86.90   [crops]          │    │
│ │ #86 04:16:14Z  -123.659871  49.120380  86.92   [crops]          │    │
│ │ #85 04:16:12Z  ⚠ Longitude: several numbers found — kept        │    │
│ │                 for review [crops]                              │    │
│ └─────────────────────────────────────────────────────────────────┘    │
│ [ ⏸ Pause ]  [ ■ Stop ]   (Esc = emergency stop)   [Diagnostics ▾]     │
└────────────────────────────────────────────────────────────────────────┘
   mini controller (always on top, movable, outside regions by default):
   [● REC 00:04:12] [⏸ Pause] [■ Stop] [! Emergency Stop]
```
Diagnostics panel (collapsible): per-source bounded raw OCR of the last
tick, `worker_status`, `capture_status`, frame/crop content diagnostics,
`ocr_status`, `parse_status`, `stability_status`, `value_status`, capture/OCR
timings, worker generations/restarts, and `ocr_executed`/cached flags. Codes
appear only here and in the journal; history rows are sentences.

PAUSED variant: banner turns yellow and **always states the cause with a
cause-specific primary action**, e.g.:
- "⏸ Paused: you pressed Pause — [Resume]"
- "⏸ Paused: target window was resized — [Disarm and re-preview]"
- "⏸ Paused: target window closed — [Disarm and choose window…]"
- "⏸ Paused: five near-uniform whole frames — [Disarm and preview
  fallback] [Resume anyway]"
- "⏸ Paused: disk limit reached — [Open folder] [Stop]"
- "⏸ Paused: three consecutive worker failures — [Resume] [Stop]"
The mini controller shows
[⏸ PAUSED 00:04:12] [▶ Resume] [■ Stop] [! Emergency Stop] in this state.

Whenever the UI is in a setup state—including same-run repair after DISARM—
three consecutive setup/request failures do not create a PAUSED session:
"Worker unavailable during setup — [Retry worker]" remains on the current
setup screen. The exact orthogonal interlock is defined with the legal-action
table below.

### FINALIZED

```
┌─ Run finalized — m2-20260718T041203Z ──────────────────────────────────┐
│ 252 ticks · 87 change events · 2 error events · 0 skipped              │
│ Output: .lab_work/m2_runs/m2-20260718T041203Z/   [Open folder]         │
│ Manifest: verified ✓        Warnings: 1 (see errors.log)               │
│ Files already written by finalize (buttons OPEN them, no rewriting):   │
│ [ Open wide CSV ] [ Open long CSV ] [ Open XYZ (85 rows, 2 excluded) ] │
│   XYZ unavailable example: "XYZ not produced: no source assigned Z"    │
│ [ Re-run export ] — regenerates all exports AND the manifest, then     │
│                     re-verifies (never leaves a stale manifest)        │
│ [ New session ]                                                        │
└────────────────────────────────────────────────────────────────────────┘
```
Finalize writes all exports and the manifest in one pass (M2-FR-061); the
per-file buttons only open existing files, so the verified-manifest
indicator can never silently go stale.

## 3. State machine and legal actions (single source of truth)

States: `IDLE → TARGET_SELECTED → REGIONS_CONFIGURED → ARMED (= READY
screen; entered by Confirm preview, which is the arming transition) →
RECORDING ↔ PAUSED → STOPPING → FINALIZED`. There is no intermediate
preview state: **Confirm preview arms**; any edit to target,
sources, or regions disarms back to REGIONS_CONFIGURED.
`setup_worker_blocked` is a separate closed boolean interlock, not a state.

| Action \ State | IDLE | TARGET | REGIONS | ARMED (READY) | RECORDING | PAUSED | STOPPING | FINAL |
|---|---|---|---|---|---|---|---|---|
| Select/replace target | ✔ | ✔ | ✔ | DISARM→TARGET¹ | — | DISARM→TARGET³ | — | ✔ (new session) |
| Add/edit/remove source | — | ✔ | ✔ | DISARM→REGIONS¹ | — | — | — | — |
| Draw region (countdown `REGION_SNAPSHOT`) | — | ✔ | ✔ | — | — | — | — | — |
| Save profile | ✔ | ✔ | ✔ | ✔ | — | — | — | ✔ |
| Load profile | ✔ | ✔ | ✔ | DISARM→REGIONS¹ | — | — | — | ✔ (new session) |
| Preview all (countdown `PREVIEW`) | — | — | ✔ | — | — | — | — | — |
| Confirm preview (`ARM`) | — | — | ✔ (after PREVIEW) | — | — | — | — | — |
| Start recording | — | — | — | ✔ | — | — | — | — |
| Retry worker⁵ | — | ✔ if blocked | ✔ if blocked | ✔ if blocked | — | — | — | — |
| Pause / Resume | — | — | — | — | ✔ pause | ✔ resume² | — | — |
| Reconfigure/re-preview | — | — | — | DISARM→REGIONS | — | DISARM→REGIONS² | — | — |
| Cancel ready / Stop session | — | — | — | DISARM→REGIONS | STOP→STOPPING | STOP→STOPPING | in progress | — |
| Emergency Stop / Esc | — | — | — | ✔ (disarm) | ✔ (≤2 s) | ✔ (≤2 s) | — | — |
| Export / open outputs | — | — | — | — | — | — | — | ✔ |
| Close app (kills worker) | ✔ | ✔ | ✔ | ✔ | ✔⁴ | ✔⁴ | ✔ | ✔ |

¹ The edit action is not executed in ARMED: the UI sends DISARM first,
invalidates the preview, transitions to the shown configuration state, and
only then performs the action.
² Direct RESUME is available for a plain user pause or resolved non-layout
cause. Resize/DPI/topology repair sends DISARM, enters REGIONS_CONFIGURED,
runs explicit PREVIEW→ARM, then RECORD_START resumes the same run under an
incremented configuration revision. No PREVIEW is legal while PAUSED.
³ Window loss sends DISARM before the user selects a replacement; no title
is auto-selected.
⁴ close during recording = emergency stop: worker terminated, journal
finalize attempted, run recoverable via `recover` if finalize incomplete.
⁵ At setup-state failure count ≥3, `setup_worker_blocked=true` overrides every
worker-dependent cell in the table: REGION_SNAPSHOT, PREVIEW, ARM, DISARM,
RECORD_START/Start, and HEALTH are unavailable. No worker exists. Local Save
profile and Close remain available; a local target/source/region edit invalidates
any prior arm, increments the configuration revision, and leaves the interlock
set. Retry worker is the only action that may spawn: after any remainder of the
saturated 5 s backoff measured from teardown, it starts a fresh generation and
sends INIT only for the current state/revision. It never reissues the failed
command. Successful INIT clears the interlock but not the setup counter; the
next successful setup/state request resets the counter. Failed INIT increments
it and leaves the interlock set.

Capture-side enforcement (architecture §7/§10): worker verbs
ARM/DISARM/RECORD_START/PAUSE/RESUME mirror these states; `CAPTURE` is
rejected unless recording; `REGION_SNAPSHOT` and `PREVIEW` are distinct,
explicit-click, one-frame operations legal only in the table's pre-ARM
states; the Tk close handler always runs the worker shutdown path.

## 4. Non-developer usability checks (acceptance)

- Every screen has exactly one primary action, labelled with a verb.
- No configuration requires editing files; profiles are optional.
- Errors are sentences ("Longitude region is outside the window — redraw
  it"), never bare codes; codes appear only in the diagnostics panel and
  journal.
- The REC/PAUSED banner is visible without scrolling at every window size
  ≥ 900×600.
- The complete manual acceptance plan (including the 30-minute soak) is executable by
  the owner without developer assistance.

## 5. Owner approval checklist (to sign in OWNER_DECISIONS)

- [ ] The journey in §1 matches how you intend to use the tool.
- [ ] **Do the value fields in your target application still show values
  when the mouse leaves it / it loses focus?** If they blank on
  mouse-out, confirm the countdown-snapshot mechanism (hover the target
  during the 3-second countdown) is workable for you — this is the
  make-or-break setup question.
- [ ] Region drawing on a countdown-captured frozen snapshot (not a live
  overlay) is right.
- [ ] Default history-on-change/error/recovery with an always-updating live
  grid is right.
- [ ] Fast stability default (record every changed second) is right.
- [ ] The always-on-top mini controller (REC/PAUSED, elapsed, Pause/Resume,
  Stop, emergency Stop) is acceptable and can sit outside the configured
  regions while you work.
- [ ] Cursor metadata default OFF is acceptable; enabling it is an explicit
  per-session choice.
- [ ] The finalize/export screen covers what you need after a session.
