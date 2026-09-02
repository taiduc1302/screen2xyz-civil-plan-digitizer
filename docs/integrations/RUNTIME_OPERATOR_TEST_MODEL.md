# Runtime, operator, and test model for civil takeoff

Status: design contract for the next runnable vertical slice on `integration/open-source-takeoff-stack`.

This document states how the civil takeoff system is supposed to run in real use, how an estimator interacts with it, how Claude/ChatGPT can connect without owning project state, and what must be tested before the integration is considered usable.

## Current truth

The repository is **not yet a complete AI takeoff application**.

What exists now:

- the existing local `screen2xyz_civil` Tk application for point/terrain review;
- a review-first quantity takeoff domain (`takeoff.py`);
- an audited sidecar takeoff workspace (`takeoff_workspace.py`);
- evidence/questions/evaluation contracts;
- a pure OpenTakeoff coordinate/request adapter;
- a pure segmentation-provider interface;
- deterministic tests for those contracts.

What does **not** exist yet:

- no takeoff review panel is wired into the Tk UI;
- no process/service runner actually starts and talks to OpenTakeoff;
- no Screen2XYZ MCP server exposes civil takeoff tools to an AI client;
- no multi-sheet bid-set project model exists for takeoff;
- no per-sheet/per-viewport scale model exists for mixed-scale sheets;
- no end-to-end test currently proves `open plan -> AI proposal -> estimator correction -> approval -> export`;
- no real Example Road/Bluebeam gold-set comparison is recorded as an automated validation gate.

A green deterministic suite therefore means the implemented contracts behave as tested. It does **not** mean the product is ready for estimator use.

## Product shape: vendor-neutral local application + optional AI clients

The target is not a Claude add-on and not a ChatGPT-only add-on. The target is one local Screen2XYZ application with a vendor-neutral MCP/API boundary.

```text
                         +----------------------+
                         |  Local estimator UI  |
                         |  Screen2XYZ Desktop  |
                         +----------+-----------+
                                    |
                                    v
+----------------+       +----------+-----------+       +------------------+
| Claude / other | <---> | Screen2XYZ Gateway  | <---> | OpenTakeoff MCP  |
| MCP client     |       | (our safety/state)  |       | geometry engine  |
+----------------+       +----------+-----------+       +------------------+
                                    |
+----------------+                  |                  +------------------+
| ChatGPT custom | <--- MCP HTTP ---+----------------> | optional SAM/local|
| app / tunnel   |                                     | segmentation      |
+----------------+                                     +------------------+
                                    |
                                    v
                         +----------+-----------+
                         | Civil Takeoff Project|
                         | state + audit + QA   |
                         +----------------------+
```

### Ownership rules

Screen2XYZ owns:

- source/document identity and hashes;
- sheet identities;
- scale/viewports and human confirmation;
- takeoff rule catalogue;
- proposed/reviewed geometry;
- evidence, withheld questions, flags, corrections, and decision history;
- final estimator-approved quantities;
- exports and evaluation records.

OpenTakeoff, SAM, or another engine may propose geometry or provide measurement evidence. They are never the database of record and never self-approve a bid quantity.

Claude, ChatGPT, or another LLM is an **orchestrator/reasoner**, not the system of record.

## Recommended daily estimator workflow

The intended operator experience is:

1. Launch **Screen2XYZ Civil Takeoff** locally.
2. Create/open one bid project and select the tender PDFs/addenda that belong to the working set.
3. Screen2XYZ indexes the set and presents the sheet list.
4. For each worked plan region, review/confirm the scale or viewport calibration.
5. Start an AI client only if desired.
6. In the AI client ask for a scope, for example: `Take off Sheet 03 roadworks. Withhold anything ambiguous and do not finalize.`
7. The agent can read plan evidence and create **proposals** through Screen2XYZ tools.
8. The local UI shows every proposed line/polygon/count on the drawing plus evidence, flags, confidence, and unresolved questions.
9. The estimator edits geometry, resolves questions, rejects, or explicitly approves each item in the local UI.
10. Run QA. Nothing blocked/unreviewed is included in final totals.
11. Export a versioned marked plan + quantity workbook/CSV and retain the `.s2t`/project audit state.
12. Human corrections are retained as private training/evaluation examples according to data classification rules.

The estimator must be able to complete steps 1-4 and 8-11 **without any cloud AI client**. AI is an acceleration layer, not a required dependency.

## Human-only gates

The MCP/agent surface must not be able to silently finalize a bid.

Recommended policy:

- agent may propose geometry;
- agent may attach evidence;
- agent may add blocker flags and questions;
- agent may request a scale or suggest a detected scale;
- agent may edit an **unapproved** proposal;
- agent may not clear a human-only finalization gate;
- agent may not approve a summable bid quantity;
- agent may not publish a final export.

Estimator approval and final export should occur in the local UI (or require a UI-issued, single-use human confirmation token). Platform-level confirmation dialogs are useful but are not a substitute for this invariant.

## MCP gateway surface

