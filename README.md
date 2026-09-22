> **Public source - September 2026:** This branch retains its own experimental
> runtime and is not promoted to production by the privacy cleanup.
> For the newsletter MCP/vector work, start with the
> [issue 4 reader guide](docs/public/ISSUE_4_READER_GUIDE.md).
> Read [the current audit](PUBLIC_RELEASE_AUDIT.md), not old private-scope notes.

# Screen2XYZ

Local Windows research tooling for screen/OCR review, preliminary civil-plan
digitization, and separately developed AI-assisted quantity-takeoff experiments.

**Reading Applied AI for Estimating, issue 4?** Start with the
[issue 4 reader guide](docs/public/ISSUE_4_READER_GUIDE.md). It distinguishes the
Civil baseline from the experimental MCP branches and links to a specific
reviewed source snapshot. This repository is not a packaged reproduction of
the article's demonstration.

## Repository status

Checked on 2026-09-22: the repository is publicly visible. Its configured default
branch is `feature/assisted-c03-validation`; the maintained integration branch
is `main`. Branch names are not release or accuracy certifications.

- The Civil baseline provides the point/terrain workflow below.
- MCP operator and vector-takeoff development is on separate branches. It has
  not been silently merged into this baseline. See the reader guide.
- All derived coordinates, elevations and quantities require qualified human
  review. They are not certified survey data or approved bid quantities.
- No project-wide public licence has been selected for this baseline. Public
  visibility does not establish unrestricted reuse rights. See
  [origin/provenance](ORIGIN_PROVENANCE.md) and
  [third-party notices](THIRD_PARTY_NOTICES.md).
- Publication/privacy verification is separate from runtime validation. Read
  [PUBLIC_RELEASE_AUDIT.md](PUBLIC_RELEASE_AUDIT.md) for the scope and remaining
  checks; no automated PASS is a release authorization.

## Civil Plan Digitizer baseline

The review-first workspace provides:

- local PDF/PNG intake, selected-page rendering, crop, scale, local origin,
  arbitrary East orientation, and an independent second-distance check;
- manual Existing/Design/Contour point entry and local PDF text/vector evidence;
- optional bounded OCR, explainable proposals and explicit approve/reject/edit;
- a persistent Point Cart, point numbering, sheet/revision metadata, undo/redo,
  filtering and reviewed contour-line vertices;
- versioned project save/reopen, calibration history and duplicate/conflict QA;
- separate approved-only Existing/Design exports and versioned estimator
  handoffs: XLSX, CSV, XYZ, NEZ, local GeoJSON, DXF and audit records;
- gated preliminary TIN previews and LandXML experiments, not certified
  engineering surfaces or validated downstream imports.

Automatic candidates are never approved silently. Editing or recalibrating
invalidates approval/export freshness. Utility, slab, slope and drawing metadata
records are excluded from terrain exports by default.

## Install and launch the baseline

From a checkout of this branch on Windows:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-civil.txt
powershell -ExecutionPolicy Bypass -File .\run_civil_plan_digitizer.ps1
```

The manual PNG workflow uses the standard library and Tkinter. Optional PDF
inspection uses the branch's requirements; baseline PDF rendering needs
host-installed Poppler `pdftoppm` on PATH. Tesseract and Windows Media OCR
availability must be checked on the operator's machine. Requirements and
rendering routes on the MCP branches differ; do not mix their setup instructions.

Read the [operator guide](docs/civil-plan-digitizer/README.md),
[QA checklist](docs/civil-plan-digitizer/QA_CHECKLIST.md), and
[limitations](docs/civil-plan-digitizer/LIMITATIONS.md) before project use.

## Validation

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe tests\run_all.py
.\.venv\Scripts\python.exe tests_m1\run_m1_tests.py
.\.venv\Scripts\python.exe tests_m2\run_m2_tests.py
.\.venv\Scripts\python.exe tests_civil\run_civil_tests.py
.\.venv\Scripts\python.exe -m screen2xyz_lab.cli verify-evidence
```

The retained 2026-07-29 handoff reports baseline 42, M1 34, M2 deterministic
498, M2 Windows integration 16 and Civil 113 passing tests. These are historical,
branch-specific results, not a fresh test run or a real-drawing accuracy claim.
Consult the exact commit's CI results and the
[synthetic benchmark boundary](docs/civil-plan-digitizer/BENCHMARK_RESULTS.md).

## Public data and safety boundary

Use only synthetic or explicitly authorized demonstration inputs. Do not commit
employer/client drawings, real-project exports, credentials, personal paths or
local agent transcripts. Keep original evidence immutable and use a separate
editable working PDF for native markups. Estimator approval remains human-only.

The [security policy](SECURITY.md) explains private reporting and the difference
between the inherited parent-repository audit and a current all-ref audit.

Conceptual and preliminary estimating data only.
