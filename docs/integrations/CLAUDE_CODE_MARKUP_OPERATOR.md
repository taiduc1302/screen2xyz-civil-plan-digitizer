# Claude Code civil-markup operator — local pilot runbook

Status: private single-sheet pilot. The goal is a controlled path where Claude Code can inspect one civil plan sheet, create or improve **proposal geometry**, and hand a deterministic markup plan to the live Bluebeam workflow. Final Bluebeam quantity approval remains human-only.

## What is runnable now

The pilot has one local source of truth: a `.s2a.json` session. Geometry is stored in rendered PDF points (72 units/in, top-left origin), so reopening or rendering at a different DPI does not change retained geometry.

The PDF workflow deliberately uses **two files**:

- an **immutable source PDF** tied to the session by exact SHA-256 and used by Screen2XYZ for clean drawing evidence; and
- a separate **editable Bluebeam working PDF** used by Revu for native markups.

This split is required. Saving Revu annotations changes PDF bytes; if the immutable source itself were used as the working file, the correct Screen2XYZ source-hash guard would invalidate the session. The working-copy validator therefore allows normal working-file byte changes while requiring its selected page drawing content to continue matching the immutable source.

Claude receives one Screen2XYZ MCP server with these important capabilities:

- `view_sheet` — returns the clean immutable selected PDF sheet as an MCP image;
- `read_sheet_text` — local vector text, explicitly marked untrusted drawing evidence;
- `get_sheet_vectors` — bounded vector-path evidence;
- `bluebeam_working_copy_status` — verifies the separately registered editable Revu file still matches the immutable drawing;
- `list_takeoff_rules` — civil rules such as road widening, ditch infill, gravel shoulder, driveway culvert, driveway reinstatement, and QA-only anchor;
- `propose_line_takeoff` / `propose_polygon_takeoff` — create unapproved proposals;
- `auto_trace_area` — optional real OpenTakeoff One-Click trace when `opentakeoff-mcp` is installed;
- `edit_unapproved_takeoff` — correct proposal geometry while retaining the original AI geometry/history;
- `flag_takeoff`, `raise_question`, `attach_evidence` — disclose uncertainty rather than silently guessing;
- `takeoff_qa` — blockers/reference/scale/questions/working-copy QA;
- `export_bluebeam_markup_plan` — writes the geometry/traceability plan for native Revu creation/readback.

There is deliberately **no MCP tool to approve final bid quantity or publish a final bid**.

## Important pilot boundary

This first runnable agent session is **one PDF page with one scale context**. Do not use it as a final quantity authority on a sheet that contains multiple measurement viewports/scales. If `sheet_info`/OpenTakeoff or the drawing itself indicates multiple plan/detail/profile scales, stop and use only a clearly bounded same-scale pilot region or wait for the scale-region project model.

For Example Road Sheet 03, use the pilot only after the estimator has confirmed the relevant plan scale and independently checked it against a known dimension in Bluebeam/Revu.

Use one writer for one `.s2a.json` session during this pilot. Do not run two independent Claude/Screen2XYZ MCP processes that mutate the same session at the same time.

## 1. One-time Windows setup

From the repository root:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-civil.txt
$env:PYTHONPATH = (Resolve-Path .\src)
.\.venv\Scripts\python.exe -m screen2xyz_civil doctor
```

The Claude/operator `view_sheet` path uses the pinned `pypdfium2` + Pillow packages installed by `requirements-civil.txt`; a separate Poppler install is not required for this pilot. Poppler `pdftoppm` is retained only as a supported legacy/fallback renderer. Tesseract is optional for OCR. Node/OpenTakeoff are optional for manual Claude proposals but required for `auto_trace_area`.

Optional OpenTakeoff install. The public package version exercised by this branch's Windows CI is pinned for reproducibility:

```powershell
npm install -g opentakeoff-mcp@0.9.68
.\.venv\Scripts\python.exe -m screen2xyz_civil doctor --deep
```

Screen2XYZ never auto-downloads or silently runs `npx -y` at takeoff time. If you use a local OpenTakeoff build instead, set `SCREEN2XYZ_OPENTAKEOFF_CMD` to the exact local command and re-run `doctor --deep`.

## 2. Create the Sheet 03 session from an immutable base PDF

First keep a controlled base file that Revu will **not** modify, for example:

`C:\Tenders\ExampleRoad\IssuedForTender_BASE.pdf`

Create the session from that file:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-init `
  "C:\Tenders\ExampleRoad\IssuedForTender_BASE.pdf" `
  --page 3 `
  --page-label 03 `
  --name "Example Road - Sheet 03" `
  --out "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json"
