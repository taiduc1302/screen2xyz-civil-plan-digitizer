# Validation environment and traceability

- Task: Screen2XYZ v2.5 — prove it works for real, polish it, and ship it
- Branch: `feature/v2.5-proven-release`
- Tested source commit: `1da7fc0bf04b1a7040b8542403547295bffff992`
- Date: 2026-08-02
- Operating system: Microsoft Windows 11 Pro
- Python: 3.14.6
- PyInstaller: 6.21.0
- Tesseract: 5.4.0.20240606
- Tesseract executable: `%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe`

## Commands executed

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python -m unittest discover -s tests_app -t . -q
$env:PATH = "$pwd\.venv\Scripts;$env:PATH"
python -m PyInstaller --version
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
powershell -ExecutionPolicy Bypass -File packaging\smoke_bundle.ps1
.\.venv\Scripts\python -m tests_app.harness --output .lab_work\v2_5_harness_ci_fix_final --count-per-style 55
```

The unchanged Civil and M2 suites had also passed earlier in the same remediation cycle at 113/113 and 498/498. The application suite passed 35/35 at this source commit.

## Results

- Windows one-folder bundle: freshly built at 44.6 MiB.
- Packaged executable launch smoke: passed with title `Screen2XYZ v2.5`.
- Real-OCR harness: passed the 95% gate at 99.09% exact with zero false duplicates, zero hallucinated rows, and exact SQLite/XLSX parity.

The generated fixture images, databases, exports, and screenshots remain disposable local output. CI runs the same proof on Windows and Ubuntu and retains the complete generated harness directory as a workflow artifact.
