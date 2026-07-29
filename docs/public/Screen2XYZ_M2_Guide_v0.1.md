# Screen2XYZ M2-Live Guide — Live Region Watcher

M2-Live watches fixed value fields in an explicitly selected window and
records their changes as reviewable, structured data. It is local-only, has
no network, controls nothing on screen, and captures only after you press
Start. Synthetic evidence only until the real-target validation passes;
conceptual and preliminary estimating data only.

## First-time setup (once)

The app needs only a Python virtual environment — there are **no third-party
dependencies** (it uses only the Python standard library: tkinter, ctypes).
From the repository root:

```powershell
python -m venv .venv
```

That is all — do **not** run `pip install`; there is nothing to install, and
the launchers set `PYTHONPATH=src` for you.

## Quick start (Windows, from the repository root)

**One-click launchers** — **right-click the `.ps1` → "Run with PowerShell"**.
(Double-clicking a `.ps1` in Explorer opens it in an editor, it does *not*
run it — that is a Windows default, not a bug.) If Windows says running
scripts is disabled, run it once with:
`powershell -ExecutionPolicy Bypass -File .\run_screen2xyz.ps1` — that
`-ExecutionPolicy Bypass` only affects that one launch, never system-wide.

```powershell
.\run_screen2xyz.ps1              # normal application
.\run_screen2xyz_demo.ps1         # automated self-test against the synthetic target
.\run_screen2xyz_demo.ps1 -Interactive   # just open the synthetic target window
.\run_screen2xyz_validation.ps1   # guided real-target validation (G-E-REAL)
.\run_screen2xyz_menu.ps1         # a simple text menu covering all of the above
```

Each launcher resolves the repository root from its own file location
(`$PSScriptRoot`, not your current directory), checks
`.venv\Scripts\python.exe` exists with a clear error otherwise, and keeps
the window open on any error (and, for the demo/validation launchers, always
holds the window open at the end so you can read the result).

**Fallback direct commands** (equivalent to the launchers above):

```powershell
$env:PYTHONPATH = "src"

# Launch the live watcher UI
.\.venv\Scripts\python.exe -m screen2xyz_m2 ui

# Try the whole workflow against a safe synthetic target (no real app needed)
.\.venv\Scripts\python.exe -m screen2xyz_m2 demo

# Run the deterministic M2 test suite
.\.venv\Scripts\python.exe tests_m2\run_m2_tests.py

# Run the real Windows integration tests (real worker + synthetic targets)
.\.venv\Scripts\python.exe tests_m2\run_m2_integration.py

# Run the bounded stress/soak harness (8-source, repeated retest/start-stop, a 40s soak)
.\.venv\Scripts\python.exe tests_m2\run_m2_soak.py

# Rebuild exports of an interrupted run
.\.venv\Scripts\python.exe -m screen2xyz_m2 recover <run_id>
```

## Guided workflow (numbered steps in the UI)

1. **Choose what to capture** — pick one window (title + process + pid) or a
   monitor, and a **backend**: `auto` (recommended default), `printwindow_clientonly`,
   or `copyfromscreen`. See "Backends explained" below.
2. **Test capture** — click **Test capture now** before doing anything else
   - it works before any field exists, since it only checks that Screen2XYZ
   can see the target at all. It takes one real capture, shows you the
   exact frame, and reports a plain PASS / WARNING / FAIL verdict. It never
   reports PASS for a solid black or white frame. Use **Retest** any time
   the target changes (moved, resized, restored). If the capture worker
   fails three times in a row it is blocked and Retest is disabled with a
   red explanation; click the **Retry** button that appears next to it to
   clear the block and try again. A persistent **Next step** card at the
   top of the window always shows the current step, what your last action
   did, and what to do next - it also disables Test capture/Retest (with a
   visible reason) whenever clicking it would not currently be legal, so a
   click is never left with no visible response. **Save diagnostic
   screenshot locally** and **Open diagnostics folder** let you inspect
   exactly what was captured, entirely offline, under
   `.lab_work/m2_diagnostics/`.
