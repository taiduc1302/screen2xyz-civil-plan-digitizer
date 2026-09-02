# Claude Code civil-markup operator — local pilot runbook

Status: private single-sheet pilot. The goal is a controlled path where Claude Code can inspect one civil plan sheet, create or improve **proposal geometry**, and hand a deterministic markup plan to the live Bluebeam workflow. Final Bluebeam quantity approval remains human-only.

## What is runnable now

The pilot has one local source of truth: a `.s2a.json` session. Geometry is stored in rendered PDF points (72 units/in, top-left origin), so reopening or rendering at a different DPI does not change retained geometry.

Claude receives one Screen2XYZ MCP server with these important capabilities:

- `view_sheet` — returns the actual selected PDF sheet as an MCP image;
- `read_sheet_text` — local vector text, explicitly marked untrusted drawing evidence;
- `get_sheet_vectors` — bounded vector-path evidence;
- `list_takeoff_rules` — civil rules such as road widening, ditch infill, gravel shoulder, driveway culvert, driveway reinstatement, and QA-only anchor;
- `propose_line_takeoff` / `propose_polygon_takeoff` — create unapproved proposals;
- `auto_trace_area` — optional real OpenTakeoff One-Click trace when `opentakeoff-mcp` is installed;
- `edit_unapproved_takeoff` — correct proposal geometry while retaining the original AI geometry/history;
- `flag_takeoff`, `raise_question`, `attach_evidence` — disclose uncertainty rather than silently guessing;
- `takeoff_qa` — blockers/reference/scale/questions QA;
- `export_bluebeam_markup_plan` — writes the geometry/traceability plan for native Revu creation/readback.

There is deliberately **no MCP tool to approve final bid quantity or publish a final bid**.

## Important pilot boundary

This first runnable agent session is **one PDF page with one scale context**. Do not use it as a final quantity authority on a sheet that contains multiple measurement viewports/scales. If `sheet_info`/OpenTakeoff or the drawing itself indicates multiple plan/detail/profile scales, stop and use only a clearly bounded same-scale pilot region or wait for the scale-region project model.

For Example Road Sheet 03, use the pilot only after the estimator has confirmed the relevant plan scale and independently checked it against a known dimension in Bluebeam/Revu.

## 1. One-time Windows setup

From the repository root:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-civil.txt
$env:PYTHONPATH = (Resolve-Path .\src)
.\.venv\Scripts\python.exe -m screen2xyz_civil doctor
```

The Claude/operator `view_sheet` path uses the pinned `pypdfium2` + Pillow
packages installed by `requirements-civil.txt`; a separate Poppler install is
not required for this pilot. Poppler `pdftoppm` is retained only as a supported
legacy/fallback renderer. Tesseract is optional for OCR. Node/OpenTakeoff are
optional for manual Claude proposals but required for `auto_trace_area`.

Optional OpenTakeoff install. The public package version exercised by this branch's Windows CI is pinned for reproducibility:

```powershell
npm install -g opentakeoff-mcp@0.9.68
.\.venv\Scripts\python.exe -m screen2xyz_civil doctor --deep
```

Screen2XYZ never auto-downloads or silently runs `npx -y` at takeoff time. If you use a local OpenTakeoff build instead, set `SCREEN2XYZ_OPENTAKEOFF_CMD` to the exact local command and re-run `doctor --deep`.

## 2. Create the Sheet 03 session

Example:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-init `
  "C:\Tenders\ExampleRoad\IssuedForTender.pdf" `
  --page 3 `
  --page-label 03 `
  --name "Example Road - Sheet 03" `
  --out "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json"
```

Use the actual PDF page number, which is not always the same as the printed sheet number.

## 3. Resolve and verify scale

If the whole pilot plan is printed 1:250 and you have independently verified it in Bluebeam against a known dimension:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-scale-ratio `
  --session "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json" `
  --ratio 250 `
  --basis "Sheet 03 PLAN 1:250; independently checked in Revu against authoritative drawing dimension" `
  --verified
```

Do **not** use `--verified` merely because the title block says 1:250. It means an estimator has independently checked the scale.

You can also calibrate using two clicked/render coordinates and later run `agent-verify-scale` on a second dimension. `agent-verify-scale` is the preferred evidence path when exact points are available.

## 4. Connect Claude Code

The local server command is:

```powershell
$env:PYTHONPATH = "C:\path\to\screen2xyz-civil-plan-digitizer\src"
C:\path\to\screen2xyz-civil-plan-digitizer\.venv\Scripts\python.exe `
  -m screen2xyz_civil mcp `
  --session "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json"
```

It speaks MCP over stdio and waits for Claude Code to launch it. Do not start it manually in another terminal unless you are using an MCP Inspector/client.

For Claude Code, register the local stdio server with the `PYTHONPATH` embedded in the MCP configuration so later Claude sessions do not depend on whatever environment happened to be active in your PowerShell window:

```powershell
claude mcp add --transport stdio `
  --env "PYTHONPATH=C:\path\to\screen2xyz-civil-plan-digitizer\src" `
  screen2xyz -- `
  "C:\path\to\screen2xyz-civil-plan-digitizer\.venv\Scripts\python.exe" `
  -m screen2xyz_civil mcp `
  --session "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json"
