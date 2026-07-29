# Screen2XYZ M1 Guide — Opt-In Still-Image Capture Review Lab

M1 turns an explicitly user-selected PNG into reviewable XYZ candidates:
select → validate → OCR → parse → validate → classify → **human review,
correction, approval** → approved-only export with provenance. Nothing is
approved or exported automatically; no network is used.

## Quick start (Windows, from the repository root)

```powershell
$env:PYTHONPATH = "src"

# Open the local review interface (Tkinter, standard library only)
.\.venv\Scripts\python.exe -m screen2xyz_m1.cli review

# Run the M1 stable test suite (expected: 34/34, exit 0)
.\.venv\Scripts\python.exe tests_m1\run_m1_tests.py

# Generate/verify the evaluation fixture and run the controlled evaluation
.\.venv\Scripts\python.exe -m screen2xyz_m1.cli generate-eval
.\.venv\Scripts\python.exe -m screen2xyz_m1.cli evaluate
```

## Review workflow

1. **Select PNG…** — an explicit file-picker choice is the only way an
   image enters the system. Intake validates extension, PNG signature and
   chunk structure, byte size (≤25 MB), and dimensions (≤8192×8192,
   ≤40 MP), and records the file's SHA-256. The source file is never
   modified or copied.
2. The image flows through the **unchanged baseline pipeline**
   (`screen2xyz_lab`): Windows OCR → labelled parser → range validation →
   duplicate/stale classification.
3. Each image becomes one **candidate** showing raw OCR (immutable),
   parsed LAT/LON/ELEV, validation state, and reason codes.
4. **Correct** — edited values are stored separately from the original
   parse and pass through the same parser/validator; invalid corrections
   are refused with reason codes.
5. **Approve / Reject** — explicit per-candidate decisions. A candidate
   with unresolved validation codes cannot be approved until corrected.
6. **Export approved** — writes `approved_points.csv` and
   `approved_points.xyz` (deterministic order, formula-safe CSV) plus the
   provenance package.

## Outputs

Each run writes only to `.lab_work/m1_runs/<run_id>/` (ignored by Git):
`raw/<candidate>.json` (immutable raw OCR + source identity),
`candidates.json`, `run_summary.json`, `approved_points.csv`,
`approved_points.xyz`, and `evidence_manifest_sha256.txt` (SHA-256 of every
artifact). The vertical reference of user images is recorded as
`UNSPECIFIED_LOCAL` — no datum is claimed.

## Controlled evaluation

`test_data/synthetic/m1_eval_v0.1/` (24 scenarios, seed 20260718) varies
canvas size, contrast, glyph softness, layout, noise text, signs, and
malformed/duplicate/stale/ambiguous cases. Retained results:
`runs/evidence/S2XYZ-M1-001/` — 15/15 exact triplets on expected-valid
scenarios, 0 false rejects, and one deliberate challenge false-accept
(letter `O` read as `0`) retained as evidence for why human review is
mandatory. Synthetic results only; not real-world accuracy.

## Optional external AI assistance

Disabled by default (`NullAssistant`). The provider seam
(`screen2xyz_m1.assist`) can only ever produce a human-readable note from
sanitized OCR text and reason codes — never approve, export, or see image
bytes — and requires explicit opt-in. No live provider is implemented; see
`M1_IMPLEMENTATION_REPORT.md`.

## Limitations and troubleshooting

- Windows-only (Windows.Media.Ocr, PowerShell adapters); en-US labels
  `LAT`/`LON`/`ELEV` only; decimal-point numbers only.
- Any unlabelled extra number in the image causes rejection
  (`EXTRA_NUMERIC_FIELD`) — crop the selection to the reading, or correct
  and approve manually.
- OCR confusions (`O`↔`0`, `I`↔`1`) can produce plausible wrong values or
  spurious rejections; the review step exists precisely for this.
- If OCR fails (`OCR_FAILURE`), confirm the file is a valid PNG and the
  en-US OCR language pack is installed.
- If the UI does not open, verify Tkinter: `python -m tkinter`.

Conceptual and preliminary estimating data only.
