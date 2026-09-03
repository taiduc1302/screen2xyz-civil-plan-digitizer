# Claude Code civil-markup operator — local pilot runbook

Status: private single-sheet pilot. The goal is a controlled path where Claude Code can inspect one civil plan sheet, create or improve **proposal geometry**, and hand a deterministic markup plan to the live Bluebeam workflow. Final Bluebeam quantity approval remains human-only.

## What is runnable now

The pilot has one local source of truth: a `.s2a.json` session. Geometry is stored in rendered PDF points (72 units/in, top-left origin), so reopening or rendering at a different DPI does not change retained geometry.

The PDF workflow deliberately uses **two files**:

- an **immutable source PDF** tied to the session by exact SHA-256 and used by Screen2XYZ for clean drawing evidence; and
- a separate **editable Bluebeam working PDF** used by Revu for native markups.

This split is required. Saving Revu annotations changes PDF bytes; if the immutable source itself were used as the working file, the correct Screen2XYZ source-hash guard would invalidate the session. The working-copy validator therefore allows normal working-file byte changes while requiring its selected-page drawing content to continue matching the immutable source.

Claude receives one Screen2XYZ MCP server with these important capabilities:

- `view_sheet` — clean immutable selected PDF sheet as an MCP image;
- `read_sheet_text` — local vector text, explicitly marked untrusted drawing evidence;
- `get_sheet_vectors` — bounded vector-path evidence;
- `bluebeam_working_copy_status` — verifies the separately registered editable Revu file still matches the immutable drawing;
- `list_takeoff_rules` — civil rules such as road widening, ditch infill, gravel shoulder, driveway culvert, driveway reinstatement, and QA-only anchor;
- `scope_status` / `account_scope_rule` — explicit no-silent-miss rule coverage;
- `propose_line_takeoff` / `propose_polygon_takeoff` — create unapproved proposals;
- `auto_trace_area` — optional real OpenTakeoff One-Click trace when `opentakeoff-mcp` is installed;
- `edit_unapproved_takeoff` — correct proposal geometry while retaining original AI geometry/history;
- `flag_takeoff`, `raise_question`, `attach_evidence` — disclose uncertainty instead of silently guessing;
- `takeoff_qa` — blockers/reference/scale/questions/working-copy/scope QA;
- `export_bluebeam_markup_plan` — deterministic geometry/traceability plan bound to the immutable source and registered Revu target.

There is deliberately **no MCP tool to approve final bid quantity or publish a final bid**.

## Important pilot boundary

This first runnable agent session is **one PDF page with one compatible scale context**. Do not use it as a final quantity authority across multiple plan/detail/profile viewports with different scales. If the drawing contains conflicting measurement scales, stop final quantity work outside the verified pilot region.

Use one writer for one `.s2a.json` session during this pilot. Do not run two independent mutating Screen2XYZ MCP processes against the same session.

For King Road Sheet 03, use the pilot only after the estimator confirms the plan scale and independently checks it against an authoritative dimension in Revu.

## 1. One-time Windows setup

From the repository root:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-civil.txt
$env:PYTHONPATH = (Resolve-Path .\src)
.\.venv\Scripts\python.exe -m screen2xyz_civil doctor
```

The Claude/operator `view_sheet` path uses pinned `pypdfium2` + Pillow, so a separate Poppler install is not required for this pilot. Poppler remains a legacy/fallback renderer. Tesseract is optional.

OpenTakeoff is optional for direct Claude line/polygon proposals and required only for `auto_trace_area`. The public package version exercised by CI is pinned for reproducibility:

```powershell
npm install -g opentakeoff-mcp@0.9.68
.\.venv\Scripts\python.exe -m screen2xyz_civil doctor --deep
```

Screen2XYZ never auto-downloads OpenTakeoff at takeoff time. A controlled local OpenTakeoff command can be supplied with `SCREEN2XYZ_OPENTAKEOFF_CMD`.

## 2. Create the Sheet 03 session from an immutable base PDF

Keep a controlled base file that Revu will **not** modify, for example:

`C:\Tenders\KingRoad\IssuedForTender_BASE.pdf`

Create the session:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src)
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-init `
  "C:\Tenders\KingRoad\IssuedForTender_BASE.pdf" `
  --page 3 `
  --page-label 03 `
  --name "King Road - Sheet 03" `
  --out "C:\Tenders\KingRoad\KingRoad_S03.s2a.json"
