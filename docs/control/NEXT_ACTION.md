# Next Action

## Current stage: owner-machine Claude Code + Bluebeam acceptance

The generic runnable vertical slice is now implemented on
`feature/claude-markup-operator-real3`.

The branch has a source-hash-bound `.s2a.json` single-sheet session, independent
scale verification, civil takeoff rules, no-silent-miss scope ledger, external
Screen2XYZ MCP stdio server, portable PDFium sheet rendering, real OpenTakeoff
0.9.68 MCP/One-Click integration, proposal/edit/evidence/question/QA tools,
Bluebeam markup-plan export, `doctor`, `agent-claude-config`, Claude Code runbook,
and the full civil-takeoff operator prompt.

GitHub CI run #130 on code head
`0204f34287ee73c46def456e8239b0f88ce73a49` passed the preserved baseline/M1/M2
suites, the 214-test Civil suite, privacy/evidence checks, Windows integration,
external Claude-style Screen2XYZ stdio MCP smoke, and real OpenTakeoff
stdio/One-Click synthetic smoke.

This proves the local proposal pipeline and protocol contracts on a clean CI
host. It does **not** prove real Example Road accuracy or native Bluebeam
measurement creation on the estimator's Revu installation.

## Exactly one recommended next action

Run a private owner-machine acceptance on the actual Example Road Sheet 03 before
merging PR #8 or generalizing the architecture.

### A. Prepare the owner workstation

Checkout/pull `feature/claude-markup-operator-real3`, then from the repository
root:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-civil.txt
npm install -g opentakeoff-mcp@0.9.68
$env:PYTHONPATH = (Resolve-Path .\src)
.\.venv\Scripts\python.exe -m screen2xyz_civil doctor --deep
```

Required Screen2XYZ checks must pass. OpenTakeoff must report a compatible real
MCP probe if `auto_trace_area` will be used. A discovered Bluebeam executable is
only a candidate route and remains `NOT LIVE_TESTED` at this point.

### B. Create the private Sheet 03 session

Use the controlled local tender PDF. Do not commit it or the generated private
session/evidence to GitHub.

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-init `
  "C:\Tenders\ExampleRoad\IssuedForTender.pdf" `
  --page <actual-pdf-page-number> `
  --page-label 03 `
  --name "Example Road - Sheet 03" `
  --out "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json"
```

### C. Resolve **and independently verify** the Sheet 03 plan scale

Do not mark the scale verified just because the title block prints `1:250`.
Use an authoritative known dimension/scale-bar check in Revu. Prefer the
`agent-calibrate` + `agent-verify-scale` path when exact points are available.

If the worked region really is one verified 1:250 plan context, the simpler
human assertion path is allowed only after that independent check:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-scale-ratio `
  --session "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json" `
  --ratio 250 `
  --basis "Sheet 03 PLAN 1:250; independently checked in Revu against authoritative dimension" `
  --verified
```

If Sheet 03 contains another measurement viewport/scale that conflicts with the
pilot region, do not finalize quantities across it with the page-wide scale.

### D. Generate Claude Code MCP registration commands

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil agent-claude-config `
  --session "C:\Tenders\ExampleRoad\ExampleRoad_S03.s2a.json"
```

Run the emitted `screen2xyz` registration command. If a local Bluebeam MCP
executable is discovered, the command also prints a candidate `bluebeam-revu`
registration. Run it only with Revu MCP enabled and the intended editable PDF
active.

In Claude Code, verify `/mcp` before giving the takeoff prompt.

### E. Prove the native Bluebeam route before production creation

If Claude Code exposes Bluebeam tools, follow
`docs/integrations/BLUEBEAM_21_10_MEASUREMENT_ACCEPTANCE.md` on a disposable
copy/context:

1. inspect the actual advertised Bluebeam tool/schema surface;
2. establish/verify scale in the target measurement context;
3. create one native Length;
4. save/read it back and confirm intent/type, unit, live computed quantity,
   geometry/metadata where exposed;
5. create one native Area;
6. save/read it back with the same checks;
7. classify the route `LIVE_TESTED` only if both succeed end to end.

If the gate fails, do not bypass Bluebeam security or fake native measurements.
Use Screen2XYZ for reviewed proposal geometry and the proven Revu GUI measurement
path, then read back the saved result where available.

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
- separate ditch regrade vs relocation, with mixed/partial work withheld rather
  than guessed;
- `ANCHOR_ROADWORKS_EXTENT` as reference/QA only, never summed.

Before stopping, Claude must have no `UNSEARCHED` rule in `scope_status` **and**
must do an instance-level visual pass so a single proposal cannot hide a second
culvert/reach.

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
- any tool/schema/scale/Studio blocker.

Initial acceptance target for this sheet:

- **0 critical silent misses** for the agreed Sheet 03 scope;
- **0 `ANCHOR` quantities summed**;
- **0 unresolved/mixed/partial items presented as final**;
- **0 wrong-scale quantities presented as QA-complete**;
- every native Bluebeam measurement created by automation read back from saved
  state;
- simple line/area quantities should normally be close enough to the reviewed
  Bluebeam result to investigate any material disagreement rather than hide it
  in an average accuracy score.

## After the acceptance result

- If the Sheet 03 pilot passes, the next development slice is multi-document
  bid-set + per-viewport `ScaleRegion` support and a dedicated takeoff review UI.
- If it fails, fix the observed failure class first and add a regression test;
  do not compensate by weakening blockers or silently accepting misses.
- Keep Draft PR #8 unmerged until the owner explicitly accepts or waives this
  gate.
- Draft PR #9 remains CI-only and must never be merged.
