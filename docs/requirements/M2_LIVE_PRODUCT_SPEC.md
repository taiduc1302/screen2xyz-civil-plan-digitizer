# M2-Live Product Specification — Live Screen-Region Watcher

Status: M2-000 planning baseline. Supersedes the preliminary M2 sketch that
previously lived in `docs/control/NEXT_ACTION.md`. Cross-references:
[architecture](../architecture/M2_LIVE_ARCHITECTURE.md),
[data contracts](M2_LIVE_DATA_CONTRACTS.md),
[UX flow](../ux/M2_LIVE_USER_FLOW_AND_WIREFRAMES.md),
[test plan](../testing/M2_LIVE_TEST_AND_ACCEPTANCE_PLAN.md).

## 1. Owner workflow (authoritative)

The user has another application open whose fixed screen fields (e.g.
longitude / latitude / elevation, X/Y/Z, station, status — numeric or
textual, possibly unlabelled) change as the user moves the mouse in that
application. Screen2XYZ must: let the user pick the capture scope
(preferably one target window), define three or more named sources with a
data type and optional X/Y/Z role, draw a rectangle for each, preview and
confirm alignment, press Start; then capture ~once per second, OCR the
regions, show the latest values in a live table, add history events only
for stable value changes and the configured retainable error/recovery cases,
save only the crops needed to audit retained
events, support Pause/Stop, and produce a recoverable journal plus CSV/JSON
exports and a strictly-gated XYZ export. Screen2XYZ never controls the
mouse; it only observes.

M1 (file-based review lab) remains a separate supported mode.

## 2. Functional requirements

Each FR has acceptance criteria (AC). Test mapping lives in the
[test plan](../testing/M2_LIVE_TEST_AND_ACCEPTANCE_PLAN.md) traceability table.

### Scope and target

- **M2-FR-001 Capture-scope selection.** The user selects exactly one
  target window from a live list (title + process name + HWND) or, as
  fallback, one monitor. AC: no capture is possible before a scope is
  selected; the chosen scope is displayed at all times afterwards.
- **M2-FR-002 Window binding.** A window target is bound by HWND+PID with
  its title recorded. AC: if the HWND dies, recording pauses with
  `pause_reason=TARGET_UNAVAILABLE`; observations use
  `capture_status=TARGET_UNAVAILABLE`; a re-resolve prompt lists candidate windows and
  requires explicit user confirmation; same-title windows are never
  auto-selected.
- **M2-FR-003 Monitor fallback.** Monitor scope uses monitor-relative
  regions and `CopyFromScreen`; the UI states that occluding windows will
  be captured. AC: scope type is recorded in the session config.

### Sources

- **M2-FR-010 Dynamic source count.** 1–8 sources; add/edit/remove/reorder
  before preview confirmation. AC: 3+ sources demonstrably work end-to-end;
  the 8-source cap is validated with a clear message.
- **M2-FR-011 Naming.** Each source has a unique non-empty display name.
  AC: duplicate names are rejected at entry with a visible error.
- **M2-FR-012 Data type.** Each source is `number`, `text`, or `auto`.
  AC: parsing behavior follows §5 of the data contracts per type. `auto`
  sources cannot be assigned an X/Y/Z role (their kind may flip per
  observation; XYZ requires a fixed numeric source).
- **M2-FR-013 Semantic role.** Optional role `x`|`y`|`z`|`metadata`|`none`
  (default `none`). AC: at most one enabled source per x/y/z; a second
  assignment prompts to move or cancel; roles never required for recording.
- **M2-FR-014 Region selection.** Rectangles are drawn on a frozen
  **snapshot frame** of the target (not a live overlay), in client-area
  coordinates for window scope. A snapshot is a single frame captured by
  the worker's `REGION_SNAPSHOT` command on an explicit user click, with a
  configurable **capture countdown (default 3 s, range 3–5 s)** so the
  user can return the pointer to the target application first — required for
  targets whose value fields only populate under hover/focus. Snapshot
  frames are displayed only, never journaled or persisted. Whole-frame
  pixel-health diagnostics may compare provisional backends (per
  M2-FR-032) and show which backend produced the image; crop OCR emptiness
  never selects a backend. AC: a rectangle fully inside the
  client area is accepted; degenerate (<8×8 px), oversized (>2000×800 px),
  or out-of-bounds rectangles are rejected; the countdown demonstrably
  allows hover-populated fields to appear in the snapshot.
