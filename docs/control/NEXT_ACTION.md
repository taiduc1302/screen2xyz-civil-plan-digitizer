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

The frozen Civil suite is currently **418 discovered tests** on `task/plan-layer-extraction` (220 at CI run #171; 255 after `bluebeam_bridge.py`; 322 after `plan_layers.py`, `earthwork.py` and the twelve added rules; 373 after `sheet_pass.py` and `cross_sections.py`; 378 with the pixel-area cross-check; 396 with `fill_layers.py`; 401 with pattern separation and per-region `polygon_health`; 405 with the zero-length-edge fix to `polygon_health`; 415 with `symbols.py`; 418 with `clip_polygon_x` returning simple parts - a concave region cut across its mouth no longer comes back as one self-touching ring). **CI is green on this branch**: `workflow_dispatch` run 33727960634 (2026-09-03) passed all three jobs at 405 tests, after one sanitization fix (an employer-identifying colour nickname in the inventory prose). Synthetic/protocol success still does **not** prove Example Road accuracy on the estimator's Revu installation.

### Since 2026-09-03: what a takeoff session now calls instead of re-deriving

- **Step 0 of every set: `cad_layers.document_regime(pdf)`.** The DEMO-001
  tender PDF is a direct Civil 3D export and carries 141 CAD layer names on
  its drawing objects - `P_Curb`, `P_Pavement edge`, `P_Ditch bottom`,
  `P_Culv`, `STM-MH-PRO`, `E_Gas`, `Shading 245 (50%)`. The day of raster
  tracing, radius fitting and deleting happened on a file that named the
  curb. `layer_dictionary` / `hints_present` read the names against the
  `P_`/`E_`, `-PRO`/`-EXI` and NCS conventions; `objects_on_layer` returns
  a layer's geometry in the raw frame, outlines separated from strokes;
  `feature_identity.CAD_LAYER_NAME` names a feature once the set's
  dictionary is confirmed against the legend. The firehall civil set is
  the other regime: a "Print To PDF" re-print with 9,033 vectors and no
  names (`REPRINT_LOST_LAYERS` - ask for the direct export). Text on both
  sets is glyph outlines (`OUTLINE_TEXT`). Approach across sets:
  `docs/integrations/TAKEOFF_APPROACH_ACROSS_DRAWING_SETS.md`. Suite 548.

- Three rules added once the whole set had been measured and real scope had nowhere to go: `PEDESTRIAN_ASPHALT_PAD` (POLYGON), `EXISTING_CULVERT_REMOVAL` (LINE), `EXISTING_HEADWALL_REMOVAL` (COUNT). Twenty-five rules: 13 LINE, 9 POLYGON, 3 COUNT.
- `symbols.find_circles(pdf, page_index, viewport, stroke=(0,0,0))` - circle symbols found in the vector content by shape, size and colour, returned in the raw frame and grouped, with `crop_symbol` for the label beside each. On DEMO-001-12 PLAN it finds exactly three 4.2 pt black circles, labelled D1, D2, D3 in the crops - the manhole count the ledger had as "2 marked, likely 3" - and the same three in DEMO-001-11's profile.
- `markup_view.render_over_drawing(pdf, page_index, shapes, out_png, window=..., zoom=...)` - the second half of the visual check: a read-back path drawn over the base PDF in a window you choose, for the two cases the host thumbnail cannot cover (a point marker, which it zooms into until no context is left, and a line-width error on a long band). It also encodes the frame trap: `draw_polyline` uses unrotated page coordinates `(x, H-y)`, `get_pixmap(clip=...)` uses displayed coordinates `(W-x, y)`.
- **Blocking, before anything else: after every host write, `create_markup_thumbnail(uniqueMarkupId=...)` and look at the image.** It draws the markup in place on the sheet from the live document. Numeric self-consistency (areas reconcile, zero overlap, `polygon_health` clean, sum equals union) proves a polygon valid, never correctly placed - 13 markups passed all of it while tracing curb-return arcs and gas lines and were deleted. `PLAN_SHEET_LAYER_METHOD.md` step 10.
- `fill_layers.split_pavement(pdf, page_index, viewport)` - **for finding patterns, not for a boundary** (its raster edge cost 16-21 % on three items; boundaries come from the drawing's vector content) - the grey fill and every hatch traced as *regions*, separated by the exact colour of the pattern drawn on them (widening 127, full-depth asphalt R&R 178, unidentified 128/153 - censused from the sheet 04 legend), each with raw-frame polygons, two independent areas, `pattern_fractions`, and the repository's own `polygon_health` verdict; unhealthy regions are excluded from totals. Its "0.03% agreement with the host on sheet 05" was agreement with **another raster trace** and is not validation. Its real wins were classification, not geometry: 77 sq m of full-depth asphalt R&R hidden inside the sheet 05 mill-and-overlay polygon, and the sheet 04 clean-segment polygons overlapping each other. Its intersection-zone geometry was written and **deleted the same day** after a render showed it tracing curb-return arcs and gas lines - `docs/integrations/FILL_LAYER_EXTRACTION.md`.
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