# Screen2XYZ

Screen2XYZ is a controlled Windows research/product repository for local
screen/OCR review, preliminary civil-plan digitization, and review-first civil
quantity takeoff experimentation.

> **Current status:** baseline, M1, and M2 are preserved on private `main`.
> Civil Plan Digitizer feature work lives outside `main`. The current Claude
> markup-operator branch adds a **runnable single-sheet MCP takeoff pilot** on
> top of the review-first quantity domain. It is not merged, released, or
> estimator/Bluebeam certified, and it deliberately does not auto-approve bid
> quantities.

All PDF/image-derived coordinates, interpretations, elevations, and quantities
are preliminary and require estimator/survey review appropriate to their use.
The repository has no selected public licence and is not authorized for public
release.

## Two Civil workflows

### Existing Civil Plan Digitizer

The existing Tk workspace provides local PDF/PNG intake, calibration, terrain
point review, OCR/vector evidence, preliminary surfaces, audited project save,
and reviewed downstream estimator handoffs. Launch it with:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_civil_plan_digitizer.ps1
```

See [`docs/civil-plan-digitizer/README.md`](docs/civil-plan-digitizer/README.md)
for the terrain/point workflow.

### Claude Code civil takeoff pilot

The new pilot is intentionally separate from the old terrain UI. It gives
Claude Code (or another MCP host) a local, auditable takeoff session without
making the LLM the project database or approval authority.

It currently provides:

- `.s2a.json` single-sheet takeoff sessions tied to source PDF SHA-256;
- resolution-independent geometry stored in rendered PDF points;
- explicit scale **resolved vs independently verified** state;
- the civil takeoff rule catalogue (`ROAD_WIDENING_FULL_STRUCTURE`,
  `DITCH_INFILL`, `DRIVEWAY_CULVERT_300`, `GRAVEL_SHOULDER_030`, etc.);
- line/polygon proposals with AI provenance, flags, evidence, questions, and
  correction history;
- MCP `view_sheet`, PDF text/vector evidence, proposal/edit/QA tools;
- optional real OpenTakeoff MCP `one_click` area tracing when installed;
- deterministic Bluebeam markup-plan export with Subject/Label/Comment
  traceability and an explicit `ANCHOR - DO NOT SUM` policy;
- **no ordinary MCP tool for estimator approval or final bid publication**.

The pilot does **not** yet replace Bluebeam. A `*.bluebeam-markup-plan.json`
file is a geometry/traceability plan, not proof that native Revu measurements
exist. Native Bluebeam measurements must still be created through a currently
proven Revu MCP path or the GUI and then read back from saved state.

The pilot is also intentionally **one sheet / one compatible scale context**.
Do not use one page-wide scale to finalize quantities across mixed plan,
profile, and detail viewports. Multi-document bid-set + `ScaleRegion` support
remains a later product slice.

## Install

From the repository root on Windows:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-civil.txt
$env:PYTHONPATH = (Resolve-Path .\src)
.\.venv\Scripts\python.exe -m screen2xyz_civil doctor
```

The Claude/operator sheet-image path uses the pinned `pypdfium2` + Pillow
packages in `requirements-civil.txt`, so a separate Poppler install is not
required for this pilot. Existing legacy Civil rendering can still use Poppler
`pdftoppm` when it is already available. Tesseract is optional. Claude Code is
reported by `doctor` as the optional operator client. OpenTakeoff/Node are
optional for manual Claude line/polygon proposals but required for
`auto_trace_area`.

Optional OpenTakeoff setup. The Windows CI protocol lane pins the reviewed
public npm package version below so the operator environment is reproducible:

```powershell
npm install -g opentakeoff-mcp@0.9.68
.\.venv\Scripts\python.exe -m screen2xyz_civil doctor --deep
```

Screen2XYZ never auto-downloads OpenTakeoff at takeoff time. An exact local
OpenTakeoff command can be supplied with `SCREEN2XYZ_OPENTAKEOFF_CMD`.

## Create a Claude takeoff session

Example for a PDF page whose printed sheet label is `03`:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-init `
  "C:\Tenders\Project\IssuedForTender.pdf" `
  --page 3 `
  --page-label 03 `
  --name "Project - Sheet 03" `
  --out "C:\Tenders\Project\Project_S03.s2a.json"
```

