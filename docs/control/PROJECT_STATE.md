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
- ~~**Large-polygon area artifact.** Three separate polygons returned host areas
  exactly 1/5 of the value computed from their own vertices, while lengths in
  the same region were exact. Not root-caused.~~ **Retracted 2026-09-03 — this
  was wrong.** There is no host artifact. Those three markups had been written
  with coordinates from the sheet's PROFILE band, and Revu correctly applied
  that band's anisotropic scale; 5.00 is simply the plan/profile axis-scale
  ratio (0.0881944 / 0.0176389). The "independently computed" figure was the
  one at fault, because it assumed the plan viewport's isotropic scale for
  geometry that was not in the plan viewport. Both numbers were meaningless for
  the bid. Root cause and canonical guard: `plan_layers.single_viewport_check`.
  `bluebeam_bridge.cross_check_quantity` still detects the symptom but now
  names the cause correctly (`SCALE_CONTEXT_MISMATCH`) instead of blaming the
  host. Kept visible rather than deleted, per the repository rule on not
  rewriting recorded evidence.
- **`MILL_OVERLAY_40MM` was recorded `NOT_PRESENT` on Sheet 03 and that was a
  silent miss of a paid item.** The legend swatch is a solid light-grey fill,
  not a hatch; that fill covers the roadway and measures **978.81 sq m** on
  Sheet 03 alone (cut at STA 1+140). Found and measured 2026-09-03.
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

## 2026-09-03 follow-up on the Example Road Sheet 03 pilot

Continuing the 2026-09-02 owner-machine session (new Claude Code session; verified live
that the Bluebeam file had not changed since, and that the owner cleared this session
as the sole writer per the Example Road project's own single-writer rule before touching
anything). Full detail: `SCOPE_LEDGER_Sheet03_page3_2026-09-02.md` ("Follow-up pass"
section) and Example Road `_STATUS_example_plan.md` §32.

- Re-ran the frozen Civil suite locally (`.venv-operator`): still **255/255, 0 failures,
  0 errors, 3 skipped** — no regression since the 2026-09-02 run. Still not re-run in CI.
- Scope ledger confirmed still 10/10 rules accounted for, 0 `UNSEARCHED`.
- Fixed a stale cross-reference: two ditch markups cited "RFI Q10" from the original
  question draft; the question survived into the RFI actually being sent but was
  renumbered to Q13 during consolidation. Corrected via `set_markup_property`, read
  back, confirmed. `DITCH_INFILL`'s bid-item gap was likewise connected to the RFI
  that actually governs it (Q4), rather than reading as an unexplained miss.
- **Root-caused and corrected, same day.** The owner looked at the live Revu window and
  reported nothing visible for `ROAD_WIDENING_FULL_STRUCTURE`. Checking
  `get_markup_shape` against the sheet's declared viewport bounds showed that polygon
  and both `GRAVEL_SHOULDER_030` lines had y-coordinates inside the **PROFILE**
  viewport (30-790), not the **PLAN** viewport (815-1515) where the actual road
  drawing is — not unverified, actually wrong. This also fully explains the x5 "area
  artifact": Revu was correctly using the PROFILE viewport's real anisotropic scale
  (1:250H/1:50V) for geometry that sits there; the 2026-09-02 "independent" 1,682 sq m
  figure wrongly assumed the PLAN viewport's isotropic scale. There was no Bluebeam
  defect. All three were deleted (confirmed by re-listing). Full detail: `SCOPE_LEDGER_
  Sheet03_page3_2026-09-02.md`, "Correction" section.
- **Resolved the same day — the sheet is now measured and marked up.** The decisive step
  was one this pilot had never taken: *rendering the sheet and looking at it*. Method now
  proven on real work: render the immutable base page with anti-aliasing **off** so page
  content carries exact colours, mask by colour (`#E5E5E5` solid = 40 mm mill & overlay
  per the sheet legend, `#808080` = the road-widening X-hatch), take outer boundaries
  from the solid-fill edge and **inner** boundaries from the drawing's own vector edge
  polylines rather than the hatch envelope. OpenTakeoff `one_click` was tried first and
  is *not* usable for this: it returns a ~1.3 sq m local patch on a sparse hatch
  regardless of sensitivity. `color_process_analyze` returns a page-wide colour list with
  no geometry; `add_markup_capture` attaches images and is unrelated.
- Written and read back from Revu, cross-checked against independent shoelace
  computation (all ≤0.19 %, `cross_check_quantity` `agrees=true`, `polygon_health`
  `safe_to_write=true`): road widening north **157.23 sq m**, south **171.32 sq m**,
  mill & overlay **978.81 sq m**, gravel shoulder north **99.08 m**, south **80.26 m**.
  Verified visually by overlaying geometry *read back out of the host* on the render.
