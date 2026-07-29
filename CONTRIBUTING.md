# Contributing

This is a private, gate-controlled proof-of-concept. `AGENTS.md` is the
binding set of working rules for any contributor or coding agent; read it
first, then `docs/control/PROJECT_STATE.md` and `docs/control/NEXT_ACTION.md`
for the current authorized scope.

## Environment

- Windows 10/11 only (the renderer and OCR adapters use Windows PowerShell,
  GDI+, and Windows.Media.Ocr).
- Python 3.14+. Create the isolated venv exactly as
  documented in `docs/public/Screen2XYZ_Local_Run_Guide_v0.2.md`
  (`--without-pip`, no system site packages). The baseline, M1, M2, and Civil
  manual PNG workflow remain standard-library only. Civil vector-PDF
  inspection optionally uses the pinned `requirements-civil.txt`; install it
  only for that local workflow. Do not add or update third-party packages
  without updating the dependency register and guardrails review.

## Tests

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe tests\run_all.py
.\.venv\Scripts\python.exe tests_civil\run_civil_tests.py
```

The suite must report exactly 42 tests, 0 failures, 0 errors, 0 skipped
(`tests/run_all.py` enforces the count). Every test maps to a row in
`docs/testing/Screen2XYZ_Test_Matrix_v0.1.csv`; when you add a test, add its
matrix row and bump `EXPECTED_TEST_COUNT` in the same change.

## Hard rules

- Never modify or delete anything under `runs/evidence/` — retained evidence
  is immutable; new runs publish to new paths copy-on-write.
- Synthetic, locally generated data only. No real drawings, screenshots,
  customer or employer material, personal names, or absolute personal paths
  in tracked content (test T-PRI-004 enforces this).
- No network code, no service-specific scraping presets, no secrets.
- Do not claim capabilities or results without reproducible evidence.