```

Use the actual PDF page number, which may differ from the printed sheet number. Do not later save Revu markups into the base PDF; its exact SHA-256 is the drawing revision/evidence guard.

## 3. Create or register the editable Bluebeam working PDF

### New markups from a clean drawing

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-working-copy `
  --session "C:\Tenders\KingRoad\KingRoad_S03.s2a.json" `
  --out "C:\Tenders\KingRoad\KingRoad_TAKEOFF_WORKING.pdf"
```

Open `KingRoad_TAKEOFF_WORKING.pdf` in Revu. This is the file whose markup bytes may change.

### Improve an existing annotated Bluebeam PDF

If a separate editable PDF already contains the AI markups to improve:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-register-working-copy `
  --session "C:\Tenders\KingRoad\KingRoad_S03.s2a.json" `
  --pdf "C:\Tenders\KingRoad\KingRoad_EXISTING_TAKEOFF.pdf"
```

Screen2XYZ does not require this annotated file to keep the same full SHA as the base. It verifies that the selected page's decoded drawing content, page geometry, and rotation match the immutable source. A wrong drawing/revision is rejected.

Check state:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-status `
  --session "C:\Tenders\KingRoad\KingRoad_S03.s2a.json"
```

A Revu save may set `modified_since_registration=true`; that is expected. `drawing_match=true` and `safe_for_bluebeam_operator=true` must remain true.

## 4. Resolve and independently verify scale

If the whole worked plan region is 1:250 and the estimator independently checks it in Revu against a known dimension:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-scale-ratio `
  --session "C:\Tenders\KingRoad\KingRoad_S03.s2a.json" `
  --ratio 250 `
  --basis "Sheet 03 PLAN 1:250; independently checked in Revu against authoritative dimension" `
  --verified
```

Do **not** use `--verified` merely because the title block says 1:250. `agent-calibrate` plus `agent-verify-scale` is the preferred two-point + independent second-dimension path when exact points are available.

## 5. Connect Claude Code

Let Screen2XYZ generate the exact registration commands for the current interpreter, repository path, session, and locally installed Revu MCP executable:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-claude-config `
  --session "C:\Tenders\KingRoad\KingRoad_S03.s2a.json"
```

The command does not silently edit Claude configuration. It always emits the `screen2xyz` registration. It presents the Bluebeam route as operator-ready only when a safe separate working PDF is registered.

Manual Screen2XYZ registration, if needed:

```powershell
claude mcp add --transport stdio `
  --env "PYTHONPATH=C:\path\to\screen2xyz-civil-plan-digitizer\src" `
  screen2xyz -- `
  "C:\path\to\screen2xyz-civil-plan-digitizer\.venv\Scripts\python.exe" `
  -m screen2xyz_civil mcp `
  --session "C:\Tenders\KingRoad\KingRoad_S03.s2a.json"
```

Confirm the connection with Claude Code `/mcp` or `claude mcp get screen2xyz`.

### Candidate Bluebeam MCP registration in Claude Code

Screen2XYZ can discover the standard local executable:

`C:\Program Files\Bluebeam Software\Bluebeam Revu\21\Revu\mcp\Bluebeam MCP Server.exe`

If Revu is installed elsewhere, set `SCREEN2XYZ_BLUEBEAM_MCP_EXE` to the exact executable and rerun `doctor` / `agent-claude-config`.

Discovery and registration establish only a candidate/current stdio route. They do **not** establish `LIVE_TESTED` native Length/Area creation.

Before native work:

1. record the exact Revu point version and confirm the Bluebeam plan/licensing required for MCP;
2. enable Revu MCP;
3. open the exact registered **working-copy PDF**, never the immutable base;
4. register the emitted `bluebeam-revu` command;
5. confirm `/mcp` actually lists the connected Bluebeam tools;
6. run `BLUEBEAM_21_10_MEASUREMENT_ACCEPTANCE.md` before production native measurement creation.

## 6. Give Claude the operating prompt

Use `prompts/CLAUDE_CODE_BLUEBEAM_TAKEOFF_PROMPT.md`.

The short form is:

> Use the `screen2xyz` MCP tools to inspect the immutable current sheet, verify the registered Bluebeam working copy, reconcile drawing legend/callouts and existing working-copy Revu markups, and create or improve all relevant civil takeoff proposals. Use OpenTakeoff only as a geometry engine and visually audit/correct its output. Withhold ambiguity instead of guessing. Export the Bluebeam markup plan. Perform native Revu work only in the registered working copy and only through a capability path that is actually exposed and live-tested; otherwise use the proven Revu GUI path. Read back every saved native measurement. Do not approve the bid or sum reference anchors.

## 7. Expected Claude workflow

Claude should start with `session_status`, `bluebeam_working_copy_status`, `view_sheet`, `read_sheet_text`, `list_takeoff_rules`, `list_takeoffs`, and `scope_status`.

For current Sheet 03 examples it should explicitly check:

- `DRIVEWAY_CULVERT_300`: actual pipe centerline/end-to-end; never substitute printed driveway width;
- `GRAVEL_DRIVEWAY_REINSTATEMENT`: actual reinstatement boundary, not a generic neat rectangle;
- `DITCH_INFILL`: separate polygon from ditch regrade/relocation;
- `GRAVEL_SHOULDER_030`: each continuous reach as Length with stated 0.30 m width retained;
- `ROAD_WIDENING_FULL_STRUCTURE`: actual X-hatch polygons/tapers;
- `MILL_OVERLAY_40MM`: actual mill/overlay hatch only;
- `FULL_DEPTH_ASPHALT_RR`: only where its specific hatch/callout exists, never because it merely appears in the legend;
- `DITCH_REGRADE` and `DITCH_RELOCATION`: separate traces; mixed scope is `MIXED/UNRESOLVED` or withheld;
- `ANCHOR_ROADWORKS_EXTENT`: QA/reference only, `DO NOT SUM`.

Claude must not call the sheet complete because an anchor exists. Every rule must end `PROPOSED`, `WITHHELD`, `NOT_PRESENT`, or `NOT_APPLICABLE`, with no `UNSEARCHED`. Then Claude must perform an instance-level visual pass because the current machine ledger is rule-level; for example, one culvert does not prove both North and South culverts were covered.

## 8. Bluebeam handoff

After proposal review:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-plan `
  --session "C:\Tenders\KingRoad\KingRoad_S03.s2a.json"