- **M2-FR-015 Config save/load.** Source sets save to a named JSON profile
  including the environment snapshot (window identity, client size, DPI,
  monitor topology, backend) under the ignored profile root using a
  generated path-safe ID and bounded display metadata. AC: traversal and
  oversized profiles are rejected; loading on a mismatched environment
  forces the preview gate and shows what changed; recording cannot start
  silently (M2-FR-031).

### Preview gate

- **M2-FR-030 Mandatory preview.** Before arming: one synchronized
  `PREVIEW` operation (explicit user click, same countdown mechanism as
  M2-FR-014); per-source crop image, dimensions, coordinates, and OCR
  preview text displayed. Because hover-dependent targets may legitimately
  show empty fields when the countdown was not used, the gate shows
  per-crop OCR results without blocking on emptiness — the user judges
  alignment. It is a distinct one-frame worker operation legal only in
  REGIONS_CONFIGURED; it never starts a loop or persists the frame. AC: the
  Start control stays disabled until the user confirms the preview;
  confirming it sends `ARM` and enters ARMED directly, with no intermediate
  session state.
- **M2-FR-031 Environment mismatch.** If the target/topology/DPI/client
  size differs from the config snapshot, recording must not start silently.
  AC: mismatch dialog shows old vs new values and requires re-preview.
- **M2-FR-032 Backend verification.** `printwindow_clientonly` is the
  provisional primary candidate based only on the synthetic GDI spike.
  `PREVIEW` evaluates capture API success and the whole-client
  `frame_content_status`; a near-uniform whole frame offers **Compare
  fallback**. If the user accepts, a new visible countdown precedes one
  separate one-frame `PREVIEW` using the alternate backend; there is no
  automatic second capture. Both results are shown. Per-crop pixel warnings and empty OCR are shown but
  never cause a backend switch. The user confirms the displayed backend,
  which is locked at `ARM` with its reason. `copyfromscreen` is a
  visible-pixels fallback; S7 determines support for the tested target and
  environment only. WGC via a C# helper remains the architecture fallback
  if neither MVP backend is acceptable. AC: `session.json` records the lock
  and no wording claims general PrintWindow occlusion immunity.

### Recording

- **M2-FR-040 Explicit operations and start.** **Periodic live** capture occurs only in the
  RECORDING state, entered by pressing Start after the preview gate. The
  only capture operations outside RECORDING are `REGION_SNAPSHOT` during
  target/region setup and `PREVIEW` while REGIONS_CONFIGURED. Each follows
  an explicit click and countdown, captures exactly one frame, performs no
  repeat, and is never journaled or persisted. `ARM` confirms configuration;
  UI Start sends `RECORD_START`; `PAUSE`, `RESUME`, `STOP`, `DISARM`, and
  `SHUTDOWN` have the legal states in the UX table. AC: the worker rejects
  the wrong operation/state combination and `CAPTURE` unless RECORDING.
  Every post-INIT request carries the authoritative UI state and configuration
  revision; PREVIEW synchronizes the complete configuration, and ARM fails if
  that preview revision is stale. Whenever the UI is `TARGET_SELECTED`,
  `REGIONS_CONFIGURED`, or `ARMED`, including same-run post-pause repair, three
  consecutive setup/request infrastructure failures never create a PAUSED
  recording state: the current setup state remains visible and the
  orthogonal `setup_worker_blocked` interlock disables every worker-dependent
  action, including snapshot, preview, ARM, DISARM, Start, and HEALTH, with
  `worker_status=UNAVAILABLE`. No replacement exists until explicit **Retry
  worker** waits any remaining saturated backoff, starts a fresh generation,
  and sends INIT only. Successful INIT re-enables the actions without resetting
  the setup counter; the next successful post-INIT setup/state request resets
  it. The first successful `RECORD_START` in a run initializes the separate
  recording failure counter; same-run re-arm/re-start preserves it until a
  successful CAPTURE.
- **M2-FR-041 Cadence.** Default 1000 ms interval (configurable 250–10000
  ms), monotonic next-deadline scheduling, no overlapping ticks (single
  outstanding capture-class request). Busy/blocked deadlines are skipped
  and counted in
  the journal's `skipped_ticks_since_last` and diagnostics. AC: with an
  artificially slowed worker, deadline N+1 is skipped, the skip counter
  increments, and no queue accumulates. The first timeout resolves the tick
  as failure, invalidates and kills/reaps that worker generation, drains and
  closes pipes, joins readers, discards late responses, applies the restart
  policy, and only then permits a request to a fresh initialized worker.
  Replacement INIT may restore RECORDING only for the same in-memory live UI
  session/revision that already received explicit Start; app relaunch/recovery
  never auto-records.
