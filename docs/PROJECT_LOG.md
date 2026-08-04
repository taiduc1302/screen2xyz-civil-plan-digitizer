# Screen2XYZ project log

This is the durable, append-only handover record for agent sessions. Read it before relying on `main`, a chat transcript, or a public headline. Append decisions and measurements in the same commit as the behavior or evidence they describe.

## Where the work is

`main` is an abandoned two-commit stub. It does not contain the application described below and must not be used as the development base.

```text
main 5525a29 (abandoned; do not use)
  └─ feature/assisted-c03-validation dcf2cf0 — draft PR #1, OPEN
      └─ feature/v2-unified-capture 2fe7e50 — draft PR #2, OPEN
          └─ feature/v2.5-proven-release 2e7ab40 — draft PR #3, OPEN
              └─ feature/v2.6-real-viewer-capture 4e9d40a — draft PR #4, OPEN
                  └─ feature/v2.7-agtek-field-fixes — current work
```

Verified against `origin` and GitHub on 2026-08-04. None of PRs #1–#4 is merged. New work must remain in the branch chain and target the immediately preceding feature branch unless the owner explicitly changes that strategy.

## What the product is

The owner is a civil estimator. Their goal is:

> Have a mode where you can either capture the screen, or load a PDF, or load an image. Then when you move over a sheet with drawings, X, Y, Z coordinates get saved into a database. X and Y come from the CAD/takeoff viewer's coordinate readout, Z comes from the elevation printed on the drawing. Ideally, before each run you can choose where X, where Y, where Z each come from. And the best part: an auto-capture screen mode — you choose the sources, press Start, and the program automatically captures data from those zones and notices when they change; when they change it keeps saving them, on and on, while that mode runs. At the end it gives an Excel file with columns of data.

The five-step application supports fixed screen OCR, cursor-centred OCR, plan clicks, plan-label OCR, clipboard, and manual sources with journal-first SQLite and XLSX/CSV export. The current field target is AGTEK GradeWork, but the application must remain source-agnostic and must not add service-specific scraping presets.

Observed field geometry: a light status strip with roughly 12 px `North: 2,768.313    East: 1,718.819` text; drawing labels such as `x 51.53`, rotated about 10–15 degrees, dark grey on approximately `#a8a8a8`; and a second monitor left of primary, producing negative screen coordinates (observed X zone `-582,1009 112x29`, Y zone `-452,1012 104x19`).

## Decision log

Append new entries at the end. Each entry must state the date, decision, reason, and evidence.

### 2026-08-04 — Preserve the unmerged branch chain

- **Decision:** Develop v2.7 from `feature/v2.6-real-viewer-capture` and target that branch with a draft PR; do not use or merge into `main`.
- **Why:** `main` is an abandoned stub and the product exists only in the stacked feature branches.
- **Evidence:** Remote heads and open draft PRs #1–#4 verified with `git ls-remote` and `gh pr list`.

### 2026-08-04 — Make the project log the mandatory handover source

- **Decision:** `docs/PROJECT_LOG.md` is the durable state record; `AGENTS.md` and a guard test enforce it.
- **Why:** Earlier control files were deleted, leaving future sessions without reliable project context.
- **Evidence:** `tests_app/test_project_log.py` checks the file, pointer, and absence of stale `docs/control/` references.

### 2026-08-04 — Use an operator-declared number format and never malformed-token `auto` fallback

- **Decision:** Numeric columns must expose an explicit display format. Ambiguous alternatives may be resolved only when exactly one interpretation fits an operator-configured range. A malformed grouped token must never fall back to `auto`.
- **Why:** `auto` can turn a punctuation OCR slip into a value roughly 1000 times too large, which is worse than rejecting the read.
- **Evidence:** Shipped parser checks: `1.844.850` is malformed in point mode but becomes `1844850` in auto mode.

### 2026-08-04 — Production cursor OCR must be no weaker than measured cursor OCR

