# Final verification

Date: 2026-08-02 (America/Vancouver)

All three complete rounds passed the unchanged harness gate: accuracy at least 95%, zero false duplicates, zero accepted hallucinations, and exact SQLite/XLSX parity.

| Round | App | Civil | M2 | Exact / truth | Accuracy | Safe failures | False duplicates | Hallucinations | SQLite/XLSX | Harness duration |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| 1 | 53/53 | 113/113 | 498/498 | 209/220 | 95.0% | 11 | 0 | 0 | exact | 1738.821 s |
| 2 | 53/53 | 113/113 | 498/498 | 209/220 | 95.0% | 11 | 0 | 0 | exact | 1737.672 s |
| 3 | 53/53 | 113/113 | 498/498 | 209/220 | 95.0% | 11 | 0 | 0 | exact | 1734.833 s |

## Commands executed per round

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m unittest discover -s tests_app -t . -q
.\.venv\Scripts\python.exe tests_civil\run_civil_tests.py
.\.venv\Scripts\python.exe -m unittest discover -s tests_m2 -t . -q
.\.venv\Scripts\python.exe -m tests_app.harness --output .lab_work\v2_6_final_round_<N>
```

The three harness commands used distinct output roots and ran concurrently. Concurrency did not share OCR caches, databases, journals, exports, or generated images. Full local artifacts remain under `.lab_work/v2_6_final_round_1`, `_2`, and `_3`; the compact metrics are retained here.
