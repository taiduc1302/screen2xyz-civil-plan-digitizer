# M2-Live Test and Acceptance Plan

Status: M2-000 planning. Layers: unit → worker-contract → integration →
manual acceptance (owner machine, **mandatory before M2 merge — mock tests
alone are insufficient**) → regression. Test IDs `T-M2L-*` map to FRs in
the traceability table (§7).

## 1. Unit tests (deterministic, no display, no worker)

| ID | Covers |
|---|---|
| T-M2L-001 | Region/source validation: bounds, ≥8×8, duplicate names, role exclusivity, threshold-only-for-number (M2-FR-010..014) |
| T-M2L-002 | Profile save/load + environment-snapshot mismatch detection (M2-FR-015, M2-FR-031) |
| T-M2L-003 | NUMBER parsing: ASCII negative/plus; parameterized direct acceptance of every enumerated U+2212/U+2010..2014/U+FE63/U+FF0D minus with original code point; parameterized rejection of other `Pd` and Unicode-name-`MINUS`/`PLUS` glyphs, including whitespace-separated forms, as MALFORMED_NUMBER; negative longitude stays negative; point/comma/thousands/precision/range/candidate rules; station/grouped-number ambiguity; O/0 I/1 report-only (M2-FR-051) |
| T-M2L-004 | TEXT/AUTO and raw bound: 4095/4096/4097-byte cases, multibyte-safe prefix, exact original byte length, `RAW_OCR_TRUNCATED`, no parse from discarded suffix, whitespace/control/formula safety, conservative auto resolution (M2-FR-050/051) |
| T-M2L-005 | Every §0 enum/causal mapping: distinct worker/capture/frame/crop/OCR/parse/stability/value/event/session fields; no generic `status`; empty OCR→MISSING_SOURCE_VALUE without capture failure; normalized provisional value remains visible; capture/parse failures never reuse a value (M2-FR-051/070) |
| T-M2L-006 | Stability engine: confirmations=1 fast path; =2 flicker suppression; per-source overrides; min_change_threshold; `stability_status`/UNSTABLE_READING behavior (M2-FR-053) |
| T-M2L-007 | Three-tier artifact matrix: provisional≠disk, stable→checkpoint, retained→journal+crops (M2-FR-052) |
| T-M2L-008 | Retention precedence and independent baselines: each source's first stable OK seeds without a change; mixed-source pending/error observations never delete comparator entries; a pre-baseline retained error followed by first stable OK seeds and emits one recovery, while an already-seeded source recovers without reseeding; constant none; stable change once; OK→MISSING/UNSTABLE none; error transition once; repeated error none; simultaneous error beats change; diagnostic first tick is retained only as diagnostic (M2-FR-044) |
| T-M2L-009 | Cached observation contract and bounded first-candidate evidence bundle: confirmations=2 event self-contained with raw/truncation/parse/evidence_frame/pixel-hash/crop; replacement, rejection, timeout, pause/stop and write-retry; exact §0 PNG payload, canonical-metadata, and accounted-owned-byte caps per source and aggregate; no size-pressure eviction, prior-value reuse, or second capture (M2-FR-054) |
| T-M2L-010 | Scheduler: monotonic deadlines, single outstanding request, skip-not-queue, skip counting, pause/resume, request+worker-generation+configuration-revision stale discard (M2-FR-041) |
| T-M2L-011 | Every UX legal-action cell: REGION_SNAPSHOT and PREVIEW only in exact pre-ARM states; CAPTURE only RECORDING; disarm-before-repreview; full mini-controller and ≤2 s emergency path (M2-FR-040/047) |
| T-M2L-012 | Complete run-package and crash recovery: session/journal/checkpoint/errors/crops plus finalized exports and verifying SHA-256 manifest; atomic crop→final file hash→journal flush/sync→checkpoint; pixel/artifact hashes distinct; partial final line warning; malformed complete line fail; missing/hash-mismatched crop null+warning; checkpoint divergence; orphan crop; canonical export rebuild (M2-FR-060/061/064) |
| T-M2L-013 | Retention modes ×4: exact change/error/recovery eligibility; `changed_only` suppresses errors/same-value recovery; `values_only` writes no PNG; diagnostic same-hash reference without duplicate bytes or second capture; no-prior-artifact null case; full frame never persisted (M2-FR-062) |
| T-M2L-014 | Storage limits: warn, hard-cap pause + error event, crop-write failure, journal-unwritable critical non-durable warning with no false retained-evidence claim, and retry/stop paths (M2-FR-063) |
| T-M2L-015 | Exports: wide/long CSV golden files, deterministic ordering, formula-safety; summary uses only the sanitized environment projection and excludes HWND, PID, raw title/process name, raw monitor device IDs, and absolute/user paths; direct-finalize versus recover byte equality is limited to wide/long CSV, XYZ, and XYZ metadata, while recovered summary/manifest differences are explicit (M2-FR-064/065) |
| T-M2L-016 | XYZ gate: all negative preconditions + positive case; UNSPECIFIED_LOCAL default (M2-FR-066) |
| T-M2L-017 | Cursor metadata toggle: fields present/absent (M2-FR-067) |
| T-M2L-018 | No-network / no-hidden-capture source scan of `screen2xyz_m2` (M2-FR-071) |
| T-M2L-019 | Authoritative data-contract §0 constants/status/paths/versions table matches every M2 document and executable default; profile root/ID traversal, 256 KiB file and metadata bounds (M2-FR-015) |
| T-M2L-028 | Scope-selection model/controller with stub enumeration: capture blocked before selection; exactly one HWND+PID target bound and displayed; same-title target never auto-resolved; monitor fallback requires visible occlusion warning/acknowledgement and serializes the exact scope into session config (M2-FR-001..003) |

