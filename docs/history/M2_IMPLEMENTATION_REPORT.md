# M2-Live Implementation Report

> Historical process record from the private predecessor repository; retained for provenance only.

Date: 2026-07-19 (updated 2026-07-21; implementation dated 2026-07-18).
Branch `feat/m2-live-region-watch-impl` (Draft PR #5), based on planning
merge `4726d0e` (PR #4). **Draft — not yet merged.** **G-E-REAL has
passed** on the owner's machine (§5o); the owner's explicit merge
decision is still required.

## 1. Executive result

The M2-Live live screen-region watcher is implemented end to end and passes
its full automated and synthetic-integration test suites on the current
Windows machine. An explicitly selected target window flows through
countdown-gated setup, a mandatory synchronized preview, ARM, explicit
Start, ~1 Hz synchronized capture + Windows OCR, a live current-values grid,
change/error-only retained-event journaling with crash-safe crops, and
deterministic CSV/JSON/strict-XYZ exports — with pause/resume, normal stop,
an always-on-top mini controller placed outside the capture regions, and a
≤2 s emergency stop. Real-target compatibility remains gated on the owner's
one consolidated `validate-real-target` run.

## 2. Gates and provenance

- G-D (UX), G-G (defaults/roadmap): closed 2026-07-18 (OD-M2-1/3/4/5/6/7).
- **G-E-SYNTHETIC**: passed 2026-07-18 — automated 6/6 trials; provisional
  backend `printwindow_clientonly` (fallback `copyfromscreen`).
- G-F scope: recorded (OD-M2-8); the live per-session confirmation is built
  into `validate-real-target` for real content.
- **G-E-REAL**: **PASSED** 2026-07-21 on the owner's machine, after a real
  Draw-region bug found live was fixed (§5o); still limited to the
  specific target/session recorded, not general real-target support.

## 3. Package map (`src/screen2xyz_m2/`)

| Module | Responsibility |
|---|---|
| `contracts.py` | §0 constants, closed enums, causal value-status mapping |
| `parsing.py` | bounded raw UTF-8, closed Unicode sign policy, number/text/auto |
| `models.py` | source/session models, validation, XYZ eligibility |
| `statemachine.py` | session states + legal-action table + setup interlock |
| `paths.py` | generated run/profile ids, traversal-safe joins |
| `profiles.py` | profile persistence + environment-mismatch detection |
| `dpi.py` / `targets.py` | PMv2 bootstrap; window/monitor enumeration; snapshots |
| `adapters/capture_worker_windows.ps1` | long-lived m2w.1 capture+OCR worker (PMv2, one frame/tick, bounded payloads, stdin-close shutdown) |
| `worker.py` | worker client: single outstanding request, generation/revision matching, stale-reply drop, exact teardown, job-object hardening |
| `scheduler.py` | monotonic non-overlapping tick scheduler (skip, not queue) |
| `stability.py` | three-tier stability + closed retention precedence + bounded evidence buffer |
| `journal.py` | crop→artifact-hash→journal→checkpoint order; tolerant recovery reader |
| `exports.py` | deterministic wide/long CSV, sanitized summary, strict XYZ, manifest |
| `recovery.py` | rebuild exports from the canonical journal |
| `controller.py` | live session: failure counters, 0/1/5 s backoff, all §0 auto-pause thresholds, cached-observation fill-forward |
| `evaluation.py` | deterministic scripted-OCR controlled evaluation |
| `ui/app.py`, `ui/layout.py` | Tkinter guided workflow: setup, region picker, responsive recording dashboard (field cards, live feed, Saved CSV rows), mini controller |
| `validate_real_target.py` | guided Tk wizard (subclasses `ui.app.M2App`) for owner G-E-REAL validation; explicit PASS/FAIL/BLOCKED |
| `demo.py`, `adapters/demo_target_windows.py` | synthetic X/Y/Z demo target (deterministic seq/session-token protocol) + automated real-pipeline self-test |
| `cli.py` | `ui` / `recover` / `validate-real-target` / `demo` |
| `run_screen2xyz*.ps1` | one-click owner launchers (normal / demo / validation / menu) |

## 4. Test results (current machine, 2026-07-19)

Current totals after the overnight reliability sprint, its two follow-up
remediation/stability-verification passes (§5g/§5h), the human-usability
pass (§5i), a real-target OCR fix from the owner's own machine (§5j), its
full re-audit with a deeper padding fix (§5k Phase 0), a silent-data-
corruption fix for OCR'd coordinate text (§5k Phase 1), a one-shared-
region multi-value workflow fix (§5k Phase 2), a TODO/limitation sweep
(§5k Phase 3), a usability pass on the real coordinate workflow (§5k
Phase 4), a real-owner-usage fix for misleading guidance on a
number-typed coordinate field (§5l), its generalization to
alphanumeric codes (§5l addendum), the owner-decided one-click
type fix + labelled corrupted-degree recovery (§5m), and its own
pre-delivery adversarial review, 12/12 confirmed and fixed (§5n):
**M2 deterministic 496/496**, real Windows integration **16/16** (the
CSV test retry-free), baseline 42/42, M1 34/34, evidence PASS,
sanitization + privacy PASS. The narrative below describes the
productization-sprint (279-test) baseline; §5f lists the +38 QA-sprint
tests, §5g the overnight-sprint tests (317→355), §5h the stability-
verification follow-up (355→363), §5i the usability pass (363→414), §5j
one real-worker integration test (11→12), §5k Phase 0 one more (12→13;
the M2 deterministic count was unaffected by either §5j or §5k Phase 0,
both being worker-side PowerShell fixes), §5k Phase 1 the `coordinate`
data type + `parse_coordinate` (M2 deterministic 414→437: 23 new
`CoordinateParsingTests` plus a humanization-label addition caught by the
existing exhaustive-enum test; Windows integration 13→14:
`CoordinateDmsOcrRegressionTests`), §5k Phase 2 `line_part` + the
XYZ-eligibility fix + hover-transience coverage (M2 deterministic
437→449: 8 `LinePartParsingTests`, 4 model tests, 1 hover scenario test;
Windows integration 14→15: `SharedRegionLinePartIntegrationTests`), §5k
Phase 3 (documentation only, no new tests), and §5k Phase 4 per-status
field-card guidance + missing-value escalation (M2 deterministic
449→456: 4 `ValueStatusGuidanceTests`, 3 `MissingValueEscalationTests`;
Windows integration unchanged, no capture/OCR/parsing code touched).

- **Baseline**: 42/42, exit 0 (unchanged).
- **M1**: 34/34, exit 0 (unchanged).
- **M2 deterministic suite** (`tests_m2/run_m2_tests.py`, frozen 279 then
  317): 0 failures/errors/skips — everything from the prior remediation
  (224) plus this sprint's new tests: `journal.write_live_snapshot`
  success/atomicity/failure-never-loses-the-event
  (`LiveCsvSnapshotTests`), `finalize_exports` row-count verification
  (`test_finalize_detects_and_warns_on_row_count_mismatch`), controller
  diagnostics counters and the live-snapshot hook
  (`LiveCsvSnapshotControllerTests`), the region-gating/staleness additions
  (`region_confirm_allowed`'s override parameter, `region_stale`), the
  persistence-state model and updated `feed_row_color`
  (`PersistenceStateTests`, updated `FeedRowColorTests`), the real-target
  validator's verdict/report logic
  (`test_validate_real_target.py`, 11 tests proving PASS is unreachable
  without every named check), and the deterministic demo protocol
  (`test_demo_protocol.py`, 19 tests: ack-matching, stale/duplicate/
  foreign-token rejection, ready validation - all via a fake queue, no
  subprocess, instant and never flaky).
- **M2 Windows integration** (`run_m2_integration.py`): 11/11 — the
  original synchronized capture+OCR and worker-exit-on-stdin-close; Auto
  resolves to PrintWindow and latches against the normal synthetic target;
  Auto falls back to CopyFromScreen within ~2 s against a real DWM-layered-
  window hang; the persisted-event-count/CSV-row-count/live-snapshot-row-
  count/verified-final-CSV-row-count proof; and 6 new real-subprocess demo-
  protocol tests (delayed first command, duplicate messages, stale session
  token, target crash, partial command across two writes, shutdown during
  command / no orphan) - **none of which need a retry**.
- **M2 stress/soak** (`tests_m2/run_m2_soak.py`, new this sprint): 5/5 - an
  8-source real capture+OCR tick, 10x repeated Retest, 5x repeated start/
  stop session cycles (no orphan), 1000x region-redraw math, and a 40-
  second continuous soak at a 150 ms interval proving live-snapshot rows
  == journal events == verified final-CSV rows throughout. See §6 for what
  this bounded harness does *not* cover (the full 5-minute/30-minute soaks).
- **Synthetic acceptance** (`acceptance_harness.py`): re-run three times this
  session. One run reproduces the exact same known limitation already
  documented at M2-011 - `change_events_only: false`, `ma3_events: 1`, the
  unfocused Tk target not compositing in this non-interactive session so
  every capture reads empty - which is an environment characteristic, not a
  logic defect (the transition logic it checks is covered deterministically
  and passing in the 224-test suite). A latent unbounded-blocking-read hazard
  in the harness's own `SyntheticTarget.command()` (predates this
  remediation, same class as the demo-target IPC issue below) was found and
  fixed with the same bounded-reader-thread pattern.
- **Real end-to-end self-test** (`python -m screen2xyz_m2 demo`): drives the
  full real pipeline (Auto backend resolution, preview, stable/changing/
  empty/malformed/Unicode-minus values, resize-triggers-repreview,
  minimize-triggers-pause, resume, manual pause/resume, stop/finalize/
  export) against a synthetic target. Passed with 18-19/19 checks across
  multiple runs this session (the one variable check,
  `preview_ocr_nonempty`, uses an any-of-N-sources bar matching
  `validate_real_target.py`'s own established convention, since live OCR can
  occasionally miss one source - the per-source detail is recorded, never
  hidden). A demo-target IPC handshake stall (bounded, never a hang) was
  found and fixed with a background reader thread plus an automatic,
  idempotent retry (`run_self_test_with_retries`), which recovers the flake
  in the large majority of runs.
- **Performance** (`perf_harness.py`, real worker, 250 ms interval, synthetic
  GDI target, burst of 40 ticks): 3-source tick mean 13.9 ms (p50 12.2,
  p95 23.0, max 38.2); 8-source mean 21.9 ms (p50 18.7, p95 33.0, max 113.0)
  — well under the research §7 200 ms budget. A large-client / CopyFromScreen
  figure and the real target remain owner-machine items.
- **Soak**: a continuous real-capture soak runs with 0 worker restarts after
  the worker fix below. Note: in a **non-interactive / background** session
  the synthetic Tk target is not composited while unfocused, so GDI
  `PrintWindow` slows to ~10–18 s/frame between `sleep(1)` ticks (measured
  actual_rate ~0.06–0.08/s) — an artifact of headless capture, **not** the
  product: the same code path bursts at ~14 ms/tick in the perf harness. A
  faithful sustained-rate / 30-minute / memory-slope soak therefore requires
  an interactive foreground desktop and is part of the owner-machine
  **G-E-REAL** M2-010 acceptance, not a synthetic claim.
- **Retained evidence**: `verify-evidence` PASS; sealed baseline/M1 evidence
  byte-untouched. Sanitization + M2 privacy/no-network scans PASS.

## 5. Defect found and fixed during testing

The soak surfaced a real worker defect: the PowerShell parent-watch used a
`Register-ObjectEvent` timer whose per-second Action ran on the PS event
queue and intermittently stalled the synchronous capture loop past the 2 s
request timeout (~1 in 3 ticks failing, each auto-restarting). It was
removed; orphan prevention now relies on stdin-close detection (S6-measured
<1 s) plus the Python job-object kill. Post-fix: 0 failures across 50
consecutive ticks. This is exactly the class of defect the soak exists to
catch.

## 5b. M2-011 adversarial review and remediation

A multi-agent adversarial review (independent reviewers, Opus-class) attacked
the implementation. It found **no BLOCKERs** but a set of MAJOR/MINOR defects,
all now fixed with a locked-down regression test per defect:

- **W1 (scheduler) — skip enforcement was dead code.** The scheduler ran
  `on_tick` synchronously on its one loop thread, so a slow tick blocked the
  loop and the single-outstanding/skip logic never triggered. Fixed: each tick
  now runs on a dedicated thread holding the in-flight lock; deadlines arriving
  mid-capture are counted as skips, never queued. Coalesced missed deadlines
  are each counted. Regression: `tests_m2/test_scheduler.py`.
- **Concurrency follow-on.** Making ticks run off the loop thread meant
  `note_skipped_tick` (loop thread) now races the tick thread's read-and-reset
  of `skipped_since_last_event`. Guarded both with a lock and an atomic
  take-and-reset so no skip is lost against a concurrent reset (else events
  under-report skipped ticks). Regression:
  `SkipCounterConcurrencyRegression`.
- **Stability D1–D4.** changed-only recovery to a *different* value is now
  retained; the first-candidate evidence buffer is released (no leak);
  error→error morphs are retained distinctly; a replaced candidate is marked
  REJECTED with its value-status recomputed.
- **Parser D6–D7.** `bound_raw` only walks back on a real UTF-8 continuation
  byte (off-by-one fixed); `parse_auto` surfaces a number's OUT_OF_RANGE /
  MALFORMED outcome instead of masking it as text.
- **Exports P1 / D5.** CSV formula-safety wraps display names in **both** wide
  headers and row keys plus long-form names and text values; strict XYZ export
  excludes any event whose axis value is not IMMEDIATE/CONFIRMED.
- **Journal P3.** Crop writes validate `source_id` against a strict pattern
  and confirm the resolved path stays inside the run directory (path-traversal
  rejected).
- **Worker W2–W5.** INIT tears down on any failure; the reader is a bounded
  binary `read1()` loop; requests match all four envelope fields
  (generation/revision/mode/request-id); teardown honors a time budget.
- **UX2–UX6.** The acceptance oracle no longer hardcodes the no-duplicate
  check; the region editor/preview picker and scope-origin re-query are real;
  overclaiming docstrings/labels were removed.

## 5c. UI, capture-reliability, and self-testing remediation (2026-07-19)

The owner tried the real M2-Live app and reported it not usable enough:
capture unreliable on the intended (real) application, no explanation of
what buttons do, no way to tell a capture is happening, no way to confirm
crops exist, and no way to test the app without a real application at hand.
Root-caused and fixed, all on synthetic evidence:

- **Real Auto backend (the root-cause fix).** The UI previously hardcoded
  `printwindow_clientonly` everywhere; there was no Auto mode at all. The
  worker (`capture_worker_windows.ps1`) now has a real `Resolve-And-Capture`:
  it tries PrintWindow, classifies the frame via the existing
  `Get-ContentStatus`, falls back to CopyFromScreen when unusable, and
  latches the effective backend for the rest of the session (never re-probes
  per tick). **A second, more serious hazard was found and fixed in the
  process**: PrintWindow can *hang indefinitely* against a real,
  DWM-layered/composited window (confirmed by direct reproduction, not just
  suspected) - a worse failure than "returns black". `TryPrintWindowBounded`
  runs the call on a background .NET thread (pure C# via `Add-Type`, not a
  PowerShell scriptblock - a raw thread has no PowerShell runspace and a
  scriptblock body on it is unsafe) and joins with a 1.5 s bound; a timeout
  is treated as unusable and the abandoned bitmap/graphics/HDC are kept
  alive (never disposed) rather than risking a cross-thread GDI+ race. Both
  the plain success path and the hang-then-fallback path are proven by new
  real-worker integration tests
  (`AutoBackendIntegrationTests` in `run_m2_integration.py`), the second
  against a purpose-built layered-window fixture
  (`docs/research/spikes/spike_layered_window_target.py`).
- **A second real bug found while auditing the UI**: `_preview()`
  unconditionally built a *new* `LiveSessionController` even when
  `_draw_region()` had already built one, silently orphaning the first
  worker process. Fixed: the controller is now built once and reused,
  mutating `sources`/`backend` in place.
- **Off-screen/visibility detection.** `targets.window_visibility()` (pure,
  tested) compares a window's client rect against the virtual-screen bounds
  and is surfaced as a warning in the UI when CopyFromScreen is the
  effective backend and part of the target is off-screen.
- **Numbered guided UI rework** (`ui/app.py`): Step 1 (target + backend
  selector, defaulting to Auto), Step 2 (**Test capture now** / Retest,
  showing a live thumbnail, dimensions, classification, and a plain-English
  PASS/WARNING/FAIL verdict that never reports PASS for a black/blank
  frame), Step 3 (add/edit fields, draw regions with real Zoom in/out/Fit to
  window and physical-pixel-coordinate mapping for large screenshots), Step
  4-6 (preview with live crop thumbnails and a per-field alignment
  checkbox gate before ARM, ready, recording). Recording adds a capture
  indicator that flips every tick, richer stats (effective backend, storage
  used, run folder), a Diagnostic snapshot button, and an Open run
  folder button. A Help panel and a first-run welcome dialog explain every
  control; Demo mode and Run full self-test are one click away.
- **Diagnostic snapshot** (`controller.diagnostic_snapshot`): writes the
  most recent per-field crops (already flowing through the tick pipeline for
  stability hashing - no extra worker round-trip) plus a sanitized metadata
  file under the ignored `.lab_work/m2_diagnostics/`; reports "no capture
  yet" honestly rather than erroring when nothing has been captured.
- **Demo mode + automated self-test** (`demo.py`,
  `adapters/demo_target_windows.py`): a synthetic X/Y/Z target (geometry
  matched to the already-proven-reliable S7 spike target, after an earlier
  attempt at new dimensions/fonts produced real OCR artifacts on this
  engine - confirmed by direct pixel inspection to be an OCR/font
  interaction, not a rendering bug) drives the exact real pipeline through
  stable/changing/empty/malformed/Unicode-minus values, a resize that
  requires re-preview, a minimize that auto-pauses, resume, manual
  pause/resume, and a finalized export, reporting PASS/FAIL.
  `python -m screen2xyz_m2 demo` and the UI's **Run full self-test** both
  use it. **A found-and-fixed reliability bug in the self-test's own IPC**:
  the demo target's command handshake occasionally stalls under Tk
  event-loop scheduling variance; every read is now bounded via a background
  reader thread (mirroring `WorkerClient`'s own reader), a stall is a fast,
  clear `TimeoutError` instead of a hang, and `run_self_test_with_retries`
  automatically retries (idempotent commands) up to twice, which empirically
  recovers the flake in nearly all cases. The same latent unbounded-read
  hazard was found in the pre-existing `tests_m2/acceptance_harness.py`
  (predates this remediation) and fixed identically.
- **Visual verification**: attempted via computer-use (screenshot); the
  permission request was **denied** (no interactive user present to approve
  in this autonomous session). Per the task's own documented fallback, a
  programmatic widget-tree/layout check was run instead (constructing the
  real `M2App`, forcing geometry with `update_idletasks`/`update`, and
  walking every screen's widget tree for overflow) across the setup,
  recording, and finalized screens - no clipping found, all required
  controls present with correct labels. A real functional check (not just
  layout) was also run by invoking `_test_capture()`/`_save_diagnostic_setup()`
  directly against the real demo target: PASS verdict, correct detail/
  explanation text, a real thumbnail image, and a real saved diagnostic file
  were all confirmed.

## 5d. Region-selection UX and live CSV feed remediation (2026-07-19)

The owner tested again and found two more usability problems: (1) after
"Draw region" it wasn't obvious the app had entered a selection mode, what
to do, whether a drag selected anything, or which area was selected — and
repeated drags stacked duplicate Confirm buttons; (2) during recording
there was no way to see what was being read versus what was actually being
written to CSV.

- **Region selection mode.** Replaced the ad-hoc picker with an explicit
  state machine (`NO_SELECTION → DRAGGING → SELECTION_READY → CONFIRMED /
  CANCELLED`, pure and unit-tested in `ui/layout.py`) driving a modal
  picker: a persistent "REGION SELECTION MODE — Field: `<name>`" banner, a
  crosshair cursor, everything outside the drag dimmed via stippled
  overlay rectangles, live x/y/w/h in original physical pixels regardless
  of zoom (`region_drag_rect` is zoom-invariant — tested explicitly), and
  Zoom in/out/Fit/100%. After release, a real one-shot crop+OCR+parse
  preview (`controller.preview_single_region`, a new, narrowly-scoped
  controller method that never touches `self.sources` or the stability
  engine) shows raw OCR, normalized value, capture/OCR/parse status, and
  content classification. **Confirm this region** stays disabled
  (`region_confirm_allowed`) until a real drag, in-bounds, produced a
  non-blank crop — a plain click can never create a region, and a
  black/white crop is refused. Esc/Cancel closes without touching the
  field's previously confirmed rect. Added **Review selected regions**: one
  screenshot with every field's region numbered and outlined, clickable to
  select that field, with Edit/Redraw/Remove.
- **Live capture and CSV feed.** A bounded (500-row) ring-buffer table with
  one color-coded row per field per tick — gray (live only), blue
  (candidate awaiting stability), green (retained **and** written to CSV),
  red (retained error), yellow (warning/empty OCR/temporary issue) — driven
  entirely from the existing `TickResult`/`on_event` data already flowing
  through the controller (no new capture/retention logic, no CSV files
  reread per tick). **written to CSV** is only ever true once
  `journal.append_event` has actually durably persisted the event (fsynced
  to `events.jsonl`); "changed" is a separate, simple last-tick-value
  comparison (`value_changed`) so a candidate can be seen moving before it
  is retained. Counters (captures, live observations, changes, retained
  events, CSV rows, errors, skipped, last capture/CSV-write time, run
  folder), Show-saved-only / Pause-auto-scroll / Clear-screen-feed (UI
  buffer only — recorded data is never touched) round out the panel.
- **Saved CSV rows tab.** Shows only rows that have actually been
  persisted, built via a new `exports.wide_csv_row`/`wide_csv_header` pair
  extracted from `wide_csv` (byte-identical refactor, existing tests still
  pass unchanged) so the displayed row is exactly what `finalize()` will
  later write — never a reimplementation of the shaping rules. A real
  integration test proves the **persisted event count exactly equals the
  actual `events_wide.csv` row count** end to end against the demo target.
- **Guided demo.** A new step-by-step wizard drives the *real* app (not a
  separate simulation) against the safe synthetic target: launches it,
  adds X/Y/Z fields, runs Test capture, opens the real region-selection
  picker for one field, previews, records, and lets the owner watch values
  move from gray/blue to green in the Live feed and Saved CSV rows update,
  then pause/resume/stop/open-run-folder — advancing only on explicit
  "Next" clicks, including after the owner finishes interacting with a
  step's own dialog.
- **Visual verification**: computer-use screenshot access remains denied in
  this autonomous session (confirmed again, not re-requested pointlessly).
  The programmatic widget-tree/layout fallback was extended to the new
  region-selection picker (built against a real demo-target screenshot) and
  the recording screen's Live-feed/Saved-CSV-rows notebook: no overflow, the
  banner and every required control present. One scan false-negative was
  investigated and resolved: the generic label-walker doesn't introspect
  `ttk.Notebook` tab text (a widget-level property of the parent, not the
  child), confirmed correct by reading the `notebook.add(..., text=...)`
  source directly rather than treated as a real gap.

## 5e. Ambitious productization sprint (2026-07-19)

The owner requested a full productization pass: truthful persistence
states, a responsive recording dashboard, region-selection completion, an
honest real-target validator, a deterministic demo protocol, a Windows
Graphics Capture (WGC) feasibility decision, one-click launchers, an
upgraded guided/automatic demo, and comprehensive tests. A five-agent
adversarial/UX/reliability/data-integrity/packaging review ran first
(read-only, in parallel) and its findings drove every change below.

**Truthful persistence (journal vs. live CSV snapshot vs. final CSV).**
The live feed's old single "written to CSV" flag conflated three different
truths. `RunJournal` now keeps an in-memory list of every journaled event
this run and, after each one, atomically regenerates
`events_wide.live.csv` / `observations_long.live.csv` / `points.live.xyz`
(temp file → flush → fsync → `os.replace`, the same pattern already used
for crops/checkpoints) via `write_live_snapshot()`. A snapshot-write
failure never loses or retries the already-fsynced journal event — it is
recorded as a separate, visible failure (`export_errors` counter,
`live_csv_snapshot: {"ok": false, "error": ...}` attached to the in-memory
event) and the session keeps recording. `finalize_exports` now writes the
official CSVs via the same atomic-replace pattern and **parses its own
output back** to verify the row count matches the journal event count
(`final_csv_row_count_verified`) — a mismatch is a warning, never hidden.
`layout.feed_row_color`/`persistence_state` expose four explicit states
(Observed live → Persisted to journal → Live CSV snapshot updated → Final
CSV finalized) and a new `orange` color for "journaled but the live
snapshot update failed," distinct from the `green` "both succeeded" case.

**Responsive recording dashboard.** Added a horizontally-scrollable strip
of per-field cards (crop thumbnail refreshed every tick, raw OCR,
normalized value, value/stability status, last-changed/last-persisted
times, region coordinates, a warning badge) supporting 1–8 fields without
clipping. The live feed gained vertical *and* horizontal scrollbars, five
column presets (Simple/OCR/Persistence/Diagnostics/All, via
`ttk.Treeview.displaycolumns` against one shared column set — the default
Simple preset is exactly the 8 columns specified: time, tick, field,
normalized value, status, changed, journal, live CSV) and a
"Show warnings only" filter alongside the existing saved-rows filter. The
Saved CSV rows tab now states in-window whether it is showing the **live
snapshot** (recording) or points to the **finalized, verified** count
(after Stop) rather than implying a CSV file that doesn't exist yet.

**Region-selection completion.** `region_confirm_allowed` now blocks
`NEAR_UNIFORM_OTHER` (a single flat non-black/white crop) by default too —
previously it was the one class silently allowed through, a real
adversarial finding — behind a new `allow_near_uniform_other` parameter the
picker only sets after an explicit "Use anyway (advanced)" checkbox *and* a
second confirmation dialog; the override is written into the field's
`notes` (visible in `session.json`). A new `region_stale()` check compares
the picker's screenshot-time client size/DPI against a live re-query at
Confirm time and blocks confirmation if the target changed underneath the
picker. The setup table gained a `preview` column and a details panel
(thumbnail + full raw OCR/normalized/status) that persists after the
picker/preview-gate/Review-regions dialog closes, populated by a single
`_record_setup_preview` write-path shared by all three. Review selected
regions gained a details panel and a **Re-test all regions** action.

**Real-target validator rebuild.** `validate_real_target.py` no longer
guesses three horizontal bands or hardcodes PrintWindow. `ValidationApp`
subclasses the real `ui.app.M2App` — the SAME setup screen, region picker,
preview gate, and recording dashboard the owner uses day to day, not a
reimplementation — adding only a consent gate, a manual BLOCKED escape, a
small always-on-top "I changed a target value" / Pause / Resume overlay
during recording, and a post-Stop verdict. `compute_verdict()` is a pure
function requiring **every one of nine named technical checks** (captures
occurred, OCR meaningful, a change was both detected *and* owner-confirmed,
journal-persisted, live-snapshot-updated, final-CSV-generated, final-CSV-
row-count-matches-journal, crop artifacts clean, no orphan worker) **and
all four owner confirmations** to return PASS — any single `False`, or a
missing key, is FAIL or an exception, never a silent pass. `build_report()`
structurally cannot carry a screenshot or window title. 11/11 deterministic
tests prove PASS is unreachable without every condition.

**Deterministic demo protocol — real root cause found.** The demo target's
command handshake now carries a strictly increasing `seq` and the target's
own `session_token` in every command and ack (`adapters/
demo_target_windows.py`'s `PROTOCOL_VERSION`/`session_token`, unknown
commands honestly ack `{"ok": false, "error": "UNKNOWN_COMMAND"}` instead
of pretending success); `DemoSession._send` only accepts a reply whose seq
*and* token match, discarding anything stale/duplicate/foreign while
continuing to wait — replacing the previous "drain the queue and hope"
workaround, which was itself the ambiguity source. Direct measurement this
session (dozens of runs, `tests_m2/test_demo_protocol.py`'s fake-queue
tests and `run_m2_integration.py`'s six real-subprocess protocol tests, all
passing with **no retry**) proves that ambiguity bug is fully closed.
A second, separate, genuine cause was found and reproduced: sending a demo-
target command while the real capture worker is actively doing repeated
GDI PrintWindow/BitBlt calls against that same Tk window can occasionally
starve the target's own `root.after`-scheduled command pump for several
seconds (a Windows message-pump contention characteristic of one window
being simultaneously the command target and the active capture subject,
reproduced with the exact error `TimeoutError: demo target did not
acknowledge seq N (...) within 8.0s`). This is bounded (never hangs) and
does not occur in the real-worker-free protocol tests; `run_self_test_
with_retries`'s docstring now states this precisely instead of "not fully
root-caused."

**Windows Graphics Capture — evidence-based deferral (not implemented).**
Confirmed via fresh investigation (Agent B) and this project's own prior
research (`docs/research/M2_LIVE_TECHNICAL_RESEARCH.md` §C5,
`docs/architecture/M2_LIVE_ARCHITECTURE.md`): WGC needs
`IGraphicsCaptureItemInterop::CreateForWindow` (a COM interop interface,
not the WinRT class-activation already used for OCR), a D3D11 device, and
delivers frames via an async `Direct3D11CaptureFramePool` event model that
needs a running Dispatcher/message pump — the current worker is a
synchronous blocking `ReadLine()` loop with no such pump. None of this has
been demonstrated reachable from PowerShell 5.1's `Add-Type`-compiled C#
in this codebase. The prior architecture doc already concluded a compiled
C#/.NET helper process (not the current PS host) would be required, kept
as the future backend seam behind the same JSON protocol. No stub or fake
backend was added; `windows_graphics_capture` remains unimplemented and
unclaimed.

**Launchers and packaging.** `run_screen2xyz.ps1` / `_demo.ps1` /
`_validation.ps1` / `_menu.ps1` resolve the repo root from their own
script location (never the caller's CWD), verify `.venv\Scripts\python.exe`
exists with a clear error and remediation steps otherwise, set
`PYTHONPATH`, never touch execution policy, and keep the window open on a
non-zero exit. All four parse cleanly and `run_screen2xyz_demo.ps1` was
run end to end for real. Packaging: no `pyproject.toml`/`requirements.txt`
exists yet, and every non-stdlib import is internal to this repo — a
PyInstaller `--onedir` build is plausible but PyInstaller is not installed
in this environment and was not installed this session (an unrequested
package/network action); a reproducible build command is documented in the
guide instead of an actual ignored build artifact.

**Guided/automatic demo upgrade.** The guided (Next-click) wizard gained
real resize→pause→"Disarm and re-preview…"→resume and minimize→restore→
Resume steps, driving the exact real UI actions — which surfaced a genuine,
separately-fixed gap: **the recording screen had no way at all to recover
from a resize/DPI pause** (no "Disarm and re-preview" control existed
anywhere). Added one, wired through the existing `pause.requires_repreview`
signal already computed by the controller, verified end to end against the
real demo target (resize → pause detected on the very next tick → recovery
button enables → re-preview succeeds). The automatic self-test
(`run_self_test`) already covered resize/minimize/pause/resume/stop and is
unchanged in scope.

**Testing.** 279 deterministic tests (up from 224), 11 real Windows
integration tests (up from 5, including 6 new demo-protocol tests and an
extended live-feed/CSV test now also asserting live-snapshot-row-count and
verified final-CSV-row-count), plus a new bounded stress/soak harness
(`tests_m2/run_m2_soak.py`): an 8-source real-capture tick, 10x repeated
Retest, 5x repeated start/stop session cycles, 1000x region-redraw math,
and a 40-second continuous soak at a 150 ms interval proving live-snapshot
rows == journal events == verified final-CSV rows throughout. This is a
bounded stand-in for the sprint's 5-minute/30-minute soak ask — see §6.

**Visual verification.** Computer-use access was explicitly requested this
session (`request_access(["Python 3.14"])`) and the user **declined** it
(a live `user_denied` response, confirming an interactive user was present
and made an active choice — not the earlier sessions' "no user available"
situation). Per that decision, no further computer-use request was made.
The established programmatic fallback was used instead, extended to every
new dashboard element against the real demo target and real controller:
the setup table's new `preview` column and details panel; all three field
cards populating with real values/statuses/persistence-state text and a
real crop thumbnail; the live feed's `journal`/`live_csv` columns
(`written` fully removed) and Simple/All preset switching; the Saved-CSV-
rows mode label; and the new resize→pause→recovery-button path, confirmed
enabling on the very next tick after a real resize. No findings.

## 5f. Autonomous QA, visual-testing, and fix-it sprint (2026-07-19)

An autonomous QA pass drove the real UI, ran a five-agent
adversarially-verified specialist review (35 confirmed findings: 1 BLOCKER,
12 MAJOR, 18 MINOR, 4 NIT), root-caused the remaining demo timing
sensitivity, stress-tested the live-CSV design, and fixed every BLOCKER and
MAJOR plus most MINOR/NIT. Highlights:

- **Visual QA method.** Computer-use was requested and the owner **declined**
  it, so — since the app is itself a screen-capture tool — each real Tk
  screen was rendered by the real `M2App` against the real demo target and
  captured to PNG via CopyFromScreen (PrintWindow hangs on the DWM-composited
  Tk window, the exact hazard the app bounds), then read back for
  inspection. This surfaced the recovery-button-clipping defect below that a
  widget-tree walk alone would have missed. Screenshots live only under the
  ignored `.lab_work/m2_ui_review/`.

- **BLOCKER — journal `event_seq` corruption.** `append_event` advanced the
  sequence number before the crop/journal write and never rolled back, so a
  single transient OSError (plausible under a file-sync/AV lock) followed
  by the explicitly-permitted Resume skipped a number; `read_journal`'s
  strict-contiguity check then raised `JOURNAL_SEQUENCE_BREAK` on
  Stop/recover, permanently losing the run the pause/resume mechanism exists
  to survive. Fixed: the number commits only after the durable fsync.

- **Data-integrity MAJORs.** The stability engine committed a transition
  before the journal was durable (a journal-write failure silently lost the
  retained change) — added transactional snapshot/restore. The live CSV
  snapshot regenerated all three exports from the full history every event
  (measured O(n): 229 ms/snapshot at 10k events, O(n²)≈15 GB written over a
  session) — replaced with byte-identical **O(1) incremental append** (~2.8 ms
  flat at 10k events). Finalize verification now reads the file back from
  disk; the skip counter is consumed only after a durable write; the
  `read_journal` per-line O(n²) rescan was hoisted; and the live-snapshot
  exception boundary was broadened beyond `OSError` to a defined set.

- **Validator false-PASS (MAJOR).** The G-E-REAL checks were satisfiable
  with zero successful captures and OCR noise. Now `captures_occurred`
  counts only OK frames, a new `observation_is_meaningful` requires a valid
  parse + OK value status per source, a new mandatory
  `every_enabled_source_meaningful` check requires every enabled source to
  produce a meaningful read, and `change_detected` requires a real
  RETAINED_CHANGE journal event.

- **UX MAJORs.** Esc = emergency stop was app-wide (a stray Esc on the setup
  screen after any Test capture dumped the user to a bogus "Finalized",
  losing setup) — now only while recording. New fields showed "region set"
  for an undrawn placeholder and passed Preview — added a confirmed-region
  set that gates the table label and Preview. Draw region froze the UI 3 s
  with a main-thread sleep — replaced with a non-blocking countdown +
  Cancel. "Select monitor…" never showed a chooser — added one. The region
  picker could grow taller than the screen — capped to the display. The
  **"Disarm and re-preview" recovery button was squeezed to a 9 px
  unreadable sliver at the bottom edge** (the only control that recovers a
  resize/DPI pause) — moved to a highlighted bar at the top, verified
  visually. Plus fixes for the interval TclError, the Resume button
  contradicting "Resume is disabled", the finalized header on an empty
  summary, high-DPI clipping of the mini controller/field cards, and a
  re-record scheduler-thread leak.

- **Capture reliability.** A hard worker-reported capture failure
  (BACKEND_FAILURE / oversize window / locked desktop) never paused — the
  session recorded nothing forever with a healthy-looking UI; added a
  failure-streak pause (which also bounds the PrintWindow-timeout GDI leak).
  A DISPLAY_INVALIDATED frame no longer journals a wrong-pixel event, and an
  off-screen move under CopyFromScreen is now detected per tick.

- **Demo timing — root-caused, not retried.** Instrumented the target/worker
  with opt-in diagnostic timestamps and localised two causes: the common
  latency was the 50 ms command-pump poll (tightened to 10 ms, ~3-4x
  faster), and the rare 8 s stall was the worker's PrintWindow synchronously
  dispatching `WM_PRINT` to the demo target's own Tk loop and hanging it —
  an artifact of the self-test capturing a window it also drives, confirmed
  by an A/B test (CopyFromScreen 4/4 vs PrintWindow 3/4 failing). The
  self-test now runs its pipeline on CopyFromScreen with the Auto probe
  moved to the end; the primary path passes **6/6 with no retry**, and the
  CSV-row-count integration test dropped its retry wrapper (3/3 clean).

- **Packaging.** The demo launcher now holds the window open on PASS (the
  report was vanishing); the impossible `pip install -e .` remediation was
  replaced with venv-only; `$PSScriptRoot` and try/catch/finally added;
  the menu delegates to the dedicated launchers; the double-click claim was
  corrected; and launcher-failure troubleshooting entries were added.

- **Soaks/stress (§14).** A real **5-minute wall-clock** demo soak and a
  **30 000-tick accelerated logical** soak (both CopyFromScreen), plus
  8-source, repeated-Retest, 50× start/stop, worker-crash/restart, and an
  O(1) live-CSV-growth benchmark. Results (memory/handle/orphan/row-equality)
  are recorded under `.lab_work/m2_autonomous_qa/`.

- **Tests.** 279 → 317 deterministic (all green), 11 real Windows
  integration (the CSV test now retry-free), and an expanded soak harness.

## 5g. Native Windows overnight end-to-end reliability sprint (2026-07-19)

Triggered by an owner-reported failure: clicking "Test capture now" could
leave Step 2 frozen at "Not tested yet" with no thumbnail, no failure, and
no next step - individual controls sometimes worked, but the complete
guided sequence did not reliably work.

- **Root cause, reproduced first via a real driver script against the real
  UI + a real demo target** (no computer-use - twice requested, twice
  declined by the owner; the same programmatic-driving fallback used in
  the prior sprint was reused): `LiveSessionController.__init__` required
  1-8 enabled sources, but Step 2 "Test capture" is deliberately placed
  before Step 3 "Add fields" in the UI's own numbering - so clicking Test
  capture on a truly fresh session raised `ValidationError`, which
  `_test_capture()`'s `except WorkerError` never caught. With no
  `root.report_callback_exception` installed anywhere, Tk silently
  swallowed it. Fixed by relaxing construction-time validation
  (`require_nonempty=False`) and moving the >=1-source requirement to
  `preview()`/`confirm_preview_and_arm()`, where it actually matters.
- **Systemic fix, not a one-off patch:** installed a sanitized
  `root.report_callback_exception` handler (logs only recognized-safe
  exception types verbatim, source frames as relative paths, to
  `.lab_work/m2_diagnostics/callback_errors.log`; always shows the owner a
  dialog; never leaves the app unusable) - this closes the entire class of
  "click does nothing" bugs, not just this one instance of it.
- **Central next-step card + progressive gating:** a persistent "Next
  step" card (pure `derive_next_step()`) and `can_test_capture()` now
  disable Test capture/Retest, with a visible reason, whenever clicking
  them would be illegal, instead of leaving them clickable-but-broken.
- **Multi-fixture E2E scenario runner** (`tests_m2/fixtures/`): drives the
  REAL `LiveSessionController` end to end against a local image-viewer
  fixture window, real installed Microsoft Excel (EXCEL.EXE launched
  directly for a correlatable PID - no computer-use needed), a COM-driven
  live cell edit, and the built-in demo target for 1/3/8-field complete
  workflows.
- **Two independent audit cycles, and a real self-correction between
  them.** Cycle 3 (7 fresh subagents) found and this session fixed
  confirmed defects beyond the original report: `_stop()` had zero
  exception handling and could permanently strand a session in `STOPPING`
  if `finalize()` raised (independently flagged by four of the seven
  auditors); a bare `subprocess.Popen` in the worker client could raise a
  plain `OSError` invisible to every `except WorkerError` site; the
  three-consecutive-failure `setup_worker_blocked` interlock had no UI
  path out; changing the backend dropdown after a worker already existed
  silently had no effect (the PowerShell worker latches its backend once
  at INIT); Pause/Resume were never state-gated; every target-reselection
  site leaked the previous capture-worker subprocess; the Preview gate
  was not modal; and a genuine parser BLOCKER - a leading decimal/
  thousands separator with no digit before it (".5", "-.5", ",5")
  silently reparsed at the wrong magnitude and, for a leading minus, the
  wrong sign, with `parse_status` reported as `OK`.

  Cycle 4 (3 targeted verification subagents, tasked specifically with
  re-checking cycle 3's claims against the actual code and actual
  persisted evidence rather than trusting the commit message) caught two
  further real problems, one of them **in this session's own prior
  work tonight**: (1) a commit message had claimed `_stop()` now used a
  bounded scheduler-drain timeout, but the code had never actually been
  changed - only the exception-safety fix had landed; fixed for real,
  with a regression test specifically designed to catch this class of
  gap (the earlier test's stub scheduler was `None`, so `scheduler.stop()`
  was never even called and could not have caught it). (2) The new
  scenario-runner tooling's "ok" field only ever meant "the pipeline
  reached `stop()` without raising" - it never compared the observed
  value to the fixture's declared truth. The first Excel run's own
  persisted evidence (`retained_after_com_change: 0`, a captured value of
  `"Clipboard Font"` - Excel ribbon chrome, not a cell) was still marked
  `"ok": true`; the claim in the prior commit message that this had
  already been verified end to end was **overstated** - it reflected a
  hand-run, ad-hoc verification script whose region fix was never
  propagated back into the reusable tooling or its persisted results
  file. Fixed properly this time: `run_scenario_matrix.py` now computes a
  real expected-vs-observed match (with an explicit negative-case
  classification for blank/near-uniform/ambiguous scenarios) before
  reporting success, and two fixture bugs the same audit found were
  fixed (`24_duplicate_values`'s region excluded its second occurrence,
  silently degrading it to a trivial single-value read instead of
  exercising `AMBIGUOUS_MULTIPLE_NUMBERS`; `14_large_needs_zoom` declared
  a 2000x1200 image against a hardcoded 640x400 canvas, so it never
  actually rendered). Re-run with the fixes: **12/14 image scenarios**
  now genuinely match their expected outcome - the remaining 2 are
  disclosed, understood non-product-bugs (an honest Windows-OCR miss on
  11pt text; Windows OCR resolving an O/0 ambiguity itself before the
  parser ever saw the intentionally-malformed input) - real Excel + a
  real COM-driven cell edit now shows `retained_after_com_change: 1`, and
  all three demo-target field-count workflows (1/3/8) show real retained
  events with a verified final-CSV row count. 30 new/updated regression
  tests added across both cycles.
- **Repetition/soak suite** (§20): 50/50 one-field, 20/20 three-field,
  10/10 eight-field complete workflows; 50/50 pause/resume cycles; 25/25
  resize/re-preview cycles; 25/25 worker-restart cycles - **180/180**,
  zero failures, no orphan process, 380s wall clock against the real
  demo target. Plus the earlier 100x real Test-capture repetition test
  (~19 ms/cycle average, no leak).
- **Tests.** 317 → 344 deterministic (all green), 11/11 Windows
  integration (unchanged), root suite 42/42 unchanged.

## 5h. Stability-verification cycle: a fresh independent review of §5g's own follow-up fix (2026-07-19)

The owner's next instruction, after §5g's three disclosed MAJORs were
fixed, was to re-verify stability and keep fixing/retesting until clean.
Rather than just re-running the existing suite, this cycle (1) re-ran the
full 180-cycle repetition/soak suite a second time specifically against
the newest code (pause/resume drain, modal dialogs, acknowledgements),
and (2) sent two FRESH subagents (no memory of writing the fix) to
independently review that same follow-up commit as if seeing it for the
first time — the same adversarial discipline §5g used on the original
bug, now turned on this session's own most recent work.

- **Second 180-cycle soak, clean.** 50/50 one-field, 20/20 three-field,
  10/10 eight-field, 50/50 pause/resume, 25/25 resize/re-preview, 25/25
  worker-restart — **180/180 again**, zero failures, 371s (vs. the first
  run's 380s) — confirms the drain-based pause/resume ordering holds
  under real repeated timing pressure against the real demo target, not
  just in unit tests.
- **Fresh review #1 (pause/resume concurrency) found a real MAJOR the
  first remediation missed:** `TickScheduler.drain()`'s timeout was a
  hardcoded 2.0 s, decoupled from the worker's actual per-tick round-trip
  budget (`_request_timeout_ms()`, which scales with the user's
  configured interval up to ~20 s) — and every caller discarded `drain`'s
  outcome, falling through to `user_pause()`/`user_resume()` regardless.
  A tick genuinely still in flight past 2 s (a legal, in-budget capture
  at a higher configured interval, or simply a loaded machine) would
  still race the exact overlapping-worker-request path the drain was
  added to close. Fixed for real this time: `drain()` now returns
  `bool`; a new `LiveSessionController.drain_budget_s()` derives the wait
  from the real per-tick budget instead of a constant; `_pause()`/
  `_resume()` now check the outcome and refuse (ask the user to retry)
  rather than proceed into the controller when a tick is still
  genuinely busy after that full budget elapses. The same review found
  two MINOR banner bugs it also confirmed by reading the exact code:
  `_pause()`'s exception handler treated a benign re-entrant
  `IllegalAction` (double-clicking Pause while already paused) the same
  as a real worker failure; `_resume()`'s `IllegalAction` branch left the
  banner stuck on "Resuming…" forever (unlike its `WorkerError` branch,
  which already corrected it). Both now restore the banner from the
  actual controller state instead of guessing or leaving stale text.
- **Fresh review #2 (modal dialogs + acknowledgements) found no BLOCKER
  or MAJOR** — it empirically verified Tk's auto-release-grab-on-destroy
  behavior against this exact machine's Tk build (via a real simulated
  OS "X" close through `WM_DELETE_WINDOW`, not just reading docs), traced
  every reachable path for a nested/overlapping grab and found none, and
  confirmed `ready_status_var`/`recovery_var` are already correctly
  `hasattr()`-guarded against the one path that can reach them before
  their owning screen is built. It flagged two MINORs: no test exercised
  the OS-close path for the two choosers (the exact scenario the modality
  fix was supposed to make safe), and — a genuine new UX gap introduced
  by making the choosers modal this session — neither had an on-screen
  Cancel button, so the OS close button was the *only* way out. Fixed:
  both `_select_window` and `_select_monitor` now have an explicit Cancel
  button and a `WM_DELETE_WINDOW` handler wired to it (matching the
  Draw-region countdown bar's existing pattern), plus new tests that
  simulate a real OS close (via Tcl's own `wm protocol` dispatch, the
  same path a genuine window-manager close event uses) and assert the
  grab is actually released afterward.
- **Tests.** 355 → 363 deterministic (all green): 3 tests proving
  `_pause()`/`_resume()` refuse rather than race a still-busy tick, 1
  proving the drain timeout is sized from the real budget, 2 proving the
  `IllegalAction` banner fixes, 2 simulating a real OS-close on the two
  choosers, 1 proving both choosers now have a Cancel button.
- **Full validation gates re-run and clean**: baseline 42/42, M1 34/34,
  M2 deterministic 363/363, Windows integration 11/11, sanitization PASS,
  `git diff --check` clean.

## 5i. Human-usability pass: the app judged as a non-developer owner (2026-07-19)

Owner directive: evaluate the whole workflow as a real human user would —
from every angle (is it convenient, understandable, does everything work?)
— and fix anything that stands between a non-developer owner and the
program's purpose, keeping fixes aligned with that purpose. A hands-on
walkthrough drove the real app cold from launch through every screen
(setup → preview → arm → record → pause → resume → resize/close recovery →
stop → finalize), and five fresh persona subagents (first-time user /
task-completion / error-recovery / plain-language / goal-completion)
independently evaluated the real code. Findings were fixed in four
goal-aligned commits, each with regression tests:

- **Plain language (Commit 1).** The app leaked raw internal codes to the
  owner in many controls, contradicting its own Help wording. A new pure,
  testable layer in `ui/layout.py` humanizes every user-facing token — the
  backend dropdown and every "effective backend" line
  (`printwindow_clientonly` → "PrintWindow"), the retention dropdown
  (`changed_and_errors` → "Changes + errors (default)", plus the caption it
  never had), field-card status and the live-feed Status column
  (`AMBIGUOUS_MULTIPLE_NUMBERS` → "More than one number in the region"),
  the feed/Saved-CSV headers (`VALUE_STATUS`/`MONOTONIC_OFFSET_MS` →
  friendly titles), and the remaining Test-capture failure codes (now a
  plain sentence + remedy). The cursor checkbox label tracks its real
  state, and the interval field is "Capture every (ms)" with a
  "1000 = once per second" hint. A guard test asserts no enum in the
  value/stability/content/backend/retention families can leak a raw token.
- **No recovery dead-ends (Commit 2).** A closed target window used to
  offer only "Disarm and re-preview", which re-previews the dead window and
  cannot recover — a dead-end into Stop. It now offers "Choose target
  window…", which rebinds the SAME run (journal + regions kept) to the
  reopened window. Pauses that need no re-preview (minimized/covered/disk/
  worker) now show a concrete first step ("Restore the window, then
  Resume"; "Free up disk space, or Stop to save what you have") instead of
  a Resume that silently re-pauses.
- **Truthful outcome (Commit 3).** The Finalized header no longer reads
  "Final CSV finalized" when the CSV failed to verify against the journal
  (it turns red and says so); an explicit XYZ line states whether the point
  cloud was written and, if not, a plain reason; a one-click "Rebuild
  exports now" replaces the terminal `recover <run_id>` command for a
  non-developer; warnings are humanized; the XYZ-eligibility line is
  reworded as optional and lists all missing axes at once.
- **Onboarding + consistency (Commit 4).** The step numbers now agree
  everywhere (the preview gate is Step 4, Ready is Step 5, matching the
  card's 6-step map); the welcome dialog got a scrollbar and leads with its
  "how to start" call to action (it used to clip that below the fold);
  adding a field auto-selects its row (so Draw/Edit/Remove aren't silent
  no-ops) and Remove gives feedback; the REGION cell reads "(not drawn)"
  until a region is confirmed (it used to show placeholder coordinates that
  contradicted the "no region drawn" status); the next-step refresh is
  hardened so it genuinely no-ops off the setup screen; the recording
  screen shows an on-screen colour legend (with yellow, previously
  undocumented); and the floating mini-controller's buttons have tooltips
  (its lone destructive "!" was unlabeled).
- **Tests.** 363 → 414 deterministic (all green), across a new
  `tests_m2/test_humanization.py` and additions to
  `test_guided_workflow.py`/`test_ui_qa.py`; baseline 42/42, M1 34/34,
  integration 11/11, sanitization PASS, `git diff --check` clean.

The core capture/journal/export pipeline was not touched by this pass —
these are presentation, guidance, and recovery-routing changes. Everything
here is still synthetic-evidence-only; no real-target or accuracy claim is
added.

## 5j. Real-target OCR fix: small on-screen text at native scale (2026-07-19)

The owner ran the app against a real target for the first time (Google
Earth's coordinate/elevation readout in the browser) and reported the
field never captured a value - the setup table's crop thumbnail clearly
showed the text, but the field stayed on "No value yet" for 34 straight
ticks. Root-caused with real evidence, not a guess:

- A standalone Windows.Media.Ocr test harness (mirroring
  `capture_worker_windows.ps1`'s exact `RecognizeAsync` call) was run
  against several synthetic reproductions of the owner's overlay (busy
  photographic background, plain background, fully opaque high-contrast,
  and a textbook dark-text-on-light-background control). **Every variant
  returned empty text at native scale (Upscale=1, the field's default),
  and every variant was correctly recognized once upscaled >=2x** -
  confirmed deterministic across three repeated runs. This ruled out
  contrast, background busyness, and light-on-dark text as the cause: the
  real problem is that most single-line on-screen UI text (status bars,
  HUD overlays, coordinate displays) renders below Windows OCR's
  effective minimum legible scale, and the crop looking legible to a
  human made the silent empty result look like an app bug rather than a
  scale issue.
- **Fixed at the source**, not by telling the owner to find the "Edit
  selected" upscale setting: `Invoke-Ocr` in
  `capture_worker_windows.ps1` now auto-floors the *internal* OCR upscale
  to at least 3x for any crop shorter than 60px, regardless of the
  field's own `upscale_factor` setting (never reduced if the owner set
  it higher; the stored config value itself is untouched - only the image
  actually fed to OCR is affected). Verified against the ACTUAL shipped
  function (extracted verbatim from the production file, not a
  re-implementation), not just the standalone harness.
- **A genuinely tiny glyph (11pt, ~8px cap height) remains an honest,
  disclosed OCR-engine limitation**, confirmed with sharper evidence than
  before: testing the exact real crop across upscale 1-12 showed
  *non-monotonic* success (4x and 6x recognized it; 1, 2, 3, 5, 7, 8, 10,
  and 12 did not) - deterministic per exact scale factor, but with no
  upscale value that reliably rescues source text this small. The fix
  targets the real, common case (realistic small UI text, ~13pt+); it
  does not and cannot promise recognition of near-illegible source
  glyphs, and the scenario matrix's `10_small_font` case (§5g) remains a
  genuine limitation, not fixed by this change.
- **A real self-correction surfaced by this fix, fixed the honest way**:
  the pre-existing `WorkerIntegrationTests.test_full_record_and_finalize`
  broke immediately after the fix. Diagnosed (not just reverted to make
  it pass again): that test's own field 1 had a **separate, unrelated
  OCR-accuracy bug** at native scale - it could misread
  `-123.654321` as `1-123.654321` (a spurious extra leading digit),
  which happened to parse as `AMBIGUOUS_MULTIPLE_NUMBERS` and get
  retained as an error - and the test's `events.jsonl`-exists assertion
  was, by accident, resting entirely on that misread rather than on the
  present/absent toggle it appeared to test. The upscale fix made that
  field's OCR reliably correct (mechanically confirmed via
  `git stash`/re-run: reverting the fix reproduces both the misread and
  the passing test; applying it fixes the misread and breaks the old
  assertion). By design (`stability.py`), a single-tick
  `MISSING_SOURCE_VALUE` observation is diagnostic-only and never
  retained as a change or error - correct behavior, since a momentarily-
  blank field is not itself meaningful data - so the present/absent
  toggle this test uses was never actually capable of producing a
  retained event on its own; genuine value-change-survives-finalize
  coverage already lives in `LiveFeedCsvIntegrationTests` (which drives
  the demo target's real continuously-changing values). The test was
  corrected to assert the true, intentional outcome (`event_count == 0`,
  `events.jsonl` absent, finalize's guaranteed files present) instead of
  an accidental one.
- **New regression coverage, at the right level.** Since the fix lives in
  PowerShell with no direct Python unit-test surface, a new dedicated
  stdlib-only synthetic Tk target
  (`docs/research/spikes/spike_small_text_target.py` - deliberately not
  Pillow-based, since CI's windows-integration job never installs
  third-party packages) renders one 13pt label at the owner's real-world
  scale. A new `SmallTextOcrRegressionTests` integration test drives the
  REAL controller + REAL worker + REAL OCR against it with the field's
  `upscale_factor` left at its untouched default, asserting the text is
  recognized. Verified this test actually catches the bug: reverting only
  the worker fix (`git stash` on that one file) makes it fail with
  `ocr_status == 'EMPTY_TEXT'`; restoring the fix makes it pass -
  confirmed across three repeated runs. Windows integration 11 -> 12.
- **Full validation gates re-run and clean**: M2 deterministic 414/414
  (unchanged - this fix has no Python-level surface), baseline 42/42,
  M1 34/34, Windows integration 12/12 (stable across three repeated
  runs), sanitization PASS, `git diff --check` clean.

## 5k. Full re-audit, real-workflow test, and a deeper OCR fix (2026-07-19)

Owner directive: independently re-audit §5j's fix, close deferred issues,
and only stop when the program demonstrably produces correct, exportable
coordinate data from a realistic target end to end. This section records
that re-audit's evidence-first findings, phase by phase, as they were
produced - not after the fact.

### Phase 0 — Re-auditing the upscale-floor fix as a hostile reviewer

- **0.1/0.2 — stability and revert-test.** `SmallTextOcrRegressionTests`
  re-run 5x clean. Revert-tested again (`git checkout` the pre-§5j worker
  file, confirm `EMPTY_TEXT`; restore, confirm `OK`) - unchanged from §5j.
- **0.3/0.4 — the floor's real gap: margin, not just scale.** A synthetic
  fixture matrix (13-18pt short numeric text, 55-120px crop heights) run
  through the ACTUAL shipped `Invoke-Ocr` (extracted verbatim from the
  production file, at the field's default `Upscale=1`) mostly succeeded -
  but a SEPARATE, tighter-margin matrix (same font sizes, crops sized to
  just the ink + 12px) returned **EMPTY TEXT at every upscale factor from
  1x to 6x, for every font size from 13pt to 18pt**, bypassing the
  height-based floor entirely (a raw scale sweep, not the shipped
  function). Only 11-12pt occasionally recognized text (3x-4x). This
  directly answers 0.3's question: yes, a real dead band exists, and the
  floor's own height-only heuristic cannot reach it, because the missing
  variable isn't height or scale - it's absolute margin around the ink.
  A dedicated padding-only sweep (native 1x scale, zero upscale, one fixed
  14pt/"42.567" crop that failed at every prior scale) proved this
  directly and monotonically:

  | border added (px, each side) | 1x | 2x | 3x | 4x | 5x | 6x |
  |---|---|---|---|---|---|---|
  | 0 | empty | empty | empty | empty | empty | empty |
  | 3-8 | empty | OK | OK | OK | OK | OK |
  | 12-30 | **OK** | OK | OK | OK | OK | OK |

  Padding alone, with **zero upscale**, recovers the same crop that
  upscale alone (1x-6x) never does. The same padding was then verified on
  the ORIGINAL §5j reproduction (busy background, semi-transparent dark
  bar, white text) - it recovered that fixture's one remaining native-
  scale (1x) failure too, without regressing the 2x-6x cases that already
  worked (confirmed 3x repeated runs, deterministic).
- **Fix implemented**: `Invoke-Ocr` now pads every crop by a fixed 16px
  border on each side (sampled from the crop's own near-corner pixel, so
  it blends rather than introducing a foreign-coloured edge) BEFORE the
  existing height-based upscale floor is evaluated - unconditionally, not
  only for short crops, since the boundary-audit evidence showed margin
  matters independently of height. A stderr-only diagnostic line
  (`ocr: crop=WxH pad=16 effective_upscale=N final=WxH`) was added per
  0.5's ask, with no protocol-schema change.
- **Verified against the real shipped function**: 11/11 previously-
  always-empty synthetic crops (the tight-margin matrix plus 3 hand-built
  isolation cases) now recognized. A NEW real-worker integration test,
  `TightMarginOcrRegressionTests`, drives the REAL controller + REAL
  worker + REAL OCR against a genuinely tight (Tk padding stripped to
  zero) captured window and revert-tests cleanly (`git stash` both
  directions, 3x stable) - **with one honest caveat**: real Windows-
  rendered (ClearType) text, captured live, turned out to be more OCR-
  forgiving at tight margins than the PIL-rendered synthetic PNGs at
  equivalent nominal dimensions - the live-capture test only reproduces
  the failure right at the edge of clipping the glyph cell itself, not at
  the same margins the PNG sweep used. This is disclosed rather than
  forced: the padding fix is proven correct and safe against the actual
  shipped code with rigorous, repeatable PNG-based evidence; its exact
  necessity through a live browser-rendered overlay (vs. a hand-built PNG)
  carries a bit more uncertainty than the upscale floor's did. See
  `TightMarginOcrRegressionTests`' docstring for the full account.
- **0.5 — DPI (ANALYSIS, not tested - this machine runs 100% scaling).**
  The floor/padding logic operates on the CAPTURED bitmap's physical
  pixels, matching the app's existing Per-Monitor-V2 design (regions are
  always stored/read in physical, not logical, pixels). At higher DPI
  (150%/200%), the SAME logical UI element captures to proportionally MORE
  physical pixels, which if anything gives the OCR engine more real detail
  to work with - there is no reason from this design for the fix to
  become less effective at higher DPI, and the fixed 16px padding remains
  a flat absolute addition regardless of scaling. `MaxImageDimension` was
  queried directly from the real engine on this machine: **10000px**. A
  worst-case realistic region (e.g. 500 logical px wide at 200% DPI =
  1000 physical px, +32px padding, x3 floor) computes to 3096px - well
  under the clamp; only an implausibly large region at high DPI and the
  floor together could approach it, and the existing MaxImageDimension
  guard already falls back safely (OCR at padded-but-native size, with a
  diagnostic) rather than failing silently, at any DPI. Real 150%/200%
  verification remains an owner-machine item, same as other DPI claims in
  this report.
- **A genuine, deterministic side effect discovered while re-validating**:
  padding fixed the mystery §3.1 was written to investigate (S7's third
  field, "Elev", previously `EMPTY_TEXT` on every run both before and
  after §5j's upscale-only fix) - now reads `87.05` correctly, every time,
  confirmed across three repeated diagnostic runs. But the SAME padding
  change introduced a new, equally deterministic misread on the target's
  SECOND field ("Lat", `49.123456` read as `49�123456`) - the OCR
  engine's fragility shifted which exact glyph pattern it stumbles on; it
  did not disappear. Critically, the new misread is caught correctly
  (`AMBIGUOUS_MULTIPLE_NUMBERS`, a genuine retained error) - never
  silently accepted as a valid wrong number. `WorkerIntegrationTests.
  test_full_record_and_finalize` was rewritten to assert this exact,
  reproduced, now-deterministic behavior per-field (Lon and Elev correct;
  Lat's specific misread explicitly asserted and explained) rather than a
  loose "any text contains 123" check - directly fulfilling this report's
  own standing instruction to "revisit whether this test can now assert on
  all three values." Full integration suite (13 tests, up from 12) re-run
  3x clean.
### Phase 1 — The silent-corruption bug: degree symbols misread as digits

The most important phase. §5j's own `test_full_record_and_finalize` output
already contained the evidence, unexamined until now: the real target's
lat/long readout OCR'd as `49008'20.06"N 123003'41.61"W` — every real
recognition this session produced misread the degree glyph (`°`) as the
digit `0`, deterministically. Fed to a plain `number` field scoped to just
the degrees (exactly what a user tightening a region "to isolate the
number" would do), that reads as `49008` — a clean, single, in-range-
looking digit run — and `parse_status: OK`. **A completely wrong value,
90-1000x too large, accepted as a normal reading with no error at all.**
This is a correctness bug, not a display bug, and it was still present
after every fix §5j/Phase 0 shipped.

- **1.1 — reproduced first, before any fix.** `phase1_repro.py` fed the
  exact corrupted string (and the isolated-degrees "danger case", `"49008"`
  alone) to the existing `parse_number`/`parse_auto`. Confirmed exactly the
  predicted failure: the full two-coordinate line correctly refuses as
  `AMBIGUOUS_MULTIPLE_NUMBERS` (multiple digit runs found, never
  auto-picked — the existing multi-number guard already covers that case),
  but the isolated single-field case (`"49008"`) parsed as
  `parse_status: OK`, `value: 49008` — the exact silent-corruption bug,
  confirmed live before writing a single line of the fix.
- **1.2 — the fix, and why the two easy options were rejected.** Two
  tempting designs were considered and explicitly rejected:
  - **(a) A `coordinate_dms` type that pattern-recognizes the specific
    corrupted-degree shape** (e.g. "a suspiciously large leading digit run
    followed by what looks like minutes/seconds") **and corrects it.**
    Rejected as dangerous: a leading digit run of `490` is structurally
    indistinguishable from a genuinely-typed `490` by content alone.
    Guessing which one happened doesn't fix the silent-wrongness problem,
    it just moves it one level down and hides the guess.
  - **(b) A post-OCR normalization step that maps known confusable glyph
    sequences back** (e.g. a lone `0` between two digit runs near a `'`/`"`
    → `°`). Rejected for the same reason: it is still a guess dressed up
    as a correction, and it would apply globally to every field, silently
    rewriting genuinely-typed data that happens to match the pattern.
  - **(c) What was built instead**: a new `coordinate` data type
    (`contracts.DATA_TYPES`) and `parsing.parse_coordinate()`, which
    structurally tokenizes degrees/minutes/seconds/hemisphere (`_COORD_RE`)
    — the "degrees" group is always whatever leads up to the first
    `'`/`′` separator, whether or not a real `°` preceded it, so a
    corrupted-to-`0` or entirely-dropped degree symbol is absorbed
    exactly as OCR produced it — and then **range-validates**: minutes/
    seconds `< 60`, degrees `≤ 90` for a N/S hemisphere or `≤ 180`
    otherwise. `49008` (or, after regex backtracking finds the only
    combination that lets the rest of the string match, `deg=4900`) fails
    that bound instantly. The corruption is caught because the *value* is
    physically impossible, never because the parser recognized the
    *glyph* mistake — satisfying the audit's constraint precisely. A new
    status, `SUSPECT_GLYPH_CONFUSION`, was added
    (`contracts.PARSE_STATUSES`/`VALUE_STATUSES`) so the owner sees a
    specific, actionable hint ("looks like an OCR mix-up") rather than a
    generic `MALFORMED_NUMBER`, and added to
    `RETAINABLE_ERROR_VALUE_STATUSES` (never silently dropped by
    retention), the feed-row warning-colour set
    (`ui/layout.py::_WARNING_VALUE_STATUSES`), and
    `VALUE_STATUS_LABELS` (plain-language: "Reading looks miskeyed — a
    coordinate part is out of range" — caught by
    `test_humanization.py`'s exhaustive-enum check, which correctly
    failed until this label was added). A real `°` character is also
    accepted by the same pattern (optional in the regex) for the case
    where OCR gets it right, in which case the value parses to correct
    decimal degrees, e.g. `49°08'20.06"N` → `49.138906`.
  - `CoordinateParsingTests` (23 new deterministic unit tests in
    `test_parsing.py`) covers every branch: correct `°`, corrupted `°`
    (the danger case, isolated and in a full DMS string), dropped `°`,
    plain decimal degrees (signed and hemisphere-signed), the `'`/`′` and
    `"`/`″`/`''` glyph and its ASCII confusables, minutes/seconds
    out-of-range, degrees out-of-range with and without a hemisphere
    letter, a Unicode replacement character (U+FFFD, what a *total*
    OCR glyph-recognition failure looks like) explicitly flagged rather
    than silently dropped, garbage/empty input, routing through
    `parse_for_source` by `data_type`, and — the exact original danger
    case — two full coordinates in one string never silently resolving to
    one. All 23 pass; full `test_parsing.py` (51 tests) and the full M2
    deterministic suite (437 tests, up from 414 after these additions
    plus the humanization label fix) re-run clean.
- **1.3 — integration-level proof, against the real engine, not a mock.**
  A new synthetic Tk target, `spike_coordinate_dms_target.py`, renders one
  DMS coordinate (`49°08'20.06"N`) at the same realistic small on-screen
  scale as the real bug (13pt, field height 28px — under the 60px
  small-crop floor), and a new `CoordinateDmsOcrRegressionTests` drives it
  through the REAL controller + REAL worker + REAL Windows OCR engine +
  the new `coordinate` parse mode. The assertion is deliberately outcome-
  agnostic about what the OCR engine does with the `°` glyph (Phase 0
  already established real ClearType-rendered text behaves differently
  from synthetic PNGs) and instead pins the one property Phase 1 exists to
  guarantee: the result is EITHER the exact correct decimal value OR one
  of the disclosed safe-failure statuses — never a silently wrong number.
  **What actually happened, live, on this machine**: the real OCR engine
  reproduced the exact real-world bug — `raw_text` came back
  `49008'20.06"N` (the same `°`→`0` misread the owner's original report
  showed) — and `parse_coordinate` caught it as `SUSPECT_GLYPH_CONFUSION`
  with `normalized_value: None`, never a wrong number. This is not a
  hypothetical fixture engineered to demonstrate the fix; it is the actual
  reported danger case, reproduced end to end through the real pipeline,
  caught correctly. 3x consecutive runs, identical result each time.
- **Full validation gates (Phase 0 + Phase 1)**: M2 deterministic
  437/437, baseline 42/42 (incl. sanitization), M1 34/34, Windows
  integration 14/14 (3x stable), sanitization PASS, `git diff --check`
  clean.

### Phase 2 — One overlay, three values: making the real workflow usable

The prior sections fixed HOW a coordinate string is parsed once a field
already has clean text; this phase addressed WHETHER the owner can get
clean text into the right field at all, given that the real target's
readout is one thin overlay line holding lat+long+elev together (e.g.
`49°08'20.06"N 123°03'41.61"W 87.05`), not the S7 fixture's convenient
three-separate-lines layout used throughout earlier sessions.

- **2.1 — the 3-sub-region attempt, measured then reproduced live.** A
  new synthetic target, `spike_coordinate_line_target.py`, renders exactly
  that combined line at 13pt Segoe UI (the realistic small on-screen scale
  established in §5j/Phase 0). Measured with real Tk font metrics: full
  line width 274px; the three values occupy `[0,106]`, `[111,229]`,
  `[234,274]`px — **only 5px of gap between adjacent values on each
  side**. That is narrower than the 12px minimum margin Phase 0 itself
  proved OCR needs to reliably recognize text at all, and far too tight a
  target for a human to reliably drag three non-overlapping sub-regions by
  mouse. This was not left as a geometric argument: three sub-regions were
  computed PROGRAMMATICALLY from those exact measured spans (zero extra
  slack — a strictly better-than-human-precision best case) and driven
  through the REAL controller + REAL worker + REAL OCR engine. Result:
  field 1 (`Lat`) → `EMPTY_TEXT` (nothing recognized at all); field 2
  (`Long`) → OCR'd as `'123003141.61 "Vi'` (badly garbled, wrong digits,
  wrong hemisphere letter); field 3 (`Elev`) → OCR'd as `'87.0�'` (a
  replacement character in place of the last digit). **None of the three
  values would have come through usable**, even at pixel-perfect,
  computer-exact region boundaries no human drag could match. The 3-sub-
  region approach is conclusively impractical, not merely inconvenient.
- **2.2 — the fix: one shared region + `line_part`.** A new optional
  `SourceConfig.line_part: int | None` field (`models.py`) lets several
  fields share ONE drawn region (the whole line): `parsing.
  parse_for_source()` gained a `line_part` parameter that, when set, first
  splits the region's OCR'd text on whitespace and parses only the
  `line_part`-th token — everything else about that field's parsing
  (`data_type`, range, precision) applies exactly as if that token were
  its entire raw text. A region with fewer tokens than requested returns
  `NO_NUMBER` (never silently reuses a neighbouring token or a prior
  tick's value — verified by a dedicated test). The UI's Edit-field dialog
  gained a "Line part (optional)" entry and a "Copy region from" picker
  that fills the rect field from another configured field, so sharing a
  region does not require the owner to hand-transcribe pixel coordinates.
  **XYZ-eligibility rule fixed to be coherent with Phase 1**: `coordinate`
  (a number-shaped, corruption-safe parser) previously could NOT hold an
  X/Y/Z role at all — `validate_source`, `xyz_eligibility`, and
  `xyz_missing_axes` required `data_type == "number"` exactly, a rule
  written before `coordinate` existed. Since lat/long fields need
  `coordinate` for OCR-corruption safety (Phase 1) and ALSO need an X/Y
  role for XYZ export, the two features were mutually exclusive until this
  fix (now `data_type in ("number", "coordinate")`, same for the
  `min_change_threshold` numeric-only gate). Driven live against the SAME
  real target, ONE shared region (a normal-width drag around the whole
  line, not a computed sub-span): `xyz_eligibility` reports eligible
  (structural check, deterministic); the real OCR engine reproduced the
  same °→0 misread Phase 1 exists to catch on both coordinate tokens
  (`Lat` → `SUSPECT_GLYPH_CONFUSION`, `Long` → `MALFORMED_NUMBER`, both
  safe, no wrong number), while the plain-number third token (no degree
  symbol involved) read cleanly (`Elev` → `OK`, `87.05`) — deterministic
  across 3 repeated runs. `LinePartParsingTests` (8 unit tests),
  `test_coordinate_type_holds_xyz_roles`/`test_line_part_*` (4 model
  tests), and a new real-worker integration test,
  `SharedRegionLinePartIntegrationTests`, pin this exactly (3x stable).
- **2.3 — hover/transience verified, not found broken.** The real
  workflow's readout is only present while the owner hovers the mouse
  over the map — it legitimately disappears and reappears as attention
  moves. Reading `stability.py` closely first: `MISSING_SOURCE_VALUE` is
  explicitly excluded from both the change-tracking and error-tracking
  paths (`process_tick`'s `if status in ("MISSING_SOURCE_VALUE",
  "UNSTABLE_READING"): continue`) — a live-only, no-op status by design,
  already correct. A new scenario test,
  `HoverTransienceScenarioTests.test_hover_on_off_on_same_then_different_
  value_no_spurious_errors` (`test_controller_policy.py`), drives the
  REAL controller through a 7-tick present/away/present-same/away/present-
  different/away/present-same cycle and asserts the exact expected
  outcome: exactly ONE retained event (the genuine value change at tick
  5), zero retained errors, and each tick's own live observation correctly
  shows that tick's true status — passed on first write, confirming
  (rather than fixing) correct existing behavior. A guide note was added
  ("A value flickers to 'No value yet' and back…") explaining this is
  expected and safe, not an error.
- **2.4 — latency/perf with 3-8 small fields, measured under the shipped
  padding+floor fix.** `perf_harness.py` (pre-existing, unmodified) against
  the S7 target with field heights forced under the 60px small-crop floor
  (44px at 3 sources, 27px at 8 sources — both trigger the padding+
  upscale path): with the target's static content (pixel-hash caching
  active, the realistic case for an UNCHANGING reading), mean tick time
  17.3ms (3 sources) / 20.5ms (8 sources), p95 35.7ms / 29.2ms — both far
  under the research §7 200ms budget and the 1000ms default interval. A
  second measurement forced a genuine (non-cached) OCR call on every field
  every tick — the realistic worst case for a CONTINUOUSLY changing
  hover-driven reading — averaged over 5 fresh runs each: **3 fields:
  ~53.7ms/tick (~11ms/field OCR); 8 fields: ~161ms/tick (~13.4ms/field
  OCR)**. Both stay under the 200ms budget even in this worst case, though
  8 fields (161-183ms observed) leaves markedly less headroom than 3
  (51.5-55.8ms). This is a DIFFERENT target/content than Phase 0's
  isolated "~11ms→~30ms" single-field number and not a controlled A/B of
  the same fixture — reported as its own measurement, not a contradiction
  of Phase 0's. One disclosed limitation surfaced by this measurement:
  `line_part` fields sharing an identical rect are NOT deduplicated at the
  capture layer — each still issues its own independent crop+OCR request
  (3x the OCR cost for what is conceptually one crop), verified safe only
  because Phase 0 already established OCR is deterministic per identical
  crop bytes (confirmed again here: three independently-captured
  observations of the same shared rect returned byte-identical raw_text
  across repeated runs) — but it is real, uncaptured perf headroom a
  future session could reclaim with a capture-level rect-dedup pass.
- **Full validation gates (Phase 2)**: M2 deterministic 449/449, baseline
  42/42, M1 34/34, Windows integration 15/15 (3x stable), `git diff
  --check` clean.

### Phase 3 — S7 field-3 root cause and a repo-wide vague-limitation sweep

- **3.1 — S7 field-3 ("Elev") EMPTY_TEXT mystery: already resolved, cross-
  referenced here rather than re-investigated.** This was root-caused as a
  genuine, deterministic side effect of Phase 0's padding fix (see "A
  genuine, deterministic side effect discovered while re-validating" under
  Phase 0 above): the field read `EMPTY_TEXT` on every run both before and
  after §5j's upscale-only fix, and now reads `87.05` correctly, every
  time, because the padding step (not the upscale floor alone) was the
  missing ingredient for that field's specific crop geometry.
  `test_full_record_and_finalize` was already rewritten in Phase 0 to
  assert this exact, now-readable value per field. No further
  investigation was needed or performed in this phase - re-litigating an
  already-evidenced root cause would not add information.
- **3.2 — repo-wide sweep for TODO/FIXME/deferred/vague-limitation
  markers.** Searched `src/`, `tests_m2/`, and every file in the repo
  (excluding `.git/`) for `TODO`, `FIXME`, `XXX:`, `HACK:`: **zero
  matches anywhere in the repository.** Searched `src/` and
  `docs/public/Screen2XYZ_M2_Guide_v0.1.md` for hedge language ("may not
  work", "not always reliable", "unclear whether", etc.): zero matches:
  the guide and worker/controller code were already free of vague
  language. Two remaining instances of "not yet resolved" in `src/`
  (`capture_worker_windows.ps1`, `ui/layout.py`) were checked and are
  precise, well-defined states (a `$null` probe-latch value before Auto
  resolves; a specific "run Test capture to find out" status string), not
  hedges. The one genuine finding was in THIS report's own §6: "the
  transient-probe latch and monitor-scope DPI reporting are noted for a
  future worker pass" - a real, prior-session limitation left without
  boundary conditions. Re-audited against the actual PowerShell source and
  rewritten in §6 with the exact mechanism and boundary for each: the
  Auto-backend probe latches once per session by design (`Handle-Capture`
  always calls `Resolve-And-Capture -ForceProbe $false`) and only an
  explicit Test capture/Retest re-probes; monitor-scoped captures report a
  literal hardcoded `dpi: 96` (`capture_worker_windows.ps1` lines 211/215)
  regardless of the monitor's real scaling, while window-scoped captures
  correctly call `GetDpiForWindow` - a metadata-accuracy gap specific to
  monitor scope, not a capture-correctness one. No vague "may not work"
  language remains in the report, the guide, or the source tree.

### Phase 4 — Usability pass on the real coordinate workflow

- **4.1 — every reachable failure status now has a concrete, specific
  action, not a generic warning icon.** Audited the recording screen's
  field cards and found every warning-coloured card showed the SAME fixed
  string, "⚠ capture/OCR issue", regardless of which of the 11 distinct
  failure statuses actually occurred - a non-technical owner had no way
  to tell a too-tight region from a wrong decimal separator from a
  genuinely gone window. Added `layout.value_status_guidance()` (mirrors
  the existing `pause_guidance()` pattern) giving each reachable
  value_status its own one-line next step, wired into `_update_field_card`
  in place of the generic fallback. `ValueStatusGuidanceTests` (4 tests)
  asserts every non-OK, non-live-only status has real guidance and none
  leaks a raw code. The card was widened (176→216px scaled height) and
  the warning label given a wraplength so the longer, specific text
  doesn't get clipped.
- **4.2 — defaults verified to work, and "No value yet" no longer stays
  silent forever.** The "gets a value" half of this requirement is
  already proven by existing evidence, not asserted fresh here:
  `SmallTextOcrRegressionTests`, `CoordinateDmsOcrRegressionTests`, and
  `SharedRegionLinePartIntegrationTests` all drive a field at realistic
  small on-screen scale with `upscale_factor` left at its default (1) and
  get a real value or a specific safe-failure status through the real
  worker + real OCR - never nothing. The "or an actionable message" half
  had a genuine gap: a field whose region was simply drawn in the wrong
  place would show "No value yet" (`MISSING_SOURCE_VALUE`) with zero
  escalation for the rest of the session, indistinguishable from a normal
  brief hover-away blip. Fixed with a per-field consecutive-missing-tick
  counter (UI-presentation only - never touches value_status, pausing, or
  the journal): below `MISSING_VALUE_HINT_TICKS` (10) the card stays
  silent exactly as a hover blip should (§5k Phase 2.3); at or above it,
  the card shows "No value in the last N captures. Confirm the region is
  drawn over the value's exact on-screen location (Edit selected), or
  Retest." `MissingValueEscalationTests` (3 tests) pins the threshold
  boundary and message content.
- **4.3 — guide walkthrough added, and two stale claims fixed in
  passing.** Added "Live map coordinates (Google Earth) walkthrough" to
  the public guide: don't attempt three tiny sub-regions (measured
  evidence why), draw one region around the whole line, add three fields
  sharing it via "Copy region from", set `coordinate` type + `line_part`
  0/1/2, what a degree-symbol misread looks like now (safe, specific,
  actionable) versus before this session (silently 10-1000x wrong), and
  an explicit "not run against your actual Google Earth window" honesty
  note. While there, found and fixed two guide passages the Phase 1/2
  work had made stale: Step 3's field-type list still said "(number/text/
  auto)" with no `coordinate`, and its role note still said "X/Y/Z
  require number fields" (pre-dating the Phase 2 XYZ-eligibility fix).
- **4.4 — `validate-real-target` wizard against the Phase 2 stand-in.**
  `ValidationApp` (`validate_real_target.py`) is architecturally a thin
  wrapper around the production `M2App` - its own code only adds a
  banner, a consent gate, and post-Stop verdict computation; every setup/
  picker/preview/recording code path in between (including the `coordinate`
  data type and `line_part` field this session added) is the exact same
  M2App code already proven against the Phase 2 synthetic stand-in by
  `SharedRegionLinePartIntegrationTests` (real controller, real worker,
  real OCR, 3x stable). `observation_is_meaningful()` (the wizard's own
  verdict-computation logic) was directly verified against a `coordinate`
  -typed observation: `OK` + a real decimal value → meaningful=True;
  `SUSPECT_GLYPH_CONFUSION` + `None` → meaningful=False - both correct.
  What was NOT done, honestly: a live, interactive run of the wizard
  itself (its consent messagebox, the "I changed a target value" prompt,
  the four post-Stop confirmation questions) requires a human at a real
  display, which this session did not have (no computer-use access this
  session; see §6). That gap is not new or specific to this session's
  changes - it is the same boundary the mandatory owner G-E-REAL run has
  always existed to cross. **Exact steps for the owner's formal run**,
  now including the new coordinate workflow:
  1. Open the target application (e.g. Google Earth) with only
     authorized, non-confidential content on screen.
  2. Run `.\run_screen2xyz_validation.ps1` (or
     `.\.venv\Scripts\python.exe -m screen2xyz_m2 validate-real-target`).
  3. Confirm the consent prompt (content is authorized/non-confidential).
  4. Select the target window, backend `auto` (recommended).
  5. Click **Test capture now**; confirm PASS/WARNING (not FAIL).
  6. Add three fields per the new guide walkthrough: Lat and Long as
     `coordinate` type with roles X/Y, Elev as `number` type with role Z
     (optional, only if XYZ export is wanted); draw ONE region around the
     whole combined readout line; use "Copy region from" so Long and Elev
     share Lat's rect; set **Line part** 0/1/2 respectively.
  7. Preview each field; tick "aligned with the intended value" for all
     three (or note in the confirmations if a field shows a flagged
     status like `SUSPECT_GLYPH_CONFUSION` instead of a value - that is
     itself useful evidence, not a failure to work around).
  8. Arm, Start recording, use the always-on-top panel to mark "I changed
     a target value" after actually panning/zooming the map so the
     reading changes, then Stop.
  9. Answer the four post-Stop confirmation questions honestly.
  10. Share only the sanitized JSON report written under `.lab_work/`
      (never a screenshot or the target's window title).
- **Full validation gates (Phase 4)**: M2 deterministic 456/456 (449 + 7
  new), baseline 42/42, M1 34/34, `git diff --check` clean. Windows
  integration unchanged by this phase (no capture/OCR/parsing code
  touched - UI guidance strings and a guide/report update only) and was
  already 15/15 (3x stable) as of Phase 2/3.

### Phase 5 — Definition-of-done check and final gates

Checked against the mission's own definition of done, phase by phase
above rather than re-asserted here:

- **Upscale heuristic survives boundary audit or replaced with a better,
  evidence-backed one, revert-tested** — Phase 0: the boundary audit found
  a real gap (margin, not scale); the padding fix closed it, verified
  against the real shipped function (11/11) and revert-tested (both
  directions, 3x stable).
- **DMS/coordinate text can never silently become a wrong numeric value,
  proven by unit + integration tests** — Phase 1: 23 unit tests plus a
  real-engine integration test that reproduced the ACTUAL reported bug
  live (°→0) and caught it as `SUSPECT_GLYPH_CONFUSION`, never a wrong
  number, 3x stable.
- **The owner's realistic one-line→x/y/z→XYZ-export workflow works end to
  end on a synthetic stand-in with default settings, proven by an
  integration test** — Phase 2: `SharedRegionLinePartIntegrationTests`
  does exactly this against a target built from the audit's own quoted
  real-target string, 3x stable; the harder claim (the 3-sub-region
  approach the owner would otherwise have to use) was proven impractical
  with live pipeline evidence, not just argued.
- **S7 field-3 mystery resolved** — Phase 0/3.1: root-caused as a real,
  deterministic side effect of the padding fix; `Elev` now reads `87.05`
  correctly every time.
- **Every reachable failure state shows an actionable plain-language
  message** — Phase 4.1/4.2: audited and found a real gap (one generic
  message for 11 distinct statuses, and no escalation for a permanently-
  empty field); both fixed and tested.
- **All suites green 3x stable, CI green, PR #5 updated and still Draft,
  report §5k written, guide updated** — this section.
- **Zero claims without evidence produced in this session** — every fix
  above is backed by a test run in this session with output shown, or an
  explicit "verified, not fixed" finding where re-audit found existing
  behavior already correct (Phase 2.3 hover-transience; Phase 4.4's
  wizard inheritance).

**What this session found that overturned or extended the prior
session's own conclusions, stated plainly**: the prior session's upscale-
only fix (§5j) was real and necessary but incomplete - margin around the
ink matters independently of scale, a gap the boundary audit proved and
closed (Phase 0). The prior session's own `test_full_record_and_finalize`
already contained the degree-symbol corruption evidence, unexamined until
this session (Phase 1). The S7 fixture's three-separate-lines layout,
used throughout every prior session's coordinate-related work, does not
match the real target's actual one-line format - a mismatch this session
found and designed around (Phase 2). No prior conclusion was found to be
simply wrong; each was real but incomplete in a way only a hostile,
evidence-first re-audit surfaced.

- **Final validation gates (whole session)**: M2 deterministic 456/456,
  Windows integration 15/15 (3x stable, confirmed again at the end of
  Phase 5), baseline 42/42 (incl. sanitization), M1 34/34,
  `git diff --check` clean. Six commits this session (`97d81fa`
  Phase 0, `966816f` Phase 1, `f92c4f4` Phase 2, `9f39379` Phase 3,
  `ba89607` Phase 4, `71cbd70` a date-error fix found during Phase 5's
  own final read-through), all pushed to
  `feat/m2-live-region-watch-impl`. PR #5 **remains Draft** - no merge,
  no force-push, at any point this session.

## 5l. Real owner usage after §5k: misleading guidance for a number-typed coordinate field (2026-07-19)

The owner tried the new coordinate workflow against their real Google
Earth window the same day §5k shipped, and reported a field that "sees
the value but won't record it." Screenshots showed the exact real-world
danger case §5k Phase 1 was built for - but the owner had not (yet)
switched the field's Type from the default `number` to `coordinate`, so
it correctly refused to guess (`AMBIGUOUS_MULTIPLE_NUMBERS`) - and the
guidance shown, "Redraw a tighter region around just this value," was
**actively wrong** for this case: the region was already scoped to one
coordinate; no amount of redrawing fixes a degree-symbol misread.

- **Root cause, not just a support answer.** The generic AMBIGUOUS_
  MULTIPLE_NUMBERS/MALFORMED_NUMBER guidance (§5k Phase 4.1) assumes the
  cause is a region that's too loose. For coordinate-shaped text on a
  `number`-typed field, the real cause is a type mismatch, and the fix is
  in Edit selected, not the region picker.
- **Fix: a permissive, UI-hint-only heuristic.** `parsing.
  looks_like_coordinate()` - deliberately looser than `_COORD_RE` (it
  `search()`s rather than requiring a full match, so trailing OCR noise
  like a stray bullet glyph doesn't block it) - detects text that has the
  shape of a DMS coordinate (digit run, optional corrupted-degree `0`,
  digit run, prime, digit run, optional hemisphere letter). Verified
  against the owner's own exact reported strings (including the stray
  glyph): all four detected correctly; elevation values ("2 cm", "14 m"),
  plain numbers, and unrelated text never falsely trigger. `layout.
  value_status_guidance()` gained optional `raw_text`/`data_type`
  keyword arguments (defaulted, so every existing call site keeps working
  unchanged) - when a field is NOT already `coordinate`-typed and its raw
  text looks coordinate-shaped, the specific "switch this field's Type to
  coordinate" hint pre-empts the generic (here wrong) one. The hint never
  fires for a field already typed `coordinate` (would be circular advice).
- **Wired into BOTH places an owner can see it** - the recording screen's
  field cards (already had generic guidance, Phase 4.1) AND the Step 4
  Preview gate, which previously showed raw OCR text and a normalized
  value with **no warning at all**, even for a hard parse failure -
  arguably the more important gap, since it is the very first screen
  where the owner could see and fix this, before ever starting a real
  recording.
- **Verified against the real, reported strings, then against the real
  pipeline.** `LooksLikeCoordinateTests`/`ValueStatusGuidanceCoordinateHintTests`
  (8 unit tests, `test_parsing.py`) use the owner's own screenshotted OCR
  output verbatim. A new integration test,
  `NumberTypeCoordinateHintIntegrationTests`, reproduces the owner's EXACT
  misconfiguration (field left on `number`, one region around one
  coordinate) through the REAL controller + REAL worker + REAL Windows OCR
  engine, then feeds the REAL resulting raw text through the REAL
  guidance function the same way the UI does - not a hand-picked string.
  Result, 3x consecutive runs: real OCR reproduced the same °→0 misread
  as before (`49008'20.06"N`), correctly refused as `AMBIGUOUS_MULTIPLE_
  NUMBERS`, and the specific coordinate-type hint fired every time.
- **Also checked, separately reported by the owner but not reproduced
  this session**: the demo self-test not passing on a first attempt, and
  the region-drawing picker window's initial-open behavior. The demo
  self-test ran 3/3 clean on this machine during this session (consistent
  with the timing-sensitivity characteristic already disclosed and
  mitigated at §5f/§9 - a first-tick PrintWindow `WM_PRINT` stall, not
  eliminated everywhere, just bounded). The picker-window report lacks
  enough detail (which window, what "opened immediately" meant) to
  reproduce; flagged here rather than guessed at.
- **Full validation gates**: M2 deterministic 464/464 (456 + 8 new),
  Windows integration 16/16 (3x stable), baseline 42/42, M1 34/34,
  `git diff --check` clean.

### 5l addendum. Generalizing the hint: alphanumeric codes, not just coordinates (2026-07-19)

Same day, immediate owner follow-up: "I need it to recognize not just
coordinates but also text and numbers and non-standard numbers" - i.e.
the same class of problem (a `number`-typed field over content that
genuinely isn't a plain number, where generic "redraw"/"check separator"
advice is wrong) generalized beyond coordinates to alphanumeric codes/
serial numbers (e.g. "SN-4829").

- **`parsing.looks_like_alphanumeric_code()`** - a second, equally
  conservative UI-hint-only heuristic. Flags text only when a letter is
  found directly touching a digit (optionally joined by `-`/`_`, never
  plain whitespace) - the shape a genuine code has. Explicitly does
  **not** flag: a clean number with a short trailing unit label
  ("87.05m", "14 m", "2 cm") - redrawing/upscaling remains the right fix
  there, not a type change; or a label prefix separated from a clean
  number by whitespace/`:`/`=` ("Elevation: 87.05", "Cursor 49, 22") -
  same reasoning. Cross-excludes anything `looks_like_coordinate()` already
  claims, so the two hints never compete for the same text.
- **Wired into the same `value_status_guidance()` extension point**:
  `MALFORMED_NUMBER` with code-shaped text, or `NO_NUMBER` with ANY
  letter present (NO_NUMBER already means "text was found, zero numeric
  candidates in it" - a letter's presence is a reliable signal the field
  isn't numeric), now suggest switching Type to "text" or "auto" instead
  of the generic redraw advice.
- **Explicitly did not overclaim "everything possible."** `text` and
  `auto` data types already existed and already handle arbitrary content
  (names, mixed text, single numbers) with no code changes needed here -
  most of what "more universal" could mean was already true; this
  addendum closes the one remaining real gap (misleading advice for the
  specific "looks numeric-ish but isn't" failure shape), not a rewrite of
  the type system. Genuinely exotic formats not anticipated here (and not
  reported by the owner) are not claimed to be covered.
- **10 new deterministic tests** (`LooksLikeAlphanumericCodeTests`,
  `ValueStatusGuidanceAlphanumericHintTests`) - including the tricky
  negative cases (trailing unit, label prefix) that prove the heuristic
  does NOT compete with the existing, already-correct advice for those
  shapes.
- **Full validation gates**: M2 deterministic 474/474 (464 + 10 new),
  Windows integration 16/16 (3x stable, re-run after this change since it
  touches `parsing.py`), baseline 42/42, M1 34/34, `git diff --check`
  clean.

## 5m. Owner escalation: hints were not enough - the app must fix and record itself (2026-07-21)

The owner's third real session (competition deadline imminent) still
showed "More than one number in the region" on both coordinate fields and
the OLD generic "redraw a tighter region" advice on the field cards. Two
distinct root causes, both real, plus an owner decision that changed a
Phase 1 constraint:

- **Why the owner saw the OLD advice even on new code**: a pixel-hash-
  cached tick deliberately blanks `obs.raw_text` (contract - a cached
  confirmation is never presented as fresh OCR). The content-aware hint
  (§5l) keys off `raw_text`, so a STATIC (unmoving) reading starved it of
  input every cached tick and fell back to the generic advice - exactly
  what the owner's screenshots showed. Fixed display-side only: the field
  card now remembers the last non-empty raw text per field and feeds THAT
  to the guidance when the current tick's is blank. No contract change -
  `obs.raw_text` itself stays blank on cached ticks everywhere else.
- **Hints demonstrably don't get acted on - the app now offers the fix
  itself.** New `layout.suggest_field_type()` (pure, headlessly tested):
  given a field's REAL preview outcome, returns the type that would
  actually work (`coordinate` for coordinate-shaped text on a number
  field; `auto` for code-shaped or letters-only text), or None when the
  current type is fine or redrawing genuinely is the right advice (a
  true two-numbers region never suggests). The Step 4 Preview gate now
  shows ONE modal yes/no listing every suggested switch; on an explicit
  yes it applies the types (releasing an X/Y/Z role if a non-numeric
  type takes it - announced, never silent) and re-runs the preview so
  the owner immediately sees the corrected result. Declining changes
  nothing.
- **The universal type is now genuinely universal**: `parse_auto`
  detects coordinate-shaped text (same heuristic as the hint) and routes
  it through the STRICT coordinate parser - decimal degrees when valid,
  the labelled recovery below when corrupted, fall-through to the
  existing number/text logic otherwise. Trailing OCR noise glyphs
  (bullets, U+FFFD) are stripped before the strict parse - mechanical
  cleanup, not value guessing.
- **OWNER DECISION - corrupted-degree recovery (supersedes the §5k
  Phase 1 "flag only" stance for one narrow shape).** Phase 1's
  `SUSPECT_GLYPH_CONFUSION` flag was correct but left the owner's real
  recordings EMPTY: on their machine OCR misreads `°` as `0` virtually
  every tick, so a safe flag every tick means no numeric data at all -
  and the owner explicitly needs recorded values ("хочу чтоб ето
  работало когда отправлю на конкурс"). New
  `parsing._recover_corrupted_degrees()`: a strict structural decode
  that fires ONLY when all of these hold - full DMS shape including a
  seconds group AND a hemisphere letter; everything before the first
  minutes separator is pure digits (a correctly-read `°` never enters
  this path); that run is >=4 digits with EXACTLY `'0'` in the position
  where `°` belongs; and the decoded degrees/minutes/seconds all pass
  the same range validation a clean reading must. The result always
  carries the `DEGREE_GLYPH_RECOVERED` warning code, which flows through
  `parse_for_source` -> controller -> journal/CSV next to the preserved
  raw text and crop - auditable, never silent. Bare `"49008"`, no-
  hemisphere strings, wrong separator digits, and decodes that still
  fail range validation all remain flagged, not guessed
  (`test_recovery_never_fires_without_full_dms_context`).
- **Verified end to end, 3x, against the real engine**: the owner's
  exact misconfiguration (default `number` field over a DMS readout) →
  real OCR reproduces the °→0 misread → the one-click dialog decision
  fires (`coordinate`) → after the switch the SAME corrupted text now
  parses to `49.138906` with the recovery label → the `auto` type on the
  same target does the same. The owner's exact on-screen values from
  their screenshots (`20°41'18.46"N` → `20.688461`, `105°55'22.59"E` →
  `105.922942`, corrupted forms included) verified in unit tests.
- **Full validation gates**: M2 deterministic 487/487, Windows
  integration 16/16 (3x stable), baseline 42/42, M1 34/34, demo
  self-test PASS, `git diff --check` clean.

## 5n. Adversarial review of §5m before delivery: 12 confirmed findings, all fixed (2026-07-21)

Ground rule for this whole audit: every fix gets adversarially verified
before being handed back, not just self-tested. §5m's diff (the
corrupted-degree recovery + one-click type-fix dialog) was reviewed by
three independent finder passes (correctness, UI-flow, safety-regression)
over the actual working diff, each finding adversarially re-verified
against the real code and real execution before being trusted. **12 of 12
findings confirmed real** - none were false positives - and all 12 are
fixed below, re-verified against real OCR 3x after the fixes.

- **Silent-wrong-value regressions in the new coordinate regex (3
  findings, the most severe class).** The original `_COORD_RE` made the
  degree symbol optional even BETWEEN degrees and minutes, so the regex
  engine could backtrack a plain digit run into an arbitrary,
  meaningless split with no real separator at all: `"12'10\"N"` (a
  feet-inches measurement, not a coordinate) matched as
  deg=1/min=2 → a confident, unflagged `1.036111`; `"20.41'18.46\"N"`
  (a real target's `°` misread as `.`) matched as deg=20.4/min=1 → a
  confident `20.421794` against a true value of `20.688461` (~30km off);
  `numeric_range`/`precision_max` were bypassed entirely on this path,
  contradicting `parse_auto`'s own contract comment two lines above it.
  **Fixed**: minutes are now reachable ONLY through a literal `°`
  (`_COORD_RE` rewritten); the corrupted (`°→0`) shape is handled by a
  SEPARATE, narrower `_CORRUPTED_DMS_RE` (a pure digit run + real
  minutes/seconds punctuation) that never overlaps with a correctly-
  written coordinate; `parse_auto`'s coordinate branch now applies
  `numeric_range`/`precision_max` exactly like the plain-number path.
- **The recovery itself could silently pick the WRONG split (2
  findings).** A short corrupted run can contain more than one digit
  that could structurally be the misread `°` - `"4008'20.06\"N"` splits
  validly as EITHER `4°08'` or `40°8'`, both physically plausible;
  `"17008'20.06\"E"` is ambiguous the same way for E/W. The original
  recovery hard-coded ONE interpretation (always treating the third-
  from-last digit as the symbol) and picked it even when a second,
  equally valid split existed - exactly the silent-wrongness this
  session's own design principle exists to prevent. **Fixed**: every
  `'0'` position in the digit run is now tried as a candidate split;
  recovery only fires when EXACTLY ONE candidate is physically valid.
  Two or more valid splits means genuine ambiguity - stays flagged, not
  guessed. (One existing test, `test_full_dms_with_dropped_degree_
  symbol_...`, asserted the OLD "always flagged" behavior for
  `"4908'20.06\"N"` - a string with only ONE `'0'`, hence genuinely
  unambiguous; updated to assert the new, correct recovery.)
- **The axis bound checked degrees alone, not the composed total.** A
  reading with degrees exactly at the pole/antimeridian (90°/180°) PLUS
  nonzero minutes/seconds is a real position past the physical limit,
  but only the degrees component was checked. **Fixed**: the bound now
  gates the composed decimal total; `90°00'00"` (exactly at the pole)
  still correctly recovers, `90°08'20"`-shaped readings correctly do not.
- **`warning_codes` silently dropped on two paths (2 findings).** A
  `DEGREE_GLYPH_RECOVERED`-labelled value - the whole point of which is
  "auditable, never silent" - lost that label on every pixel-hash-cached
  tick after the first (the cached-replay block in `controller.py`
  copied every other parse-derived field except this one), and had
  nowhere to appear in either CSV export at all (present on the
  journal's own `Observation`, surfaced by neither exporter). **Fixed**:
  the cached-replay block now copies `warning_codes` alongside its
  siblings; `LONG_CSV_HEADER` gained a `warning_codes` column (the
  natural home - it is already the per-observation audit-trail export;
  the wide CSV's fixed 2-column-per-field schema was left alone as
  lower-risk under the deadline).
- **UI-flow bugs in the new one-click dialog (2 findings).** The
  `gate.after(200, offer_type_fix)` timer was never cancelled on
  destroy - Tk deletes the callback's Tcl command but leaves the timer
  armed, so clicking either button within 200ms threw a background Tcl
  error (a `winfo_exists()` guard inside the callback was dead code,
  provably unreachable, since Tk errors out before that body ever runs).
  Separately, `_show_preview_gate`'s unconditional `self._refresh_table()`
  crashes with `TclError` when reached via `_disarm_and_repreview()`
  (which already destroyed the setup screen's Treeview) - a **pre-
  existing** bug this session's own new `offer_type_fix()` call also
  runs into on that same path. **Fixed**: the timer's job id is now
  tracked and explicitly `after_cancel()`-ed on every path that destroys
  the gate; `_refresh_table()` gained the same "not on the setup screen"
  guard `_refresh_next_step()` already documents and applies for exactly
  this reason.
- **The role-clearing side effect was disclosed too late to matter.**
  The yes/no dialog never mentioned that accepting could clear an X/Y/Z
  role until after the owner had already said yes, and the compensating
  status-bar announcement was proven to never actually paint (`_preview()`
  overwrites the same StringVar with "Previewing…" before the event loop
  processes an idle redraw for the announcement). **Fixed**: the dialog
  text itself now names which fields would lose their role BEFORE asking
  for yes/no; if any role is actually cleared, a blocking confirmation
  dialog (the same pattern the Edit-field dialog already uses for this
  exact rule) replaces the silently-overwritten status message.
- **11 new deterministic tests** covering every finding by its own
  concrete failing input (not a generic smoke test), plus the full owner-
  scenario live verification re-run 3x against the real controller/
  worker/OCR engine after all fixes, confirming the exact real-world
  degree-corruption case still recovers correctly end to end.
- **Full validation gates**: M2 deterministic 496/496 (487 + 9 net new -
  one existing test's assertion was updated, not added), Windows
  integration 16/16 (3x stable, re-run since this touches `parsing.py`/
  `controller.py`), baseline 42/42, M1 34/34, demo self-test PASS,
  `git diff --check` clean.

## 5o. CI canary fix, a real Draw-region bug found live, and G-E-REAL PASS (2026-07-21)

**CI fix.** `tests_m2/run_m2_tests.py`'s frozen `EXPECTED_TEST_COUNT`
canary (`"update EXPECTED_TEST_COUNT intentionally in the same commit
that adds or removes tests"`) was not updated when §5m/§5n's new tests
landed, so PR #5's `deterministic tests (windows-latest)` CI job failed
on an otherwise green suite (`Ran 496 tests ... OK`, 0 failures/errors,
`##[error]Process completed with exit code 1` from the stale-count
check alone). Corrected to the real count (496, then 498 after the
Draw-region tests below). No test behavior, assertion, or coverage
changed.

**Draw-region blocked-worker bug, found during the owner's own
G-E-REAL run.** While running `validate-real-target` against a real
target, the owner hit a real dead end: clicking "Draw region…" showed
the 3 s countdown and then nothing — no picker window, no visible
error. Root cause: repeated real-worker capture failures against the
live target latched `setup_worker_blocked` (the same latch Test
Capture/Retest already handle), and `region_snapshot()` then raises
`IllegalAction`, not `WorkerError`. `_draw_region`'s countdown callback
only caught `WorkerError`, so the `IllegalAction` fell through to the
generic top-level callback-exception handler (a non-topmost dialog,
easy to miss behind the real target window) with no mention of Retry —
and "Draw region…" itself was never disabled the way Test Capture/
Retest already are when blocked, so it kept looking clickable. **Fixed**
in `ui/app.py`: `_draw_region` now catches `IllegalAction` and gives an
actionable "click Retry" message when the worker is blocked (mirrors
the existing `_pause`/`_resume` `IllegalAction` handling); "Draw
region…" is now disabled/enabled in sync with the same blocked latch as
Test Capture/Retest. 2 new regression tests added
(`DrawRegionBlockedWorkerTests`).

**G-E-REAL: PASS**, achieved on the owner's own machine on 2026-07-21
after the fix above. The full attempt sequence, in order (all under
`.lab_work/m2_runs/real_target_validation/`, gitignored, never
committed): `BLOCKED` (worker latched, before the fix) →
`FAIL` → `FAIL` (working through the fix) → **`PASS`**
(`g_e_real_20260721T193502Z.json`). The final report: all 4 required
owner confirmations true (`crops_aligned`, `values_corresponded_to_
real_target`, `recording_ui_understandable`, `exported_row_meaningful`);
2 sources, both `region_confirmed`, 24/24 captures `ok`, 5 retained
changes, `final_csv_row_count` (5) matching `journal_event_count` (5)
and `live_csv_row_count` (5); `orphan_process_check: none_found`;
`target_identity_included: false`. Per the module's own guarantee, the
report contains no screenshot, no window title, and no target identity.
As the report itself states, this reflects only the target and session
just recorded, not general real-target support.

**Full validation gates after both fixes**: M2 deterministic 498/498,
Windows integration 16/16, baseline 42/42, M1 34/34, `git diff --check`
clean.

## 6. Honest limitations

- Real-target capture is now proven against one real target/session
  (**G-E-REAL PASS**, §5o) — but, as that report itself states, this
  reflects only the target and session just recorded, not general
  real-target support across arbitrary applications. The Auto backend's
  PrintWindow→CopyFromScreen fallback and bounded hang-timeout are also
  validated against a real, reproduced DWM-layered-window hang (not
  merely a synthetic flat-black frame).
- Windows Graphics Capture (WGC) is **not implemented**; Auto only chooses
  between PrintWindow and CopyFromScreen. §5e records a concrete,
  evidence-based reason (COM interop + D3D11 + async frame delivery not
  reachable from the current PS-5.1-hosted worker), not just a deferral.
- Mixed-DPI (≠100%) is designed for (PMv2 in both processes) but untested on
  this 100%-scaling machine.
- The region-drawing picker now supports real zoom/fit and physical-pixel
  coordinate mapping for large screenshots, but has not been exercised
  against a screenshot larger than this machine's own display.
- The demo self-test's handshake timing sensitivity is now **root-caused and
  fixed at the source** (§5f/§9): the common latency was the command-pump
  poll interval (tightened 50→10 ms) and the rare 8 s stall was PrintWindow's
  `WM_PRINT` dispatch to the target's own Tk loop (the self-test now runs on
  CopyFromScreen with the Auto probe last). The primary self-test path passes
  6/6 with no retry, and the CSV-row-count integration test dropped its retry
  wrapper; `run_self_test_with_retries` is kept only as a vestigial
  last-resort guard, not the mechanism that makes it pass.
- The 5-minute real-time and 30 000-tick accelerated soaks **were run** this
  session (§5f), plus worker-crash/restart and an O(1) live-CSV-growth
  benchmark; results are under `.lab_work/m2_autonomous_qa/`. A genuinely
  multi-hour endurance soak is still an owner-machine item.
- PyInstaller packaging was investigated and a reproducible build command
  documented, but not installed or built this session (no unrequested
  package/network action) - see §5e.
- §5g's overnight sprint found three further real MAJOR issues, disclosed
  at the time rather than rushed, and **all three since fixed** in a
  follow-up commit the same session: (1) `_pause()`/`_resume()` touched
  the controller/worker directly with no synchronization against a
  concurrently in-flight tick - a losing race could produce an extra
  worker restart or a `PauseState` overwrite; fixed via a new
  `TickScheduler.drain()` primitive and reordering both handlers to drain
  before touching the controller (mirroring `_stop()`/`_emergency_stop()`'s
  already-safe order), and `_handle_pause`'s one remaining direct
  cross-thread `root.after()` call was removed in favor of the existing
  thread-safe tick-result queue. (2) The "Draw region" countdown bar and
  the target/monitor choosers were not modal, so the setup screen could be
  edited out from under them; all three now use `transient()`+`grab_set()`
  (the Preview gate was already fixed earlier). (3) Preview/Start
  recording/the resize-recovery re-preview/Retest-all-regions had no
  "Working…" acknowledgement, unlike Test capture's existing pattern; all
  four now show an immediate status message on their own screen's visible
  status widget before the blocking call. §5h then sent fresh reviewers at
  this exact follow-up commit and found the drain fix above was real but
  still incomplete (a timeout decoupled from the real worker budget, with
  its outcome discarded) plus two banner bugs and a modality-introduced
  UX gap — all fixed there too.
- Some worker-side capture findings are improved but not fully rewritten in
  the PowerShell worker: the PrintWindow-timeout GDI leak is now **bounded**
  by the new capture-failure-streak pause (the session stops issuing
  captures) rather than eliminated at source. Two items previously noted
  only vaguely as "for a future worker pass" - re-audited this session
  (Phase 3.2 sweep) and now stated with their exact boundary conditions
  rather than left open-ended:
  - **The Auto-backend probe latches once per session, by design, and is
    never re-probed automatically.** `Handle-Capture` always calls
    `Resolve-And-Capture -ForceProbe $false` (`capture_worker_windows.ps1`
    line 581), reusing whatever backend Auto resolved at first PREVIEW/
    REGION_SNAPSHOT/RECORDING tick for the rest of the session; only an
    explicit owner "Test capture"/Retest (`ForceProbe $true`) re-probes.
    Boundary: if the target's renderability changes mid-session (e.g. it
    switches into/out of a state PrintWindow can no longer capture) without
    the owner running Retest, Auto will keep using the now-stale latched
    backend rather than silently detecting and switching - the owner-
    visible signal is the field going blank/wrong, not an automatic
    recovery. This is a deliberate latch-not-poll design (re-probing every
    tick would add per-tick backend-selection cost for a condition that
    rarely changes), not an oversight; documented here so it is not an
    unstated assumption.
  - **Monitor-scoped captures report a hardcoded `dpi: 96`, never the
    monitor's real scaling.** `Capture-Frame`'s monitor-scope branch sets
    `dpi = 96` literally (`capture_worker_windows.ps1` lines 211 and 215),
    unlike the window-scope branch which calls the real
    `GetDpiForWindow` (line 137). Boundary: the CAPTURED PIXELS are still
    correct (`CopyFromScreen` reads real physical screen pixels regardless
    of this field), so a monitor-scoped session's actual OCR/values are not
    affected by this on a 100%-scaled monitor; but any exported or
    UI-displayed `dpi` metadata for a monitor-scoped session on a monitor
    running above 100% scaling will read exactly 96 regardless of the true
    value - a metadata-accuracy gap, not a capture-correctness one, and
    specifically scoped to monitor (not window) capture mode.
  The high-impact "records nothing forever" and "wrong-pixel event" cases
  are fully fixed controller-side (§5f).
- The recording screen's new "Disarm and re-preview" recovery button
  (added this session) has been proven against the synthetic demo target
  only, not yet against a real target's actual resize/DPI behavior.
- The synthetic acceptance harness reproduces the same known headless-
  capture-composition limitation documented at M2-011 (an unfocused Tk
  window does not composite for GDI capture in this non-interactive
  session); this is an environment characteristic of running here, not of
  the product, and does not affect the owner's interactive desktop.
- Windows.Media.Ocr unpackaged use is outside its documented support
  envelope (RSK-M2-09); it works on this machine.
- Visual UI verification used a programmatic widget-tree/layout check
  against the real running app, not a human-eye screenshot — interactive
  computer-use access was explicitly requested this session and the owner
  declined it, so no screenshot-based review of the new dashboard/picker
  layout has been done.
- The new `coordinate` data type (§5k Phase 1) parses exactly ONE lat/
  long-style value per field, by design — it never tries to split a
  combined "lat long" overlay line into two coordinates itself (that
  structural decomposition, if wanted, belongs to a higher layer that
  knows the field's intended scope, not this parsing primitive; see §5k
  Phase 2's own scope for the one-region/multi-value question). A field
  fed more than one coordinate's worth of text simply does not match and
  returns `MALFORMED_NUMBER`, the same failure class as any other
  non-numeric text — it is never silently truncated to "the first one".
  Its range validation also means a field genuinely at the poles or the
  ±180° meridian (`degrees == 90` or `== 180` exactly) is accepted
  (`<=`, not `<`), but there is no way for the parser to distinguish a
  degrees value that is merely large-but-real (e.g. a survey using
  something other than WGS84 lat/long) from OCR corruption landing in the
  same numeric neighbourhood — the design accepts that a coordinate field
  is specifically for lat/long-shaped data, not an arbitrary large number.
- No production-readiness or real-world-accuracy claim is made.

## 7. Merge recommendation

Functionally complete and green on synthetic evidence. **G-E-REAL has
passed** (§5o) on the owner's machine. Final merge still requires the
owner's explicit merge decision — by design, this report does not make
that decision.

Conceptual and preliminary estimating data only.
