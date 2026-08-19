# Defect 2 — cursor OCR safety evidence

Date: 2026-08-04  
Branch: `feature/v2.7-agtek-field-fixes`  
Baseline: `4e9d40a`

## RED reproduction

The new end-to-end regression used real Tesseract through `DefaultReader` and
`ScreenOcrBackend`, with caching disabled. The 12 locally generated fixtures use
17 px dark-grey text on `#a8a8a8`, an `x` marker, -12 degree rotation, and a
160x60 cursor box at negative virtual-desktop coordinates.

Against the v2.6 shipped cursor policy, parsed-value results were:

- AGTEK-style fixtures: 6/12 correct, 6 wrong accepted, 0 rejected.
- Existing rotated plan labels: 36/48 correct, 12 wrong accepted, 0 rejected.
- The policy-drift test was RED because production had no configurable minimum
  decimal count and did not share the measured harness policy.

These local results differ from the supplied task measurements, so both are kept
distinct. Raw local RED output is retained in `.lab_work/v2_7_red/` and the
formal regression remains in `tests_app/test_agtek_cursor_ocr.py`.

## Implemented policy

- PSM modes `(6, 7)`, upscale 2.
- Rotation angles `(0, ±8, ±10, ±12, ±15, ±20, ±25)`.
- Confidence floor 0.60, numeric range supplied by the column, and minimum
  decimal count supplied by the column (default 2).
- At least seven distinct angle/preprocessing variants must agree on a parsed
  value.
- Competing interpretations whose centers overlap are treated as the same
  rendered label; the value with the most distinct-variant support wins.
  Spatially separate labels remain candidates, preserving nearest-label choice.
- Production and the proof harness call the same policy factory. A field-by-field
  drift guard compares confidence, consensus, precision, PSM, and upscale.

The 0.60 confidence threshold is lower than the supplied 0.85 policy, but it is
not a looser acceptance rule in isolation: distinct-variant consensus, precision,
range, and overlapping-read resolution are all enforced. The complete policy was
measured end to end with zero wrong accepted values.

## GREEN measurements

| Fixture set | Correct | Wrong accepted | Rejected | Duration |
|---|---:|---:|---:|---:|
| AGTEK-style 12 | 12/12 | 0 | 0 | 113.6 s combined with two drift tests |
| Existing rotated labels | 48/48 | 0 | 0 | 560.2 s |

The existing-label comparison used correctly centred 160x60 canvases. An earlier
diagnostic put small-crop coordinates into a 160x60 cursor frame and produced
1/48 correct and 47 artificial rejections; that invalid geometry was discarded,
not used as evidence, and rerun correctly.

Fast/regression suites after the compatibility correction:

- application: 66/66 in 135.784 s;
- Civil: 113/113 in 3.582 s;
- M2: 498/498 in 19.350 s.

No OCR cache was used for either real-cursor measurement. This is synthetic
evidence, not validation against a live AGTEK GradeWork window.

## Final-round correction

The first full final-round harness exposed a second path that returned the first
two-variant consensus before measuring stronger alternatives. It produced
173/220 exact, 44 wrong accepted, and 3 safe failures. Across the ten recurring
wrong labels, wrong interpretations had support of 1–6 variants while correct
interpretations had 9–19. The shared boundary was therefore raised to seven and
±8°/±10° angles were added. Direct general-image measurement then produced
47/48 correct, 0 wrong accepted, and 1 safe rejection; the focused ten-label
regression accepted no wrong values. AGTEK 12/12, grey 3/3, and the combined
fixture remained green under the stricter policy.