The first Screen2XYZ MCP server should expose high-level tools rather than raw filesystem or shell access.

### Read tools

- `project_status`
- `list_documents`
- `list_sheets`
- `sheet_info`
- `view_sheet`
- `read_sheet_text`
- `get_sheet_vectors`
- `get_scale_regions`
- `list_takeoff_rules`
- `list_takeoffs`
- `takeoff_qa`
- `list_questions`
- `get_evidence`

### Proposal tools

- `suggest_scale`
- `propose_line_takeoff`
- `propose_polygon_takeoff`
- `propose_count_takeoff`
- `auto_trace_area` (delegates to OpenTakeoff when available)
- `symbol_sweep` / `count_marks` (delegates when available)
- `attach_evidence`
- `raise_question`
- `edit_unapproved_takeoff`
- `reject_proposal` (optional; rejection reason required)

### Human-only operations (not ordinary agent tools)

- `confirm_scale_region`
- `approve_takeoff`
- `clear_human_review_gate`
- `publish_final_export`

## One gateway, multiple AI clients

### Local Claude/MCP clients

For a local MCP client that supports stdio, run the Screen2XYZ gateway locally and connect the client to it. The gateway may itself own the child OpenTakeoff process so the AI client sees one coherent tool surface rather than two independent databases.

### Claude API remote connector

If the AI runtime expects a URL-based MCP server, run the same gateway with Streamable HTTP/SSE transport and authenticate it. The business logic must be identical to stdio mode.

### ChatGPT

ChatGPT custom MCP apps connect to a remote MCP endpoint rather than a local stdio process. A local/on-prem Screen2XYZ gateway therefore needs the supported secure tunnel/remote connection path. ChatGPT should still see the **same Screen2XYZ tools** as any other client.

Do not write separate Claude and ChatGPT business logic. Only transports/configuration differ.

## Data/privacy modes

Adding a cloud LLM changes the privacy boundary even if the PDF itself never leaves the PC. Tool replies can contain drawing text, cropped images, coordinates, and quantities.

The gateway should therefore have explicit modes:

- `LOCAL_ONLY`: no external AI connection; local UI/local models only.
- `CLOUD_METADATA`: cloud agent can receive derived metadata/text/geometry, but no raster image unless the estimator explicitly enables it.
- `CLOUD_FULL`: selected drawing crops/images may be returned to an approved cloud client.

Plan text is untrusted data. Text extracted from a drawing must never be interpreted as instructions to the agent or as permission to run commands, access unrelated files, or bypass review gates.

## Required project-model correction: bid set, not one selected page

The existing terrain workflow intentionally creates one Civil project around one selected PDF page. That is too narrow for quantity takeoff.

The takeoff runtime should introduce a bid-set root instead of treating one `CivilProject` as the whole tender:

```text
CivilTakeoffProject
  project_id
  documents[]
    document_id, path/hash/revision/role
    sheets[]
      sheet_id, page_index, title, rotation, render frame
      scale_regions[]
      evidence index
  takeoffs[]
  evidence[]
  questions[]
  decision_log[]
```

Existing `CivilProject` can remain the proven single-page terrain/point workflow or become a child/view for a selected sheet. Do not force multi-sheet takeoff state into the old terrain schema before the new model is proven.

## Required scale correction: sheet scale is not enough

Civil sheets can contain plan/profile/details at different scales. A single `metres_per_pixel` value for an entire page is unsafe.

Introduce `ScaleRegion` / viewport semantics:

- polygon/rectangle region in source-page coordinates;
- calibration revision;
- metres-per-pixel;
- evidence/provenance;
- human-confirmed flag;
- optional label such as `PLAN 1:250` / `PROFILE H 1:500 V 1:50`.

A summable line/polygon must be fully contained by exactly one compatible confirmed scale region. If it crosses regions or is outside all confirmed regions, finalization fails closed.

## Coordinate contract

Every retained geometry must identify its frame. Pixel coordinates alone are not sufficient if a sheet can be rendered again at another DPI.

Persist or derive at minimum:

- document hash;
- sheet/page id;
- source page width/height in PDF points;
- PDF rotation;
- render DPI or a resolution-independent normalized/source-point representation;
- crop/viewport transform if any.

Preferred long-term representation: source PDF points or normalized sheet coordinates as canonical geometry, with rendered pixel coordinates treated as a view. OpenTakeoff conversions should be tested from that canonical frame.

## Runtime implementation slices

### R1 - truthful local vertical slice

- add takeoff panel/table/overlay to local UI;
- load/save `.s2t` workspace next to the existing project;
- create/edit/reject/approve manual line/polygon/count takeoffs;
- display blockers/questions/evidence;
- export a basic reviewed quantity table;
- no AI required.

Acceptance: a human can reproduce Sheet 03 quantities completely through Screen2XYZ without editing JSON or running Python manually.

### R2 - environment doctor + packaging

Add one command such as:

```powershell
.\run_civil_plan_digitizer.ps1 -Doctor
```

or:

```powershell
.\.venv\Scripts\python.exe -m screen2xyz_civil doctor
```

