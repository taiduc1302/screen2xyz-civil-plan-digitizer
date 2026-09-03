# Screen2XYZ

Screen2XYZ is a controlled Windows research/product repository for local screen/OCR review, preliminary civil-plan digitization, and review-first civil quantity takeoff experimentation.

> **Current status:** baseline, M1, and M2 are preserved on private `main`. Civil Plan Digitizer feature work lives outside `main`. The current Claude markup-operator branch adds a **runnable single-sheet MCP takeoff pilot** on top of the review-first quantity domain. It is not merged, released, or estimator/Bluebeam certified, and it deliberately does not auto-approve bid quantities.

All PDF/image-derived coordinates, interpretations, elevations, and quantities are preliminary and require estimator/survey review appropriate to their use. The repository has no selected public licence and is not authorized for public release.

## Two Civil workflows

### Existing Civil Plan Digitizer

The existing Tk workspace provides local PDF/PNG intake, calibration, terrain point review, OCR/vector evidence, preliminary surfaces, audited project save, and reviewed downstream estimator handoffs:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_civil_plan_digitizer.ps1
```

See [`docs/civil-plan-digitizer/README.md`](docs/civil-plan-digitizer/README.md).

### Claude Code civil takeoff pilot

The takeoff pilot gives Claude Code (or another MCP host) a local auditable session without making the LLM the project database or approval authority.

It provides:

- `.s2a.json` single-sheet sessions tied to an **immutable source PDF SHA-256**;
- a separately registered **editable Bluebeam working PDF** whose full bytes may change as markups are saved while its underlying selected-page drawing must continue to match the source;
- DPI-independent proposal geometry in rendered PDF points;
- explicit scale **resolved vs independently verified** state;
- civil rules such as road widening, mill/overlay, ditch infill/regrade/relocation, gravel shoulder, driveway culvert/reinstatement, and QA-only anchor;
- line/polygon proposals with AI provenance, flags, evidence, questions, and correction history;
- a no-silent-miss rule-level scope ledger plus an explicit second visual instance pass;
- MCP sheet image/text/vector evidence, working-copy status, proposal/edit/QA tools;
- optional real OpenTakeoff MCP One-Click area tracing;
- local discovery of Bluebeam's MCP executable plus copy/paste Claude Code registration output;
- deterministic Bluebeam markup-plan export bound to the immutable source and registered Revu target;
- **no ordinary MCP tool for estimator approval or final bid publication**.

The pilot does **not** yet replace Bluebeam. A `*.bluebeam-markup-plan.json` file is geometry/traceability, not proof that native Revu measurements exist. Native Bluebeam measurements must be created on the registered working PDF through a currently proven Revu route and then read back from saved state.

The pilot is intentionally **one sheet / one compatible scale context / one Screen2XYZ writer**. Multi-document bid sets and per-viewport `ScaleRegion` support remain later slices.

## Install

From the repository root on Windows:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-civil.txt
$env:PYTHONPATH = (Resolve-Path .\src)
.\.venv\Scripts\python.exe -m screen2xyz_civil doctor
```

The operator sheet-image path uses pinned `pypdfium2` + Pillow, so a separate Poppler install is not required for this pilot. Tesseract is optional. Node/OpenTakeoff are optional for direct Claude line/polygon proposals but required for `auto_trace_area`.

Optional OpenTakeoff:

```powershell
npm install -g opentakeoff-mcp@0.9.68
.\.venv\Scripts\python.exe -m screen2xyz_civil doctor --deep
```

Screen2XYZ never auto-downloads OpenTakeoff at takeoff time. A custom local command can be supplied with `SCREEN2XYZ_OPENTAKEOFF_CMD`.

## Safe PDF layout: base vs Bluebeam working copy

Do **not** use one mutable PDF for both Screen2XYZ source evidence and Revu markups.

Use:

```text
IssuedForTender_BASE.pdf        <- immutable, exact SHA guarded by Screen2XYZ
ExampleRoad_TAKEOFF_WORKING.pdf    <- editable in Revu, native markups live here
ExampleRoad_S03.s2a.json           <- Screen2XYZ proposal/audit state
```

This prevents a normal Revu markup save from invalidating the controlled source revision.

## Create a Sheet 03 session

Create the session from the immutable base:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-init `
  "C:\Tenders\ExampleRoad\IssuedForTender_BASE.pdf" `
  --page 3 `
  --page-label 03 `
  --name "Example Road - Sheet 03" `
  --out "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json"
```

Use the actual PDF page number; it may differ from the printed sheet number.

### If starting from a clean drawing

Create/register a separate exact working copy:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-working-copy `
  --session "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json" `
  --out "C:\Tenders\ExampleRoad\ExampleRoad_TAKEOFF_WORKING.pdf"
```

### If improving an existing annotated takeoff PDF

Keep a clean immutable base and register the existing editable annotated PDF:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-register-working-copy `
  --session "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json" `
  --pdf "C:\Tenders\ExampleRoad\ExampleRoad_EXISTING_TAKEOFF.pdf"
```

The full file SHA may differ because of annotations/metadata. Registration requires the selected page's decoded drawing content, page boxes, and rotation to match the immutable source. A wrong revision is rejected.

