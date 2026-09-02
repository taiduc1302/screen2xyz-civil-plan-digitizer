# Screen2XYZ Project State

| Field | Current value |
|---|---|
| Date | 2026-09-02 |
| Project version | v0.2 baseline + M1 + M2 preserved; Civil Plan Digitizer plus review-first civil takeoff/Claude operator pilot |
| Lifecycle phase | Private feature pilot; owner-machine acceptance required before default-branch merge or production Bluebeam claims |
| Current `main` observed by CI harness | `5525a29b3c1c643a31804f6e7cf8aa8bd6786ce6` |
| Civil parent/default feature branch | `feature/assisted-c03-validation` |
| Integration base | `integration/open-source-takeoff-stack` at `709460d095a8316f43bfe1f00d89c7b47c4fda33` |
| Active operator branch | `feature/claude-markup-operator-real3` |
| Clean review PR | Draft PR #8 -> `integration/open-source-takeoff-stack`; keep Draft until owner-machine acceptance |
| CI harness PR | Draft PR #9 -> `main`; CI-only, **DO NOT MERGE** |
| Civil authorization | OD-006; implementation, tests, docs, feature commits, and justified dependencies authorized; default-branch merge/release remain owner gates |
| Latest fully green code verification | GitHub CI run #130 on `0204f34287ee73c46def456e8239b0f88ce73a49`: baseline PASS, M1 PASS, M2 deterministic PASS, Civil deterministic PASS with frozen count **214**, retained-evidence/privacy scans PASS, headless Windows integration PASS, external Claude-style Screen2XYZ stdio MCP PASS, real OpenTakeoff 0.9.68 stdio/One-Click synthetic smoke PASS |
| Output classification | Conceptual/preliminary estimating data until estimator review; no real-plan accuracy or native-Bluebeam certification claim |

## Current sources of truth

- `AGENTS.md` - repository and parent-agent working rules.
- `CLAUDE.md` - repository rules for Claude Code.
- `docs/control/OWNER_DECISIONS.md` - owner authorizations, including OD-006.
- `docs/control/PROJECT_STATE.md` - current operator/integration status.
- `docs/control/NEXT_ACTION.md` - owner-machine acceptance gate.
- `docs/civil-plan-digitizer/` - preserved Civil Plan Digitizer architecture and terrain-point workflow.
- `docs/integrations/UPSTREAM_TAKEOFF_STACK.md` - pinned upstream/license boundary.
- `docs/integrations/RUNTIME_OPERATOR_TEST_MODEL.md` - target runtime/operator/test architecture.
- `docs/integrations/CLAUDE_CODE_MARKUP_OPERATOR.md` - installation and operator runbook.
- `docs/integrations/BLUEBEAM_21_10_MEASUREMENT_ACCEPTANCE.md` - native Revu create/save/readback gate.
- `prompts/CLAUDE_CODE_BLUEBEAM_TAKEOFF_PROMPT.md` - full Claude Code task prompt.
- `docs/integrations/CONSTRUCTDRAWINGAI_IDEA_REVIEW.md` - clean-room comparison and independently implemented ideas.

## Preserved product lines

- Sealed synthetic baseline and retained evidence remain immutable.
- M1 explicit-review/approved-only workflow remains available.
- M2-Live remains isolated under `src/screen2xyz_m2/`.
- Existing Civil Plan Digitizer terrain-point contracts remain under `src/screen2xyz_civil/`; the takeoff operator is additive, not a destructive migration.
- The older `.s2t.json` takeoff-workspace/domain code remains useful as integration architecture. The runnable Claude pilot uses a separate source-hash-bound `.s2a.json` agent session so the existing Civil project schema is not silently migrated.

## Runnable Claude civil-takeoff pilot now present

### Agent session and scale controls

`src/screen2xyz_civil/agent_session.py` provides a single-sheet `.s2a.json` session with:

- exact source PDF path + SHA-256 identity and stale-source refusal;
- 1-based page selection plus drawing page label;
- canonical DPI-independent geometry in rendered PDF points;
- explicit `SCALE_RESOLVED` vs `SCALE_VERIFIED` state;
- printed-ratio, two-point calibration, and independent second-dimension verification paths;
- line/polygon proposal persistence, correction history, evidence/questions, QA, and deterministic Bluebeam markup-plan export.

Scale-dependent quantities remain blocked while scale is unverified. Changing scale invalidates dependent quantity state.

### Review-first civil takeoff domain

`src/screen2xyz_civil/takeoff.py` contains normalized line/polygon/count records and current civil rules for:

- `ANCHOR_ROADWORKS_EXTENT` - reference/QA only, never summable;
- `ROAD_WIDENING_FULL_STRUCTURE`;
- `MILL_OVERLAY_40MM`;
- `FULL_DEPTH_ASPHALT_RR`;
- `DITCH_INFILL`;
- `DITCH_REGRADE`;
- `DITCH_RELOCATION`;
- `GRAVEL_SHOULDER_030` with stated 0.30 m width;
- `DRIVEWAY_CULVERT_300`;
- `GRAVEL_DRIVEWAY_REINSTATEMENT`.

Blockers include `PARTIAL`, `MIXED`, `UNRESOLVED`, `TENTATIVE`, `SCALE_UNVERIFIED`, `SCOPE_UNMAPPED`, and `GEOMETRY_UNVERIFIED`. The agent surface does not expose estimator approval.

### Scope/coverage guard

`src/screen2xyz_civil/scope_ledger.py` tracks each rule as `UNSEARCHED`, `PROPOSED`, `WITHHELD`, `NOT_PRESENT`, or `NOT_APPLICABLE`.

