# S2XYZ-M1-001 — M1 controlled evaluation evidence

Retained results of the M1 intake-pipeline controlled evaluation
(2026-07-17, current machine). Copy-on-write: never modify these files;
new evaluations publish under a new task ID. This directory is separate
from, and does not alter, the sealed baseline evidence in
`runs/evidence/S2XYZ-CODEX-003/`.

## Contents

- `m1_eval_metrics.json` — scored outcomes for all 24 scenarios of the
  deterministic fixture `test_data/synthetic/m1_eval_v0.1/` (seed 20260718).
- `candidates.json` — full candidate state including retained raw OCR text
  per scenario.

## Headline results

- 15/15 expected-valid scenarios parsed to **exact triplets (100%; target ≥90%)**
  across varied canvas sizes, contrast, glyph softness, layouts, and
  numberless noise.
- 0 false rejects.
- 8/9 expected-invalid scenarios rejected; **1 false accept (M015)**: the
  rendered latitude contains the letter `O` inside the digits and Windows
  OCR read it as `0`, producing a plausible but wrong reading. This is an
  intentional challenge case retained as evidence of why mandatory human
  review exists; it was not tuned away.
- 1 rejected-code mismatch (M013): expected `STALE_READING`, observed
  `MALFORMED_ELEV` because OCR read `10 m` as `IO m` on the 1800-px canvas —
  still safely rejected, and a genuine example of OCR variability across
  render conditions. (Stale detection itself is proven 6/6 in the baseline
  evidence and by unit tests.)
- 0 automatic approvals; 0 exports without approval (structural: the
  evaluation never approves, and export requires explicit approval).

## What this does and does not evaluate

Evaluates: the intake boundary and automatic OCR→parse→validate→classify
stage over a deliberately varied synthetic set. Does **not** evaluate:
real construction drawings, real screenshots, human review ergonomics
(covered by deterministic unit tests), cross-machine OCR behaviour, or any
real-world accuracy.

All content is synthetic, generated from seed 20260718 by
`screen2xyz_m1.evaluation`; no real project, location, or personal data.

Conceptual and preliminary estimating data only.
