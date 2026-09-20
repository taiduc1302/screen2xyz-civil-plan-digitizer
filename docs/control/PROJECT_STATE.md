# Screen2XYZ Civil Plan Digitizer Project State

| Field | Current value |
|---|---|
| Date | 2026-09-20 |
| Project version | Screen2XYZ v0.2 + integrated Civil Plan Digitizer assisted-validation workflow |
| Lifecycle phase | Integrated private/review-first Civil workflow; real-plan/downstream acceptance and public release remain gated |
| Intended canonical branch | `main` |
| Current `main` | `077f2b110498269bbd41c592fd0e68865ccfc21d` (PR #21 merge) |
| GitHub default-branch setting | Still `feature/assisted-c03-validation`; admin switch to `main` is pending Issue #19 |
| Civil integration | PR #1 merged 2026-09-20 |
| Repository maintenance | PR #15 reconciled maintenance; PR #21 brought main CI Actions runtimes to v7 |
| Civil authorization | OD-006 remains the governing implementation/validation boundary |
| Output classification | Conceptual and preliminary estimating data only |

## Current sources of truth

- `AGENTS.md` — repository and parent-agent working rules.
- `docs/control/OWNER_DECISIONS.md` — owner authorizations, including OD-006.
- `M2_IMPLEMENTATION_REPORT.md` — retained M2 implementation and owner-machine gate evidence.
- `docs/civil-plan-digitizer/` — Civil workflow, decisions, QA, operator guidance, and limitations.
- `.civil-plan-digitizer-progress.json` — retained machine-readable Civil implementation history.
- Issue #19 — remaining repository-admin default-branch setting change.
- `docs/control/NEXT_ACTION.md` — current handoff.

Historical evidence and reports remain immutable and must not be rewritten to make old branch states look current.

## Integrated state

- The sealed synthetic baseline and retained evidence remain preserved.
- M1 explicit-review/approved-only workflow remains available.
- M2-Live remains integrated under `src/screen2xyz_m2/`.
- Civil Plan Digitizer is integrated on `main` under `src/screen2xyz_civil/` through PR #1.
- Structured issue/PR workflow and repository-maintenance configuration are integrated.
- Main CI now uses the reviewed v7 checkout/setup-python action runtimes through PR #21.

The PR #1 integration recorded the following validation for that revision:

- baseline: 42/42 PASS;
- M1: 34/34 PASS;
- M2 deterministic: 498/498 PASS;
- M2 Windows integration: 16/16 PASS;
- Civil Plan Digitizer: 113/113 PASS;
- compileall: PASS;
- synthetic benchmark CPD-SYNTH-BENCH-001: exact and repeatable.

Those results are evidence for that validated revision only. They are not a guarantee for later changes or arbitrary real drawings.

## Civil authorization boundary

Authorized under the existing owner decision: implementation on task branches, tests, synthetic fixtures, documentation, local benchmarks, and justified local dependencies.

Still gated / not implied by any merge:

- real proprietary-drawing validation outside an explicitly authorized local session;
- AGTEK, Civil 3D, Kubla, or other downstream acceptance;
- certified-survey, engineering, terrain, or earthwork-accuracy claims;
- automatic approval or unreviewed quantity/export promotion;
- public release, licence selection, or redistribution rights;
- destructive Git operations or deletion/rewriting of retained evidence.

## Current branch and review state

`main` is the intended canonical branch after the Civil reconciliation. GitHub still reports `feature/assisted-c03-validation` as the repository default; Issue #19 tracks the manual repository-setting change.

The following open PRs are retained draft/future work, not approved merge candidates:

- PR #2 — unified capture workflow; draft against `main`, currently requires reconciliation.
- PR #3 — v2.5 proof/package work stacked on PR #2.
- PR #4 — v2.6 real-viewer capture stacked on PR #3.
- PR #5 — v2.7 AGTEK/OCR work stacked on PR #4.
- PR #7 — open-source takeoff-stack integration draft against `main`, currently requires reconciliation.
- PR #8 — Claude markup-operator pilot stacked on PR #7.
- PR #10 — plan-layer extraction draft against `main`, currently requires reconciliation.

Each draft must be reviewed against current `main`, current governance, licensing/provenance boundaries, and its own reproducible validation. Their existence does not authorize merge.

## Current limitations

- Real drawing extraction and downstream import compatibility remain unverified beyond explicitly retained evidence.
- Poppler and Windows OCR availability remain runtime/deployment concerns.
- Local East/North values are local coordinates, not geodetic coordinates.
- Preliminary surfaces do not infer authoritative engineering breaklines.
- Public licensing/release remains unresolved.
- Any dependency or open-source integration must preserve local-processing, licensing, provenance, and review-first constraints.

## Next controlled objective

First finish repository hygiene that affects future work: change the GitHub default branch to `main` via Issue #19. Then review the retained draft stacks individually from their actual dependency order rather than merging them simply to clear the queue. Real-plan/downstream validation remains a separate owner-controlled gate. See `docs/control/NEXT_ACTION.md`.
