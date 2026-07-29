# M2-Live Implementation Master Prompt

Status: agent-neutral execution prompt. **Execution requires gates G-D (UX),
G-E-SYNTHETIC (automated synthetic-target gate per OD-M2-9), the recorded
G-F scope (OD-M2-8), and G-G (scope/defaults/roadmap) recorded green.
G-E-REAL (owner-machine real-target validation with the live content
confirmation) is not required to begin implementation but blocks the final
implementation-PR merge and every real-target support claim.**

---

Implement Screen2XYZ M2-Live, a source-agnostic Windows screen-region watcher,
in the current repository. Treat every result as conceptual and preliminary
unless separately validated.

## Read before writing

Read `AGENTS.md`, `docs/control/PROJECT_STATE.md`, and
`docs/control/NEXT_ACTION.md`, then read every document below in full:

- `docs/requirements/M2_LIVE_DATA_CONTRACTS.md` — **single source of truth
  for constants, closed enums, limits, schemas, and protocol commands**;
- `docs/requirements/M2_LIVE_PRODUCT_SPEC.md` — functional requirements and
  acceptance criteria;
- `docs/architecture/M2_LIVE_ARCHITECTURE.md` — components, lifecycle,
  backend policy, scheduling, evidence, and rejected alternatives;
- `docs/ux/M2_LIVE_USER_FLOW_AND_WIREFRAMES.md` — screens and legal
  state/action transitions;
- `docs/testing/M2_LIVE_TEST_AND_ACCEPTANCE_PLAN.md` — planned automated and
  manual acceptance IDs;
- `docs/guardrails/M2_LIVE_PRIVACY_AND_THREAT_REVIEW.md` and
  `docs/guardrails/M2_LIVE_RISK_REGISTER.md` — mandatory mitigations;
- `docs/control/M2_LIVE_IMPLEMENTATION_ROADMAP.md` — milestone scope and gates;
- `docs/control/M2_LIVE_OWNER_DECISIONS.md` — actual owner decisions; and
- `docs/research/M2_LIVE_TECHNICAL_RESEARCH.md` — measured evidence and its
  limitations, including what was not tested.

Stop and report any conflict. Do not silently invent a resolution or treat a
planning recommendation as an owner decision.

## Execution boundary

1. After verifying G-D/G-E/G-F/G-G, create
   `feat/m2-live-region-watch-impl` from the then-current `main`. Implement one
   roadmap milestone at a time with task-scoped commits. Keep the PR Draft
   through M2-010 and never merge without the owner's explicit release decision.
2. Preserve baseline and M1 source, tests, and retained evidence. Reuse only the
   public functions explicitly allowed by architecture §1. Never import private
   members of `screen2xyz_lab.parser`. New accepted evaluation evidence gets a
   new immutable task/run directory; corrective work never edits or deletes a
   prior evidence run.
3. Keep the application source-agnostic: no named-service presets, scraping,
   navigation, pointer control, access-control bypass, network extraction, or
   proprietary/unlicensed fixtures. Manual work requires the recorded G-F
   permission and non-confidential authorized demonstration content.
4. Use the platform/runtime boundary approved by the architecture. Add no
   dependency or support claim without a recorded decision and reproducible
   validation. The measured current-machine spikes are not universal support
   evidence.

## Non-negotiable behavior

- Set per-monitor-v2 DPI awareness before any coordinate-bearing UI or Win32
  call. Re-query client origin each tick; pause/disarm on the exact invalidation
  conditions and thresholds in data contracts §0.
- Implement exactly these worker commands and their legal states:
  `INIT`, `REGION_SNAPSHOT`, `PREVIEW`, `ARM`, `DISARM`, `RECORD_START`,
  `CAPTURE`, `PAUSE`, `RESUME`, `HEALTH`, `STOP`, `SHUTDOWN`.
  `REGION_SNAPSHOT` and `PREVIEW` are distinct, explicit, one-frame setup
  operations. Only `CAPTURE` is periodic, and only in RECORDING.
- Bound every JSON line, full-frame PNG, changed crop, aggregate response, raw
  OCR string, profile, and candidate evidence buffer using data contracts §0.
  Use a bounded reader before allocation. Match `request_id`,
  `worker_generation`, `configuration_revision`, and the expected closed
  `worker_mode`; discard stale or mismatched replies.
