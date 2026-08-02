# Third-Party Notices

Screen2XYZ installs third-party Python packages from PyPI and can use optional host tools. They are not vendored in this repository.

| Component | Licence | Use |
|---|---|---|
| CPython | PSF-2.0 | Application runtime |
| pypdf | BSD-3-Clause | Local PDF inspection |
| openpyxl | MIT | XLSX creation and verification |
| defusedxml | PSF-2.0 | XML hardening for workbook reads |
| Pillow | HPND | Image intake and preprocessing |
| mss | MIT | Local screen-zone capture |
| pytesseract | Apache-2.0 | Python interface to local Tesseract OCR |
| Tesseract OCR | Apache-2.0 | Optional local OCR executable and language data |
| Poppler | GPL-2.0-or-later | Optional host `pdftoppm` PDF renderer |
| Windows Media OCR / PowerShell | Microsoft platform terms | Windows OCR fallback and adapter host |

See `requirements.txt` for the supported Python dependency ranges. Users are responsible for complying with the licences and distribution terms of optional host tools.
