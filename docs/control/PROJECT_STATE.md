# Screen2XYZ Project State

| Field | Current value |
|---|---|
| Date | 2026-07-28 |
| Project version | v0.2 synthetic OCR baseline, M1 review lab, and M2-Live watcher merged; Civil Plan Digitizer in feature development |
| Lifecycle phase | Civil local feature handoff ready with one preserved flaky M2 integration gate; no public release |
| Current main | `3958eeafc0450d2b8339bfeee13103053e9242dc` (PR #5 merge) |
| Active task | Civil Plan Digitizer autonomous implementation |
| Active branch | `feature/civil-plan-digitizer-overnight` |
| Civil authorization | OD-006; implementation, tests, docs, local commits, and justified local dependencies authorized |
| Integrated pull requests | PR #1 orchestration, PR #2 baseline, PR #3 M1, PR #4 M2 planning, PR #5 M2 implementation |
| M2 gate status | G-E-REAL recorded PASS on the owner machine 2026-07-21 in `M2_IMPLEMENTATION_REPORT.md`; PR #5 merged 2026-07-21 |
| Latest post-feature verification | 2026-07-28: baseline 42/42, M1 34/34, M2 deterministic 498/498, Civil 88/88, evidence 0 errors, privacy/sanitization 11/11, compile/UI/civil OCR PASS; M2 Windows integration 15/16 twice due one intermittent `EMPTY_TEXT` OCR case |
| Output classification | Conceptual and preliminary estimating data only |

## Current sources of truth

- `AGENTS.md` — repository and parent-agent working rules.
- `docs/control/OWNER_DECISIONS.md` — owner authorizations, including OD-006.
- `M2_IMPLEMENTATION_REPORT.md` — M2 implementation and owner-machine gate
  evidence.
- `docs/civil-plan-digitizer/` — civil plan implementation, decisions,
  worklog, QA, and limitations.
- `.civil-plan-digitizer-progress.json` — machine-readable resume checkpoint.

## Preserved integrated work

- The sealed synthetic baseline and retained evidence remain immutable.
- The M1 explicit-review/approved-only workflow remains available.
- M2-Live is implemented under `src/screen2xyz_m2/` and merged through PR #5.
- Civil development is isolated under `src/screen2xyz_civil/`; it must not
  rewrite baseline, M1, M2 state models, or retained run evidence.

## Civil authorization boundary

Authorized: a local feature branch, implementation, tests, synthetic fixtures,
documentation, local benchmarks, small local commits, and justified local
dependencies.

Not authorized: modifying or pushing the default branch, merging, public
release, external upload of drawings, proprietary fixtures, destructive Git
operations, certified-survey claims, automatic approval, or unreviewed export.

## Current limitations and gates

- Civil drawing extraction and downstream import compatibility require real,
  authorized local validation.
- Poppler and Windows OCR availability are deployment/runtime concerns.
- Local East/North values are not geodetic coordinates.
- Preliminary surfaces do not infer engineering breaklines.
- Public licensing and release remain unresolved.
- The unchanged M2 number-typed-coordinate integration case is host-OCR
  flaky: full suite 15/16 on two final attempts; isolated case 5/8 PASS and
  3/8 `EMPTY_TEXT`. This is not recorded as a clean integration pass.

## Next controlled objective

Review the unpushed Civil feature branch, its tests, claims, and the preserved
M2 OCR flake before authorizing any push, merge, real-plan validation, or
downstream promotion.
