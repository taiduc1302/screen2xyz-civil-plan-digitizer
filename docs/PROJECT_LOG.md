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
