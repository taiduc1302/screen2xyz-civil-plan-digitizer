# Windows bundle

Build from the repository root with:

```powershell
python -m pip install -r requirements-build.txt
.\packaging\build_windows.ps1
.\packaging\smoke_bundle.ps1
```

The output is `dist/Screen2XYZ-Setup/Screen2XYZ.exe`. The folder includes Python and the required Python libraries; Tesseract and Poppler remain optional system tools and the app gives clickable installation help when they are absent.

The verified local v2.5.0 build contained 1,010 files and measured 44.63 MiB uncompressed. Its ZIP measured 22.01 MiB. GitHub runner size can vary slightly with the pinned Python and dependency builds; the release workflow publishes the actual ZIP and SHA-256 checksum.