- **M2-FR-042 Synchronized observation.** All sources in a tick come from
  **one capture call producing one frame**; crops are derived in worker
  memory from that frame. AC: event records show one frame_id across all
  source observations, and the worker-contract tests assert exactly one
  capture invocation (single `capture_ms` timing) per CAPTURE request —
  label-equality alone is insufficient.
- **M2-FR-043 Live table.** The current-values grid updates **every tick**
  (provisional values), including ticks that retain nothing. AC: with
  constant values, the grid still refreshes (tick counter advances) while
  history stays unchanged.
- **M2-FR-044 Deterministic history retention.** Apply the data-contract
  §6a precedence: retainable error transition first, stable-signature
  change or error recovery second, diagnostic mode third, otherwise no
  event. `MISSING_SOURCE_VALUE` and `UNSTABLE_READING` are live/diagnostic
  only; repeated identical errors retain once. Each source's first stable OK
  value seeds a non-change baseline independently. AC: constant input for 60 s
  yields 0 change events after baseline seeding; pending/error sources never
  appear as map deletion; one later value change yields exactly 1; OK→empty OCR
  yields none; one error transition and its recovery each retain once.
- **M2-FR-045 Pause/Resume/Stop.** Pause suspends capture (worker idle,
  REC indicator changes); Resume re-enters RECORDING; Stop finalizes. AC:
  Pause/Stop latch while a request is in flight, schedule no new tick, and
  send no overlapping command; they act after that response or its timeout
  teardown. No frame is captured while PAUSED; Stop always produces a finalized
  session even mid-tick. If a resize/DPI/topology change requires preview,
  PAUSED first sends DISARM and returns to REGIONS_CONFIGURED; explicit
  PREVIEW→ARM→RECORD_START resumes the same journal with an incremented
  configuration revision.
  A `PAUSE` command timeout resolves to PAUSED before worker replacement; a
  `RESUME` timeout remains PAUSED and requires another explicit Resume. Stop,
  shutdown, UI close, and emergency paths never trigger a replacement restart.
- **M2-FR-046 Visible recording state.** While RECORDING: REC indicator,
  target identity, elapsed time, actual rate, last tick duration, skipped
  ticks, OCR error count, changed-event count, disk usage. AC: all elements
  present in the recording screen per the UX spec.
- **M2-FR-047 Mini controller and emergency stop.** While
  RECORDING/PAUSED a movable **always-on-top mini controller** shows clear
  REC/PAUSED state, elapsed time, Pause/Resume, normal Stop, and an
  unambiguous emergency Stop. It chooses a screen position that does not
  intersect the union of configured regions; if no free corner exists it
  warns and requires the user to place it before recording. This prevents
  self-capture under `copyfromscreen`. It stays usable when the target
  covers the main window. Esc (when either Screen2XYZ window has focus),
  emergency Stop, and UI close stop capture within 2000 ms independent of
  the interval; an overdue worker is killed immediately. AC: no worker
  survives UI exit; MA-4 exercises every backend accepted and authorized after
  S7, target-over-main-window,
  placement, Pause/Resume, Stop, and emergency Stop.
  (`RegisterHotKey` global stop is a deferred option — it is not a
  keyboard hook — recorded, not implemented, in MVP.)

### Observation, parsing, stability

- **M2-FR-050 Raw preservation.** Raw OCR text per source per executed OCR
  is preserved verbatim up to the authoritative 4096 UTF-8-byte bound.
  Longer text retains the longest complete-code-point prefix and records
  `raw_truncated:true`, `raw_original_utf8_bytes`, and
  `RAW_OCR_TRUNCATED`; it is not parsed as complete input and never silently
  creates a value. AC: exact-boundary, multibyte-boundary and oversized
  cases; retained stabilized events carry a self-contained evidence raw.
