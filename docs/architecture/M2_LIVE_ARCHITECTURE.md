# M2-Live Architecture

Status: selected from measured evidence (spikes S1–S6) and official research;
final validation of the capture backend against the real target application
is gated on S7 (milestone M2-001, owner machine). Sources of truth:
[research](../research/M2_LIVE_TECHNICAL_RESEARCH.md),
[product spec](../requirements/M2_LIVE_PRODUCT_SPEC.md),
[data contracts](../requirements/M2_LIVE_DATA_CONTRACTS.md).
The authoritative constants, enums, state names, paths, and
`protocol_version: "m2w.1"` live in data contracts §0; this document does
not override them.

## 1. Reuse inventory (file-level, verified 2026-07-17)

| Category | Items |
|---|---|
| Reuse unchanged | `screen2xyz_lab/evidence.py` (`atomic_write_bytes/json`, `sha256_file`, `write_manifest`, `privacy_findings`); `screen2xyz_lab/exporters.py` (`csv_bytes`, `formula_safe_display`, `xyz_bytes`); repository sanitization test pattern |
| Adapt as pattern (no import) | `ocr_windows.ps1` WinRT bootstrap → long-lived worker; M1 `ui.py` Tk layout patterns; M1 run-dir + manifest conventions; `run_m1_tests.py` runner |
| Must NOT reuse | `screen2xyz_lab/parser.py` (label-driven LAT/LON/ELEV; private `_canonical_decimal`/`_NUMBER_RE` — M2 gets a **public generic parser**); `screen2xyz_lab/temporal.py` (labelled-triplet classifier); M1 `session.py` approval model (M2 is a recorder); M1 `intake.py` (file-based) |
| New design | capture worker + protocol; scheduler; stability/change detection; journal; source config; picker/preview; state machine; recovery |

The earlier "~70% reusable" claim is retired; the honest statement is:
**evidence/export utilities and conventions reuse cleanly (~15% of the new
surface); the live core is new.**

## 2. Component diagram

