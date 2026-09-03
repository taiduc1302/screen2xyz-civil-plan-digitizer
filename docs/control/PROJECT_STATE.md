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
| Civil authorization | OD-006; implementation/tests/docs/feature commits and justified dependencies authorized; default-branch merge/release remain owner gates |
| Latest fully green complete verification | GitHub CI run **#171** on `1508ef16da27545ac8be13763a2410fc574a7dd4`: baseline PASS, M1 PASS, M2 deterministic PASS, Civil deterministic PASS with frozen count **220**, retained-evidence/privacy PASS, headless Windows integration PASS, external Claude-style Screen2XYZ stdio MCP PASS, real OpenTakeoff 0.9.68 stdio/One-Click synthetic smoke PASS |
| Local-only verification since that CI run | 2026-09-02 owner machine, `task/bluebeam-bridge-failclosed-checks`: frozen Civil suite **255/255 green** (223 before `bluebeam_bridge.py`, +32 for it). Not yet re-run in CI. |
| Output classification | Conceptual/preliminary estimating data until estimator review; no real-plan accuracy or native-Bluebeam certification claim |

## Current sources of truth

- `AGENTS.md` — repository/parent-agent rules.
- `CLAUDE.md` — Claude Code repository rules.
- `docs/control/OWNER_DECISIONS.md` — owner authorizations including OD-006.
- `docs/control/PROJECT_STATE.md` — current implementation/acceptance state.
- `docs/control/NEXT_ACTION.md` — private owner-machine acceptance sequence.
- `docs/integrations/UPSTREAM_TAKEOFF_STACK.md` — upstream/license boundary.
- `docs/integrations/RUNTIME_OPERATOR_TEST_MODEL.md` — larger runtime/operator/test architecture.
- `docs/integrations/CLAUDE_CODE_MARKUP_OPERATOR.md` — installation/operator runbook.
- `docs/integrations/BLUEBEAM_21_10_MEASUREMENT_ACCEPTANCE.md` — native Revu create/save/readback gate.
- `prompts/CLAUDE_CODE_BLUEBEAM_TAKEOFF_PROMPT.md` — full Claude takeoff task prompt.
- `docs/integrations/CONSTRUCTDRAWINGAI_IDEA_REVIEW.md` — clean-room external architecture review.

## Preserved product lines

- Sealed synthetic baseline and retained evidence remain immutable.
- M1 explicit-review/approved-only workflow remains available.
- M2-Live remains isolated under `src/screen2xyz_m2/`.
- Existing Civil Plan Digitizer terrain-point contracts remain under `src/screen2xyz_civil/`; the takeoff operator is additive, not a destructive migration.
- The older `.s2t.json` takeoff-workspace/domain code remains useful as integration architecture. The runnable Claude pilot uses a separate `.s2a.json` session so the existing Civil project schema is not silently migrated.

## Runnable operator architecture

### 1. Immutable source plus editable Revu working copy

The pilot deliberately separates the controlled drawing source from the file Revu mutates:

```text
IssuedForTender_BASE.pdf       immutable source, exact SHA-256 guarded
ExampleRoad_TAKEOFF_WORKING.pdf   editable Revu working copy
ExampleRoad_S03.s2a.json          proposal/audit/session state
```

`src/screen2xyz_civil/working_copy.py` provides:

- exact immutable source authority;
- creation/registration of a separate Revu working PDF;
- selected-page drawing fingerprints based on decoded page content + page boxes + rotation;
- tolerance for ordinary annotation/metadata byte changes in the working file;
- rejection when the working drawing/revision no longer matches the immutable source;
- a document contract embedded into the exported Bluebeam markup plan.

Native Revu work must never mutate the immutable source PDF.

### 2. Agent session and scale controls

`src/screen2xyz_civil/agent_session.py` provides a single-sheet `.s2a.json` session with:

- exact source PDF path + SHA-256 and stale-source refusal;
- page selection/label;
- canonical DPI-independent geometry in rendered PDF points;
- explicit `SCALE_RESOLVED` vs `SCALE_VERIFIED` state;
- printed-ratio, two-point calibration, and independent second-dimension verification;
- proposal persistence, correction history, evidence/questions, QA, and deterministic Bluebeam plan export.