- **Decision:** Ship the proven cursor ladder (or a measured stronger replacement), default elevation precision to two decimals, and guard production-versus-harness policy fields in tests.
- **Why:** v2.6 measured one strict plan-label policy while shipping a materially weaker cursor policy.
- **Evidence:** AGTEK-style and 48-label measurements recorded below show wrong-accepted values only under the shipped policy.

### 2026-08-04 — Prefer explicit rejection and visible partial capture

- **Decision:** Wrong values must be rejected. Partial rows are allowed only by explicit opt-in and must remain visibly incomplete in the database and export.
- **Why:** An accepted wrong elevation can corrupt earthwork quantities; a rejection costs a re-hover. Silent empty sessions and silent partial rows are both unacceptable.
- **Evidence:** Field session produced zero rows while Z failed, despite a misleading healthy status; v2.6 calibration retained 21 wrong values under an unsafe configuration.

### 2026-08-04 — Implement explicit numeric display formats with range-only punctuation recovery

- **Decision:** Numeric mappings may declare one of `1,234.56`, `1.234,56`, `1234.56`, or `1234,56`. Exact declared syntax is used first. A malformed punctuation token is recovered only when a configured numeric range admits exactly one interpretation; zero matches reject as out of range and multiple matches reject as ambiguous. No `auto` fallback is called.
- **Why:** This preserves the operator's knowledge of the viewer format while safely recovering the observed repeated-separator slip without turning it into a roughly 1000x integer.
- **Evidence:** Red/green tests and measurements in `runs/evidence/S2XYZ-V2.7-AGTEK-2026-08-04/DEFECT1_FORMAT_OCR.md`.

### 2026-08-04 — Require measured multi-variant consensus for cursor elevations

- **Decision:** Production cursor OCR and the proof harness use one policy factory. Elevations default to two decimal places, require two distinct angle/preprocessing variants to agree, and resolve overlapping competing reads by independent-variant support while retaining spatially separate labels for nearest-cursor selection.
- **Why:** A confidence threshold alone both accepted wrong values and rejected valid low-contrast reads. The combined policy recovered the supplied geometry without accepting a wrong elevation.
- **Evidence:** Red/green tests and cache-disabled measurements in `runs/evidence/S2XYZ-V2.7-AGTEK-2026-08-04/DEFECT2_CURSOR_OCR.md`.

### 2026-08-04 — Make channel failures visible and partial Z explicit

- **Decision:** Track health independently for every mapped channel and pause after 10 never-successful or consecutive failed attempts by default. Missing Z remains strict unless the operator explicitly enables flagged partial capture for the session.
- **Why:** A globally healthy message concealed a continuously failing Z channel and allowed an entire session to finish with no retained rows. Partial data must be useful without ever looking complete.
- **Evidence:** Red/green tests, schema migration, and export checks in `runs/evidence/S2XYZ-V2.7-AGTEK-2026-08-04/DEFECT3_CHANNEL_HEALTH_PARTIAL.md`.

### 2026-08-04 — Identify v2.7 consistently at runtime

- **Decision:** Set the application runtime version to `2.7.0` and show `Screen2XYZ v2.7` in the window and bundled quick-start.
- **Why:** The prior v2.6 build still identified itself as v2.5, so operator reports could not establish which build was running.
- **Evidence:** Red/green launcher contract in `runs/evidence/S2XYZ-V2.7-AGTEK-2026-08-04/DEFECT4_VERSION.md`.

### 2026-08-04 — Retain field geometry as source-agnostic regression fixtures

- **Decision:** Preserve negative virtual-desktop coordinates, warn rather than block tight 18–23 px single-line zones, and prove cursor OCR on multiple grey contrast levels, markers, neighbouring labels, and the combined observed geometry.
- **Why:** Each condition occurred in the first field session and was absent or weaker in the earlier white-background fixtures.
- **Evidence:** Seven-check matrix in `runs/evidence/S2XYZ-V2.7-AGTEK-2026-08-04/ADDITIONAL_FIELD_CHECKS.md`.

## Measurement log

Append every new measured number at the end with exact configuration and retained evidence path.

