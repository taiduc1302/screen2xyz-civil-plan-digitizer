# Next Action

## Current stage: review-first civil quantity takeoff integration

The additive takeoff core, OpenTakeoff bridge contract, optional segmentation boundary, audited `.s2t.json` workspace, evidence/question layer, and takeoff evaluation contracts are implemented on `integration/open-source-takeoff-stack`.

The tested code state passed GitHub CI run #39: baseline, M1, M2 deterministic, Civil deterministic frozen count 178, retained evidence verification, privacy/sanitization, and Windows real-worker integration all succeeded. Draft PR #7 is the clean review PR against `feature/assisted-c03-validation`; draft PR #6 exists only to exercise the `main`-targeted CI workflow and must not be merged.

## Exactly one recommended next action

Run one **owner-authorized real civil takeoff validation session** using a private/local drawing already being manually reviewed by the estimator, with Sheet 03 of the current Example Road workflow as the preferred first case if project-data handling permits.

The validation should compare the new system against the estimator-reviewed Bluebeam result for a small, explicit rule set:

1. `DRIVEWAY_CULVERT_300` - line endpoints/centerline and length;
2. `GRAVEL_DRIVEWAY_REINSTATEMENT` - actual reinstatement polygon and area;
3. `DITCH_INFILL` - hatch boundary and area;
4. `GRAVEL_SHOULDER_030` - continuous reaches and stated 0.30 m width;
5. `ROAD_WIDENING_FULL_STRUCTURE` - hatch coverage;
6. `ANCHOR_ROADWORKS_EXTENT` - confirm it remains QA-only and never enters totals;
7. one intentionally unresolved/partial ditch case - confirm the system discloses/withholds it rather than silently summing it.

During that same session, run the pinned OpenTakeoff MCP locally and verify that Screen2XYZ -> OpenTakeoff coordinate/scale translation lands the same proposal geometry on the correct sheet. Record corrections in the `.s2t.json` sidecar and evaluate **coverage, silent misses, rule mapping, and quantity error** as private real-plan evidence. Do not commit the proprietary drawing or raw private evidence to Git.

Only after this real session should the next implementation target be chosen between estimator UI integration, richer PDF/CAD hatch geometry, marked-plan/Bluebeam handoff, or a SAM 2 runtime adapter.

Real-data accuracy claims, default-branch merge, public release/licensing, AGTEK/Bluebeam certification, and any proprietary fixture commit remain separate owner gates.
