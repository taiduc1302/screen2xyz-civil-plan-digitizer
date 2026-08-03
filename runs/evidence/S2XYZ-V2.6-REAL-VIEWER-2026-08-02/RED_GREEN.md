# Screen2XYZ v2.6 red/green record

Date: 2026-08-02 (America/Vancouver)

These regressions were written and executed before the corresponding production changes. Raw local console logs remain under `.lab_work/v2_6_red/`; this retained summary records the observable pre-fix state without presenting failed output as passing evidence.

| Area | Red state | Green state |
|---|---|---|
| Token-scoped OCR confidence | 5 tests: 4 failures, 1 pass; label prefixes, a stray colon, a suppressed word, and the default whitelist policy failed | 5/5 pass |
| Cursor OCR source | Import error: `CursorOcrCandidate` absent | 4/4 pass, including nearest-of-two, snap rejection, rotation policy, and SQLite/XLSX mixed-source persistence |
| Zone picker policy | Import error: `VirtualDesktopBounds` absent | 4/4 pass, including virtual desktop geometry, overlay-free preview ordering, warnings, and tall-zone rejection |
| Missing automatic OCR confidence | Automatic capture retained a reading with `confidence=None` | 4/4 capture tests pass; the new regression confirms no row is retained |
| Per-column numeric ranges | 5 tests: 4 errors because `ChannelSource.numeric_range` was absent | 5/5 pass, including profile round-trip and capture-pipeline rejection |
| Harness integrity | 8 tests: 1 failure and 1 error; `plan_labels_used` remained and no cache-disabled factory existed | 8/8 pass; the tautological field is absent and the harness backend reports `cache_enabled=False` |

Combined targeted green run: 30/30 tests passed.

## Commands

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m unittest tests_app.test_real_viewer_ocr -v
.\.venv\Scripts\python.exe -m unittest tests_app.test_cursor_capture -v
.\.venv\Scripts\python.exe -m unittest tests_app.test_zone_picker_policy -v
.\.venv\Scripts\python.exe -m unittest tests_app.test_capture -v
.\.venv\Scripts\python.exe -m unittest tests_app.test_mapping -v
.\.venv\Scripts\python.exe -m unittest tests_app.test_harness_contract -v
```
