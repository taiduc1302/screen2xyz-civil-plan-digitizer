# Accuracy and validation

> **Preliminary data only.** This page documents a software proof, not survey validation. Screen2XYZ output is for conceptual and preliminary estimating unless independently validated against an authoritative source.

## Latest measured result

| Metric | Windows result, 2026-08-02 |
|---|---:|
| Scripted coordinate changes | 220 |
| Exact rows retained | 215 |
| Accuracy (`exact / ground truth`) | **97.73%** |
| Safely rejected OCR/parse attempts | 5 |
| False duplicate rows | **0** |
| Rows containing a value absent from ground truth | **0** |
| SQLite rows exactly reproduced in XLSX | **Yes** |
| Plan labels rendered / exercised | 48 / 48 |
| Harness duration | 274.966 seconds |

Environment: Windows 11, Python 3.14.6, Tesseract 5.4.0.20240606. The retained local result includes the [metrics, summary, environment, and exact commands](../runs/evidence/S2XYZ-V2.5-LOCAL-2026-08-02/). The same proof is configured as a separate Ubuntu/Windows CI matrix job, with its metrics written to the GitHub Actions job summary and the full output retained as a workflow artifact.

## Method

The self-contained harness in [`tests_app/harness/`](../tests_app/harness/) does not inject parsed readings.

1. Pillow renders four status-bar styles using bundled SIL Open Font License fonts at 11, 12, 13, and 14 pixels.
2. The 220 unique X/Y pairs cover light and dark backgrounds, point and comma decimal separators, grouped and ungrouped thousands, negative values, and a value change on every scripted frame.
3. A synthetic plan renders 48 known elevation labels. Labels include 15–25° rotation, design-grade ovals, and existing-grade cross markers.
4. The harness crops the real image bytes where screen capture would, then uses the production Tesseract backend with padding, scale/binarization variants, numeric whitelist, locale-aware parsing, confidence/range/precision gates, and consensus across deskew retries.
5. Every coordinate change is presented for the production default of two stability confirmations. Production `CapturePipeline`, M2 `StabilityEngine`, journal-first `SessionStore`, SQLite, and XLSX export process the readings.
6. The scorer compares retained `(X, Y, Z)` tuples with ground truth, counts duplicates and out-of-ground-truth values, and opens every XLSX to compare it field-for-field with SQLite.

The acceptance gate is machine-enforced:

- accuracy ≥95%;
- zero false duplicates;
- zero accepted hallucinations; and
- exact SQLite/XLSX parity.

The five misses in the latest run were all rejected reads in the 12-pixel comma-decimal dark status-bar style: two fell below the 0.45 confidence gate and three produced malformed coordinate tokens. No rotated plan-label error or guessed coordinate was written to the database. This fail-closed behavior is why `captured rows` can be below 220 while accepted hallucinations remain zero.

## Reproduce it

Install the project dependencies and Tesseract, then run:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python -m tests_app.harness --output .lab_work\v2_5_harness
Get-Content .lab_work\v2_5_harness\metrics.json
```

The output directory contains the generated status frames, fake plan and ground truth, per-session SQLite/journals, XLSX exports, `metrics.json`, and `summary.md`. It is disposable local test output; the generators, scorer, bundled font, and licence are committed so the evidence is reproducible.

CI runs the same command on Ubuntu and Windows after installing real Tesseract. It never substitutes injected values when Tesseract is unavailable.

## What is validated

- The generated PNG → real OCR → numeric parser → stability/dedup → journal/SQLite → XLSX path works end to end on the documented fixtures.
- The fixture includes small status text, locale separators, grouping, negatives, rotation, and two plan marker conventions.
- All malformed or low-confidence status-bar reads in the measured run were rejected instead of accepted as different values.
- XLSX reflects the retained SQLite rows exactly for the tested fields.

## What is not validated

- No accuracy claim is made for every viewer, drawing, font, monitor, DPI setting, compression level, language, or OCR engine version.
- The harness does not establish coordinate reference system correctness, drawing calibration correctness, source-data authority, positional accuracy, or survey-grade accuracy.
- The synthetic plan is not a proprietary drawing and does not prove compatibility with every real plan convention.
- The metric is point-row exactness for this harness, not a field-survey error bound or confidence interval.
- Edits made during operator review remain human decisions and require independent checking.

Use tight zones, run **Test mapping**, watch zone health, review every session, and validate exported points against an authoritative source.