Scale-dependent quantities remain blocked while scale is unverified. Scale changes invalidate dependent quantity state.

### 3. Review-first civil takeoff domain

Current rules include:

- `ANCHOR_ROADWORKS_EXTENT` — reference/QA only, never summable;
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

### 4. Scope / silent-miss guard

`scope_ledger.py` tracks each rule as:

`UNSEARCHED -> PROPOSED / WITHHELD / NOT_PRESENT / NOT_APPLICABLE`

`PROPOSED` is derived from actual geometry, not merely agent assertion. Claude may not finish while rules remain `UNSEARCHED`. Because this ledger is currently rule-level, the full prompt requires a second visual instance pass so one culvert/reach cannot silently stand in for multiple occurrences.

### 5. Screen2XYZ MCP gateway

`mcp_gateway.py` provides a real local stdio/Streamable-HTTP MCP server with:

- immutable sheet image/text/vector evidence;
- Bluebeam working-copy status;
- civil rule/takeoff/scope listing;
- line/polygon proposals;
- optional OpenTakeoff area trace;
- proposal geometry edits;
- flags, first-class questions, evidence links;
- takeoff/scope/working-copy QA;
- deterministic markup-plan export bound to the registered Revu target.

It intentionally has no normal `approve_takeoff` or final-bid publication tool. Drawing text is labelled untrusted project evidence.

The external stdio smoke launches the server as a separate process, obtains a real synthetic PDF sheet image, persists proposal geometry, closes the MCP client, and verifies state on disk.

### 6. Real optional OpenTakeoff integration

`opentakeoff_runtime.py` launches installed `opentakeoff-mcp` through the MCP Python client. CI pins public `opentakeoff-mcp@0.9.68`, verifies the expected tool contract, and executes a real synthetic One-Click trace.

OpenTakeoff remains a geometry engine only. Screen2XYZ owns project state, review status, provenance, uncertainty, and corrections. One-Click output enters as unverified geometry until visually checked.

### 7. Portable rendering and environment diagnostics

The Claude/operator `view_sheet` path uses pinned `pypdfium2` + Pillow, so Poppler is no longer a hard prerequisite for this pilot. `doctor` verifies required Python/PDF/MCP dependencies and optionally probes OpenTakeoff.

`agent-claude-config` emits copy/paste Claude Code stdio registration for:

1. the Screen2XYZ session; and
2. when locally discovered and a safe working PDF exists, a candidate `Bluebeam MCP Server.exe` route.

Bluebeam discovery/registration is classified `DISCOVERED_STDIO_ROUTE_NOT_LIVE_TESTED`; it is not proof of native measurement creation.

### 8. Fail-closed Bluebeam bridge (`bluebeam_bridge.py`)

Added after the 2026-09-02 owner-machine Sheet 03 run. Pure checks, no Bluebeam
calls: the operator reads the host and passes values in.

- `polygon_health` — refuses a stray-vertex outline before it reaches the host.
  The real failure scored `perimeter/sqrt(area) = 29.4`, did **not**
  self-intersect, and still produced a meaningless host area. Blocking by
  default; a long road corridor scores ~7 and passes.
- `cross_check_quantity` — independently computed vs host-reported quantity. A
  clean integer ratio is reported as a host scale/viewport fault, not a
  geometry error, because that is what was actually observed.
- `markup_text_plan` / `audit_host_text` — Bluebeam renders `label` onto the
  sheet; provenance belongs in the session record, not the drawing.
- `page_identity_report` — a viewer page label and a consultant drawing number
  are different identifiers and must both be recorded.
- `render_shows_host_state` — a render of the file on disk is not evidence
  while Revu holds unsaved markups in memory.
- `reconcile` — drift between the session and the host, including host markups
  that no proposal claims.

## Owner-machine results, 2026-09-02

Recorded because they change rows above, and because the audit of 2026-08-31
concluded the opposite on one of them.

- **Native measurement create/save/readback: PASSED** on this machine. A
  disposable `PolyLine`/`Perimeter` (200 pt) read back `17.64 m` against
  `17.6388 m` computed before creation, and a disposable `Polygon`/`Area`
  (150x150 pt) read back `175.01 sq m` / `52.92 m` against `175.008` / `52.916`
  computed before creation. Both disposables were deleted and the pre-existing
  production markups re-listed unchanged. This supersedes the 2026-08-31
  audit's "never actually produced" finding for this exact host.