- Three findings the ledger did not have: `MILL_OVERLAY_40MM` had been recorded
  `NOT_PRESENT` and is in fact the largest area on the sheet (a genuine silent miss);
  `FULL_DEPTH_ASPHALT_RR` `NOT_PRESENT` is confirmed numerically (hatch strokes split
  102/101 between 45° and 135°, no single-direction excess); and sheets 03/04 overlap by
  ~20 m (matchlines at STA ~1+157 and ~1+137.8), so all quantities were cut at STA 1+140.
- `DITCH_REGRADE`/`DITCH_RELOCATION` and `DITCH_INFILL` remain correctly `WITHHELD` —
  both need the City's RFI answer (Q13, Q4), not further AI inference.
- File still not saved to disk (no Bluebeam MCP save tool exists; `Ctrl+S` in Revu is
  the owner's action). This remains the single largest risk to today's and the prior
  session's work.

## 2026-09-03, later: the rest of the set becomes calls, and sheets 09/10 are measured

Second session of the day, working in the same local clone as the takeoff session
and pushing `task/plan-layer-extraction` to GitHub for the first time (125 commits
that had existed only on this machine). No proprietary drawing data is tracked;
the Example Road manifests and thumbnails stay in the project folder.

- **`sheet_pass.py`.** Method steps 0-4 (render AA-off, exact-colour census,
  subtract the title-block floor, name the layers) as one call. Reproduces the
  hand-built inventory exactly on sheets 04-06. Running it over all eleven drawing
  sheets found: the baseline colours in the inventory doc were descriptions, not
  RGB (five of seven guessed keys matched nothing - now *derived* by
  `derive_title_block_baseline`, floor = minimum over the drawing sheets); sheets
  11/12 carry a rasterised image (24 800 distinct colours, 39-40 greys above the
  floor in a tonal ramp against 4-9 on vector sheets) so exact-colour separation
  is declared unreliable there rather than reported as forty layers; grey-153 on
  04/06 and (221,221,109) on 08 were never listed. Anti-aliasing is process-global
  in MuPDF and is now restored after each render.
- **`cross_sections.py`.** Sheets 09/10 are pure vector: grid 0.12 pt (28.35 pt =
  0.5 m at 1:50, 141.7 pt = 5 m at 1:100 - the grid verifies the declared scale
  on every panel), surfaces 0.84 pt (design drawn 2-3 times to look heavy,
  existing as ~6 pt dashes, structure boxes), every label an outlined glyph - no
  text at all beyond the consultant's address. Design = upper envelope after
  averaging the copies; subgrade = lower envelope (structure depth 0.63 m on all
  fourteen panels); existing = traced dashes, gaps closed along the design where
  both ends sit on it. Extracted edge-of-pavement and centreline elevations match
  the printed ones to the centimetre. Stations are not read - drawn as outlines,
  no OCR - each panel gets a thumbnail with the three surfaces overlaid and the
  operator names it. **1+080-1+360, 280 m: to subgrade cut 1 117 m³ / fill 488
  m³; to finished surface 131 / 744.** No 1+200 is drawn (`SECTION_SPACING_TOO_
  WIDE`), nothing before 1+080 or after 1+360 (`RANGE_NOT_EXTRAPOLATED`). 31.04
  tendered 2 160 m³ is for the whole project; the order agrees, and no further
  reconciliation is possible from these sheets. Pay-item surface, density and the
  comparison stay the estimator's.
- Three defects caught by looking at the overlay thumbnails rather than the
  numbers: a chord closing every polyline (pymupdf `finish()` closes by default),
  the lower envelope running diagonally at box edges (~0.7 sq m of invented cut
  per edge), and a three-neighbour simplifier that dropped the crown of the road
  under dense sampling (fixed by the takeoff session, Douglas-Peucker).
- **Two-working-copy question closed.** `06 Bluebeam/...Claude_2026-09-01.pdf`
  holds 17 markups; on pages 4-6 all are ANCHOR / PARTIAL / MIXED / INFO. Nothing
  countable, nothing to double-count. Reference only.
- `pixel_area_m2` / `fill_or_hatch`: the pixel-count cross-check formalised, with
  the two-DPI test that separates a fill (area DPI-invariant, 0.85% on the mill
  fill) from a hatch (9% drift on the widening X-hatch - pixel area invalid).
- **`fill_layers.py`.** The grey fill on the plan sheets is not a vector path
  but a PDF tiling pattern (65 x 36 px cells with seams), crossed by linework,
  with the widening X-hatch drawn over it. `split_pavement` renders the
  viewport AA-off, heals seams and linework with a 2 px closing, turns the
  hatch into a region with a closing of half its measured line gap, labels the
  connected regions, traces each boundary along pixel edges and returns raw-
  frame polygons for paved works / widening / mill and overlay, each with a
  polygon area and a painted-pixel area reconciled by colour. Validated on
  sheet 05 against the host polygons read back from Revu, clipped to the same
  stations: widening +0.26%, mill and overlay +0.59%. It measured the
  Example Road junction intersection on sheet 04 (1+183.4-1+240.0: paved works 1 326,
  widening 315, mill and overlay 1 002 sq m - previously UNSEARCHED) and the
  Example Avenue ends on sheet 06 (53 + 69 sq m beyond sheet 04's matchlines; the
  rest of sheet 06 is the same ground drawn again), and found the sheet 04
  clean-segment host polygons overlapping each other by 34.2 sq m (vector-
  exact, confirmed by the session that owns them, and rewritten by it the same
  day: widening 144.37 / 113.74, M&O 385.53, no overlaps). See
  `docs/integrations/FILL_LAYER_EXTRACTION.md`.
- **Patterns by exact colour, and the pre-write gate at extraction.** The
  sheet 04 legend swatches, censused with anti-aliasing off, put the widening
  X-hatch at `(127,127,127)` and FULL DEPTH ASPHALT REMOVAL AND REPLACEMENT at
  `(178,178,178)` - the "unidentified grey-178" of the inventory, a pay item
  recorded NOT_PRESENT on sheet 03 and never searched elsewhere. `split_pavement`
  now closes every secondary hatch on its own radius and counts each region
  once under the pattern drawn on it, reports `pattern_fractions` per region,
  splits self-touching outlines into simple lobes and runs `polygon_health`
  on every region, excluding refusals from totals. Sheet 05 widening now
  matches the host to 0.03%, and **the host's sheet 05 mill-and-overlay
  polygon turns out to contain 77 sq m of full-depth asphalt R&R**; the sheet
  04 intersection zone carries 194 sq m of it in four patches. Landing pads
  (`(128,128,128)`, not in any legend) are separated out at 4.7 sq m instead
  of leaking into the widening. The owning session verified the 77 sq m against
  sheet 05's own legend, split its polygon into M&O east/west plus a full-depth
  markup, and all five reconcile to the original 559.01 with zero overlap.
- **`polygon_health` false positive found by the owning session and fixed.**
  A ring that repeats its first vertex (shapely's convention) or carries two
  consecutive equal vertices (host rounding to 0.1 pt) has a zero-length edge;
  that edge touches its neighbours at a shared point, and the touch test read
  it as a crossing on five polygons shapely called valid. Rings are now
  normalised before any edge test; a bowtie is still caught. Also recorded from
  that write: Revu silently bridges a two-ring SVG path into one invalid
  polygon - one ring per Polygon markup, holed or split items as separate
  markups.
- **`symbols.py` - the first tool for a COUNT rule.** Circle symbols found in
  the vector content by shape, size and colour (a manhole here is a 4.2 pt
  black circle, a hydro pole a 5.6 pt grey one), returned in the raw frame and
  grouped, with a crop per candidate for the label beside it. On DEMO-001-12 it
  finds exactly three, labelled D1-D3 in the crops, and the same three in
  DEMO-001-11's profile - the count the ledger had as "2 marked, likely 3".
- **CI is green on this branch for the first time** (`workflow_dispatch` run
  33727960634, all three jobs), after adding numpy to
  `requirements-civil.txt` and removing one employer-identifying colour
  nickname that the sanitization scan caught in the inventory prose. PyMuPDF
  (AGPL) is deliberately not a requirement: the three render/vector entry
  points import it lazily and the whole Civil suite runs with it blocked.
- **`clip_polygon_x` returns simple parts.** Sutherland-Hodgman joined the
  pieces of a concave region on either side of a cut with edges along the cut
  line - right area, self-touching boundary - caught by the owning session
  writing the sheet 04 intersection. Chains inside the band are now linked
  through their crossing points paired in y order; the clipped sheet 04
  mill-and-overlay piece is 385.54 sq m against the owning session's shapely
  385.53, and a 1.39 sq m sliver at a cut is refused by `polygon_health` and
  excluded rather than summed.
- **Written to Revu by the owning session, same day:** the sheet 04
  intersection zone (13 markups: 5 widening, 3 mill-and-overlay, 5 full-depth
  asphalt R&R, sum 1 213.90 sq m, pads and grey-153 withheld), the sheet 05
  full-depth split (M&O east/west 420.43 + 61.89, full-depth 74.60, all
  reconciling to the original 559.01), the rewritten sheet 04 clean segment,
  and the third manhole. Still open: sheet 06's two Example Avenue end bands.
- Civil suite **418**, green locally; CI green on the branch at 405 and 415
  (runs 33727960634, 33728429939, 33728660462).

## Current limitations / remaining gates

- Pilot is intentionally one PDF page / one compatible scale context.
- Cross-section stations are read from thumbnails by the operator, not by the
  code; 09/10 numbers cover 1+080-1+360 only and no other stretch has sections.
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