# Validation environment and traceability

- Task: Screen2XYZ v2.5 — prove it works for real, polish it, and ship it
- Branch: `feature/v2.5-proven-release`
- Tested source commit: `73b1be97da55391421883b68c28fffce6bddff11`
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
.\.venv\Scripts\python -m unittest discover -s tests_m2 -t . -q
$env:PATH = "$pwd\.venv\Scripts;$env:PATH"
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1 -DistPath .lab_work\dist-fail-closed -WorkPath .lab_work\pyinstaller-fail-closed
powershell -ExecutionPolicy Bypass -File packaging\smoke_bundle.ps1 -Executable .lab_work\dist-fail-closed\Screen2XYZ-Setup\Screen2XYZ.exe
.\.venv\Scripts\python -m tests_app.harness --output .lab_work\v2_5_harness_fail_closed_final --count-per-style 55
```

The unchanged Civil suite had passed earlier in the same remediation cycle at 113/113. The application suite passed 36/36 and M2 passed 498/498 at this source commit.

## Results

- Windows one-folder bundle: freshly built at 44.6 MiB.
- Packaged executable launch smoke: passed with title `Screen2XYZ v2.5`.
- Real-OCR harness: 220/220 exact, zero false duplicates, zero hallucinated rows, zero OCR/parse failures, and exact SQLite/XLSX parity.

The original default PyInstaller work directory could not be cleaned because its generated `localpycs` directory acquired a deny-delete ACL in the LocalWorkspace workspace. No source or retained evidence was altered; the same build script was rerun with new generated `-WorkPath` and `-DistPath` parameters and passed.

The generated fixture images, databases, exports, and screenshots remain disposable local output. CI runs the same proof on Windows and Ubuntu and retains the complete generated harness directory, including hidden SQLite/journal files, as a workflow artifact.