Then resolve **and independently verify** the relevant scale. For a true 1:250
single-scale pilot that the estimator has separately checked against an
authoritative drawing dimension:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-scale-ratio `
  --session "C:\Tenders\Project\Project_S03.s2a.json" `
  --ratio 250 `
  --basis "PLAN 1:250; independently checked against authoritative dimension in Revu" `
  --verified
```

Do not pass `--verified` solely because the title block prints `1:250`.
`agent-calibrate` and `agent-verify-scale` provide a two-point + independent
second-dimension path when exact coordinates are available.

## Connect Claude Code

Screen2XYZ serves the session over local MCP stdio. Register it with Claude
Code using the current documented option order: MCP options first, then the
server name, then `--`, then the subprocess command. Embed `PYTHONPATH` in the
MCP registration so future Claude sessions do not depend on a temporary shell
environment:

```powershell
claude mcp add --transport stdio `
  --env "PYTHONPATH=C:\path\to\screen2xyz-civil-plan-digitizer\src" `
  screen2xyz -- `
  "C:\path\to\screen2xyz-civil-plan-digitizer\.venv\Scripts\python.exe" `
  -m screen2xyz_civil mcp `
  --session "C:\Tenders\Project\Project_S03.s2a.json"
```

Confirm the connection with Claude Code `/mcp` or:

```powershell
claude mcp get screen2xyz
```

Then use
[`prompts/CLAUDE_CODE_BLUEBEAM_TAKEOFF_PROMPT.md`](prompts/CLAUDE_CODE_BLUEBEAM_TAKEOFF_PROMPT.md).
Full operator/setup detail is in
[`docs/integrations/CLAUDE_CODE_MARKUP_OPERATOR.md`](docs/integrations/CLAUDE_CODE_MARKUP_OPERATOR.md).

## Export the Bluebeam markup plan

After Claude has proposed/corrected and QA'd the sheet:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-plan `
  --session "C:\Tenders\Project\Project_S03.s2a.json"
```

The output contains canonical and render/OpenTakeoff geometry, preview quantity,
flags, scale state, traceability fields, and the native-Revu creation/readback
policy for each item.

## Validation

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe tests_civil\run_civil_tests.py
.\.venv\Scripts\python.exe -m tests_civil.benchmark_civil
.\.venv\Scripts\python.exe -m screen2xyz_civil doctor --deep
```

The current branch freezes the Civil suite at **210 discovered tests**. Tests
that exercise the real OpenTakeoff process or the external Claude-style stdio
operator path are deliberately skipped in the ordinary deterministic lane and
are enabled in the separate Windows protocol smoke lane. Synthetic/unit/MCP
results are pipeline and contract evidence, not real-drawing takeoff accuracy.
The private acceptance gate is an estimator-reviewed plan such as King Road
Sheet 03 compared against Bluebeam, with expected-item coverage, silent misses,
rule correctness, quantity error, geometry corrections, withheld items, and
native Revu readback recorded without committing the proprietary drawing.

See
[`RUNTIME_OPERATOR_TEST_MODEL.md`](docs/integrations/RUNTIME_OPERATOR_TEST_MODEL.md)
for the larger bid-set/scale-region/runtime/test architecture.

## Preserved product lines

| Area | Current scope |
|---|---|
| `src/screen2xyz_lab/` | Sealed synthetic OCR baseline, evidence, metrics, CLI |
| `src/screen2xyz_m1/` | Explicit local PNG review/correction/approval workflow |
| `src/screen2xyz_m2/` | M2-Live local watcher product line |
| `src/screen2xyz_civil/` | Civil Plan Digitizer + review-first takeoff/MCP pilot |
| `tests/` | 42 baseline tests |
| `tests_m1/` | 34 M1 tests |
| `tests_m2/` | 498 deterministic M2 tests plus Windows integration tests |
| `tests_civil/` | 210 discovered Civil tests on the Claude operator branch, with live lanes gated by environment |
| `docs/control/` | Authorization, current state, and next gate |

## Claims and release boundary

- Synthetic tests are not evidence of real-plan accuracy.
- A green MCP test does not prove native Bluebeam markup creation.
- OpenTakeoff confidence is a review prioritizer, not estimator verification.
- `ANCHOR - DO NOT SUM` is QA/reference geometry and never a bid total.
- Scale-dependent QA requires both resolved and independently verified scale.
- Estimator review/approval and final bid publication remain human-only.
- Multi-sheet bid sets, per-viewport scales, general marked-PDF/Bluebeam
  interoperability, real-plan accuracy claims, default-branch merge, public
  licensing, and release remain separate gates.

Conceptual and preliminary estimating data only.