```

The saved `*.bluebeam-markup-plan.json` contains traceability, canonical/render/OpenTakeoff geometry, flags, preview quantity, scale state, and the immutable-source/registered-working-copy document contract.

The JSON is **not** evidence that native Revu measurements exist. Final native work must occur only in the registered working PDF and every created/edited measurement must be read back from saved Revu state.

## 9. Test and acceptance sequence

Before proprietary tender data:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe tests_civil\run_civil_tests.py
.\.venv\Scripts\python.exe -m screen2xyz_civil doctor --deep
```

The frozen Civil suite is **236 discovered tests**. The separate Windows protocol lane also launches the same external stdio Screen2XYZ process a real MCP host uses and a real OpenTakeoff 0.9.68 process against owned synthetic PDFs.

Then run a private owner-machine acceptance on Sheet 03. Record at minimum:

- expected scope instances;
- silent misses and wrong rules;
- geometry corrections;
- Screen2XYZ vs reviewed Revu quantity;
- unresolved/withheld items;
- working-copy drawing match before/after Revu saves;
- Bluebeam tool/schema capability state;
- native Length/Area create/save/readback result.

Do not commit proprietary base PDFs, working PDFs, sessions, or private takeoff evidence to GitHub.

## Ready-enough gate for Claude Code

The pilot is ready for a real operator test only when:

1. deterministic Civil tests pass;
2. `doctor` passes required dependencies;
3. immutable base and separate working PDF are registered and `safe_for_bluebeam_operator=true`;
4. Claude Code `/mcp` shows `screen2xyz` connected;
5. `session_status`, `bluebeam_working_copy_status`, `view_sheet`, proposal tools, save/reopen, and `agent-plan` work locally;
6. `doctor --deep` reports OpenTakeoff compatible if `auto_trace_area` will be used;
7. the estimator independently verifies the relevant scale;
8. if native Bluebeam MCP creation is desired, Revu is on the registered working copy and the disposable native Length+Area create/save/readback acceptance gate passes;
9. if that Bluebeam gate fails, Claude stops at the reviewed Screen2XYZ plan or uses a separately proven GUI operator path instead of pretending native measurements were created.

A successful Sheet 03 pilot is the gate before multi-document bid sets, per-viewport `ScaleRegion` support, a dedicated takeoff review UI, and broader Bluebeam-native automation.

## References

- Bluebeam Revu MCP overview: `https://support.bluebeam.com/revu/resources/revu-mcp.html`
- Bluebeam Claude setup: `https://support.bluebeam.com/revu/how-to/mcp-claude.html`
- Bluebeam AnythingLLM setup (documents local MCP executable): `https://support.bluebeam.com/revu/how-to/mcp-anything.html`
- Anthropic Claude Code MCP: `https://docs.anthropic.com/en/docs/claude-code/mcp`
