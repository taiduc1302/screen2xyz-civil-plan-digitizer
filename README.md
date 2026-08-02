# Screen2XYZ v2

> **Preliminary data only.** Screen2XYZ produces conceptual estimating data, not certified survey data. Validate every output against an authoritative source before relying on it.

Screen2XYZ is a local Windows-first capture tool that turns visible coordinate and elevation readouts into reviewable point rows. It has one launcher and three modes:

1. **Live screen capture** — watch mapped rectangles and retain stable changed values.
2. **Load PDF** — render a plan page locally, then capture against it.
3. **Load image** — open PNG, JPG, JPEG, or BMP plans directly.

Before a session, map X, Y, Z and optional Description/Point number columns to screen-zone OCR, a calibrated plan click, the nearest plan elevation label, clipboard text, or a manual value. Named profiles keep those mappings in the project folder.

Captured points are journaled before being written to the project-local SQLite database. The default exports are a single XLSX workbook or CSV; the existing multi-artifact estimator handoff remains under **Export → Advanced estimator export**.

## Quickstart

This sequence is intentionally short enough to record as a quickstart GIF:

1. Run `run_screen2xyz.ps1` and choose one of the three modes.
2. Choose a project folder and, for plan modes, a PDF or image.
3. Map X/Y/Z. Use **Pick** to draw each screen OCR zone and confirm its live preview.
4. Select **Start**. Automatic mappings retain stable changes; plan-label mappings retain a row when you click the plan.
5. Watch the row counter and last X/Y/Z values, then choose **Export XLSX**.

## Install

Requirements: Python 3.11 or newer and Windows 10/11.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
.\run_screen2xyz.ps1
```

Optional local tools:

- **Tesseract OCR** improves cross-platform OCR and is preferred when found.
- **Poppler `pdftoppm`** on `PATH` enables PDF page rendering.
- On Windows, Windows Media OCR is used when Tesseract is unavailable.

Screen capture and OCR stay local. The application does not upload plans or captured values.

## Channel mapping

| Output | Supported sources |
|---|---|
| X / Y / Z | `screen_zone_ocr`, `plan_click`, `plan_label_ocr`, `clipboard`, `manual` |
| Description / Point number | The same source choices, with text parsing for extras |

Automatic Start/Stop is available when all mapped sources are screen zones or clipboard. A plan-derived Z makes capture click-driven, allowing the current screen-zone X/Y and the nearest recognized plan elevation to be retained together.

## Storage and export

Each project folder contains `.screen2xyz/screen2xyz.sqlite3`, mapping profiles, rendered PDF pages, and per-session M2 journals. The journal is the crash-safety source used to replay any point not yet committed to SQLite.

The default XLSX contains:

- **Points** — PointNumber, X, Y, Z, Description, source methods, confidence, and timestamp.
- **Session** — mapping, calibration metadata when available, app version, and the preliminary-data warning.

## Tests

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python -m unittest discover -s tests_app -t . -v
.\.venv\Scripts\python tests_civil\run_civil_tests.py
```

The automated acceptance test uses injected, synthetic readings. It verifies the X/Y screen-zone plus plan-label Z flow through SQLite and XLSX; it is not evidence of OCR accuracy on a particular viewer or drawing.

## Licence

Screen2XYZ is available under the [MIT License](LICENSE). Third-party components remain subject to their own licences; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