Check status:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-status `
  --session "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json"
```

A later Revu save may set `modified_since_registration=true`; that is expected. `drawing_match=true` and `safe_for_bluebeam_operator=true` must remain true.

## Resolve and verify scale

For a true 1:250 single-scale pilot that the estimator independently checked against an authoritative drawing dimension:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-scale-ratio `
  --session "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json" `
  --ratio 250 `
  --basis "PLAN 1:250; independently checked against authoritative dimension in Revu" `
  --verified
```

Do not pass `--verified` solely because the title block prints `1:250`. `agent-calibrate` + `agent-verify-scale` provide the preferred two-point + independent second-dimension path when exact coordinates are available.

## Connect Claude Code

Let Screen2XYZ print exact registration commands for the current interpreter/session and, when safe, the locally discovered Bluebeam MCP executable:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-claude-config `
  --session "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json"
```

It always prints the `screen2xyz` local stdio registration. It withholds the Bluebeam operator route until a safe separate working PDF is registered. If Bluebeam's standard MCP executable is found and the working copy is safe, it prints a candidate `bluebeam-revu` registration command.

Bluebeam MCP discovery/registration is **not** `LIVE_TESTED` native measurement capability. In Revu, enable MCP, open the exact registered working PDF, verify `/mcp` shows the actual Bluebeam tool surface, then run the disposable Length+Area create/save/readback gate in [`BLUEBEAM_21_10_MEASUREMENT_ACCEPTANCE.md`](docs/integrations/BLUEBEAM_21_10_MEASUREMENT_ACCEPTANCE.md).

Manual Screen2XYZ registration, if needed:

```powershell
claude mcp add --transport stdio `
  --env "PYTHONPATH=C:\path\to\screen2xyz-civil-plan-digitizer\src" `
  screen2xyz -- `
  "C:\path\to\screen2xyz-civil-plan-digitizer\.venv\Scripts\python.exe" `
  -m screen2xyz_civil mcp `
  --session "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json"
```

Confirm with Claude Code `/mcp` or `claude mcp get screen2xyz`.

Then use [`prompts/CLAUDE_CODE_BLUEBEAM_TAKEOFF_PROMPT.md`](prompts/CLAUDE_CODE_BLUEBEAM_TAKEOFF_PROMPT.md). Full setup/operator detail is in [`docs/integrations/CLAUDE_CODE_MARKUP_OPERATOR.md`](docs/integrations/CLAUDE_CODE_MARKUP_OPERATOR.md).

## What Claude is expected to do on Sheet 03

The full prompt makes Claude inspect the clean source, reconcile existing markups from the registered Revu working copy, and systematically account for visible scope such as:

- North/South 300 mm driveway culverts as separate instances;
- gravel driveway reinstatement;
- ditch infill;
- 0.30 m gravel shoulder reaches;
- X-hatched full-structure road widening;
- 40 mm mill/overlay where actually shown;
- full-depth asphalt R&R only where its actual hatch/callout exists;
- separate ditch regrade vs relocation, withholding mixed/partial traces instead of guessing;
- `ANCHOR_ROADWORKS_EXTENT` as reference/QA only, never summed.

It must finish with no `UNSEARCHED` rule and then perform an instance-level visual pass because the machine ledger is currently rule-level.

## Export the Bluebeam markup plan

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-plan `
  --session "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json"
```

The saved plan includes the immutable-source/working-copy document contract plus canonical/OpenTakeoff geometry, preview quantity, flags, scale state, traceability fields, and native-Revu creation/readback policy.

## Validation

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe tests_civil\run_civil_tests.py
.\.venv\Scripts\python.exe -m tests_civil.benchmark_civil
.\.venv\Scripts\python.exe -m screen2xyz_civil doctor --deep
```

The current branch freezes the Civil suite at **236 discovered tests**. Separate Windows protocol smoke tests launch the same external stdio Screen2XYZ server an MCP host uses and real OpenTakeoff 0.9.68 against owned synthetic PDFs. Synthetic/unit/protocol results are pipeline evidence, not real-drawing accuracy.

The private acceptance gate is an estimator-reviewed plan such as Example Road Sheet 03 compared against Bluebeam, with expected-item coverage, silent misses, rule correctness, quantity error, geometry corrections, withheld items, working-copy integrity, and native Revu readback recorded without committing proprietary drawings.

## Claims and release boundary

- Synthetic tests are not evidence of real-plan accuracy.
- A green MCP test does not prove native Bluebeam measurement creation.
- A discovered Bluebeam MCP executable or successful Claude registration does not prove native Length/Area create/save/readback.
- The immutable Screen2XYZ source must never be used as the mutable Revu markup file.
- OpenTakeoff confidence is a review prioritizer, not estimator verification.
- `ANCHOR - DO NOT SUM` is QA/reference geometry and never a bid total.
- Scale-dependent QA requires both resolved and independently verified scale.
- Estimator review/approval and final bid publication remain human-only.
- Multi-sheet bid sets, per-viewport scales, general marked-PDF/Bluebeam interoperability, real-plan accuracy claims, default-branch merge, public licensing, and release remain separate gates.

Conceptual and preliminary estimating data only.