```

Use the actual PDF page number, which is not always the same as the printed sheet number. Do not later save markups into `IssuedForTender_BASE.pdf`; its exact hash is the revision/evidence guard.

## 3. Create or register the editable Bluebeam working PDF

### New markups from a clean drawing

Have Screen2XYZ make an exact separate copy and register it:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-working-copy `
  --session "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json" `
  --out "C:\Tenders\ExampleRoad\ExampleRoad_TAKEOFF_WORKING.pdf"
```

Open **`ExampleRoad_TAKEOFF_WORKING.pdf`** in Revu. This is the file whose markup bytes may change.

### Improve an existing annotated Bluebeam PDF

If a separate editable PDF already contains the AI markups you want Claude to improve, register it instead:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-register-working-copy `
  --session "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json" `
  --pdf "C:\Tenders\ExampleRoad\ExampleRoad_EXISTING_TAKEOFF.pdf"
```

Screen2XYZ does **not** require this annotated file to have the same full SHA as the base. It verifies that the selected page's decoded drawing stream, page geometry, and rotation match the immutable source. A wrong drawing/revision is rejected.

Check the state at any time:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-status `
  --session "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json"
```

A Revu save may set `modified_since_registration=true`; that is expected. `drawing_match` and `safe_for_bluebeam_operator` must remain true.

## 4. Resolve and verify scale

If the whole pilot plan is printed 1:250 and you have independently verified it in Bluebeam against a known dimension:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-scale-ratio `
  --session "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json" `
  --ratio 250 `
  --basis "Sheet 03 PLAN 1:250; independently checked in Revu against authoritative dimension" `
  --verified
```

Do **not** use `--verified` merely because the title block says 1:250. It means an estimator has independently checked the scale. You can also calibrate using two clicked/render coordinates and later run `agent-verify-scale` on a second dimension; that is the preferred evidence path when exact points are available.

## 5. Connect Claude Code

First let Screen2XYZ generate the exact registration commands for the current interpreter, repository path, session, and locally installed Revu MCP executable:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-claude-config `
  --session "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json"
```

The command never edits Claude configuration itself. It always emits the `screen2xyz` registration. It only presents the Bluebeam route as operator-ready when a safe separate working copy is registered. Copy/run the emitted commands and verify them with `/mcp` or `claude mcp get screen2xyz`.

The equivalent manual Screen2XYZ registration is:

```powershell
claude mcp add --transport stdio `
  --env "PYTHONPATH=C:\path\to\screen2xyz-civil-plan-digitizer\src" `
  screen2xyz -- `
  "C:\path\to\screen2xyz-civil-plan-digitizer\.venv\Scripts\python.exe" `
  -m screen2xyz_civil mcp `
  --session "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json"
```

Claude Code requires all MCP options before the server name, then `--`, then the actual server command/arguments.

### Candidate Bluebeam MCP registration in Claude Code

Bluebeam's Revu documentation directly supports named MCP hosts and separately documents the local stdio executable used by AnythingLLM:

`C:\Program Files\Bluebeam Software\Bluebeam Revu\21\Revu\mcp\Bluebeam MCP Server.exe`

Claude Code supports arbitrary local stdio MCP servers. Therefore `agent-claude-config` can emit a candidate `bluebeam-revu` registration when this executable exists. This is an interoperability route, **not** evidence that native Length/Area creation has passed in Claude Code.

Before trying it:

1. record the exact Revu point version and confirm the Bluebeam plan required for MCP;
2. enable Revu MCP in `Revu > Preferences > Admin > MCP`;
3. open the exact registered **working-copy PDF**, never the immutable base;
4. register the emitted `bluebeam-revu` command in Claude Code;
5. confirm `/mcp` actually lists Bluebeam tools;
6. run `BLUEBEAM_21_10_MEASUREMENT_ACCEPTANCE.md` before production measurement creation.

A discovered executable or visible tool list establishes at most a candidate/current surface. Only a disposable native Length + native Area create/save/readback pass establishes `LIVE_TESTED` measurement creation on that machine.

If Revu is installed elsewhere, set `SCREEN2XYZ_BLUEBEAM_MCP_EXE` to the exact MCP executable and rerun `doctor` / `agent-claude-config`.

## 6. Give Claude the operating prompt

Use `prompts/CLAUDE_CODE_BLUEBEAM_TAKEOFF_PROMPT.md` as the task prompt. The short form is:

> Use the `screen2xyz` MCP tools to inspect the immutable current sheet, verify the registered Bluebeam working copy, compare drawing legend/callouts and existing working-copy Revu markups against current proposals, and create or improve all relevant civil takeoff proposals. Use OpenTakeoff `auto_trace_area` only when useful, then visually audit/correct it. Withhold ambiguity instead of guessing. Export the Bluebeam markup plan. Perform native Revu work only in the registered working copy and only through a capability path that is actually exposed and live-tested; otherwise use the proven Revu GUI path. Read back every saved native measurement. Do not approve the bid or sum reference anchors.

The full prompt contains the Sheet 03 rule/QA/coverage procedure and completion gates.

## 7. Expected Claude workflow

Claude should call `session_status`, `bluebeam_working_copy_status`, `view_sheet`, `read_sheet_text`, `list_takeoff_rules`, `list_takeoffs`, and `scope_status`. If Bluebeam is connected, it must verify the active Revu document is the registered working PDF before listing/editing markups.

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

Claude must not call the sheet complete merely because an anchor exists. Coverage means each expected visible scope is either `PROPOSED`, explicitly `WITHHELD/QUESTION`, or clearly `NOT PRESENT`; a silent miss is a failure. Because the current machine ledger is rule-level, Claude must also perform a final **instance-level visual pass** (for example, verify both North and South culverts rather than treating one culvert as coverage for the whole culvert rule).

## 8. Bluebeam handoff

After proposal review:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-plan `
  --session "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json"
