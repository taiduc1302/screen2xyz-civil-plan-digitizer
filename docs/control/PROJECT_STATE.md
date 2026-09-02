# Screen2XYZ Project State

| Field | Current value |
|---|---|
| Date | 2026-09-02 |
| Project version | v0.2 baseline + M1 + M2 preserved; Civil Plan Digitizer parent branch plus review-first civil quantity-takeoff integration under test |
| Lifecycle phase | Private feature integration; no default-branch merge or public release |
| Current `main` observed by integration PR | `5525a29b3c1c643a31804f6e7cf8aa8bd6786ce6` |
| Civil parent branch | `feature/assisted-c03-validation` at integration merge-base `dcf2cf00c972b503558426b17b6ec51460617f01` |
| Active integration branch | `integration/open-source-takeoff-stack` |
| Clean review PR | Draft PR #7 -> `feature/assisted-c03-validation` |
| CI harness PR | Draft PR #6 -> `main`; CI-only, do not merge |
| Civil authorization | OD-006; implementation, tests, docs, local/feature commits, and justified dependencies authorized; default-branch merge/release remain owner gates |
| Latest integration verification | GitHub CI run #39 on code commit `a07d3ec18d2e2ae323b3f61a5a589fe365a0a044`: baseline PASS, M1 PASS, M2 deterministic PASS, Civil deterministic PASS with frozen count 178, retained-evidence verification PASS, privacy/sanitization PASS, Windows real-worker integration PASS |
| Current integration head | `a70d9d85371a20aa5a99a7554caf75cd7410c0bc`; difference from tested code commit above is ConstructDrawingAI clean-room review documentation only |
| Output classification | Conceptual and preliminary estimating data only; no real-plan accuracy or certified engineering/survey claim |

## Current sources of truth

- `AGENTS.md` - repository and parent-agent working rules.
- `docs/control/OWNER_DECISIONS.md` - owner authorizations, including OD-006.
- `docs/control/PROJECT_STATE.md` - current integration status.
- `docs/control/NEXT_ACTION.md` - next controlled validation gate.
- `docs/civil-plan-digitizer/` - existing Civil Plan Digitizer architecture, decisions, QA, limitations, and worklog.
- `docs/integrations/UPSTREAM_TAKEOFF_STACK.md` - fixed upstream snapshots and license boundary.
- `docs/integrations/TAKEOFF_INTEGRATION_PLAN.md` - civil quantity integration design/phase plan.
- `docs/integrations/CONSTRUCTDRAWINGAI_IDEA_REVIEW.md` - clean-room comparison and independently implemented ideas.

## Preserved integrated work

- The sealed synthetic baseline and retained evidence remain immutable.
- The M1 explicit-review/approved-only workflow remains available.
- M2-Live remains isolated under `src/screen2xyz_m2/`.
- The pre-existing Civil Plan Digitizer remains under `src/screen2xyz_civil/` and its terrain-point contracts are not replaced by the takeoff work.
- The quantity integration is additive and uses a separate `.s2t.json` sidecar during validation rather than migrating the proven Civil project schema in place.

## Civil quantity integration now present

### Review-first takeoff domain

`src/screen2xyz_civil/takeoff.py` adds normalized line/polygon/count measurement records with:

- explicit civil rules and units;
- review-required / approved / edited-and-approved / rejected states;
- non-summable reference geometry such as `ANCHOR - DO NOT SUM`;
- blocker flags such as `PARTIAL`, `MIXED`, `UNRESOLVED`, `TENTATIVE`, `SCALE_UNVERIFIED`, and `GEOMETRY_UNVERIFIED`;
- explicit scale-gated quantity math;
- machine provenance, immutable original proposal geometry, and estimator correction history;
- correction records suitable for later controlled evaluation/training exports.

Initial civil rules cover road widening, 40 mm mill/overlay, full-depth asphalt R&R, ditch infill, ditch regrade, ditch relocation, 0.30 m gravel shoulder, 300 mm driveway culvert, gravel driveway reinstatement, and QA-only roadworks anchors.

### Audited takeoff workspace

`src/screen2xyz_civil/takeoff_workspace.py` adds an atomic `.s2t.json` workspace linked to the existing Civil project id, source hash/identity, and calibration revision. Quantity approval is invalidated when scale changes. Scale confirmation and every add/edit/flag/evidence/question/approve/reject action are audited.

### External-engine boundaries

- `adapters/opentakeoff.py` translates the existing Screen2XYZ pixel/calibration frame to the reviewed OpenTakeoff MCP coordinate/scale contract without making OpenTakeoff the project database.
- `adapters/segmentation.py` defines a dependency-free proposal interface; SAM 2 may sit behind it later, but segmentation geometry always enters with `GEOMETRY_UNVERIFIED` and cannot approve itself.
- PDF.js is not vendored separately because the chosen OpenTakeoff path already owns its browser PDF/vector dependency. Existing Python PDF extraction remains the local Screen2XYZ path.

### Evidence, withheld uncertainty, and evaluation

- `takeoff_context.py` adds source-linked evidence refs, typed relationships, data classification, and first-class unresolved questions.
- An open `ERROR` question related to a takeoff blocks quantity approval until explicitly resolved.
- `takeoff_eval.py` separates `SYNTHETIC` from `REAL` evaluation lanes and refuses synthetic results as real-plan accuracy evidence.
- Evaluation distinguishes proposed items, disclosed-withheld items, and silent misses.

## External-source / license boundary

- OpenTakeoff, PDF.js, and SAM 2 were reviewed as Apache-2.0 upstream components/ideas with pinned snapshots and notices requirements.
- ConstructDrawingAI is PolyForm Noncommercial and is **not** integrated as source code. Only its public architecture/design documentation was reviewed for ideas after the Screen2XYZ takeoff core passed CI. Useful missing concepts were independently implemented in Screen2XYZ: evidence relationships, first-class withheld questions, stricter synthetic-vs-real evaluation, and data-reuse classification.

## Current limitations and remaining gates

- No authorized real civil drawing has yet been run end-to-end through the new takeoff workspace as committed test evidence.
- OpenTakeoff MCP request translation is deterministic-tested, but actual `opentakeoff-mcp` runtime execution has not yet been validated on the owner workstation in this branch.
- SAM 2 is only an optional provider contract; model weights/runtime are intentionally absent.
- Takeoff review does not yet have a dedicated estimator UI inside the Civil Plan Digitizer.
- Marked-plan PDF / direct Bluebeam handoff has not yet been promoted into this integration branch.
- The current Python PDF vector adapter does not yet expose complete path geometry for every CAD-exported hatch; its existing evidence remains bounded.
- Real-plan quantity/coverage accuracy is unknown. Synthetic deterministic tests are pipeline/contract evidence only.
- Local East/North remains non-geodetic unless tied to a verified survey basis.
- Default-branch merge, public release, public licensing, proprietary fixture commits, and certified claims remain unauthorized.

## Preserved prior evidence

The July 2026 project state recorded the existing baseline/M1/M2/Civil feature work and its then-current host OCR limitations. This update does not erase those historical reports; it supersedes the stale active-branch/next-action fields for the current quantity-integration task.
