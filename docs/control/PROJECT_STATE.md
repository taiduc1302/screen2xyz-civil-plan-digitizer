# Screen2XYZ Civil Plan Digitizer Project State

| Field | Current value |
|---|---|
| Date | 2026-09-20 |
| Project version | Screen2XYZ v0.2 + integrated Civil Plan Digitizer assisted-validation workflow |
| Lifecycle phase | Integrated private/review-first Civil workflow; real-plan/downstream acceptance and public release remain gated |
| Intended canonical branch | `main` |
| Current `main` | `df02203c17a80851765794b534380d0966aebc84` |
| GitHub default-branch setting | Still `feature/assisted-c03-validation`; admin switch to `main` is pending Issue #19 |
| Civil integration | PR #1 merged 2026-09-20 at merge commit `e93eb45825e03273874e41fcc878f58e2dd30d12` |
| Repository maintenance | PR #15 merged 2026-09-20 at `df02203c17a80851765794b534380d0966aebc84` |
| Civil authorization | OD-006 remains the governing implementation/validation boundary |
| Open downstream drafts | PR #2 (`feature/v2-unified-capture`, conflict/reconciliation required) and PR #7 (`integration/open-source-takeoff-stack`, draft) |
| Output classification | Conceptual and preliminary estimating data only |

## Current sources of truth

- `AGENTS.md` — repository and parent-agent working rules.
- `docs/control/OWNER_DECISIONS.md` — owner authorizations, including OD-006.
- `M2_IMPLEMENTATION_REPORT.md` — M2 implementation and owner-machine gate evidence.
- `docs/civil-plan-digitizer/` — Civil workflow, decisions, QA, operator guidance, and limitations.
- `.civil-plan-digitizer-progress.json` — retained machine-readable Civil implementation checkpoint/history.
- Issue #19 — remaining repository-admin default-branch setting change.
- `docs/control/NEXT_ACTION.md` — current handoff.

Historical evidence and reports remain immutable and should not be rewritten to make old branch states look current.

## Integrated state

- The sealed synthetic baseline and retained evidence remain preserved.
- M1 explicit-review/approved-only workflow remains available.
- M2-Live is integrated under `src/screen2xyz_m2/`.
- Civil Plan Digitizer is integrated on `main` under `src/screen2xyz_civil/` through PR #1.
- Structured issue/PR workflow is integrated through PR #12.
- Main-line CI/maintenance configuration is integrated through PR #15.

The PR #1 merge recorded the following validation for that integrated Civil revision:

- baseline: 42/42 PASS;
- M1: 34/34 PASS;
- M2 deterministic: 498/498 PASS;
- M2 Windows integration: 16/16 PASS;
- Civil Plan Digitizer: 113/113 PASS;
- compileall: PASS;
- synthetic benchmark CPD-SYNTH-BENCH-001: exact and repeatable.

Treat those results as evidence for the validated revision, not as a guarantee for later changes or arbitrary real drawings.

## Civil authorization boundary

Authorized under the existing owner decision: implementation on task branches, tests, synthetic fixtures, documentation, local benchmarks, and justified local dependencies.

Still gated / not implied by the merge:

- real proprietary-drawing validation outside an explicitly authorized local session;
- AGTEK, Civil 3D, Kubla, or other downstream acceptance;
- certified-survey, engineering, terrain, or earthwork-accuracy claims;
- automatic approval or unreviewed quantity/export promotion;
- public release, licence selection, or redistribution rights;
- destructive Git operations or deletion/rewriting of retained evidence.

## Current branch and review state

`main` is the intended canonical branch after the Civil reconciliation. GitHub still reports the old assisted-C03 feature branch as the repository default; Issue #19 tracks the manual repository-setting change.

PR #2 and PR #7 are draft future/integration work. Their existence is not approval to merge them. They must be reviewed against current `main`, current governance, and their own validation evidence.

## Current limitations

- Real drawing extraction and downstream import compatibility remain unverified beyond the explicitly retained evidence.
- Poppler and Windows OCR availability remain runtime/deployment concerns.
- Local East/North values are local coordinates, not geodetic coordinates.
- Preliminary surfaces do not infer authoritative engineering breaklines.
- Public licensing/release remains unresolved.
- Any new dependency or open-source integration must preserve local-processing, licensing, provenance, and review-first constraints.

## Next controlled objective

First finish repository hygiene that affects future work: switch the GitHub default branch to `main` via Issue #19 and keep `main` CI current. Then review the remaining draft integration PRs individually. Real-plan/downstream validation remains a separate owner-controlled gate. See `docs/control/NEXT_ACTION.md`.