- **M2-FR-051 Generic parsing.** Number/text/auto parsing per the data
  contracts §0/§5, using distinct `capture_status`, `ocr_status`,
  `parse_status`, `stability_status`, and `value_status` fields. Sign
  handling is closed: ASCII `+`/`-`; the enumerated Unicode minus/hyphen
  variants (including U+2212, en dash, and U+2011 non-breaking hyphen) are
  normalized only when directly adjacent to the first digit and record the
  original code point. Whitespace-separated signs and every other adjacent
  Unicode-category-`Pd` or Unicode-name-`MINUS`/`PLUS` sign-like glyph follow
  the closed rejection algorithm in data contracts §5: `MALFORMED_NUMBER`,
  never silently dropped. Station
  notation (`0+250.00`) and space-grouped numbers are **unsupported as
  numeric in MVP** (they parse as AMBIGUOUS_MULTIPLE_NUMBERS; use text
  type; a per-source pattern is a documented deferred feature). AC: unit
  tests cover ASCII negative/plus, Unicode minus, en dash, non-breaking
  hyphen, unrecognized dash, separated sign, and a BC-style negative
  longitude; multiple plausible numbers are never silently resolved.
- **M2-FR-052 Observation tiers.** Three tiers with distinct artifacts:
  *provisional* (every tick; UI + diagnostics only, no disk except
  diagnostic mode), *stable state* (after stability policy; memory +
  periodic checkpoint), *retained event* (stable signature changed or retained
  error; journal append + crops). AC: artifact matrix in data contracts §7
  is enforced by tests.
- **M2-FR-053 Stability policy.** Default `stability_confirmations = 1`
  (every changed normalized tuple retains immediately — continuous mouse
  movement is the primary use case and is never suppressed by default).
  Optional per-session and per-source: confirmations ≥2, numeric
  `min_change_threshold`, debounce. AC: with confirmations=1 a value
  changing every tick yields one event per tick; with confirmations=2 a
  single-tick OCR flicker yields no event. Stabilized mode follows the
  bounded first-candidate evidence ownership and eviction rules in data
  contracts §6b; buffer overflow pauses instead of silently losing evidence.
- **M2-FR-054 OCR-skip contract.** If a source crop's pixel hash equals the
  previous tick's, OCR may be skipped; the observation is recorded with
  `ocr_executed=false, confirmation="pixel_hash_cached"`. A cached
  confirmation never masquerades as new OCR, and OCR failure/timeout never
  reuses a prior value. A retained cached confirmation embeds the earlier
  candidate raw/crop evidence and its `evidence_frame_id`; no second capture
  retrieves evidence. AC: contract, bounds, replacement/rejection/timeout,
  and self-contained retained-event fields asserted in worker/unit tests.

### Storage, recovery, exports

- **M2-FR-060 Canonical journal.** Append-only `events.jsonl`, flushed per
  event after crops are atomically written and their final artifact bytes
  hashed; a due checkpoint follows the journal. Recovery treats the journal
  as canonical, tolerates only a partial final line, warns/nulls missing or
  hash-mismatched crop references, reports checkpoint divergence and orphan
  crops, and never crashes for one missing crop. AC: every ordering and
  recovery branch in data contracts §6c is exercised.
- **M2-FR-061 Run package.** `session.json` (config+environment snapshot),
  `events.jsonl`, periodic `state_checkpoint.json`, `errors.log`, crops
  under `crops/`, finalization adds wide CSV, long CSV, `run_summary.json`,
  optional XYZ, and a SHA-256 manifest. All under ignored
  `.lab_work/m2_runs/<run_id>/`. AC: manifest verifies; no tracked outputs.
- **M2-FR-062 Crop retention modes.** `changed_and_errors` (default),
  `changed_only`, `every_tick_diagnostic`, `values_only`, with eligibility
  and crop semantics exactly as data contracts §6a. AC: errors/recoveries and
  stable changes follow each mode's closed precedence; `values_only` writes no
  PNGs; diagnostic unchanged crops reference an earlier same-hash artifact
  without duplicate bytes or a second capture; full frames are never persisted
  in any mode.
- **M2-FR-063 Storage limits.** Disk-usage indicator; configurable warning
  (default 200 MiB) and hard cap (default 500 MiB) per session; hitting the
  cap pauses and attempts a retained error only if the journal is writable.
  Crop/journal failure always produces a critical non-durable UI warning
  and pauses; it never falsely guarantees durable error evidence. AC:
  simulated-full-disk and journal-unwritable tests.
