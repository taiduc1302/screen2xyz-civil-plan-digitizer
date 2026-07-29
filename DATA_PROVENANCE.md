# Data Provenance

All data in this repository is synthetic and locally generated. No real
drawings, screenshots, survey data, project records, or customer material is
present, and automated tests enforce this boundary.

## Authoritative registers

- `docs/guardrails/Screen2XYZ_Dataset_and_Licence_Register_v0.1.csv` — every
  dataset (the 60-image fixture and the OCR preflight probe), with SHA-256
  identities, generation commit, seed, classification, and redistribution
  status.
- `docs/guardrails/Screen2XYZ_Dependency_and_Licence_Register_v0.1.csv` —
  every runtime dependency (CPython, Windows PowerShell, .NET Framework,
  System.Drawing/GDI+, Windows.Media.Ocr, the in-place Arial system font),
  with licence evidence status. No third-party Python package is used or
  redistributed.

## How the fixture is produced

`test_data/synthetic/s2xyz_fixture_v0.1/` is generated deterministically from
seed `20260715` by `src/screen2xyz_lab/fixture.py` plus the Windows renderer
adapter. `python -m screen2xyz_lab.cli generate` verifies an existing fixture
byte-for-byte against the deterministic generation (ground truth, render
jobs, manifest, and every PNG hash) instead of regenerating it. Images
contain only the allowlisted PNG chunk types (`IHDR`, `sRGB`, `gAMA`,
`pHYs`, `IDAT`, `IEND`), so no textual or EXIF-style metadata can be
embedded.

Three image pairs (S004/S020, S024/S040, S044/S060) are intentionally
byte-identical: the stale and duplicate copies of the same base value share
a render variation, and the pipeline classifies them differently (STALE vs
DUPLICATE) purely from temporal order — demonstrating that classification
depends on sequence context, not image content.

## What "synthetic" does and does not support

Results in `runs/evidence/S2XYZ-CODEX-003/` characterize OCR of clean,
machine-rendered text on one Windows machine only. They are not evidence of
real-world screenshot accuracy, cross-machine robustness, or production
readiness. Output classification everywhere: *Conceptual and preliminary
estimating data only.*