## 2. Worker contract tests (mock worker process — a Python stub speaking the protocol)

| ID | Covers |
|---|---|
| T-M2L-020 | request_id + worker_generation + configuration_revision + worker_mode echo; one response/request; unknown/stale tuple dropped; bounded reader rejects >96 MiB before unbounded allocation; only one request can be outstanding |
| T-M2L-021 | First timeout ⇒ current tick CAPTURE_FAILURE, sends blocked, old generation invalid, late response dropped, no prior-value reuse, and no new request until fresh INIT |
| T-M2L-022 | Exact teardown: invalidate generation; kill and reap old PID; drain only buffered diagnostics; close stdin/stdout/stderr; signal/join readers; backoff 0/1/5 s with 5 s saturated for failures 3+; same-process/same-session restoration; relaunch never auto-records. Requests in TARGET/REGIONS/ARMED—including same-run repair—use a separate setup counter and never enter PAUSED: failures 1-2 spawn/INIT automatically; count ≥3 leaves no worker and sets `setup_worker_blocked`, with every worker-dependent action rejected until Retry worker waits any remaining backoff, spawns, and sends INIT only. Successful Retry INIT clears the flag but not the counter; a following successful setup/state request resets it, while failed INIT stays blocked. First RECORD_START initializes the recording counter; same-run disarm/re-arm/re-start preserves it; every recording failure count ≥3 pauses, Resume without a successful CAPTURE leaves that streak intact and the next failure re-pauses, and only successful CAPTURE resets it. |
| T-M2L-023 | stderr diagnostics captured to errors.log, never parsed as protocol |
| T-M2L-024 | INIT negotiation: protocol/schema, PMv2, backend IDs, MaxImageDimension, 8/64/64/96 MiB limits, session/revision/restored-state echo; any mismatch refused |
| T-M2L-025 | Pause/Stop intent during an in-flight request never overlaps a command; matched response or timeout teardown completes first; PAUSE-command timeout restores PAUSED, RESUME-command timeout remains PAUSED and requires explicit retry; shutdown ordering STOP→SHUTDOWN→wait→kill; STOP/SHUTDOWN/UI-close/emergency paths never back off or spawn a replacement; emergency invalidates/kills immediately; stdin close ends stub |
| T-M2L-026 | Crop protocol: changed hash automatically returns same-frame bytes; unchanged never resends; no `want_crops`/second capture; decoded/aggregate caps; unretained discard; diagnostic unchanged references prior same-hash artifact |
| T-M2L-027 | Every §10 command-legality row and setup synchronization: fresh-generation INIT first; target/source/region/backend edits increment the UI revision; setup requests synchronize/reset worker mode to SETUP; PREVIEW carries the complete bounded configuration and records PREVIEWED at its exact revision; stale-revision ARM fails; REGION_SNAPSHOT only TARGET/REGIONS; ARM/DISARM/RECORD_START/CAPTURE/PAUSE/RESUME transitions; HEALTH between requests; STOP only RECORDING/PAUSED; normal SHUTDOWN after STOP or from non-recording mode. Inject three TARGET/REGIONS/ARMED request failures both before first Start and during PAUSED→DISARM→repair; assert setup state remains legal, no worker/journal tick exists, `setup_worker_blocked` overrides every worker-dependent action including ARM/Start, Retry worker alone spawns/INIT without reissuing, successful INIT merely clears the flag, only the next successful setup/state request resets the setup counter, and the existing recording counter survives repair (M2-FR-040). |

