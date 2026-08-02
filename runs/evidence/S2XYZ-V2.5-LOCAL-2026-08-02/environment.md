# Validation environment and traceability

- Task: Screen2XYZ v2.5 — prove it works for real, polish it, and ship it
- Branch: `feature/v2.5-proven-release`
- Tested source commit: `bec497fca06899352971f782050937aea498adff`
- Date: 2026-08-02
- Operating system: Microsoft Windows 11 Pro
- Python: 3.14.6
- Tesseract: 5.4.0.20240606
- Tesseract executable: `C:\Users\Mvu\AppData\Local\Programs\Tesseract-OCR\tesseract.exe`

## Commands executed

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests_app -t . -q
python tests_civil/run_civil_tests.py
python -m unittest discover -s tests_m2 -t . -q
python tests_app/tk_smoke.py --output .lab_work/tk-smoke-remediation-final
powershell -ExecutionPolicy Bypass -File packaging/build_windows.ps1
powershell -ExecutionPolicy Bypass -File packaging/smoke_bundle.ps1
python -m tests_app.harness --output .lab_work/v2_5_harness_remediated --count-per-style 55
```

## Results

- Application tests: 34 passed.
- Civil regression: 113 passed.
- M2 regression: 498 passed.
- Scripted Tk smoke: passed and wrote screenshots.
- Windows one-folder bundle: built at 44.6 MiB; packaged executable launch smoke passed.
- Real-OCR harness: passed the 95% gate at 97.73% exact with zero false duplicates, zero hallucinated rows, and exact SQLite/XLSX parity.

The generated fixture images, databases, exports, and screenshots remain disposable local output. CI runs the same proof on Windows and Ubuntu and retains the complete generated harness directory as a workflow artifact.
