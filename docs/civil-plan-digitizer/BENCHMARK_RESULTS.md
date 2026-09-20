# Civil Plan Digitizer Synthetic Benchmark

- Dataset: `CPD-SYNTH-BENCH-001`
- Date: 2026-07-28
- Environment: Windows, Python 3.12.10
Command:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m tests_civil.benchmark_civil
```

> This is a synthetic rule-level benchmark. It does not run an OCR engine or
> use a real drawing. The exact scores below must not be represented as
> real-world plan accuracy.

## Recorded result

| Measure | Result |
|---|---:|
| Synthetic type-classification cases | 105 |
| Exact expected type | 105/105 |
| Synthetic terrain Existing/Design cases | 50 |
| Exact terrain type | 50/50 |
| Correct target symbol association with distractor | 50/50 |
| Numeric parse round trips | 81/81 exact |
| Pixel/local/pixel transform round trips | 121 |
| Maximum transform round-trip error | `1.5888218580782548e-14` px |
| Surface fixture | 5 vertices, 4 triangles |
| Repeated classification evaluations | 10,500 |
| Classification repeatability | identical across 100 iterations |
| Timed classification loop | 0.448 s on this run |
| Mean classification time | 42.63 microseconds/case on this run |
| Peak Python traced memory | 71,686 bytes on this run |

Timing and memory are observational machine results and will vary. The
classification fixture covers Existing crosses, Design ovals, plausible
unassociated decimals, percentages, invert context, metadata context, and
nearby distractor symbols. It deliberately measures deterministic code paths,
not OCR or vector-shape discovery.

## Explicitly not measured

- real-drawing OCR accuracy;
- real-drawing vector-symbol precision or recall;
- estimator time savings;
- AGTEK, Civil 3D, Kubla, or downstream LandXML acceptance;
- survey, engineering, surface, or quantity accuracy.

## Next validation dataset

A future authorized benchmark should use locally held, legally permitted,
representative plan pages with a double-reviewed ground-truth ledger. It should
report OCR box recall, numeric precision/recall, terrain type confusion matrix,
association precision/recall by symbol family, coordinate residuals at control
points, review time, false-export rate, and downstream application/version
results. Proprietary pages and OCR crops must remain uncommitted.