- **`set_page_scale` is blocked at account/organization level, not by Studio
  Session or DMS.** The 2026-08-31 audit could not isolate the cause. The same
  `-5: Not allowed due to security restrictions` reproduces on a plain local
  file with no Studio Session and no DMS attachment. Payload note: `Precision`
  must be a string.
- **Large-polygon area artifact.** Three separate polygons returned host areas
  exactly 1/5 of the value computed from their own vertices, while lengths in
  the same region were exact. Not root-caused. `cross_check_quantity` now
  detects the class.
- Scale for Sheet 03 was resolved from the printed 1:250 ratio and
  independently verified against the disposable Length result
  (`0.088194 m/pt`, error 0.006%).

## Bluebeam capability boundary

The pilot deliberately separates:

1. `PRODUCT_DOCUMENTED` — Bluebeam documents the general capability for a named Revu version;
2. `CURRENT_SURFACE_EXPOSED` — the owner-machine MCP host advertises a usable route/schema;
3. `LIVE_TESTED` — a disposable native measurement was created, saved, and read back with live Revu-computed quantity in that exact environment.

A discovered executable, visible MCP tool list, generic Line, or generic Polygon is insufficient for level 3. Before Claude may mass-create native production Length/Area measurements, the owner machine must pass `BLUEBEAM_21_10_MEASUREMENT_ACCEPTANCE.md` for both native Length and native Area.

If that gate fails, the safe path is reviewed Screen2XYZ geometry plus the proven Revu GUI measurement route on the registered working PDF, followed by saved-state readback where available.

Direct production PDF `/Measure` dictionary injection remains out of bounds.

## ConstructDrawingAI / upstream boundary

- OpenTakeoff, PDF.js, and SAM 2 were reviewed as open upstream components/ideas with pinned provenance/license notes.
- ConstructDrawingAI is PolyForm Noncommercial and is **not** copied into Screen2XYZ.
- Independently implemented ideas include evidence relationships, explicit withheld questions, synthetic-vs-real evaluation separation, data-reuse classification, and silent-miss accounting.

## Current limitations / remaining gates

- Pilot is intentionally one PDF page / one compatible scale context.
- `.s2a.json` assumes one mutating writer.
- Scope ledger is rule-level; instance-level visual reconciliation remains required.
- Native Bluebeam Length/Area create/edit/save/readback is **not yet LIVE_TESTED** for the owner's exact Claude Code/Revu environment.
- No proprietary Example Road sheet is committed as CI evidence; real-plan quantity/coverage accuracy remains unknown until private acceptance.
- SAM 2 remains optional and is not part of the core runtime.
- There is not yet a dedicated takeoff review UI merged into the Civil Tk workspace.
- Multi-document bid sets, per-viewport `ScaleRegion`, broader Bluebeam interoperability, and real-plan accuracy claims remain later gates.
- Default-branch merge, public release/licensing, proprietary fixture commits, and certified claims remain unauthorized.

## Next gate

The next task is a private owner-machine Example Road Sheet 03 acceptance:

`checkout operator branch -> doctor --deep -> create immutable-base session -> create/register separate Revu working PDF -> verify working-copy drawing match -> independently verify scale -> agent-claude-config -> connect Screen2XYZ (+ candidate Bluebeam) in Claude Code -> disposable native Revu Length+Area create/save/readback acceptance -> run full takeoff prompt -> compare against estimator-reviewed Bluebeam gold -> record coverage/silent-miss/geometry/quantity/working-copy/readback evidence`.

Acceptance target includes:

- 0 critical silent misses;
- 0 anchors summed;
- no mixed/partial/unresolved item presented as final;
- no wrong-scale item presented as QA-complete;
- 0 native edits to the immutable base PDF;
- working-copy `drawing_match=true` after Revu saves;
- every automated native Revu measurement read back from saved state.

Only after that result should PR #8 be considered for promotion or the architecture generalized to multi-sheet/ScaleRegion operation.