- `PROPOSED` is derived from actual geometry, not an agent assertion.
- A rule cannot be hidden as absent/not applicable while current geometry exists.
- Claude is instructed not to stop with `UNSEARCHED` rules.
- Because the current ledger is rule-level, the prompt requires a second instance-level visual pass so one culvert/reach cannot silently stand in for multiple separate occurrences.

### Screen2XYZ MCP gateway for Claude Code

`src/screen2xyz_civil/mcp_gateway.py` is a real local MCP stdio/Streamable-HTTP server. Its Claude-facing surface includes:

- sheet image/text/vector evidence;
- civil rule/takeoff/scope listing;
- line/polygon proposals;
- optional OpenTakeoff area trace;
- proposal geometry edits;
- flags, first-class questions, and evidence links;
- takeoff QA and deterministic markup-plan export.

It intentionally has no normal `approve_takeoff` or final bid publication tool. Drawing text is labelled untrusted project evidence, not model instructions.

The external stdio smoke test launches the server as a separate process, calls the same route an MCP host uses, obtains a real sheet image, proposes geometry, closes the client, and verifies persistence on disk.

### Real optional OpenTakeoff integration

`src/screen2xyz_civil/opentakeoff_runtime.py` launches an installed `opentakeoff-mcp` through the MCP Python client. CI pins/reviews public `opentakeoff-mcp@0.9.68` and verifies the required tool contract plus a real synthetic One-Click trace.

OpenTakeoff remains a geometry engine only. Screen2XYZ retains project state, review status, provenance, and corrections. One-Click output enters as unverified geometry until visually checked.

### Portable sheet rendering

The Claude/operator `view_sheet` path uses pinned `pypdfium2` + Pillow, so Poppler is no longer a hard prerequisite for this pilot. The legacy Poppler renderer remains a supported fallback for older Civil paths.

### Environment and host setup

`doctor` verifies the required Python/PDF/MCP runtime and optionally probes OpenTakeoff. `agent-claude-config` prints copy/paste Claude Code registrations for:

1. the Screen2XYZ session MCP server; and
2. when discovered, the installed `Bluebeam MCP Server.exe` as a **candidate** local stdio route.

Bluebeam discovery/registration is explicitly classified `DISCOVERED_STDIO_ROUTE_NOT_LIVE_TESTED`; it is not proof of native measurement creation.

## Bluebeam capability boundary

The pilot deliberately separates:

1. `PRODUCT_DOCUMENTED` - Bluebeam documents a capability for a named Revu version;
2. `CURRENT_SURFACE_EXPOSED` - the owner-machine MCP host actually advertises a usable route/schema;
3. `LIVE_TESTED` - a disposable or production-safe native measurement was created, saved, and read back with a live computed quantity in that exact environment.

A discovered executable or visible tool list is insufficient for level 3. Before Claude may mass-create production native Length/Area measurements, the owner machine must pass `BLUEBEAM_21_10_MEASUREMENT_ACCEPTANCE.md`. If that gate fails, the safe path is reviewed Screen2XYZ geometry plus the proven Revu GUI measurement route, followed by saved-state readback where available.

Direct production PDF `/Measure` dictionary injection is out of bounds.

## ConstructDrawingAI / external-source boundary

- OpenTakeoff, PDF.js, and SAM 2 were reviewed as Apache-2.0 upstream components/ideas with pinned provenance/license notes.
- ConstructDrawingAI is PolyForm Noncommercial and is **not** copied into Screen2XYZ. Only public architecture/design ideas were reviewed after the takeoff core passed CI.
- Independently implemented ideas include evidence relationships, explicit withheld questions, synthetic-vs-real evaluation separation, data-reuse classification, and silent-miss accounting.

## Current limitations and remaining gates

- The runnable agent pilot is intentionally **one PDF page / one compatible scale context**. It is not yet the final bid-set + per-viewport `ScaleRegion` product.
- The current `.s2a.json` pilot assumes a single writer. Do not run two mutating Screen2XYZ MCP processes against the same session concurrently.
- Rule-level scope coverage still requires the explicit second visual instance pass.
- Native Bluebeam measurement create/edit/save/readback has **not** been declared `LIVE_TESTED` for the owner's Claude Code/Revu environment.
- No authorized proprietary Example Road sheet is committed as CI evidence. Real-plan quantity/coverage accuracy remains unknown until private owner-machine acceptance.
- SAM 2 remains optional; weights/runtime are intentionally absent from core.
- There is not yet a dedicated takeoff review UI merged into the existing Civil Tk workspace.
- Multi-sheet bid sets, mixed plan/profile/detail scale regions, full native Bluebeam interoperability, and real-plan accuracy claims are later gates.
- Local East/North remains non-geodetic unless tied to verified survey control.
- Default-branch merge, public release, public licensing, proprietary fixture commits, and certified claims remain unauthorized.

## Next gate

The next task is no longer more generic architecture. It is a private owner-machine acceptance on Example Road Sheet 03:

`checkout branch -> doctor --deep -> create/verify Sheet 03 session -> agent-claude-config -> connect Screen2XYZ (+ candidate Bluebeam) in Claude Code -> run disposable Revu Length+Area acceptance -> execute full takeoff prompt -> compare against estimator-reviewed Bluebeam gold -> record coverage/silent-miss/geometry/quantity/readback evidence`.

Only after that result should the branch be promoted or generalized to multi-sheet/ScaleRegion operation.