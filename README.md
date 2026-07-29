# Screen2XYZ

Screen2XYZ is a controlled Windows research/product repository for local
screen/OCR review and preliminary civil-plan digitization.

> **Current status:** the synthetic OCR baseline, M1 PNG review lab, and
> M2-Live watcher are merged on private `main`. The Civil Plan Digitizer is
> implemented and being stabilized on
> `feature/assisted-c03-validation`; it is not merged, released, or
> downstream-certified.

All PDF/image-derived coordinates and elevations are preliminary and require
estimator or survey review. They are not certified survey data. The repository
has no selected public licence and is not authorized for public release.

## Civil Plan Digitizer

The new review-first workspace provides:

- local PDF/PNG source intake, selected-page rendering, crop, scale, local
  origin, arbitrary East orientation, and independent second-distance check;
- reliable manual Existing/Design/Contour point entry;
- asynchronous local PDF text/vector extraction and bounded multi-angle
  Tesseract OCR, with Windows Media OCR as the local fallback;
- explainable numeric filtering, symbol proposals, candidate associations,
  alternatives, confidence/reasons, and explicit approve/reject/edit/merge;
- a persistent Point Cart with point numbering, sheet/revision metadata,
  undo/redo, bulk review, filtering, and reviewed contour-line vertices;
- schema-versioned atomic save/reopen with calibration and decision history;
- duplicate/conflict QA and approved-only, separate Existing/Design exports;
- atomically published, versioned handoffs with an eight-sheet estimator XLSX,
  AGTEK CSV, XYZ, NEZ, local GeoJSON, DXF, contour/breakline data, hashes,
  reports, and audit records;
- feature-flagged, separate Existing/Design preliminary TIN previews with
  reviewed boundaries, exclusions, breakline/no-cross barriers, triangle
  flags/disabling, point-sample cut/fill, and gated preliminary LandXML.

Automatic candidates are never approved silently. Editing or recalibrating
invalidates approval/export freshness. Utility, slab, slope, and drawing
metadata records are excluded from terrain exports by default.

### Install and launch

From the repository root on Windows:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-civil.txt
powershell -ExecutionPolicy Bypass -File .\run_civil_plan_digitizer.ps1
```

The manual PNG workflow remains standard-library/Tkinter only. Optional PDF
inspection uses pinned `pypdf`; PDF rendering requires a host-installed
Poppler `pdftoppm` on `PATH`. If installed, local Tesseract is preferred for
small rotated grade labels; Windows Media OCR remains the fallback. No drawing
is uploaded.

Read the [Civil Plan Digitizer guide](docs/civil-plan-digitizer/README.md),
[QA checklist](docs/civil-plan-digitizer/QA_CHECKLIST.md), and
[limitations](docs/civil-plan-digitizer/LIMITATIONS.md) before project use.

### Civil validation

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe tests_civil\run_civil_tests.py
.\.venv\Scripts\python.exe -m tests_civil.benchmark_civil
```

The civil suite currently contains 113 deterministic tests. The benchmark uses
synthetic rule fixtures only; its exact scores are not real-drawing OCR or
symbol accuracy. See
[BENCHMARK_RESULTS.md](docs/civil-plan-digitizer/BENCHMARK_RESULTS.md).

## Preserved product lines

| Area | Current scope |
|---|---|
| `src/screen2xyz_lab/` | Sealed synthetic OCR baseline, evidence, metrics, and CLI |
| `src/screen2xyz_m1/` | Explicit local PNG review/correction/approval and approved-only export |
| `src/screen2xyz_m2/` | Merged M2-Live local region watcher with owner-machine gate evidence |
| `src/screen2xyz_civil/` | Feature-branch Civil Plan Digitizer described above |
| `tests/` | 42 baseline tests |
| `tests_m1/` | 34 M1 tests |
| `tests_m2/` | 498 deterministic M2 tests plus 16 Windows integration tests |
| `tests_civil/` | 113 deterministic civil tests and synthetic benchmark |
| `runs/evidence/` | Immutable retained baseline/M1 evidence |
| `docs/control/` | Current authorization, project state, and next action |

The final standalone validation on 2026-07-29 passed baseline 42/42, M1
34/34, M2 deterministic 498/498, M2 Windows integration 16/16, Civil
113/113, retained-evidence verification, and compile. See the Civil worklog
and project state for the exact scope and remaining external gates.

## Baseline commands

The baseline setup and commands remain documented in
`docs/public/Screen2XYZ_Local_Run_Guide_v0.2.md`.

```powershell
$env:PYTHONPATH = "src"
py -3.14 tests\run_all.py
py -3.14 tests_m1\run_m1_tests.py
py -3.14 tests_m2\run_m2_tests.py
py -3.14 -m screen2xyz_lab.cli verify-evidence
```

## Claims and release boundary

- Synthetic tests and a synthetic OCR integration image are not evidence of
  real-plan accuracy.
- Local East/North values are not geodetic coordinates.
- The preliminary TIN is not an engineering surface; cut/fill samples are not
  volumes or quantities.
- AGTEK/Civil 3D/Kubla/LandXML compatibility is not certified.
- Real drawing validation, default-branch merge, licence selection, and public
  release require separate owner decisions.

Conceptual and preliminary estimating data only.