- A fresh generation may restore RECORDING/PAUSED only inside the same live UI
  process and same session/configuration revision after explicit Start. A
  relaunched/recovery UI never auto-records. Validate the restored-state echo.
- Enforce a single in-flight request. On timeout, mark it terminal and prohibit
  sends; invalidate the generation and discard late output; terminate/force-kill
  and wait/reap the old PID; drain only already-buffered diagnostics; close
  stdin/stdout/stderr; signal and join both reader threads; only then apply the
  exact 0/1/5-second restart policy, saturating at 5 seconds for failure 3 and
  every later failure. Requests issued in TARGET_SELECTED, REGIONS_CONFIGURED,
  or ARMED—including same-run repair—use the setup counter: failures 1-2 complete
  fresh INIT automatically; count ≥3 leaves the setup UI state unchanged,
  spawns no replacement, sets the closed `setup_worker_blocked` interlock, and
  disables every worker-dependent action. Explicit Retry worker waits any
  remaining saturated delay, spawns a fresh generation, and sends INIT only;
  successful INIT clears the interlock but the next successful setup/state
  request resets the separate setup counter. Requests in RECORDING/PAUSED use
  the recording counter. Its first RECORD_START initializes it; same-run
  disarm/re-arm/re-start preserves it. Successful `CAPTURE` alone resets that
  recording streak; every failure count
  ≥3 pauses, so Resume followed by another failure re-pauses. PAUSE timeout
  resolves to PAUSED; RESUME timeout remains PAUSED. STOP/SHUTDOWN, UI close,
  and Emergency Stop are terminal and never restart. Graceful and emergency
  stop must meet their independent §0 bounds.
- Treat capture availability/content, OCR, parsing, stability, value, event,
  worker, and pause causes as separate closed fields. Never use a generic
  `status`, never call empty OCR a blank frame, and never surface a previous
  value as the current failed observation.
- Apply the exact raw UTF-8 truncation contract and closed sign policy. A
  truncated input is never parsed as complete; unrecognized or separated
  dash/minus glyphs must not turn a negative-looking token positive.
- Capture once per tick. Changed hashes automatically return same-frame bounded
  crop bytes; there is no crop-request flag and no second evidence capture.
  In stabilized mode retain the first-candidate self-contained evidence bundle,
  one per source, with explicit replacement/discard/timeout rules. Exceeding a
  cap pauses; it never evicts another source silently.
- Apply retention precedence exactly: new retainable error, then stable
  change/error recovery, then diagnostic. Repeated identical errors retain once;
  missing and unstable readings are diagnostic-only. An unchanged diagnostic
  event references an already persisted same-hash crop instead of duplicating it.
- Commit durable state in this order: atomic crop write and flush; hash final
  bytes; append/flush/durably sync the canonical JSONL line; then atomically
  replace a due checkpoint. Implement the exact partial-line, malformed-line,
  crop-mismatch, checkpoint-divergence, and orphan-crop recovery outcomes. Export
  only from the canonical valid journal.
- Keep cursor metadata visible, optional, and default off unless the recorded
  OD-M2-5 decision explicitly changes it. The mini controller must always expose
  the state-legal Pause/Resume, Stop, and Emergency Stop actions and prevent
  overlapping requests.

## Verification and stop conditions

After each milestone, capture reproducible results for the current baseline
suite, M1 suite, then-current M2 suite, retained-evidence verifier, repository
sanitization test, `git diff --check`, scoped diff, and proof that prior evidence
and ignored capture outputs are untouched. The M2 test suite and its count do
not exist at planning time; create it when the roadmap authorizes it and never
claim a result before running it.

Stop without merging on any failed gate, sealed-evidence change, sensitive or
unlicensed artifact at risk of staging, malformed/oversized protocol ambiguity,
need to weaken a requirement/test, authoritative-document conflict, or missing
owner authorization. Update controller files only with verified facts at
milestone boundaries.

Definition of done is the roadmap's M2-011 gate: requirements are demonstrably
met or limitations are explicit; authorized MA-1..MA-8 outcomes are recorded;
regressions, evidence verification, sanitization, and independent review pass;
and the owner makes the merge decision. Until then the implementation remains a
Draft PR and no production-readiness claim is permitted.