It must report Python/Tk, pypdf, openpyxl, Poppler, Tesseract, Node, OpenTakeoff, writable project/cache folders, and gateway availability. Required vs optional dependencies must be explicit.

### R3 - real OpenTakeoff runner

Implement a process/service boundary that:

- starts a pinned OpenTakeoff MCP build;
- performs MCP initialize/tool discovery;
- verifies expected tool contracts;
- loads the intended document/sheet;
- sends scale/measure calls;
- converts replies into Screen2XYZ proposal/evidence objects;
- handles timeout/crash/restart without corrupting project state;
- never lets OpenTakeoff become the approval authority.

### R4 - Screen2XYZ MCP gateway

Implement stdio and Streamable HTTP transports over the same application service. Add tool schemas, authorization/scoping, untrusted-plan-text handling, and human-only gates.

### R5 - bid-set + scale-region model

Add multi-document, multi-sheet state and viewport/scale regions. Migrate the takeoff workspace only after backward-compatibility tests exist.

### R6 - marked-plan/Bluebeam handoff

Only after coordinate parity is proven, add marked PDF/annotation export and then validate the exact Bluebeam workflow. Do not claim Bluebeam compatibility from JSON/unit tests alone.

## Test strategy

A reliable system needs several separate test layers. A large unit-test count alone is not enough.

### T0 - deterministic unit/state tests (CI)

Keep the existing suites green. Add tests for every state invariant, conversion, blocker, persistence round trip, rule, and source/scale transition.

### T1 - coordinate/render contract tests (CI)

Synthetic PDFs must cover:

- 72, 144, 150, and 300 DPI;
- page rotations 0/90/180/270;
- letter, Arch D/E, and nonstandard page sizes;
- crop offsets;
- re-render/reopen;
- line and polygon parity between canonical geometry and rendered views.

### T2 - scale-region tests (CI)

Cover:

- one scale per sheet;
- two viewports with different scales;
- geometry wholly inside region A/B;
- geometry crossing a viewport boundary -> blocked;
- unconfirmed scale -> blocked;
- changed calibration -> all dependent quantities invalidated.

### T3 - real OpenTakeoff protocol integration (CI where possible)

Install/start the pinned OpenTakeoff package, initialize MCP, load a generated PDF, set scale, call line/polygon tools, compare returned quantities with Screen2XYZ math, shut down cleanly. This must exercise the real process/protocol, not only a mocked request dictionary.

### T4 - UI smoke tests (Windows)

Verify launch, open project, create manual takeoff, edit, approve, save, reopen, and export. At least one owner-machine test should exercise the real Tk UI.

### T5 - private real-plan gold set (owner machine; not public CI)

Build a controlled dataset from estimator-reviewed Bluebeam work. For each expected item retain:

- sheet and rule;
- reviewed geometry;
- reviewed quantity;
- status: expected/proposed/withheld;
- evidence references;
- correction history.

Example Road Sheet 03 should be the first acceptance set because it already contains line, polygon, anchor, partial/mixed scope, culvert, shoulder, driveway, and ditch cases.

### T6 - adversarial/failure tests

Test missing Poppler/Tesseract/Node/OpenTakeoff, encrypted PDF, scanned PDF, malformed PDF, process crash, timeout, bad tool schema, stale document hash, wrong page, wrong scale, conflicting evidence, unsupported scope, and drawing text that resembles tool/system instructions.

### T7 - performance/operability tests

Track project open time, sheet render/index time, OpenTakeoff trace latency, memory, and time to reopen a project. Record the test hardware.

## Real-plan acceptance metrics

Do not use one generic `accuracy` number.

Track at minimum:

- expected-item coverage;
- explicit-withheld rate;
- **silent-miss rate**;
- wrong-rule rate;
- false-positive rate;
- line/area quantity error;
- geometry overlap/distance metric appropriate to the geometry type;
- critical invariant violations (anchor summed, wrong scale finalized, unresolved item finalized).

Initial safety target for estimator trials:

- critical invariant violations: **0**;
- silent misses on the curated acceptance set: **0** before calling a scope complete;
- simple reviewed line/area quantity parity: target <=2% error;
- irregular/ambiguous geometry may use a wider provisional tolerance but must be explicitly flagged and reviewed.

These thresholds are product gates, not claims of general real-world accuracy.

## Merge/readiness gates

Do not call the takeoff integration ready for normal use until all are true:

1. local manual takeoff UI vertical slice works;
2. bid-set + scale-region model is decided and covered by tests;
3. real OpenTakeoff runtime protocol test passes;
4. Screen2XYZ gateway can be launched with a documented one-command path;
5. at least one supported AI client can call the gateway in a controlled test;
6. a private Example Road/Bluebeam gold-set run has no critical invariant failure and no silent miss for the agreed scope;
7. save/reopen/export round trip passes;
8. operator guide and environment doctor match the actual commands;
9. marked-plan/Bluebeam compatibility is either validated or clearly marked unavailable.

Until then the integration PR should remain draft.