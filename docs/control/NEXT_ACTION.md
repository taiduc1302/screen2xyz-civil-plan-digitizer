# Next Action

## Current stage: owner-machine Claude Code + Bluebeam acceptance

The runnable single-sheet vertical slice is implemented on
`feature/claude-markup-operator-real3`.

The branch now has:

- source-SHA-bound `.s2a.json` session state;
- a governed **immutable base PDF + separate editable Bluebeam working PDF** model;
- working-copy drawing-fingerprint validation that tolerates ordinary markup/metadata byte changes but rejects a wrong drawing/revision;
- independent scale resolution/verification;
- civil takeoff rules and no-silent-miss scope ledger;
- external Screen2XYZ MCP stdio server for Claude Code;
- portable PDFium sheet rendering;
- real OpenTakeoff 0.9.68 MCP/One-Click integration;
- proposal/edit/evidence/question/QA tools;
- Bluebeam markup-plan export bound to the immutable source and registered Revu target;
- `doctor`, `agent-working-copy`, `agent-register-working-copy`, `agent-status`, and `agent-claude-config`;
- Claude Code runbook, native Revu acceptance gate, and full civil-takeoff operator prompt.

The frozen Civil suite is currently **405 discovered tests** on `task/plan-layer-extraction` (220 at CI run #171; 255 after `bluebeam_bridge.py`; 322 after `plan_layers.py`, `earthwork.py` and the twelve added rules; 373 after `sheet_pass.py` and `cross_sections.py`; 378 with the pixel-area cross-check; 396 with `fill_layers.py`; 401 with pattern separation and per-region `polygon_health`; 405 with the zero-length-edge fix to `polygon_health` - a ring that repeats its first vertex or a consecutive duplicate vertex no longer reads as a self-intersection). Green locally in `.venv-operator`; not re-run in CI. Synthetic/protocol success still does **not** prove Example Road accuracy on the estimator's Revu installation.

### Since 2026-09-03: what a takeoff session now calls instead of re-deriving

- `fill_layers.split_pavement(pdf, page_index, viewport)` - the grey fill and every hatch traced as *regions*, separated by the exact colour of the pattern drawn on them (widening 127, full-depth asphalt R&R 178, unidentified 128/153 - censused from the sheet 04 legend), each with raw-frame polygons, two independent areas, `pattern_fractions`, and the repository's own `polygon_health` verdict; unhealthy regions are excluded from totals. Validated on sheet 05 against the host polygons to 0.03% on widening. It measured the Example Road junction intersection on sheet 04 (1 328 sq m, previously UNSEARCHED, of which 194 sq m is full-depth asphalt R&R) and the Example Avenue ends on sheet 06, found the sheet 04 clean-segment host polygons overlapping each other (fixed by the owning session), and found 77 sq m of full-depth asphalt R&R inside the sheet 05 mill-and-overlay polygon - `docs/integrations/FILL_LAYER_EXTRACTION.md`.
- `sheet_pass.sheet_opening_pass(pdf, page_index, viewport=...)` - method steps 0-4 for any sheet in one call; reports layers present, unnamed ones, and whether the sheet is rasterised. `derive_title_block_baseline` regenerates the furniture floor for another drawing set.
- `cross_sections.extract_panels / render_panel / measure_sections` - both surfaces and the subgrade of every cross-section panel from the PDF vectors, scale verified from the grid, areas per panel, volumes across sheets once the operator names the panels from their thumbnails. Applied to DEMO-001-09/10: fourteen panels, no blockers - `docs/integrations/CROSS_SECTION_EXTRACTION.md`.
- `sheet_pass.pixel_area_m2 / fill_or_hatch` - the pixel-count cross-check the ledger has been doing by hand, and the two-DPI test that says whether a colour is a fill (pixel area valid) or a hatch (it is not).
- The two-working-copy question for sheets 04-06 is closed in `PLAN_SHEET_LAYER_METHOD.md`: the other copy holds reference geometry only.
- The branch is on GitHub as `origin/task/plan-layer-extraction`; two sessions commit to the same local clone, so `git log` and `git status` before each commit.

## Exactly one recommended next action

After current-head CI is green, run a private owner-machine acceptance on the actual Example Road Sheet 03 before merging PR #8 or generalizing the architecture.

### A. Prepare the owner workstation

Checkout/pull `feature/claude-markup-operator-real3`, then from the repository root:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-civil.txt
npm install -g opentakeoff-mcp@0.9.68
$env:PYTHONPATH = (Resolve-Path .\src)
.\.venv\Scripts\python.exe -m screen2xyz_civil doctor --deep
```

Required Screen2XYZ checks must pass. OpenTakeoff must report a compatible real MCP probe if `auto_trace_area` will be used. A discovered Bluebeam executable is only a candidate route and remains `NOT LIVE_TESTED` at this point.

### B. Establish immutable base and editable Revu working PDF

Do **not** point Screen2XYZ at the same PDF that Revu will save markups into.

Keep a controlled local base such as:

`C:\Tenders\ExampleRoad\IssuedForTender_BASE.pdf`

Create the private Sheet 03 session from that immutable file:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-init `
  "C:\Tenders\ExampleRoad\IssuedForTender_BASE.pdf" `
  --page <actual-pdf-page-number> `
  --page-label 03 `
  --name "Example Road - Sheet 03" `
  --out "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json"
```

If starting from a clean plan, create a working copy:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-working-copy `
  --session "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json" `
  --out "C:\Tenders\ExampleRoad\ExampleRoad_TAKEOFF_WORKING.pdf"
```

If the existing AI markups already live in a separate editable PDF and the goal is to improve them, register that file instead:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-register-working-copy `
  --session "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json" `
  --pdf "C:\Tenders\ExampleRoad\ExampleRoad_EXISTING_TAKEOFF.pdf"
```

Registration must report `drawing_match=true` and `safe_for_bluebeam_operator=true`. A different full SHA is acceptable for an existing annotated file; a different underlying selected-page drawing is not.

Do not commit the base PDF, working PDF, generated private session, or evidence to GitHub.

### C. Resolve **and independently verify** the Sheet 03 plan scale

Do not mark the scale verified just because the title block prints `1:250`. Use an authoritative known dimension/scale-bar check in Revu. Prefer `agent-calibrate` + `agent-verify-scale` when exact points are available.

If the worked region really is one verified 1:250 plan context, the simpler human assertion path is allowed only after that independent check:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-scale-ratio `
  --session "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json" `
  --ratio 250 `
  --basis "Sheet 03 PLAN 1:250; independently checked in Revu against authoritative dimension" `
  --verified
```

If Sheet 03 contains another measurement viewport/scale that conflicts with the pilot region, do not finalize quantities across it with the page-wide scale.

### D. Generate Claude Code MCP registration commands

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-claude-config `
  --session "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json"
```

Run the emitted `screen2xyz` registration command. The command only presents the Bluebeam operator route when a separate safe working PDF is registered. If the local Bluebeam MCP executable is found, run the candidate `bluebeam-revu` registration only with Revu MCP enabled and the **registered working PDF** active.

In Claude Code, verify `/mcp` before giving the takeoff prompt. The immutable base PDF must never be the active file being mutated by the Bluebeam operator.

### E. Prove the native Bluebeam route before production creation

If Claude Code exposes Bluebeam tools, follow
`docs/integrations/BLUEBEAM_21_10_MEASUREMENT_ACCEPTANCE.md` on a disposable clone of the registered working copy:

1. inspect the actual advertised Bluebeam tool/schema surface;
2. confirm the working-copy/drawing contract and active PDF;
3. establish/verify scale in the target measurement context;
4. create one native Length;
5. save/read it back and confirm native intent/type, unit, live Revu-computed quantity, geometry/metadata where exposed;
6. create one native Area;
7. save/read it back with the same checks;
8. classify the route `LIVE_TESTED` only if both succeed end to end.

If the gate fails, do not bypass Bluebeam security or fake native measurements. Use Screen2XYZ for reviewed proposal geometry and the proven Revu GUI measurement path **on the working PDF**, then read back the saved result where available.

### F. Run the full Claude takeoff task

From the repository root, give Claude Code the contents of:

`prompts/CLAUDE_CODE_BLUEBEAM_TAKEOFF_PROMPT.md`

The target Sheet 03 pass must explicitly cover at least:

- North and South 300 mm driveway culverts as separate instances;
- North and South gravel driveway reinstatement;
- ditch infill;
- 0.30 m gravel shoulder reaches;
- X-hatched full-structure road widening;
- 40 mm mill/overlay where actually shown;
- full-depth asphalt R&R only where its specific hatch/callout is present;
- separate ditch regrade vs relocation, with mixed/partial work withheld rather than guessed;
- `ANCHOR_ROADWORKS_EXTENT` as reference/QA only, never summed.

Before stopping, Claude must have no `UNSEARCHED` rule in `scope_status`, must do an instance-level visual pass so one proposal cannot hide a second culvert/reach, and must confirm `bluebeam_working_copy_status.drawing_match=true` after any native Revu saves.

### G. Compare against estimator-reviewed Bluebeam gold

Record privately:

- expected scope instances;
- proposed / withheld / not-present / not-applicable status;
- silent misses;
- wrong-rule classifications;
- geometry corrections required;
- Screen2XYZ quantity vs reviewed Revu quantity;
- whether OpenTakeoff helped or hurt each geometry;
- whether native Bluebeam create/save/readback matched the intended proposal;
- working-copy drawing-integrity result before/after Revu work;
- any tool/schema/scale/Studio blocker.

Initial acceptance target for this sheet:

- **0 critical silent misses** for the agreed Sheet 03 scope;
- **0 `ANCHOR` quantities summed**;
- **0 unresolved/mixed/partial items presented as final**;
- **0 wrong-scale quantities presented as QA-complete**;
- **0 native edits to the immutable source PDF**;
- `drawing_match=true` for the registered working PDF after markup saves;
- every native Bluebeam measurement created by automation read back from saved state;
- simple line/area quantities close enough to the reviewed Bluebeam result that any material disagreement is investigated rather than hidden in an average score.

## After the acceptance result

- If the Sheet 03 pilot passes, the next development slice is multi-document bid-set + per-viewport `ScaleRegion` support and a dedicated takeoff review UI.
- If it fails, fix the observed failure class first and add a regression test; do not compensate by weakening blockers or silently accepting misses.
- Keep Draft PR #8 unmerged until the owner explicitly accepts or waives this gate.
- Draft PR #9 remains CI-only and must never be merged.