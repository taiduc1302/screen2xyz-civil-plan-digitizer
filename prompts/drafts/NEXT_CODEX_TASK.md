# DRAFT — NOT APPROVED

## TASK ID

`S2XYZ-CODEX-004` (proposed only)

## PROJECT

Screen2XYZ — Terrain Capture & Earthwork POC

## PROPOSED TASK TYPE

Synthetic OCR robustness extension for the existing v0.2 laboratory.

## VERIFIED STARTING POINT

S2XYZ-CODEX-003 established the planning baseline and evaluated actual local OCR on one frozen 60-image synthetic fixture. That controlled fixture met all run-scoped targets, including 42/42 exact valid readings, 18/18 expected-invalid rejection, zero false accepts, zero false rejects, 6/6 duplicate detection, 6/6 stale detection, and zero differences across the 69-item deterministic repeatability whitelist.

The result is limited to the current computer and the fixed generated-image conditions. Live capture is `Not executed`. No real-source operation, coordinate transformation, downstream import, terrain calculation, earthwork calculation, production readiness, licence, or public-release conclusion exists.

## PROPOSED OBJECTIVE

Measure whether the selected local OCR/parser boundary remains reliable across a broader but still locally generated synthetic visual-stress matrix without changing the accepted v0.2 fixture or weakening any existing target.

## PROPOSED SCOPE

- Preserve the v0.2 fixture and evidence copy-on-write.
- Add a separately versioned synthetic-only stress fixture with controlled contrast, blur, compression, spacing, and font-size variations.
- Freeze expected values and target definitions before execution.
- Retain actual OCR text, exact per-condition metrics, failures, and two-run repeatability evidence.
- Reuse the source-agnostic image boundary; do not add live capture or a real data source.

## PROPOSED EXCLUSIONS

- Real third-party data or screenshots.
- Service-specific profiles or automation.
- Cursor or GUI automation.
- Coordinate transformation or downstream import testing.
- Terrain or earthwork calculations.
- Production, authoritative, compatibility, licence, or public-release claims.

## PROPOSED ACCEPTANCE BOUNDARY

The task would be complete when the new synthetic stress fixture, pre-frozen targets, actual OCR evidence, exact failed cases, repeatability comparison, and independent review are retained without modifying S2XYZ-CODEX-003 evidence.

## OWNER AUTHORIZATION

Not granted. This draft must be reviewed and explicitly approved before execution.

## EXACTLY ONE RECOMMENDED NEXT ACTION

Review this draft after the S2XYZ-CODEX-003 pull request is assessed, then either approve a revised synthetic-robustness task or leave the project at the current controlled evaluation boundary.

Conceptual and preliminary estimating data only.
