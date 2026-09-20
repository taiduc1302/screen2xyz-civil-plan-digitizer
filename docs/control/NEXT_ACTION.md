# Next Action

## Current stage: reconciled Civil mainline, owner-controlled follow-up

The assisted Civil Plan Digitizer workflow is integrated into `main` through PR #1. Repository/CI maintenance is also current on `main`, including the reviewed Actions runtime update merged through PR #21.

## Exactly one repository-admin action

Change the GitHub repository default branch from `feature/assisted-c03-validation` to `main` (Issue #19).

The code/history reconciliation is complete. The remaining blocker is the repository setting itself, which the connected GitHub integration available here cannot change. Until it is changed, treat `main` as the intended canonical code line and avoid starting new work from the stale default branch.

## Draft review order after the default-branch switch

Do not merge the open draft stack merely to reduce the PR count.

1. PR #2 — reconcile the unified-capture draft against current `main`.
2. PRs #3 → #4 → #5 — review only in dependency order because each is stacked on the prior draft.
3. PR #7 — separately review the open-source takeoff integration for licensing, provenance, local-processing boundaries, dependency risk, and current-main CI.
4. PR #8 — review only after PR #7 has a disposition because it is stacked on that branch.
5. PR #10 — independently reconcile the plan-layer extraction draft against current `main`.

Each draft must earn its own current evidence and merge decision.

## Separate owner gates

Real proprietary-drawing validation, downstream AGTEK/Civil 3D/Kubla acceptance, automatic quantity promotion, public release, licence selection, redistribution, and certified accuracy claims remain separate owner decisions. Existing merges do not grant those approvals.

## Standing workflow

For new work:

1. read `AGENTS.md`, `PROJECT_STATE.md`, and this file;
2. branch from current `main` after the default-branch setting is corrected;
3. preserve retained evidence and review-first behavior;
4. use synthetic/public-safe data unless an explicit local real-data validation session is authorized;
5. require reproducible tests and current-main CI;
6. update these control files only when accepted repository state actually changes.
