# Third-Party Notices

This repository redistributes **no** third-party code, fonts, images, models,
or datasets. It uses the following components in place on the host machine:

| Component | Use | Redistribution |
|---|---|---|
| CPython 3.14 (PSF-2.0) | Pipeline and tests | Not redistributed |
| Windows PowerShell 5.1 | Adapter host | OS component; not redistributed |
| .NET Framework / System.Drawing (GDI+) | Synthetic text rendering | OS component; not redistributed |
| Windows.Media.Ocr | Local OCR engine | OS component; not redistributed |
| Arial (system font) | Fixture rendering, used in place | Font binary must never be committed or redistributed |
| pypdf 6.14.2 (BSD-3-Clause) | Optional local Civil PDF text/page inspection | Installed from PyPI; not vendored or redistributed |
| Poppler `pdfinfo` / `pdftoppm` (GPL-2.0-or-later) | Optional local Civil PDF metadata/raster adapter | Host executable only; not redistributed |

Full identities, versions, hashes, and licence-evidence status are recorded
in `docs/guardrails/Screen2XYZ_Dependency_and_Licence_Register_v0.1.csv` and
in the retained evidence at
`runs/evidence/S2XYZ-CODEX-003/dependency_inventory.txt`.

No repository licence has been selected; see the Licensing section of the
README. Nothing in this file grants any rights in the repository content.
