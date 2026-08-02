# Changelog

All notable public changes are recorded here.

## [2.5.0] - 2026-08-02

### Added

- Realistic ≥200-row image-to-XLSX proof harness with real Tesseract, rotated synthetic plan labels, machine-enforced accuracy/no-hallucination gates, and Ubuntu/Windows CI jobs.
- Global Windows capture hotkeys, an always-on-top per-zone health overlay, automatic pause on repeated OCR failures or display/DPI changes, and a re-pick flow.
- Configurable XY dedup distance and point numbering, non-retaining mapping tests, and an audited review/edit/soft-delete/re-export workflow.
- PyInstaller `Screen2XYZ-Setup` folder build, packaged launch smoke, tag-triggered release workflow, ZIP checksums, and a bundled offline five-step first-run guide.
- Public screenshots, persona quick starts, troubleshooting, FAQ, and accuracy methodology.

### Changed

- Numeric OCR now uses bounded retry policies, preprocessing variants, locale repair, confidence/range/precision gates, and optional deskew consensus.
- Tesseract discovery includes user-local Windows installations.
- Missing Tesseract or Poppler now produces clear in-app install guidance and disables only the affected capability.
- App version and title updated to 2.5.0.

### Validation

- Realistic proof: 215/220 exact rows (97.73%), zero false duplicates, zero accepted hallucinations, exact SQLite/XLSX parity.
- Local Windows regression: tests_app 28/28, tests_civil 113/113, tests_m2 498/498, scripted Tk smoke pass, packaged executable launch pass.
- Local Windows bundle: 44.63 MiB folder; 22.01 MiB ZIP.

## [2.0.0] - 2026-08-02

### Added

- One Tkinter application with Live screen capture, Load PDF, and Load image modes.
- Per-column source mapping for X/Y/Z and optional fields, reusable mapping profiles, and screen-zone picker previews.
- Stable automatic capture and mixed screen/plan click capture using the retained M2 and Civil cores.
- Journal-first project-local SQLite storage, one-click XLSX/CSV, and optional advanced estimator export.
- Public-source repository preparation, installation guidance, and preliminary-data warnings.
