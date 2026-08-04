# Screen2XYZ v2.7 final verification

Date: 2026-08-04  
Verified commit: `18c37096ae6480ef029aba66c1ff6a567100ac7a`  
Branch: `feature/v2.7-agtek-field-fixes`

This is the complete clean verification round required by the updated task
objective. It restarted from the beginning after the retained failed attempt in
`FAILED_FINAL_ROUND_1.md`.

## Round result

| Gate | Result |
|---|---|
| Application suite | 77/77 passed in 324.792 s |
| Civil suite | 113/113 passed in 4.102 s |
| M2 suite | 498/498 passed in 20.899 s |
| Tk functional smoke | Passed; fresh screenshots under `.lab_work/final-round-restart-1/tk` |
| Cache-disabled 220-row harness | 217/220 exact (98.636%); 3 safe failures; 0 wrong accepted; 0 false duplicates; SQLite/XLSX exact |
| Real cursor OCR | 12 correct, 0 wrong accepted, 0 rejected |
| Grey contrast fixtures | 3 correct, 0 wrong accepted, 0 rejected (contrast differences 96, 68, 44) |
| Combined AGTEK geometry | Passed: cursor 51.53 and North 2768.313 exact |
| Fresh PyInstaller bundle | Built and launch-smoked as `Screen2XYZ v2.7` |

## Harness details

- Tesseract: `v5.4.0.20240606`, resolved locally by the application adapter.
- Backend OCR cache: disabled.
- Ground truth: 220 rows; captured: 217; exactly correct: 217.
- OCR/parse failures: 3, all safe X-channel rejections in status fixtures.
- Wrong accepted / hallucinated: 0.
- False duplicate rows: 0.
- SQLite/XLSX exact parity: true, including the Status column.
- Duration: 3284.702 seconds.
- Accuracy margin above the 95% gate: 3.636 percentage points.
- One additional failure would produce 216/220 = 98.182%, still 3.182
  percentage points above the gate.

The complete generated metrics and failure list remain under
`.lab_work/final-round-restart-1/harness/`. The earlier failed 173/220 run and
its 44 wrong accepted values remain separately under `.lab_work/final-round-1/`
and are summarized in retained repository evidence.

## Bundle provenance

- Python: 3.14.6.
- PyInstaller: 6.21.0.
- Files: 1,010.
- Size: 46,828,509 bytes (44.659 MiB).
- Executable SHA-256:
  `06E846905916F8CC2BEC65B2E7D234FF11CC2DFC00857272A89807A97D7F8FA4`.
- Launch smoke window title: `Screen2XYZ v2.7`.
- Fresh paths: `.lab_work/final-round-restart-1/build/` and
  `.lab_work/final-round-restart-1/dist/Screen2XYZ-Setup/`.

## Scope limit

No automated test drives a live AGTEK GradeWork window. The fixtures reproduce
observed geometry synthetically; operator validation against the real viewer is
still outstanding. Results remain conceptual and preliminary unless validated
against an authoritative source.
