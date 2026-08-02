# Screen2XYZ v2.5 local release proof

- Result: **PASS**
- Accuracy: 97.73% (215/220 exact rows)
- False duplicate rows: 0
- Hallucinated rows: 0
- Safely rejected OCR/parse attempts: 5
- SQLite/XLSX exact: Yes
- Plan labels rendered and exercised: 48/48
- Duration: 274.966 seconds

All five rejected reads came from the 12-pixel comma-decimal dark status-bar style. Two were below the confidence gate and three were malformed. No guessed replacement was retained.

This is synthetic software-test evidence, not source-data or survey validation. Screen2XYZ results remain conceptual and preliminary unless independently validated against an authoritative source.