## 3. Integration tests (real PS worker + synthetic Tk target window; skipped-with-reason off-Windows)

| ID | Covers |
|---|---|
| T-M2L-029 | Synthetic live target appears in the real picker; explicit selection remains visible throughout setup/recording; a same-title second target is not auto-selected; monitor fallback displays and records the visible-pixels/occlusion warning and exact session scope (M2-FR-001..003) |
| T-M2L-030 | One synchronized frame: all observations share frame_id, **exactly one capture invocation (single capture_ms) per tick asserted at the contract level**; crops match drawn regions (M2-FR-042) |
| T-M2L-031 | Live pipeline on a Tk window with values changed programmatically each 500 ms: change events retained, constant periods retain none (M2-FR-043/044) |
| T-M2L-032 | PrintWindow backend on occluded synthetic target: content still correct (S3 reproduction) |
| T-M2L-033 | CopyFromScreen fallback comparison/lock + visible warning; §0 luma range/mean heuristic catches dark/light/other uniform frames without misclassifying a bright non-uniform S3 frame; empty OCR never switches backend (M2-FR-032) |
| T-M2L-034 | Minimized target ⇒ `capture_status=TARGET_MINIMIZED` ⇒ auto-pause after 5; missing/invalid identity pauses immediately |
| T-M2L-035 | Target window closed mid-run ⇒ pause + re-resolve prompt state |
| T-M2L-036 | Pause/Resume/Stop mid-tick; recording screen shows REC, selected target, elapsed time, actual rate, last tick duration, skipped ticks, OCR error count, changed-event count, and disk usage; mini-controller placement and every action; emergency ≤2 s; finalize/recover behavior (M2-FR-045..047) |
| T-M2L-037 | Worker exits on UI close (S6 reproduction, automated) |
| T-M2L-038 | 5-minute mini-soak at 1 s: no queue growth, stable memory, journal integrity |
| T-M2L-039 | Exact §0 recording automatic-pause thresholds/reasons: whole-frame near-uniform streak, recording worker-failure streak, unavailable/minimized target, client/DPI/topology invalidation; empty OCR alone never pauses; the distinct pre-record setup-block behavior is not mislabeled PAUSED; hung-worker orphan dies with UI (job object) |

## 4. Performance tests (recorded, budgets from research §7)

T-M2L-040 tick-duration distribution at 3 and 8 sources vs budget —
including crop-hash cost and a large-client (≥1920×1080) CopyFromScreen
row, since the S4 basis was a 640×220 GDI client via PrintWindow only;
T-M2L-041 worker startup; T-M2L-042 30-minute soak memory/disk slope
(owner machine, part of M2-010).

## 5. Manual acceptance (owner machine, intended target — MANDATORY AND GATED)

Before MA-1 or any later target trial, OD-M2-8/G-F must record the basis for
capture/process/store permission. The displayed content must be synthetic,
owner-created, government-open, or appropriately licensed non-confidential
demonstration data. Unknown rights, confidential content, or any need to
bypass access/capture protections stops the trial. Screenshots remain local
and ignored; none enters Git, a PR/issue, logs, or chat.