```
┌────────────────────────── python (screen2xyz_m2, Tk UI, PMv2) ─────────────────────────┐
│ state machine: IDLE→TARGET_SELECTED→REGIONS_CONFIGURED→ARMED                           │
│                →RECORDING↔PAUSED→STOPPING→FINALIZED                                    │
│                                                                                        │
│  target_picker   region_editor    preview_gate     live_view (grid + history + diag)   │
│        │               │               │                       ▲                       │
│        └───────────────┴───────┬───────┘                       │ queue + after()       │
│                                ▼                               │                       │
│  scheduler (monotonic deadlines, no overlap) ── worker_client (thread; JSON lines) ────┤
│                                │                               │                       │
│  stability engine → journal (events.jsonl, checkpoint, crops) ─┘                       │
└────────────────────────────────│───────────────────────────────────────────────────────┘
                                 │ stdin/stdout (UTF-8 JSON lines), stderr = diagnostics
                                 ▼
┌────────── capture+OCR worker: powershell.exe -NoProfile -NonInteractive (child) ───────┐
│ Add-Type C#: GetClientRect/ClientToScreen/PrintWindow/IsIconic/GetDpiForWindow/        │
│              GetCursorPos/ScreenToClient  +  System.Drawing frame/crop                 │
│ WinRT: OcrEngine (created once)                                                        │
│ lifecycle: stdin-close ⇒ exit; parent Process.WaitForExit watch; CREATE_NO_WINDOW      │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

One tick data flow: scheduler fires → one worker CAPTURE request (scope,
regions, per-region previous pixel hash) → worker captures **one frame** in
memory → derives and hashes every crop → OCRs changed hashes → automatically
returns bounded PNG bytes for every changed hash from that same frame
(unchanged hashes never resend bytes) → Python parses and updates the live
grid → the bounded candidate-evidence buffer and retention engine decide →
required crops are atomically written and hashed → one journal line is
appended/flushed → a due checkpoint follows → next deadline. There is no
`want_crops` flag and no second evidence capture.

## 3. Worker technology decision (evidence-based)

| Option | Verdict | Evidence & reasoning |
|---|---|---|
| **A. One long-lived PowerShell 5.1 (Add-Type C#) capture+OCR worker — SELECTED** | ✅ | S2: READY in 280 ms, 17 ms round-trips, and no measured .NET heap growth over 60 requests; S4: full 3-source tick 23.6 ms in one process. Capture+OCR in one process ⇒ frame synchronization by construction and no cross-process pixel shipping per tick. PrintWindow is documented-blocking with no timeout (research C4) — an out-of-process call site is the clean kill boundary. Zero new toolchain; the WinRT bootstrap is measured on the current machine. |
| B. Compiled C#/.NET helper exe | Rejected for MVP; **fallback + future WGC host** | Same runtime behavior as A but adds a compile/distribute step and a second artifact to version. Becomes attractive if PS 5.1 fragility appears (encoding, Add-Type quirks) or when Windows.Graphics.Capture (D3D interop) is adopted — WGC is not reachable from PS 5.1/stdlib practically (research C5). |
| C. Python ctypes capture in-process + separate OCR worker | Rejected | Puts the unboundable PrintWindow call inside the UI process (a hung target stalls a Python thread that cannot be killed); ships every frame's crops across a pipe each tick; two protocols instead of one. No measured advantage: capture is 3.7 ms in-worker. |
| D. Split capture worker + OCR worker | Rejected | Two lifecycles/protocols and cross-process frame hand-off with no benefit at measured loads; justified only if OCR ever needs independent scaling — not the case at 5 ms/crop. |

Fallback strategy: if M2-001 (S7) shows the PS worker cannot capture the
real target with either backend, escalate to Option B hosting
Windows.Graphics.Capture (documented Win32 interop path, 1903+), keeping
the same JSON protocol so the Python side is unchanged.

## 4. Capture-backend policy (conditional, per session)

1. **Provisional primary candidate:
   `PrintWindow(hwnd, dc, PW_CLIENTONLY)`** — the only documented flag used.
   It produced clean client-area capture in 14–15 ms and happened to keep
   the synthetic GDI/Tk content visible under the S3 occluder. That measured
   result is target/environment-specific and is not a general occlusion
   guarantee.
2. **Fallback: `Graphics.CopyFromScreen`** of the client rect
   (`ClientToScreen(0,0)` + `GetClientRect`) — documented visible-pixels
   semantics; captures occluders (S3-verified), so when this backend is
   locked the UI shows a persistent "keep the target window visible and
   uncovered" notice and occlusion becomes a user-managed limitation.
3. **Backend selection and blank handling.** `REGION_SNAPSHOT` may show a
   provisional comparison, but only explicit `PREVIEW` plus `ARM` locks a
   backend in `session.json`. The frame/crop heuristic and thresholds are
   the data-contract §0 values. A near-uniform **whole client frame** while
   the target is healthy offers a user-triggered fallback comparison. That
   click runs a fresh countdown and one separate setup operation with the
   alternate backend; both results are shown, and there is no automatic
   dual capture. The warning heuristic is not proof of protected content.
   Crop-level pixel warnings are diagnostic only. `ocr_status=EMPTY_TEXT`
   derives `MISSING_SOURCE_VALUE` and never means backend failure, never
   switches backend, and never alone pauses. During recording, only five
   consecutive near-uniform whole frames while the target remains healthy
   auto-pause with `pause_reason=BACKEND_BLANK_STREAK`, offering
   [Try fallback backend] / [Resume]; the backend is never switched
   silently mid-session. Until S7 records a target-specific occlusion trial,
   the "keep the target window visible" notice applies to both backends.
4. **Prohibited:** `PW_RENDERFULLCONTENT` (undocumented — research C4) is
   never load-bearing in production or the owner gate;
   Desktop Duplication (no per-window scope); WGC in MVP (D3D interop cost)
   — WGC is the designed-in future backend behind the same worker protocol.
5. Per-backend documented limitations (occlusion, minimized, protected
   content via `WDA_EXCLUDEFROMCAPTURE`, hw-accelerated windows, RDP) are
   catalogued in research §1 and surfaced in the risk register; minimized
   targets are always pre-checked with `IsIconic` → `TARGET_MINIMIZED`
   (never trusting undocumented PrintWindow-on-minimized output).

## 5. Scope and coordinate model

MVP: exactly **one target window** (HWND+PID), regions in **client-area
coordinates**; monitor scope (monitor-relative regions, CopyFromScreen) as
the explicit fallback profile. Multi-window/multi-monitor source sets:
unsupported in MVP (spec §4). Per tick the worker re-derives the client
origin via `ClientToScreen` — window movement needs no user action. Defined
behaviors: resized → pause + re-preview; minimized (`IsIconic`) →
`capture_status=TARGET_MINIMIZED` observations, auto-pause after 5
consecutive; identity-invalid/closed → immediate
`pause_reason=TARGET_UNAVAILABLE` + explicit re-resolve;
environment change →
pause + preview gate, with **client-size change (returned every tick) as
the primary trigger**, supplemented by the polled `GetDpiForWindow` value
and `WM_DISPLAYCHANGE` on the hidden watcher window — noting that a
DPI-unaware target reports 96 regardless of monitor scale (research D2),
so the target's awareness context is recorded in the environment snapshot
and the DPI signal is advisory for such targets. **Both processes are
PMv2:** the UI sets it before any HWND (S5-verified; research D1), and the
worker sets it in its bootstrap before any window/DC call and reports it
in the INIT reply (all coordinate-bearing calls execute in the worker).

## 6. Scheduler

Monotonic next-deadline loop (`time.monotonic`): `deadline += interval`
until in the future. **Single-outstanding-request invariant:** at most one
worker request—and therefore at most one capture-class operation—is ever
in flight. A deadline that arrives while a request is
outstanding (or while the worker is restarting) is **skipped** and counted
in `skipped_ticks_since_last` and diagnostics, never queued. Tk `after()`
drives UI wake-ups but deadlines come from monotonic arithmetic (Tk timers
have no accuracy guarantee — research P4). Worker calls run on a dedicated
thread; results return to Tk via queue + `after`-polling; **Python's
monotonic clock is the sole authority for `monotonic_offset_ms`** (the
worker reports only durations).

Timeout recovery has one teardown order. For a scheduled `CAPTURE` after a
successful `RECORD_START`, on the first request timeout:

1. Mark the request terminal; publish the current tick as
   `worker_status=REQUEST_TIMEOUT` / `value_status=CAPTURE_FAILURE` with no
   prior-value reuse, increment the consecutive failure streak, and prohibit
   new sends. If the failure count is 3 or greater, set the logical state to PAUSED
   before choosing the replacement's restored state.
2. Invalidate the `worker_generation`; all queued/late messages from it are
   discarded even if their request ID matches.
3. Terminate, then force-kill if needed, and `wait`/reap the old PID before
   any replacement spawn. A documented-blocking PrintWindow call is never
   left alive.
4. Drain only already-buffered diagnostics without blocking; close stdin,
   stdout and stderr; signal and join both reader threads.
5. Apply the §0 backoff, start a fresh generation, complete `INIT`, and only
   then permit another request. Failures one and two restore the still-visible
   RECORDING session; failure three and every later failure use the saturated
   5 s delay, restore PAUSED, and require explicit Resume. The counter remains
   at 3 or higher across Resume; another failure re-pauses immediately, while
   the first successful CAPTURE resets it to zero. No request can reach the old
   process or overlap the new one.

The recording failure streak includes timeouts, malformed/oversized protocol
lines, unexpected process exits and capture backend failures after recording
consent; only a successful `CAPTURE` resets it. Every recording failure at
count 3 or higher auto-pauses with `WORKER_FAILURE_STREAK`. HEALTH has its own 1 s timeout and runs only
between requests; it cannot rescue a blocked capture. A replacement INIT
restores the same logical RECORDING/PAUSED state only within the still-running
UI process and same session/configuration revision, as data contracts §10
specifies; a relaunched UI never auto-restores RECORDING.

Whenever the current UI state is `TARGET_SELECTED`, `REGIONS_CONFIGURED`, or
`ARMED`—including a post-recording DISARM/re-preview repair—the same invalidate
→ terminate/force-kill and reap → drain buffered diagnostics → close all three
pipes → signal/join readers order applies, but no failed setup-state operation
creates a journal tick or enters `PAUSED`. A separate setup counter leaves that
setup state unchanged. Failures 1-2
continue through backoff → fresh generation → INIT automatically. At count 3
or greater no replacement is spawned: the orthogonal UI interlock
`setup_worker_blocked=true` reports `worker_status=UNAVAILABLE` and overrides
every worker-dependent legal action. **Retry worker** waits any remainder of
the saturated 5 s delay measured from teardown, spawns a fresh generation, and
sends only INIT; it never reissues the failed command. Successful INIT clears
the interlock but not the counter, which resets only when the next post-INIT
setup/state request succeeds. Failed Retry INIT increments the counter and
remains blocked. The first successful `RECORD_START` in a live run initializes
the separate recording counter at zero. That recording counter is preserved
across PAUSED → DISARM → setup repair → ARM → RECORD_START; re-arm/re-start does
not reset it, and the next successful CAPTURE remains its only reset.

Pause and Stop intents never overlap an outstanding request. The UI latches the
intent, stops scheduling deadlines, and waits for the matching response or its
normal timeout teardown. Pause then sends `PAUSE`; Stop enters STOPPING and
sends `STOP`, `SHUTDOWN`, waits at most 2 s, then kills/reaps. Emergency Stop
does not wait for the outstanding request: it invalidates the generation,
kills/reaps immediately, and remains within the 2 s hard bound.
If `PAUSE` itself times out, the latched safety intent wins: UI state becomes
PAUSED before teardown and replacement INIT restores PAUSED. If `RESUME` times
out, UI state remains PAUSED and another explicit Resume is required. Both
increment the recording failure counter. STOP/SHUTDOWN, UI close, and Emergency
Stop are terminal paths: neither counter nor backoff can start a replacement.

## 7. Worker protocol (JSON lines, UTF-8, stdout=protocol / stderr=diagnostics)

Python owns the closed UI state. The worker owns the distinct `worker_mode` and
validates the `ui_session_state` plus `configuration_revision` request envelope
defined by data contracts §10. Local edits increment the revision; a setup
request synchronizes it and resets the worker to SETUP. PREVIEW success enters
PREVIEWED for that revision, and ARM fails unless the revision still matches.
Commands:

- `INIT` (protocol_version, session_id, configuration_revision,
  restore_session_state, scope, backend policy, OCR language,
  cursor-metadata flag) → capabilities reply that echoes restored state and
  mapped worker mode
  (protocol_version, max_image_dimension, available_languages,
  backends {printwindow_clientonly, copyfromscreen}, protocol size limits,
  **dpi_awareness** —
  the worker bootstrap calls `SetProcessDpiAwarenessContext(PMv2)` via
  P/Invoke **before any window/DC use** and reports the effective context;
  a non-PMv2 or limit mismatch is a startup failure.
- `REGION_SNAPSHOT` — explicit-click one-frame full-client PNG for the
  region canvas, legal only in TARGET_SELECTED or REGIONS_CONFIGURED.
- `PREVIEW` — distinct explicit-click one-frame capture carrying the complete
  bounded configuration, configured crops
  and OCR, legal only in REGIONS_CONFIGURED before ARM. The UI performs the
  visible 3–5 s countdown and sends exactly one request at its end. Both
  setup operations are displayed in memory only, never persisted or
  journaled, and never start a timer/loop.
- `ARM` / `DISARM` — enter/leave the armed state at an exact configuration
  revision (session.json backend lock recorded at ARM).
- `RECORD_START` / `PAUSE` / `RESUME` — recording-state transitions;
  `CAPTURE` is **rejected unless recording**; both setup operations are
  rejected after ARM. A pause requiring region/environment repair first
  uses DISARM → REGIONS_CONFIGURED → PREVIEW → ARM → RECORD_START.
- `HEALTH` (1 s timeout, used only between requests); `STOP` (end
  session, keep process); `SHUTDOWN`.
- `CAPTURE` (request_id, worker_generation, configuration_revision, frame_seq,
  regions[{source_id, rect, prev_pixel_sha256}]) → one response with the
  same request/generation/revision plus worker mode, one frame,
  window/cursor/timing fields, distinct
  `capture_status`/`frame_content_status`, and per-source
  `{capture_status,crop_content_status,ocr_status,pixel_sha256,crop_w,
  crop_h,ocr_executed,confirmation,raw_text,raw_truncated,
  raw_original_utf8_bytes,warning_codes,ocr_ms,crop_png_b64?}`. Python adds
  parse/stability/value/event fields; the exact enums and mappings are data
  contracts §0/§5.

Rules: one response per request ID/generation/revision, with the expected
worker mode; a bounded streaming reader
rejects a line over 96 MiB before unbounded allocation. Malformed or
oversized stdout ⇒ fail closed and the §6 teardown/restart; stale responses
discarded;
timeouts never reuse prior values; worker exits on stdin close
(S6-verified, <1 s) and additionally watches the parent via
`Process.GetProcessById(parentPid)` captured **once at startup** then
`WaitForExit` (avoids the documented PID-reuse race — research P5); Python
launches the worker with `CREATE_NO_WINDOW` and, as hardening, assigns it
to a kill-on-close Job object via ctypes (unjobbed-window race accepted and
documented).

Crop/evidence ownership follows data contracts §6b. The worker always ships
bounded `crop_png_b64` from the same CAPTURE frame for every changed
`pixel_sha256`; unchanged sources never ship duplicate bytes. Python buffers
the first candidate's complete evidence bundle—not only the PNG—under the
§0 PNG-payload, canonical-metadata, and total-accounting caps. Replacement, rejection, timeout,
pause/stop and overflow behavior is deterministic. A future T-M2L-009 must
prove a confirmations=2 retained event is self-contained (raw/truncation,
parse result, evidence frame, pixel hash and crop) without a second capture.

## 8. Stability engine (three tiers)

- **Provisional observation** — every tick, per source: causal fields,
  parsed value and `stability_status`; drives the live grid and diagnostics; no disk (except
  every-tick diagnostic mode).
- **Stable state** — per source, after policy: default
  `stability_confirmations=1` (a changed normalized value is stable
  immediately — fast continuous changes are the primary workflow and are
  never suppressed by default); optional ≥2 confirmations (value must
  repeat in consecutive frames), optional numeric `min_change_threshold`
  (deltas below threshold don't count as change), optional debounce-ms —
  all settable per session and overridable per source. Held in memory;
  checkpointed every 15 s only after the journal state it reflects.
- **Retained event** — the exact precedence is data contracts §6a:
  retained error transition, then stable-signature change/error recovery,
  then diagnostic. Missing hover values and rejected unstable candidates
  do not retain outside diagnostic mode. Required evidence follows §6b and
  the crop→final-artifact-hash→journal→checkpoint order in §6c.

Trade-off (documented for the owner, OD-M2-4): confirmations=1 retains
single-tick OCR flicker as real events (auditable — causal fields and crops let a
reviewer discard them); confirmations=2 suppresses flicker but halves the
effective sample rate of continuously changing values and can miss readings
the user paused on for <2 ticks. Default: 1 (fast mode), because the
workflow is continuous mouse movement and false events are auditable while
missed readings are unrecoverable.

`value_status=UNSTABLE_READING` with `stability_status=REJECTED` is shown
when confirmations≥2 is configured and a candidate fails to repeat; the
provisional parsed value remains visible and is diagnostic-only.

## 9. Journal, storage, recovery

Canonical: `events.jsonl` (schema in data contracts §6). For every event,
required crops are atomically written/flushed, final PNG bytes are hashed,
the referencing JSON line is appended/flushed/durably synced, and only then
may a due checkpoint be atomically replaced. `session.json` is written at
ARMED; `state_checkpoint.json` is advisory;
`errors.log` for worker stderr excerpts; crops at
`crops/<event_seq>/<source_id>.png`. Finalize (STOPPING→FINALIZED): wide
CSV, long CSV, `run_summary.json`, conditional `points.xyz`, then
`evidence_manifest_sha256.txt` via `write_manifest`. Recovery:
`python -m screen2xyz_m2 recover <run_dir>` re-derives finalization from
the canonical valid journal, ignoring only an unterminated final line with
a warning. Missing/hash-mismatched crops become null in the recovered view;
checkpoint divergence and orphan crops are reported; malformed complete
lines fail closed. The journal is never rewritten. Storage failure is a
critical non-durable UI state and only best-effort journal evidence—never a
guaranteed retained error. Retention modes and disk limits per spec
M2-FR-062/063; full frames are never written to disk in any mode.

## 10. UI state machine

States and legal actions are specified in the
[UX document](../ux/M2_LIVE_USER_FLOW_AND_WIREFRAMES.md) §3 (single source
of truth for the state/action table). The capture worker enforces the
server side via the explicit `ARM`/`DISARM`/`RECORD_START`/`PAUSE`/`RESUME`
protocol verbs (§7): `CAPTURE` is rejected unless recording;
`REGION_SNAPSHOT` and `PREVIEW` are distinct one-shot explicit-click
operations accepted only in their pre-ARM configuration states.
The always-on-top mini controller is a normal UI component, not a capture
overlay: before RECORD_START its placement algorithm rejects intersection
with configured regions (or requires explicit user relocation) so
CopyFromScreen cannot capture Screen2XYZ's own controls. It exposes
REC/PAUSED, elapsed time, Pause/Resume, Stop, and the ≤2 s emergency path.

## 11. Privacy model

Consent = explicit target selection + preview confirmation + Start. Visible
recording state at all times; Esc/Stop/UI-close all end capture (worker dies
with the UI — S6). No autostart, no service, no keylogging, no cursor
control (cursor *position reading* is a per-session opt-in metadata field,
default OFF per M2-FR-067), no network (future M2 tests must enforce this),
no full-frame persistence,
outputs only under ignored `.lab_work/m2_runs/`. Threats and mitigations:
[privacy & threat review](../guardrails/M2_LIVE_PRIVACY_AND_THREAT_REVIEW.md).
Any future S7 or manual real-target trial is additionally blocked on the
recorded data-use/capture-permission gate and must show only authorized,
non-confidential demonstration content; unknown rights or capture
protections stop the trial.