```

Claude Code requires all MCP options before the server name, then `--`, then the actual server command/arguments. Confirm the connection with:

```text
/mcp
```

or from the shell:

```powershell
claude mcp get screen2xyz
```

If you want this configuration shared at project scope instead, Claude Code also supports a project `.mcp.json`; keep proprietary tender/session paths out of committed configuration. The Screen2XYZ business logic is independent of Claude-specific configuration.

## 5. Give Claude the operating prompt

Use `prompts/CLAUDE_CODE_BLUEBEAM_TAKEOFF_PROMPT.md` as the task prompt. The short form is:

> Use the `screen2xyz` MCP tools to inspect the current sheet, compare drawing legend/callouts against existing proposals, and create or improve all relevant civil takeoff proposals. Use OpenTakeoff `auto_trace_area` only when useful, then visually audit and correct the polygon. Withhold ambiguity instead of guessing. Export the Bluebeam markup plan. If a live Bluebeam/Revu tool surface is available, create/update native measurements only through a capability path that is actually exposed and live-tested; otherwise use the proven Revu GUI path. Read back every saved native measurement and quantity. Do not approve the bid or silently sum reference anchors.

The full prompt contains the Sheet 03 rule/QA/coverage procedure and completion gates.

## 6. Expected Claude workflow

Claude should call `session_status`, then `view_sheet`, `read_sheet_text`, and `list_takeoff_rules`. It should compare the visible drawing/legend with `list_takeoffs` and identify both missing work and incorrect geometry.

For current Sheet 03 examples the first-pass rules include:

- `DRIVEWAY_CULVERT_300`: line along the actual 300 mm culvert centerline/end-to-end; never substitute printed driveway width;
- `GRAVEL_DRIVEWAY_REINSTATEMENT`: actual reinstatement polygon, not a generic rectangle;
- `DITCH_INFILL`: separate polygon from ditch regrade/relocation;
- `GRAVEL_SHOULDER_030`: continuous shoulder reach as Length with stated 0.30 m width retained in the rule;
- `ROAD_WIDENING_FULL_STRUCTURE`: actual X-hatch coverage polygon(s);
- `MILL_OVERLAY_40MM`: actual mill/overlay hatch only;
- `FULL_DEPTH_ASPHALT_RR`: only where that specific hatch exists; never infer it merely because it appears in the legend;
- `DITCH_REGRADE` and `DITCH_RELOCATION`: separate traces; a mixed trace is `MIXED/UNRESOLVED`;
- `ANCHOR_ROADWORKS_EXTENT`: QA/reference only, `DO NOT SUM`.

Claude must not call the sheet complete merely because an anchor exists. Coverage means each expected visible scope is either `PROPOSED`, explicitly `WITHHELD/QUESTION`, or clearly `NOT PRESENT`; a silent miss is a failure.

## 7. Bluebeam handoff

After proposal review:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-plan `
  --session "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json"
```

This writes `*.bluebeam-markup-plan.json` beside the session. It contains Subject/Label/Comment traceability, canonical geometry, render coordinates, OpenTakeoff coordinates, flags, preview quantity, and the rule that an anchor is reference-only.

The JSON is **not** evidence that native Revu markups were created. The final operator step must create or edit native Bluebeam measurements and read them back from the saved PDF/session. For scale-dependent measurements, final QA requires both `SCALE_RESOLVED=Y` and `SCALE_VERIFIED=Y`.

If Claude Code has a Bluebeam/Revu MCP server connected, use the acceptance procedure in `BLUEBEAM_21_10_MEASUREMENT_ACCEPTANCE.md` before allowing mass native measurement creation on the owner machine. If no live-tested native creation path exists in Claude Code, the Screen2XYZ pilot still produces the reviewed geometry/markup plan, but native Revu placement must use the proven GUI/operator route.

## 8. Test/acceptance sequence

Before using proprietary tender data:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe tests_civil\run_civil_tests.py
.\.venv\Scripts\python.exe -m screen2xyz_civil doctor --deep
```

Then do a private owner-machine acceptance pass on Sheet 03. Compare Claude/Screen2XYZ proposals against the estimator-reviewed Bluebeam result. Record at minimum: expected-item coverage, silent misses, wrong rule, quantity error, geometry correction, unresolved/withheld items, and whether native Bluebeam readback matched the intended markup.

Do not commit the proprietary PDF or private tender evidence to GitHub.

## Current definition of “ready enough to use with Claude Code”

The pilot is ready for a real operator test when:

1. deterministic Civil tests pass;
2. `doctor` passes required dependencies;
3. Claude Code `/mcp` shows `screen2xyz` connected;
4. `session_status`, `view_sheet`, manual proposal tools, save/reopen, and `agent-plan` work locally;
5. `doctor --deep` reports OpenTakeoff compatible if `auto_trace_area` will be used;
6. the estimator has independently verified the page/viewport scale;
7. native Bluebeam creation/readback is executed through the current proven Revu route, not assumed from the Screen2XYZ JSON.

A successful single Sheet 03 pilot is the gate before generalizing to multi-document bid sets, per-viewport scale regions, and automated Bluebeam-native creation.