MA-1 **S7 gate replay**: run the tracked one-shot tool three separate times
with explicit `present`, `absent`, and `occluded` trial labels and the 3–5 s
countdown. The occluded trial covers the identified value area with a benign,
non-confidential occluder. Record API success, whole-frame health, dimensions,
DPI, latency, and the in-process factual visual verdict for both PW_CLIENTONLY
and CopyFromScreen. The tool must reject hidden/minimized or mid-capture target
changes, require matching dimensions/origin/DPI across two successful backends,
classify capture-API failure separately from trial-invalid infrastructure/state
failure, and return nonzero for any trial-invalid or incomplete record.
`--save` is optional; default transient previews are reviewed then deleted on
normal completion. A successful explicit save publishes a unique no-overwrite
ignored `trial_record.json` last, with a SHA-256 manifest binding each validated
PNG to the trial/backend/verdict; verify it locally and never commit/share it.
The result is target/environment-specific, not a general PrintWindow claim.
MA-2 Configure ≥3 authorized demonstration sources via countdown snapshots; preview gate
crops visibly aligned.
MA-3 60-second mouse sweep: history rows correspond to visually observed
values; spot-check ≥10 events against the retained crops; no duplicate
rows for unchanged values; errors visible and explained; **repeat 10 s of
the sweep with the target partially covered** and record the backend's
actual behavior.
MA-4 For each backend accepted and authorized after S7, verify the mini controller starts outside all source
regions, remains visible when the target covers the main window, shows
REC/PAUSED+elapsed, and performs Pause/Resume, normal Stop, Esc and
emergency Stop. Emergency capture termination is ≤2 s and no worker remains.
MA-5 30-minute soak: memory flat ±50 MiB, disk within retention policy,
actual rate ≥0.95×requested, skipped ticks <1%.
MA-6 Kill the UI at each storage boundary; `recover` follows §6c, rebuilds
exports from canonical valid journal events, tolerates only the partial
final line, and warns/nulls a deliberately missing crop without crashing.
MA-7 XYZ export opens in a text editor with correct axis order; wide CSV
opens in a spreadsheet with no formula execution.
MA-8 A non-developer (the owner) completes MA-2..MA-7 using only the UI
and the M2 guide.

## 6. Regression (every milestone)

Baseline 42/42; M1 34/34; `verify-evidence` PASS; sealed evidence
byte-identical; repository sanitization (T-PRI-004) PASS; no tracked
capture outputs. Compare `git status --porcelain` before and after tests and
require no unexpected delta; require literal cleanliness after the milestone
changes are committed.

## 7. Traceability

| FR | Tests |
|---|---|
| M2-FR-001/002/003 | T-M2L-028/029/034/035, MA-2 |
| M2-FR-010..015 | T-M2L-001/002/019, MA-2 |
| M2-FR-030/031/032 | T-M2L-002, T-M2L-033, MA-1/2 |
| M2-FR-040/041 | T-M2L-010/011, T-M2L-038 |
| M2-FR-042/043/044 | T-M2L-030/031, MA-3 |
| M2-FR-045/047 | T-M2L-011/025/036/037/039, MA-4 |
| M2-FR-046 | T-M2L-036 |
| M2-FR-050/051 | T-M2L-003/004/005, MA-3 |
| M2-FR-052/053/054 | T-M2L-006/007/008/009 |
| M2-FR-060..064 | T-M2L-012/013/014/026, T-M2L-036, MA-6 |
| M2-FR-065/066/067 | T-M2L-015/016/017, MA-7 |
| M2-FR-070/071 | T-M2L-018/023, MA-4/5 |
| NFR-01 | T-M2L-038/040/041/042, MA-5 |
| NFR-02 | T-M2L-018 plus dependency/import and worker-host review at every milestone |
| NFR-03 | T-M2L-030..039 skipped-with-reason off Windows; MA-1..8 only on the recorded owner machine |
| NFR-04 | T-M2L-012/021/022/025/037/039, MA-6 |
| NFR-05 | T-M2L-012/015 plus two-run canonical-journal export comparison |
| NFR-06 | Regression §6 at every milestone |

Runner: `tests_m2/run_m2_tests.py` with a frozen expected count (pattern of
`tests_m1/run_m1_tests.py`); integration tests carry a separate marker and
their own expected count so the deterministic set stays interaction-free.