### 2026-08-02 — v2.5 cached synthetic harness

- **Result:** 220/220 exact (100.0%), zero reported duplicates and hallucinations.
- **Configuration:** Generated happy-case numeric crops; OCR cache enabled for repeated pixels; harness-only numeric ranges differed from the shipped reader.
- **Evidence:** `docs/ACCURACY.md` and prior v2.5 evidence under `runs/evidence/`.
- **Interpretation:** Historical result only. It did not predict the operator's first real viewer test.

### 2026-08-02 — v2.6 cache-disabled unsafe calibration

- **Result:** 151/220 exact (68.64%), 48 rejected, 21 wrong-accepted.
- **Configuration:** Cache disabled; narrowed retry ladder during calibration.
- **Evidence:** `runs/evidence/S2XYZ-V2.6-REAL-VIEWER-2026-08-02/CALIBRATION_RUNS.md`.

### 2026-08-02 — v2.6 final verification baseline

- **Result:** Three identical rounds, each 209/220 exact (95.00%), 11 safe rejections, zero false duplicates, zero wrong-accepted, exact SQLite/XLSX parity. Margin above the 95% gate: 0.00 percentage points; one more failure would fail the gate.
- **Configuration:** Real Tesseract 5; cache disabled; two stability confirmations; plan-label policy `confidence_min=0.85`, `consensus_min=2`, `precision_min=2`, PSM `(6,7)`, upscale 2.
- **Evidence:** `runs/evidence/S2XYZ-V2.6-REAL-VIEWER-2026-08-02/FINAL_VERIFICATION.md` and adjacent round metric JSON files.

### 2026-08-04 — AGTEK-style 12-label cursor comparison supplied for reproduction

- **Result:** Shipped cursor policy: 10 correct, 2 wrong-accepted, 0 rejected. Proven policy: 12 correct, 0 wrong-accepted, 0 rejected.
- **Configuration:** Real Tesseract 5; 17 px dark-grey text on `#a8a8a8`; -12 degree rotation; `x` marker; 160x60 cursor box. Shipped: PSM `(6,11)`, upscale 4, confidence 0.35, consensus 1, no minimum precision. Proven: PSM `(6,7)`, upscale 2, confidence 0.85, consensus 2, minimum precision 2.
- **Evidence:** Controlling v2.7 task; must be independently reproduced and retained before claiming fixed.

### 2026-08-04 — Existing 48-label cursor-policy comparison supplied for reproduction

- **Result:** Shipped policy: 29 correct, 19 wrong-accepted, 0 rejected. Proven policy: 46 correct, 0 wrong-accepted, 2 rejected.
- **Configuration:** Real Tesseract 5 over the harness's 48 rotated labels, cache disabled.
- **Evidence:** Controlling v2.7 task; must be independently reproduced and retained before claiming fixed.

### 2026-08-04 — Defect 1 declared-format and status OCR measurement

- **Result:** The supplied parser hazard reproduced exactly: `1.844.850` was malformed in point mode but accepted as `1844850` in auto mode. Before the fix, safe recovery under four declared formats was unavailable; after the fix, 4/4 supplied slip variants recovered as `1844.850` only under the unique range `(1800,1900)`. Seven format regressions passed.
- **Status OCR rate:** The locally generated AGTEK-style 12 px light-strip fixture was 24/24 correct, 0 wrong, 0 rejected both before and after. The synthetic fixture did not reproduce the operator's real-window OCR failure, so no OCR-rate improvement is claimed.
- **Fast suites:** app 63/63, Civil 113/113, M2 498/498.
- **Configuration and evidence:** Real Tesseract 5, cache disabled, 12 North/East pairs, fixed zones 112x29 and 104x29; `runs/evidence/S2XYZ-V2.7-AGTEK-2026-08-04/DEFECT1_FORMAT_OCR.md`.

### 2026-08-04 — Defect 2 real cursor OCR measurement