- **M2-FR-064 Recovery command.** `recover <run_dir>` rebuilds exports and
  summary from the journal of an unfinalized run. AC: CSV and XYZ outputs
  and XYZ metadata are byte-equal to those of an equivalent direct finalization
  from the same canonical journal and session configuration;
  `run_summary.json` counters are re-derived from the journal; the checkpoint
  is cross-check input only and never overrides it. The summary is flagged
  `recovered: true`, and its explicitly best-effort per-tick timing fields may
  differ because non-retained ticks are not journaled; its manifest may
  therefore differ too. No byte-equality claim applies to those fields.
- **M2-FR-065 Exports.** Wide CSV (one row per retained event), long CSV
  (one row per source observation), JSON summary; formula-safe text fields;
  deterministic ordering by event sequence. AC: golden-file tests.
- **M2-FR-066 XYZ gate (filter semantics).** XYZ is offered only when
  exactly one enabled `number`-type source is assigned each of X, Y, Z
  (`auto` and `text` sources are not role-assignable). Its **rows are the
  `RETAINED_CHANGE` events whose X, Y, and Z observations all have
  `value_status=OK`, stable/confirmed numeric values**; events failing this
  are excluded and their count recorded as
  `excluded_event_count` in `points_xyz_metadata.json`. Axis order is
  shown explicitly; the coordinate reference is always recorded as
  `UNSPECIFIED_LOCAL` in MVP (a user-configurable `coordinate_reference`
  field is deferred — no such control exists yet). Finalize and `recover`
  apply the identical gate. AC: negative tests for each precondition plus
  the exclusion count.
- **M2-FR-067 Optional cursor metadata.** Per-session opt-in (default OFF,
  visible in setup): each frame records `GetCursorPos` screen coords and
  client-area coords when window-scoped. Collected only while RECORDING,
  never controls the pointer, excluded when the toggle is off. AC: toggle
  off → fields absent from journal; toggle on → present per frame.
  Rationale: links each retained event to where the user was pointing —
  direct audit value for the mouse-driven workflow — at near-zero cost.

### Diagnostics and privacy

- **M2-FR-070 Diagnostics.** Per-tick timings (capture, OCR, total), worker
  restarts, skipped ticks, frame/crop pixel-health results, and the distinct
  worker/capture/OCR/parse/stability/value fields plus last bounded raw OCR
  per source are visible in a diagnostics panel and recorded where the
  retention contract permits. Empty OCR is `MISSING_SOURCE_VALUE`; it is
  not a capture failure and never alone pauses or switches backends. AC: UX
  fields and the automatic-pause thresholds from data contracts §0.
- **M2-FR-071 Privacy/consent.** No recurring or recorded capture before
  Start; before Start the only captures are single user-triggered
  `REGION_SNAPSHOT` and `PREVIEW` operations in their legal states,
  displayed once and never persisted. S7 and later manual acceptance are
  separately blocked on recorded data-use/capture permission and may show
  only synthetic, owner-created, government-open, or appropriately licensed
  non-confidential demonstration content. No autostart, no background
  service, no keylogging, no
  cursor control, no network, no full-screen persistence, no tracked
  capture outputs; worker dies with the UI. AC: guardrails doc threats
  each map to a test or review item.

## 3. Non-functional requirements

- **M2-NFR-01 Cadence headroom:** typical tick ≤ 200 ms at 3 sources
  (measured 23.6 ms; budget table in research §7).
- **M2-NFR-02 Stdlib-only Python**, PS 5.1 + .NET Framework + WinRT OCR on
  the worker side; no third-party packages.
- **M2-NFR-03 Windows 11 current machine** is the only validated platform.
- **M2-NFR-04 Crash containment:** UI crash never leaves a worker running;
  worker crash never corrupts the journal beyond one partial line.
- **M2-NFR-05 Determinism:** given the same valid canonical journal, session
  configuration, and finalization mode, exports are byte-deterministic in
  event-sequence order. Direct-finalize/recover equality is scoped exactly by
  M2-FR-064; capture timestamps, recovered/best-effort summary fields, and the
  resulting manifest differences are outside that cross-mode claim.
- **M2-NFR-06 Baseline/M1 regression:** 42/42 + 34/34 + evidence PASS +
  sanitization PASS at every milestone.

## 4. Non-goals (MVP)

Multi-window or multi-monitor source sets; background/continuous capture
without visible recording state; real construction drawings; coordinate
transformation; named third-party application integration or presets; terrain
reconstruction; production packaging; live external-AI assistance; any
real-world accuracy claim; Windows.Graphics.Capture implementation (future
backend seam only); PW_RENDERFULLCONTENT reliance.
