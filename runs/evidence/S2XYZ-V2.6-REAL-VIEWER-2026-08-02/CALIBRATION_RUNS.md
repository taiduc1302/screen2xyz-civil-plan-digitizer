# Pre-verification calibration runs

These runs were used to detect and correct unsafe harness configurations. They are not release passes and are retained so the development record does not hide failed results.

| Configuration | Ground truth | Exact | Accuracy | Safe failures | Hallucinations | Result |
|---|---:|---:|---:|---:|---:|---|
| Bounded single-pass smoke | 8 | 6 | 75.0% | 1 | 1 | FAIL |
| Bounded same-pass consensus smoke | 8 | 6 | 75.0% | 1 | 1 | FAIL |
| Bounded independent-pass smoke | 8 | 7 | 87.5% | 1 | 0 | FAIL |
| Full narrowed-retry calibration | 220 | 151 | 68.64% | 48 | 21 | FAIL |
| Bounded preprocessing consensus | 8 | 7 | 87.5% | 0 | 1 | FAIL |
| Bounded rotation consensus | 8 | 7 | 87.5% | 0 | 1 | FAIL |
| Bounded 0.85 confidence-gated consensus | 8 | 8 | 100.0% | 0 | 0 | PASS |

The unsafe shortcuts were removed. Final verification uses cache-disabled OCR, two independent stability confirmations, preprocessing consensus, and the 0.85 plan-label confidence gate.
