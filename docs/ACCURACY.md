# Accuracy and validation

> **Preliminary data only.** This page documents a software proof, not survey validation. Screen2XYZ output is for conceptual and preliminary estimating unless independently validated against an authoritative source.

## Measured range

The prior v2.5 retained passing range was **97.3%–100.0% exact rows**. The stricter v2.6 cache-disabled verification is reported separately below; the historical maximum must not be presented alone as expected viewer performance.

## v2.7 production cursor-pipeline verification

| Ground truth | Exact rows | Accuracy | Safe OCR/parse failures | False duplicates | Accepted hallucinations | SQLite/XLSX exact | Duration |
|---:|---:|---:|---:|---:|---:|---|---:|
| 220 | 212 | **96.36%** | 16 attempts | 0 | 0 | Yes | 505.708 s |

Environment: Windows, Python 3.12.13, Tesseract 5.5.0. The cache-disabled proof ran on 2026-08-18 against the production cursor image path: local padding, deskew angles through ±30°, local Tesseract TSV boxes, inverse-mapped boxes, spatial consensus, nearest-cursor selection, and journal-first SQLite/XLSX export. The 16 failed polling attempts correspond to safe rejections; no rejected value was stored. This is fixture-specific evidence, not live AGTEK validation.

## v2.6 cache-disabled verification

| Round | Ground truth | Exact rows | Accuracy | Safe failures | False duplicates | Accepted hallucinations | SQLite/XLSX exact | Duration |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| 1 | 220 | 209 | **95.0%** | 11 | 0 | 0 | Yes | 1738.821 s |
| 2 | 220 | 209 | **95.0%** | 11 | 0 | 0 | Yes | 1737.672 s |
| 3 | 220 | 209 | **95.0%** | 11 | 0 | 0 | Yes | 1734.833 s |

Environment: Windows, Python 3.14.6, Tesseract 5.4.0.20240606. Each round independently ran 53 app tests, 113 Civil tests, 498 M2 tests, and the full harness. OCR caching was disabled, so both stability confirmations for every scripted row executed Tesseract. The 11 unsuccessful attempts in each round were rejected; none became a wrong retained value.

## Latest retained v2.5 result

| Metric | Windows result, 2026-08-02 |
|---|---:|
| Scripted coordinate changes | 220 |
| Exact rows retained | 220 |
| Accuracy (`exact / ground truth`) | **100.00%** |
| Safely rejected OCR/parse attempts | 0 |
| False duplicate rows | **0** |
| Rows containing a value absent from ground truth | **0** |
| SQLite rows exactly reproduced in XLSX | **Yes** |
| Plan labels rendered | 48 |
| Harness duration | 610.002 seconds |

Environment: Windows 11, Python 3.14.6, Tesseract 5.4.0.20240606. The latest retained local result includes the [metrics, summary, environment, and exact commands](../runs/evidence/S2XYZ-V2.5-LOCAL-2026-08-02-FAIL-CLOSED/); [prior measurements](../runs/evidence/) remain preserved. The same proof is configured as a separate Ubuntu/Windows CI matrix job, with its metrics written to the GitHub Actions job summary and the full output retained as a workflow artifact.

## Method

The self-contained harness in [`tests_app/harness/`](../tests_app/harness/) does not inject parsed readings.

1. Pillow renders four status-bar styles using bundled SIL Open Font License fonts at 11, 12, 13, and 14 pixels.
2. The 220 unique X/Y pairs cover light and dark backgrounds, point and comma decimal separators, grouped and ungrouped thousands, negative values, and a value change on every scripted frame.
3. A synthetic plan renders 48 known elevation labels. Labels include 15–25° rotation, design-grade ovals, and existing-grade cross markers.
4. The harness crops the real image bytes where screen capture would, then runs plan Z through the production cursor-image API: local padding, Tesseract TSV boxes, deskew inverse mapping, spatial consensus, and nearest-cursor selection. Status X/Y uses the production image reader. A character whitelist is optional rather than assumed, so prefixed labels can be recognized and then reduced to the accepted numeric token.
5. The proof uses one confirmation per scripted frame so it measures every freshly rendered OCR tuple; deterministic AutoCapture stability/debounce tests cover the multi-confirmation state machine separately. OCR caching is disabled. Production `CapturePipeline`, M2 `StabilityEngine`, journal-first `SessionStore`, SQLite, and XLSX export process the readings.
6. The scorer compares retained `(X, Y, Z)` tuples with ground truth, counts duplicates and out-of-ground-truth values, and opens every XLSX to compare it field-for-field with SQLite.

The acceptance gate is machine-enforced:

- accuracy ≥95%;
- zero false duplicates;
- zero accepted hallucinations; and
- exact SQLite/XLSX parity.

Passing results are reported in their version-specific tables above. The retry ladder uses image-only dark-background normalization, grayscale, and fixed threshold variants; it does not reconstruct missing punctuation or otherwise change an OCR token's numeric magnitude. No guessed coordinate may be written to the database.

## Reproduce it

Install the project dependencies and Tesseract, then run:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python -m tests_app.harness --output .lab_work\v2_7_harness
Get-Content .lab_work\v2_7_harness\metrics.json
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
