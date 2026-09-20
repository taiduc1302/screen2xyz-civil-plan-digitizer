# Next Action

## Current stage: reconciled Civil mainline, owner-controlled follow-up

The assisted Civil Plan Digitizer workflow is no longer an unpushed local feature. It was integrated into `main` through PR #1 with recorded synthetic/regression validation, and CI/repository maintenance was aligned through PR #15.

## Immediate repository action

Change the GitHub repository default branch from `feature/assisted-c03-validation` to `main` (Issue #19). The branch contents are reconciled; the remaining blocker is the repository-admin setting, which this connected integration cannot change.

Until that setting is changed, treat `main` as the intended canonical code line and avoid creating new work from the stale default branch.

## Review queue after the default-branch setting

- PR #2 — `feature/v2-unified-capture`: large draft, currently requires conflict/reconciliation work against current `main`. Do not merge as-is.
- PR #7 — `integration/open-source-takeoff-stack`: draft integration work; review licensing, provenance, local-processing boundaries, dependency risk, and current-main CI before any merge decision.

Each draft remains a separate scope and must earn its own validation. Do not combine them simply to clear the queue.

## Separate owner gates

Real proprietary-drawing validation, downstream AGTEK/Civil 3D/Kubla acceptance, automatic quantity promotion, public release, licence selection, and any certified accuracy claim remain separate owner decisions. The PR #1 merge does not grant those approvals.

## Standing workflow

For new work:

1. read `AGENTS.md`, `PROJECT_STATE.md`, and this file;
2. branch from current `main` once the default-branch setting is corrected;
3. preserve retained evidence and review-first behavior;
4. use synthetic/public-safe data unless an explicit local real-data validation session is authorized;
5. require reproducible tests and current-main CI;
6. update these control files only when accepted repository state actually changes.