3. **Add fields and draw regions** — add 1–8 fields, name each, set type
   (number/text/auto/**coordinate** — for lat/long-style text; see the
   walkthrough below) and optional role (X/Y/Z/metadata/none — X/Y/Z
   require a number or coordinate field), then **Draw region…**. Screen2XYZ enters **REGION
   SELECTION MODE**: a large banner names the field, the cursor becomes a
   crosshair, everything outside your drag is dimmed, and live x/y/width/
   height are shown in original physical pixels no matter how far you Zoom
   in/out (Fit to window and 100% are also available). Release the drag and
   a real crop + OCR preview appears (raw OCR, normalized value, capture/
   OCR/parse status, content classification) — **Confirm this region**
   stays disabled until the crop is real and non-blank. A crop that is a
   single flat color other than black/white is blocked by default too
   (it might be a genuinely blank field, or the wrong region); tick
   **"Use anyway (advanced)"** and confirm a second warning dialog if you
   are sure — this override is recorded in the session's saved metadata.
   If the target resizes or its DPI changes while the picker is open,
   Confirm is blocked until you Redraw against a fresh snapshot. **Redraw**
   clears the in-progress selection; **Cancel** (or Esc) closes without
   touching the field's previously confirmed region. After you confirm, the
   setup table keeps a thumbnail/OCR/normalized-value preview for that
   field — select its row to see the full details below the table, without
   reopening the picker. **Review selected regions** shows every field's
   region numbered and outlined on one screenshot with a details panel for
   the selected one — click a region to select that field, then Edit/
   Redraw/Remove it, or **Re-test all regions** to refresh every field's
   preview at once.
4. **Preview and verify** — a real capture + OCR runs for every field; you
   must tick "aligned with the intended value" for each one before you can
   arm. This is the point where a wrong region or wrong backend shows up
   clearly, before you commit to recording.
5. **Arm / Start** — Confirming preview arms the session; **START RECORDING**
   begins the actual ~1 Hz capture loop.
6. **Recording** — a red **● REC** banner, a **● captured** indicator that
   flips on every tick so you can see the program working even when nothing
   changed, elapsed time, last tick duration, skipped-tick count, OCR error
   count, target-visibility/pause-reason status, the effective backend, and
   storage used. **Field cards** — one compact card per field, scrollable
   sideways for up to 8 fields without clipping — show a live crop
   thumbnail, raw OCR, normalized value, value/stability status, last-
   changed/last-persisted times, the region's coordinates, and a warning
   badge. The **Live capture and CSV feed** shows one color-coded scrolling
   row per field per tick — gray (observed live only), blue (a candidate
   awaiting stability confirmation), green (persisted to journal **and**
   the live CSV snapshot updated), orange (persisted to journal but the
   live CSV snapshot update failed), red (retained error), yellow (a
   warning, empty OCR, or temporary capture issue). A **Columns** preset
   picker (Simple/OCR/Persistence/Diagnostics/All) shows only what you
   need; the feed has both vertical and horizontal scrollbars. Filters:
   Show-saved-rows-only, Show-warnings-only, Pause-auto-scroll, and Clear-
   screen-feed (clears only what's displayed, never recorded data).
   **The four persistence states, in order**: *Observed live* (this tick's
   reading, nothing saved yet) → *Persisted to journal* (durably fsynced to
   `events.jsonl` - the real, crash-safe record) → *Live CSV snapshot
   updated* (a best-effort preview file regenerated so you can inspect
   progress in a spreadsheet while still recording) → *Final CSV finalized*
   (only after Stop, with its row count verified against the journal). The
   **Saved CSV rows** tab is clearly labeled as showing the **live
   snapshot** while recording (`events_wide.live.csv`), until then showing
   "No rows have been written yet." **Diagnostic snapshot** saves the
   current per-field crops locally on demand; **Open run folder** / **Open
   CSV folder** jump straight to the output. A movable always-on-top mini
   controller (placed outside your capture regions) shows REC/PAUSED and
   Pause/Resume/Stop/Emergency Stop even when the target covers the main
   window.
7. **Pause / Resume / Stop** — Stop finalizes; Esc is an emergency stop that
   ends capture within 2 seconds. If the target resizes or its DPI changes,
   recording auto-pauses and Resume is disabled until you click **Disarm
   and re-preview…**, which reconfigures, re-snapshots the target, and
   reopens the real preview gate — confirming it returns you to the Ready
   screen, where Start Recording continues the *same* run (nothing is
   lost, only the on-screen feed resets).
8. **Finalized** — wide CSV (one row per retained event), long CSV (one row
   per observation), a sanitized summary, a strict XYZ (only when one
   number field each holds X/Y/Z and all three read OK), and a SHA-256
   manifest, all under the ignored `.lab_work/m2_runs/<run_id>/`. The
   Finalized screen shows the verified final CSV row count (checked against
   the journal - a mismatch would be shown as a warning, never hidden) and
   the live-snapshot row count you saw while recording, side by side.
   **Open run folder** is right there on the finalized screen.

`Help` (button, top-right) explains every control in one place, including
Draw region, Confirm this region, the advanced near-uniform override,
Redraw, Review selected regions, field cards, the Live feed's column
presets, the four persistence states (Observed live / Persisted to journal
/ Live CSV snapshot updated / Final CSV finalized), Saved CSV rows, and
"stability state"; `How this works` re-shows the first-run welcome
walkthrough at any time.

## Demo mode — try it without a real application

Click **Demo mode** in the UI, or run:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_m2 demo
```

This launches a safe, synthetic X/Y/Z target window with no real data, and
(from the command line) automatically drives the entire real pipeline
against it — Auto backend resolution, preview, stable/changing/empty/
malformed/Unicode-minus values, a resize that requires re-preview, a
minimize that auto-pauses, resume, manual pause/resume, and a finalized
export — then prints a PASS/FAIL report. **Run full self-test** in the UI
does the same thing with a small progress dialog and a readable report.
Every command to the demo target carries a sequence number and a session
token that its ack must echo back exactly, so a stale or duplicate reply
can never be mistaken for the current one. The self-test runs its capture
pipeline on CopyFromScreen (a framebuffer copy that sends no messages to the
demo target's window), which eliminated a rare handshake stall that used to
occur when PrintWindow was used against the target the test also drives; it
now passes reliably without needing a retry.

**Guided demo** (button, top-right) walks through the whole workflow one
visible action at a time against the real app - launching the target,
adding fields, Test capture, opening the real REGION SELECTION MODE picker,
previewing, recording, watching field cards and the Live feed move
gray/blue to green, resizing the target and using the real "Disarm and
re-preview…" recovery button, minimizing/restoring, pausing/resuming, and
finalizing - advancing only when you click Next, including after you
finish interacting with a step's own dialog.

## Backends explained

- **Auto (default, recommended)** — tries PrintWindow first, checks the
  result against real content (not solid black or white), and falls back to
  CopyFromScreen if PrintWindow can't see the window. Once resolved it is
  remembered for the rest of the session (it does not re-test every tick).
  A hung PrintWindow call (this happens on some real, DWM-composited
  windows) is bounded to ~1.5 seconds before falling back, so it can never
  stall the capture loop.
- **PrintWindow (explicit)** — can see a window's content even if another
  window covers it, but not every application supports it.
- **CopyFromScreen (explicit)** — always works, but only sees pixels that
  are actually visible on screen: covered or off-screen parts are lost. If
  your target is larger than the desktop or spans monitors, the setup
  screen shows a warning when this applies.

## Live map coordinates (Google Earth) walkthrough

This walks through the specific case this app was built for: a map
application (e.g. Google Earth) whose lat/long/elevation readout is one
thin line of small text, such as `49°08'20.06"N 123°03'41.61"W 87.05`, in
a corner of the window.

1. **Don't try to draw three separate tiny boxes.** Measured evidence: at
   realistic on-screen scale the three values sit only ~5px apart - too
   tight for a mouse-drawn region to reliably isolate just one without
   catching a sliver of its neighbour. Draw **one** region around the
   **whole line** instead, with normal margin on all sides, the same way
   you'd draw any other field.
2. **Add three fields that share that one region.** Add "Lat", "Long", and
   "Elev" as usual (Step 3). For Lat and Long, set **Type** to
   **coordinate** (not number) - it understands `°`/`'`/`"` and, if OCR
   ever misreads the degree symbol as a stray digit (a real, observed OCR
   behavior - see below), it flags that instead of quietly saving a wrong
   value. For Elev, plain **number** is fine. Give Lat and Long **Role**
   X and Y; give Elev **Role** Z if you want an XYZ export - coordinate
   fields are just as valid an X/Y holder as number fields.
3. **Give every field the same region.** Draw the region once (on
   whichever field you add first), then for the other two open **Edit
   selected** and use **"Copy region from"** to copy that same rect in,
   rather than re-drawing or hand-typing coordinates.
4. **Set which part of the line each field reads.** Still in **Edit
   selected**, set **Line part** to `0` for the first value on the line
   (Lat), `1` for the second (Long), `2` for the third (Elev). Each field
   then reads only its own piece of the shared region's text - the region
   itself never needs to change again even if you reorder fields.
5. **Leave Upscale factor at its default (1).** Small on-screen text like
   this is upscaled automatically before reading; you should not need to
   set it by hand for a normal readout at this scale.
6. **What you'll see if OCR misreads the degree symbol.** Windows OCR can
   read `°` as the digit `0` at this text scale - a real, reproduced
   behavior, not a hypothetical. A **coordinate**-typed field never turns
   that into a silently wrong number: it shows **"Reading looks miskeyed
   - a coordinate part is out of range"** and an actionable hint to widen
   the region slightly or Retest, exactly like any other flagged field -
   never a number that merely looks plausible but is actually 10-1000x
   too large.
7. **A value blinking to "No value yet" is normal**, not an error, if the
   readout only appears while you hover the map (see Troubleshooting
   above) - it does not touch your saved history. If a field genuinely
   never gets a value across many captures, the field card will say so
   explicitly with a concrete next step, rather than staying silent.

**Honest about limits**: this walkthrough, the `coordinate` type, and the
shared-region/line-part feature were built and proven against a synthetic
stand-in target that renders the same combined-line format at the same
on-screen scale - driven through the real capture worker and real Windows
OCR engine, not a mock (see `M2_IMPLEMENTATION_REPORT.md` §5k Phases 1-2
for the exact evidence). They have **not** been run against your actual
Google Earth window. Real-target support is not claimed until you run the
formal validation below against your own application.

## Real-target validation (owner, one time)

Real-target support is **not claimed** until you run:

```powershell
.\run_screen2xyz_validation.ps1
# or: .\.venv\Scripts\python.exe -m screen2xyz_m2 validate-real-target
```

This opens a guided wizard built on the exact same setup screen, region
picker, preview gate, and recording dashboard you use normally - not a
separate tool. It first asks you to confirm the target contains only
authorized, non-confidential content (declining marks the run BLOCKED
immediately); you then select the real target, draw 1-8 real regions, and
confirm the real preview for each field. While recording, a small always-
on-top panel lets you mark "I changed a target value" (required) and
exercise Pause/Resume. After Stop it asks four plain-language confirmation
questions (crops aligned? values matched the real target? was the
recording screen understandable? was an exported row meaningful?) and
computes the result: **PASS** only if every technical check (captures
occurred, OCR was meaningful, a change was both detected and owner-
confirmed, the event was journaled, the live CSV snapshot updated, the
final CSV was generated and its row count verified against the journal,
crop artifacts are clean, no worker process was left running) **and** all
four confirmations are true; otherwise **FAIL**, or **BLOCKED** for an
environmental limitation (declined consent, or "Mark as BLOCKED" on the
setup screen if capture itself isn't supported for this target). A
sanitized JSON report (no screenshots, no raw window identity) is written
under the ignored run root - share only that JSON.

## Where output files are stored

Everything is under the repository's ignored `.lab_work/` directory and
never committed or uploaded:
- `.lab_work/m2_runs/<run_id>/` — recording exports (CSV/JSON/manifest).
- `.lab_work/m2_diagnostics/<timestamp>/` — manual diagnostic snapshots
  (setup-screen or recording-screen button) and their sanitized metadata.
- `.lab_work/m2_profiles/` — saved source/session profiles, if used.

## Troubleshooting

- **"Test capture now" seemed to do nothing** — fixed: this was a real bug
  where clicking Test capture before any field existed (the normal order -
  Step 2 comes before Step 3) crashed a check silently, leaving Step 2
  frozen at "Not tested yet" with no error shown. It now works correctly
  before any field exists. If a click still ever appears to do nothing, an
  internal-error dialog will now always appear (never a silent freeze),
  and the failure is logged locally under
  `.lab_work/m2_diagnostics/callback_errors.log`.
- **Changed the backend dropdown but nothing seems different** — fixed:
  changing Auto/PrintWindow/CopyFromScreen after a worker had already
  started used to have no effect until you reselected the target. The
  next Test capture/Retest now always restarts the capture worker with
  the newly selected backend.
- **A launcher opened in Notepad instead of starting the app** — that is
  expected: Windows opens a double-clicked `.ps1` in an editor. Right-click
  the launcher → "Run with PowerShell" instead.
- **"running scripts is disabled on this system"** — run the launcher once
  with `powershell -ExecutionPolicy Bypass -File .\run_screen2xyz.ps1` (that
  only affects that one launch, never system-wide).
- **Launcher says the virtual environment is missing** — from the repository
  root run `python -m venv .venv` once. There is nothing to `pip install` —
  the app has no third-party dependencies.
- **Black or blank preview** — run Test capture. If it reports FAIL with
  "cannot see this window", switch to CopyFromScreen explicitly, or keep
  Auto and let it fall back automatically.
- **Empty OCR** — most small on-screen text (status bars, HUD overlays,
  coordinate readouts) is now upscaled automatically before reading, so
  this is less common than it used to be. If it still happens: the
  field's region may not contain the value, or the text is genuinely too
  tiny to read reliably (well under a normal label's size) — try Retest,
  redraw the region tighter around just the digits, or increase the
  field's upscale factor via Edit selected for a bit more margin.
- **A value flickers to "No value yet" and back while I'm using the app** —
  expected and safe if the field only shows text when you hover the mouse
  over it (e.g. a map's coordinate readout that appears/disappears as you
  move). Each disappearance is shown live so you always see what this
  instant's capture actually found, but it is never treated as an error
  and never touches your saved history — nothing is recorded for it, and
  your last real reading is kept until a genuinely new one arrives. Only
  an actual value change gets a new saved row; repeatedly hovering on and
  off the same value adds nothing to your history.
- **"More than one number in the region" on a lat/long field, and "redraw
  a tighter region" doesn't help** — the field's Type is still **number**;
  it needs to be **coordinate** (or **auto**, which understands
  coordinates too). You no longer have to fix this by hand: the Step 4
  Preview gate now detects it and shows a **one-click "Fix field types?"
  dialog** — click **Yes** and it switches the types and re-runs the
  preview for you. (The per-field hint text also still appears on the
  Preview rows and the recording screen's field cards.)
- **OCR reads the degree symbol (°) as a zero** — a real, common OCR
  behavior at small text sizes (e.g. `49°08'20.06"N` captured as
  `49008'20.06"N`). A `coordinate` or `auto` field now **recovers the
  numeric value automatically** when the reading has the full
  degrees-minutes-seconds shape with a compass letter: the impossible
  digit run is decoded back (`49008'20.06"N` → `49.138906`) and the row
  is labelled `DEGREE_GLYPH_RECOVERED` in the exported data, next to the
  preserved raw text — so every recovered value is auditable, never
  silent. Partial shapes (no compass letter, no seconds) are never
  guessed at; they stay flagged instead.
- **A number field won't read a serial number or code (e.g. "SN-4829")**
  — that field's Type is still **number**, which correctly refuses
  content that mixes letters and digits. If the value genuinely isn't a
  pure number, switch its Type to **text** or **auto** (Edit selected);
  the app shows this exact suggestion itself once it recognizes the
  content looks like a code. (A number with a plain unit suffix, like
  "14 m", is unaffected — that already works as a number.)
- **Target too large** — for a window bigger than your monitor, prefer a
  window-scoped capture with client-relative regions over monitor capture;
  the setup screen's off-screen warning tells you when CopyFromScreen would
  lose part of the window.
- **Target moved** — client-relative regions track the window automatically;
  a resize instead pauses recording. Click **Disarm and re-preview…** on
  the recording screen, confirm the real preview gate again, then click
  START RECORDING to continue the same run.
- **Minimized window** — recording auto-pauses after a few ticks; restore
  the window and Resume.
- **Pause/Resume says "still busy" and asks you to click again** — a
  capture was genuinely still in progress when you clicked; this is
  expected and safe (it protects against the same tick being touched from
  two places at once). Click the same button again a moment later.
- **Window/monitor picker won't let me back out** — click **Cancel** in
  the picker (added alongside the target/monitor choosers becoming
  modal), or use the window's normal close button; both correctly return
  you to the setup screen with nothing changed.
- **Covered window** — with CopyFromScreen, a covered region reads as
  blank/wrong; keep the target uncovered, or use PrintWindow/Auto if the
  target supports it.
- **Stale regions after a DPI/monitor change** — re-run Test capture and
  Preview; a display change pauses recording and requires Disarm and
  re-preview, exactly as for a resize, rather than silently reading the
  wrong pixels.
- **Questionable near-uniform crop** — if a drawn region's crop is a single
  flat color other than solid black/white, Confirm is blocked by default
  (it might be a genuinely blank field, or a wrong region); tick "Use
  anyway (advanced)" and confirm the follow-up warning only if you are sure
  - the override is recorded in the session's saved metadata so it is
  never silent.
- **Off-screen region rejected** — Confirm this region is blocked if the
  drag would place any part of the rectangle outside the captured frame;
  redraw fully inside the visible screenshot.
- **Live CSV snapshot update failed** — a row can show orange: persisted to
  journal (safe) but the live preview file update failed this tick (e.g. a
  temporary file-lock); the underlying event is never lost, and the next
  successful tick regenerates the snapshot from every event so far.
- **Finalization failure** — if Stop reports that the final CSV could not be
  verified, or the app closed before finalizing, click **Rebuild exports
  now** on the finished screen — it rebuilds the CSV/XYZ files from the
  canonical journal in-app, no terminal needed. (The command-line
  equivalent, if you ever need it, is
  `.\.venv\Scripts\python.exe -m screen2xyz_m2 recover <run_id>`.)
- **Target window closed while recording** — recording pauses and the
  recovery bar offers **Choose target window…**; pick the window again (if it
  reopened) to continue the SAME run against it — your fields, regions and
  already-captured data are kept — or click Stop to save what you have.
- **XYZ point cloud** — after Stop, the finished screen states plainly
  whether `points.xyz` was written (and how many points) or, if not, why:
  XYZ is optional and needs exactly one number field assigned to each of X,
  Y and Z.
- **Demo won't start / times out** — see the Demo mode section above; a
  bounded IPC timeout there is a Windows message-pump contention
  characteristic of the demo tooling, not a product defect, and retries
  automatically.
- **"Is this value actually being saved?"** — check the row's color/label
  in the Live feed: green means persisted to journal AND the live CSV
  snapshot updated; orange means persisted to journal but the snapshot
  update failed (still safe); anything else has not been durably saved yet,
  no matter what the field card or live grid currently shows. The Saved CSV
  rows tab only ever shows rows that have actually been persisted.

## Honest limitations

- Windows-only; en-US OCR by default; decimal-point numbers (station and
  space-grouped numbers are unsupported as numeric — use text type). A
  number with no leading zero before its decimal point (".5" instead of
  "0.5") is also unsupported as numeric and correctly reports
  MALFORMED_NUMBER rather than guessing at its magnitude/sign — use text
  type, or ensure the source always displays the leading zero.
- Real-target capture reliability beyond the synthetic demo target is
  unproven until you run `validate-real-target` on your own application;
  Auto's PrintWindow→CopyFromScreen fallback and its bounded timeout are
  validated against a real, reproduced DWM-composited-window hang, not
  against every possible application. The new "Disarm and re-preview"
  recovery button has likewise only been proven against the synthetic
  demo target's resize, not a real target's resize/DPI behavior yet.
- Windows Graphics Capture (WGC) is not implemented; Auto only chooses
  between PrintWindow and CopyFromScreen. This is a concrete, evidence-
  based deferral (COM interop + a D3D11 device + an async frame-delivery
  model not reachable from the current PowerShell-hosted worker), not a
  placeholder - see M2_IMPLEMENTATION_REPORT.md §5e for the detail.
- The demo self-test's command handshake with its own synthetic target has
  an intermittent timing sensitivity (bounded — it always fails fast and
  clearly rather than hanging, and retries automatically). This is now
  root-caused as Windows message-pump contention between the real capture
  worker and the target's own event loop when both act on the same window
  concurrently - not an unresolved protocol ambiguity, which is separately
  and conclusively fixed. It affects the demo tooling itself, not the
  capture/backend/parsing pipeline, which is covered by dedicated
  deterministic and real-worker integration tests.
- The full 5-minute real-time and 30-minute accelerated soaks have not been
  run; a bounded 40-second soak plus 8-source/repeated-action stress tests
  were run instead (see `tests_m2/run_m2_soak.py`).
- A local PyInstaller build was not attempted (not installed in this
  environment); a reproducible build command is documented in
  M2_IMPLEMENTATION_REPORT.md instead.
- Mixed-DPI is designed for (Per-Monitor-V2 in both processes) but untested
  on a genuinely mixed-DPI multi-monitor setup.
- Not a production, survey-grade, or real-world-accuracy tool.

Conceptual and preliminary estimating data only.