- **Local RED result:** v2.6 shipped policy produced 6/12 correct, 6 wrong accepted, 0 rejected on the AGTEK-style set, and 36/48 correct, 12 wrong accepted, 0 rejected on the existing rotated-label set. These independently reproduced counts differ from the controlling prompt's supplied 10/12 and 29/48 baselines and are therefore reported separately.
- **GREEN result:** Current production policy produced 12/12 correct, 0 wrong accepted, 0 rejected on the AGTEK-style set and 48/48 correct, 0 wrong accepted, 0 rejected on the existing rotated-label set. The 48-label run took 560.2 seconds.
- **Policy:** Real Tesseract, cache disabled, PSM `(6,7)`, upscale 2, confidence 0.60, consensus 2 distinct variants, precision 2, bounded elevation range, rotations 0/±12/±15/±20/±25, overlapping-read support resolution.
- **Suites:** application 66/66, Civil 113/113, M2 498/498.
- **Evidence:** `runs/evidence/S2XYZ-V2.7-AGTEK-2026-08-04/DEFECT2_CURSOR_OCR.md`.

### 2026-08-04 — Defect 3 channel-health and partial-row verification

- **Result:** Per-channel counters and last-success/failure details passed; a never-successful Z paused at attempt 10 with the channel and OCR reason named; strict mode retained zero rows; opt-in partial mode stored SQL NULL Z plus `PARTIAL_MISSING_Z` and exported an empty Z with a visible Status column.
- **Migration:** A v2.6 `z NOT NULL` database migrated to nullable Z without losing its existing point, which remained `COMPLETE`.
- **Suites:** application 71/71, Civil 113/113, M2 498/498, Tk functional smoke passed.
- **Evidence:** `runs/evidence/S2XYZ-V2.7-AGTEK-2026-08-04/DEFECT3_CHANNEL_HEALTH_PARTIAL.md`.

### 2026-08-04 — Defect 4 version verification

- **Result:** Runtime `2.7.0`, title `Screen2XYZ v2.7`, quick-start v2.7; launcher 6/6, application 71/71, Civil 113/113, M2 498/498.
- **Evidence:** `runs/evidence/S2XYZ-V2.7-AGTEK-2026-08-04/DEFECT4_VERSION.md`.

### 2026-08-04 — Additional field-check measurement

- **Result:** Negative coordinate capture passed; all heights 18–30 behaved as specified; grey contrasts 96/68/44 were 3/3 correct with zero wrong or rejected; markers were excluded in 12/12; nearest of two consensus-backed labels won; the combined AGTEK-geometry fixture read 51.53 and 2768.313 exactly; five label-text regressions remained green.
- **Suites:** application 75/75, Civil 113/113, M2 498/498.
- **Evidence:** `runs/evidence/S2XYZ-V2.7-AGTEK-2026-08-04/ADDITIONAL_FIELD_CHECKS.md`.

## Known traps

- **`main` looks valid but is not the product.** It is the abandoned `5525a29` stub.
- **Happy-case synthetic OCR is not field proof.** Cropping only the number omits real label prefixes, markers, tight edges, low contrast, and neighbouring values.
- **Measured-versus-shipped policy drift invalidates a proof.** v2.5 harness ranges were not shipped; v2.6's strict plan-label settings were not used by cursor OCR.
- **OCR caching can manufacture repeatability.** Cache replay helped hide per-attempt variation and wrong acceptance. Safety measurements must disable it.
- **Never use `auto` as a malformed grouped-number fallback.** `1.844.850` under `auto` becomes `1844850`, silently accepting a roughly 1000x error.
- **Partial one-field tweaks do not fix cursor OCR.** On the 48-label set, precision alone left 8 wrong; range left 7; consensus alone left 13; confidence alone left 7. PSM and upscale are also material.
- **Zero wrong-accepted is more important than maximizing raw capture.** Report safe rejections plainly.

## Open questions for the owner

- Operator validation against a real, live AGTEK GradeWork window remains outstanding; no automated test drives that application.
- Project-specific numeric ranges and any non-default declared formats must be chosen by the operator for each actual job.
