# Screen2XYZ v2.5 local CI-remediation proof

- Result: **PASS**
- Accuracy: 99.09% (218/220 exact rows)
- False duplicate rows: 0
- Hallucinated rows: 0
- Safely rejected OCR/parse attempts: 2
- SQLite/XLSX exact: Yes
- Plan labels rendered and exercised: 48/48
- Duration: 275.488 seconds

Both rejected reads came from the 12-pixel comma-decimal dark status-bar style and remained below the 0.35 confidence gate after the retry ladder. No guessed replacement was retained.

This copy-on-write record supersedes the earlier local result for the current release head without deleting it. It is synthetic software-test evidence, not source-data or survey validation. Results remain conceptual and preliminary unless independently validated against an authoritative source.
