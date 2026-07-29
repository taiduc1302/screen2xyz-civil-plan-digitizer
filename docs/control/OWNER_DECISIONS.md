# Owner Decisions

## OD-001 - Orchestration bridge acceptance

| Field | Current value |
|---|---|
| Status | Decided and implemented |
| Owner decision | Accept the S2XYZ-CODEX-002 orchestration bridge and authorize merge of pull request #1. |
| Evidence considered | Connected pull-request review workflow, complete branch diff, task validation, and project-owner instruction. |
| Result | Pull request #1 was merged into `main` at `a8afa5a678fefa183f1c4b7a3648416cff24f39a`. |
| Audit clarification | No separate S2XYZ-AUDIT-002 task exists. Earlier projected references are superseded by the owner's explicit review and merge disposition. |

## OD-002 - Conditional S2XYZ-CODEX-003 authorization

| Field | Current value |
|---|---|
| Status | Authorized for this run only |
| Owner decision | Proceed autonomously through G1-G4 when, and only when, each gate's documented evidence and review conditions are satisfied. |
| Required gate wording | `Conditionally approved by the project owner through S2XYZ-CODEX-003 for the scoped synthetic OCR lab only.` |
| Authorization boundary | Planning, synthetic-only implementation after G4, local tests/evidence, checkpoint commits/pushes, one draft pull request, and one `OWNER_HANDOFF` comment. |
| Exclusions | Real third-party data, service-specific automation, public release, repository licence selection, production architecture, authoritative or downstream compatibility claims, and merge of the new pull request. |

## Run-scoped decisions attached to OD-002

- Current Windows environment only.
- Decimal degrees in EPSG:4326 with explicit longitude/latitude axis handling.
- Elevation in metres with `SYNTHETIC_LOCAL` as the synthetic vertical reference.
- English visible labels `lat`, `lon`, and `elev`.
- No cursor control and no real-source automation.
- Actual OCR only on locally generated synthetic screenshots.
- Live screen capture is optional only in an interactive desktop session and otherwise must be `Not executed`.
- Coordinate transformation is a future interface only.
- Downstream preparation is documentation only; no import or compatibility claim is authorized.
- No repository licence is selected and public release is prohibited.

These are scoped evaluation decisions, not universal product, legal, architecture, production, dataset, licence, or release approvals.

## OD-003 - M2-000 planning task

| Field | Current value |
|---|---|
| Status | Planning work requested; product/risk decisions still pending |
| Owner instruction | Prepare the M2-Live research and architecture package on `plan/m2-live-region-watch`, validate it, push it, and open a Draft planning PR. |
| Authorized boundary | Planning documents, disposable bounded research-gate tools, regression/sanitization validation, logical commits, push, and one Draft PR. |
| Explicit exclusions | Production M2 code, S7 execution before data-use permission, implementation-branch creation, implied owner-gate passage, merge, and production/readiness claims. |
| Decision record | Product, UX, backend, retention, cursor, and capture/data-use decisions are enumerated in `M2_LIVE_OWNER_DECISIONS.md`. |

## OD-004 - M2-000 implementation defaults, UX, and roadmap authorization

| Field | Current value |
|---|---|
| Status | Recorded 2026-07-18 in chat (claude-sonnet-5 session) |
| Owner decision | Approve OD-M2-1 (scope), OD-M2-3 (retention/disk defaults), OD-M2-4 (cadence/stability defaults), OD-M2-5 (cursor metadata, default off), OD-M2-6 (UX journey as implementation baseline), and OD-M2-7 (roadmap M2-002..M2-011 and the future implementation-branch/PR boundary). Record the OD-M2-2 backend decision rule and the OD-M2-8 capture/data-use permission scope, both without yet satisfying their live execution gates. |
| Gates closed by this decision | G-D (UX approval) and G-G (scope/defaults/roadmap) |
| Gates NOT closed by this decision | G-E (real S7 trial result) and the live, per-session G-F confirmation — both require the owner physically at the machine with a real authorized target, which the agent cannot perform or fabricate |
| Full decision text | `docs/control/M2_LIVE_OWNER_DECISIONS.md` |

## OD-005 - G-E gate split and maximum-autonomy implementation authorization

| Field | Current value |
|---|---|
| Status | Recorded 2026-07-18 in chat (maximum-autonomy continuation prompt) |
| Owner decision | Split gate G-E into **G-E-SYNTHETIC** (automated synthetic-target compatibility gate with machine-readable oracles; sufficient to begin and complete implementation, merge planning PR #4, and open a Draft implementation PR) and **G-E-REAL** (owner-machine real-target validation; mandatory before final implementation-PR merge and any real-target support claim). Authorize autonomous execution through planning closeout, synthetic S7, PR #4 merge, implementation branch creation, full M2-Live implementation (M2-002..M2-011), automated/synthetic/performance/soak testing, CI, adversarial review, and Draft implementation-PR updates — pausing only for the final consolidated real-target validation and the final merge decision. |
| Explicit limits preserved | No confidential content; no capture-protection bypass; no hidden recording/keylogging/pointer control/network upload; no committed screenshots or `.lab_work/`; no force push or history rewrite; sealed baseline/M1 evidence immutable; final implementation PR is never merged without the owner's explicit decision; G-E-REAL is never claimed without actual owner-machine validation. |
| Full decision text | `docs/control/M2_LIVE_OWNER_DECISIONS.md` (OD-M2-9) |

## OD-006 - Civil Plan Digitizer autonomous feature authorization

| Field | Current value |
|---|---|
| Status | Authorized 2026-07-28 by the owner’s pasted autonomous Goal brief |
| Owner decision | On a new feature branch, design, implement, test, document, and stabilize the Screen2XYZ Civil Plan Digitizer through the highest feasible priority level, beginning with a reliable manual workflow and continuing through local extraction, review, QA, AGTEK handoff, and preliminary surfaces where stable. |
| Authorized boundary | Repository inspection; source, tests, synthetic fixtures, documentation, local dependencies when justified, new local branch, multiple local commits, builds/tests/benchmarks, and architecture improvements that preserve existing functionality. |
| Explicit limits | No default-branch push or merge, no public release, no confidential drawing upload, no proprietary drawing commit, no credential/licence disclosure, no destructive Git cleanup, no silent discard of user work, and no certified-survey or validated-downstream claim. |
| Review policy | Preliminary PDF/image-derived data requires estimator or survey review. Unreviewed points are excluded by default and Existing/Design remain separate. |

## Decisions currently required

No product decision blocks the authorized Civil Plan Digitizer implementation.
Real proprietary-drawing validation, downstream AGTEK/Civil 3D/Kubla
acceptance, public licensing, and any default-branch merge remain owner gates.