```

This writes `*.bluebeam-markup-plan.json` beside the session. It contains Subject/Label/Comment traceability, canonical geometry, render coordinates, OpenTakeoff coordinates, flags, preview quantity, working-copy status, and the rule that an anchor is reference-only.

The JSON is **not** evidence that native Revu markups were created. The final operator step must create or edit native Bluebeam measurements **in the registered working copy** and read them back from saved Revu state. For scale-dependent measurements, final QA requires both `SCALE_RESOLVED=Y` and `SCALE_VERIFIED=Y`.

If Claude Code has a Bluebeam/Revu MCP server connected, use the acceptance procedure in `BLUEBEAM_21_10_MEASUREMENT_ACCEPTANCE.md` before allowing mass native measurement creation on the owner machine. If no live-tested native creation path exists in Claude Code, the Screen2XYZ pilot still produces reviewed geometry/markup plan, while native Revu placement uses the proven GUI/operator route on the working copy.

## 9. Test/acceptance sequence

Before using proprietary tender data:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe tests_civil\run_civil_tests.py
.\.venv\Scripts\python.exe -m screen2xyz_civil doctor --deep
```

The frozen Civil suite is **219 discovered tests** on this branch. The external protocol lane additionally launches the same stdio Screen2XYZ process a real MCP host uses and a real OpenTakeoff 0.9.68 process against owned synthetic PDFs.

Then do a private owner-machine acceptance pass on Sheet 03. Compare Claude/Screen2XYZ proposals against the estimator-reviewed Bluebeam result. Record at minimum: expected-item coverage, silent misses, wrong rule, quantity error, geometry correction, unresolved/withheld items, working-copy drawing match, and whether native Bluebeam readback matched the intended markup.

Do not commit the proprietary base PDF, working PDF, private session, or takeoff evidence to GitHub.

## Current definition of “ready enough to use with Claude Code”

The pilot is ready for a real operator test when:

1. deterministic Civil tests pass;
2. `doctor` passes required dependencies;
3. immutable base and separate Bluebeam working PDF are registered and `safe_for_bluebeam_operator=true`;
4. Claude Code `/mcp` shows `screen2xyz` connected;
5. `session_status`, `bluebeam_working_copy_status`, `view_sheet`, manual proposal tools, save/reopen, and `agent-plan` work locally;
6. `doctor --deep` reports OpenTakeoff compatible if `auto_trace_area` will be used;
7. the estimator has independently verified the page/viewport scale;
8. if native Bluebeam MCP creation is desired, Revu is on the registered working copy, `/mcp` shows the actual Bluebeam tools, and the disposable native Length+Area create/save/readback acceptance gate passes;
9. if that Bluebeam gate does not pass, Claude stops at the Screen2XYZ plan or uses a separate proven GUI operator path instead of pretending native markups were created.

A successful single Sheet 03 pilot is the gate before generalizing to multi-document bid sets, per-viewport scale regions, and automated Bluebeam-native creation.

## References for the host boundary

- Bluebeam Revu MCP overview: `https://support.bluebeam.com/revu/resources/revu-mcp.html`
- Bluebeam Claude Desktop setup: `https://support.bluebeam.com/revu/how-to/mcp-claude.html`
- Bluebeam AnythingLLM setup (documents the local MCP executable path): `https://support.bluebeam.com/revu/how-to/mcp-anything.html`
- Anthropic Claude Code MCP: `https://docs.anthropic.com/en/docs/claude-code/mcp`