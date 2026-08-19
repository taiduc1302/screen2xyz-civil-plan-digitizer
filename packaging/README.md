# Windows bundle

Build from the repository root with:

```powershell
python -m pip install -r requirements-build.txt
.\packaging\build_windows.ps1
.\packaging\smoke_bundle.ps1
```

The output is `dist/Screen2XYZ-Setup/Screen2XYZ.exe`. The folder includes Python and the required Python libraries; Tesseract and Poppler remain optional system tools and the app gives clickable installation help when they are absent.

The v2.7 release workflow publishes the actual ZIP and SHA-256 checksum. GitHub runner size can vary slightly with the pinned Python and dependency builds.
