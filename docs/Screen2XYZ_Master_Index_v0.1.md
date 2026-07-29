# Screen2XYZ Project Master Index

| Field | Value |
|---|---|
| Document | Project Master Index |
| Version | v0.1, controller-maintained |
| Date | 2026-07-28 |
| Lifecycle | Private controlled implementation; no public release |
| Accepted main | `3958eeafc0450d2b8339bfeee13103053e9242dc` (PR #5 merge) |
| Integrated product lines | synthetic baseline, M1 review lab, M2-Live watcher |
| Active task | Civil Plan Digitizer implementation and stabilization |
| Active branch | `feature/civil-plan-digitizer-overnight` |
| Authorization | OD-006 |
| Output class | Conceptual and preliminary estimating data only |

## Controller determination

PRs #1–#5 are integrated on private `main`. The M2 real-target owner-machine
gate is recorded PASS in `M2_IMPLEMENTATION_REPORT.md`. The sealed baseline and
M1 retained evidence remain immutable.

OD-006 authorizes the isolated Civil Plan Digitizer feature implementation,
tests, synthetic benchmark, documents, local dependencies, and local commits.
It does not authorize a default-branch push/merge, public release, proprietary
drawing commit/upload, certified-survey claim, automatic approval, or validated
downstream compatibility claim.

## Current sources of truth

| Priority | Document | Purpose |
|---:|---|---|
| 1 | `AGENTS.md` | Repository execution and evidence rules |
| 2 | `docs/control/PROJECT_STATE.md` | Current integrated and feature state |
| 3 | `docs/control/NEXT_ACTION.md` | Exactly one recommended next action |
| 4 | `docs/control/OWNER_DECISIONS.md` | OD-001 through OD-006 authorizations |
| 5 | `.civil-plan-digitizer-progress.json` | Machine-readable civil resume checkpoint |
| Civil | `docs/civil-plan-digitizer/README.md` | Operator guide |
| Civil | `docs/civil-plan-digitizer/ARCHITECTURE.md` | Architecture and invariants |
| Civil | `docs/civil-plan-digitizer/DETECTION_RULES.md` | Candidate rules and review semantics |
| Civil | `docs/civil-plan-digitizer/AGTEK_WORKFLOW.md` | Versioned handoff and downstream gate |
| Civil | `docs/civil-plan-digitizer/QA_CHECKLIST.md` | Per-project estimator checklist |
| Civil | `docs/civil-plan-digitizer/LIMITATIONS.md` | Explicit validation/product limits |
| Civil | `docs/civil-plan-digitizer/BENCHMARK_RESULTS.md` | Synthetic benchmark only |
| Civil | `docs/civil-plan-digitizer/OVERNIGHT_WORKLOG.md` | Chronological implementation evidence |
| M2 | `M2_IMPLEMENTATION_REPORT.md` | M2 implementation and owner-machine evidence |
| Baseline | `runs/evidence/` | Immutable retained baseline/M1 evidence |

Historical charter, requirements, architecture, testing, UX, research,
guardrails, decisions, and public guides remain under their existing `docs/`
folders. Historical status language is superseded by `PROJECT_STATE.md` where
it describes an earlier lifecycle stage.

## Task register

| Task/product line | Current status |
|---|---|
| S2XYZ-CODEX-000/001 | Verified historical bootstrap/control work |
| S2XYZ-CODEX-002 | Orchestration bridge merged through PR #1 |
| S2XYZ-CODEX-003 | Synthetic baseline merged through PR #2 |
| M1 opt-in PNG review lab | Merged through PR #3 |
| M2-000 planning | Merged through PR #4 |
| M2 implementation | Merged through PR #5; G-E-REAL recorded PASS |
| Civil Plan Digitizer | Feature branch implemented; final regression/docs in progress |

## Current authorization boundary

The Civil feature may operate only on authorized local sources. It is
review-first: automatic candidates are never approved, Existing and Design
remain separate, and exports include approved terrain points only. Every
coordinate/surface output is preliminary and local.

Real proprietary-drawing validation, downstream AGTEK/Civil 3D/Kubla testing,
final merge, licence selection, packaging, and public release remain explicit
owner gates.

## Exactly one recommended next action

Complete the documented full post-feature regression and sanitization gates,
record the results and residual human/downstream gates, then hand the unpushed
feature branch to the owner for review.
