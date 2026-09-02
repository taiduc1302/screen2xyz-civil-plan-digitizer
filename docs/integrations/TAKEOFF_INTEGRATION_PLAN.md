# Civil takeoff integration plan

Status: active implementation on `integration/open-source-takeoff-stack`.

This plan extends the existing review-first Civil Plan Digitizer without replacing its proven terrain-point workflow. The current `screen2xyz_civil` package remains the system of record for source identity, calibration, review state, audit history, persistence, and downstream estimator handoff.

## Architectural finding

The existing repository is strong at **point/terrain digitization** but does not yet have a first-class **quantity takeoff domain**. OpenTakeoff is strong at **measured shapes and agent-driven takeoff**, but it should not become the owner of Screen2XYZ project state. The clean seam is therefore:

```text
Screen2XYZ project / source / calibration / review
        |
        +--> PDF text + vector evidence (existing Python adapters)
        |
        +--> civil interpretation + rule catalogue (new, owned here)
        |
        +--> normalized TakeoffMeasurement domain (new, owned here)
        |        |
        |        +--> local/manual geometry
        |        +--> OpenTakeoff proposal adapter (optional)
        |        +--> raster segmentation proposal adapter (optional SAM 2)
        |
        +--> estimator correction / approval / QA gate
        |
        +--> auditable quantities + correction/eval records
        |
        +--> marked-plan / estimating exports (later vertical slice)
```

OpenTakeoff remains an optional Apache-2.0 upstream dependency/service. PDF.js remains behind OpenTakeoff/browser-side PDF functionality unless a browser component is intentionally added. SAM 2 remains an optional fallback and must never be required for vector-first plans.

## Design rules

1. **One internal takeoff model.** Manual, AI, OpenTakeoff, and future segmentation proposals normalize into the same internal model before review.
2. **Explicit scale gate.** A line/area quantity is not final unless a reviewed project calibration exists. A detected printed scale is evidence, not an adopted scale.
3. **Original proposal is immutable evidence.** Human geometry corrections preserve the original proposed geometry and append correction history.
4. **No silent approval.** Automatic proposals always enter a review-required state. Only explicit estimator action can approve a summable quantity.
5. **Scope flags can block finalization.** `PARTIAL`, `MIXED`, `UNRESOLVED`, `TENTATIVE`, and similar flags are machine-readable blockers.
6. **Reference geometry is separate from bid quantity.** `ANCHOR - DO NOT SUM` may be useful for coverage QA but must never enter quantity totals.
7. **Civil semantics live here.** Rules such as ditch infill, road widening, shoulder width, driveway reinstatement, and culvert centerline logic are our domain layer rather than patches inside an upstream general-purpose engine.
8. **External engines are adapters, not databases.** Upstream tools may propose/edit geometry, but Screen2XYZ owns project persistence, audit history, rule mapping, and estimator verdicts.
9. **Fail closed.** Missing adapter executables, unsupported coordinate frames, missing scale, or ambiguous scope produce an actionable review/blocker state.
10. **Commercial-compatible path only.** Apache-2.0 components may be integrated with notices. ConstructDrawingAI remains research/reference only; its source code is not copied.

## Initial civil rule catalogue

The first deterministic rules are based on the current estimator-reviewed Example Road examples:

| Rule | Geometry | Default unit | Finalization behavior |
|---|---|---:|---|
| Roadworks extent anchor | polygon | m2 | reference only; never summable |
| Road widening - full road structure | polygon | m2 | summable after review + scale |
| 40 mm mill and overlay | polygon | m2 | summable after review + scale |
| Full-depth asphalt removal/replacement | polygon | m2 | summable after review + scale |
| Ditch infill | polygon | m2 | separate from ditch regrade/relocation |
| 0.30 m gravel shoulder | line | m | preserve stated width = 0.30 m |
| 300 mm driveway culvert | line | m | trace pipe centerline/end-to-end, not driveway width |
| Gravel driveway reinstatement | polygon | m2 | follow actual reinstatement boundary |

## Implementation phases

### Phase A - normalized takeoff core (now)

- Add deterministic takeoff geometry, measurement, provenance, correction, and rule models.
- Add quantity math from reviewed `metres_per_pixel` calibration.
- Add approval/finalization gates and QA summaries.
- Add deterministic tests including Example Road-style cases.

Acceptance:
- reference anchors cannot be approved/summed;
- line and polygon quantities are deterministic;
- blocker flags prevent approval;
- human correction keeps immutable original proposal geometry;
- approved totals include only approved, summable records.

### Phase B - project/persistence integration

- Store takeoff measurements in `CivilProject` with backward-compatible load defaults.
- Invalidate quantity approval/export freshness when calibration changes.
- Add audit events for add/edit/reject/approve.
- Add takeoff QA into project QA without weakening existing terrain QA.

### Phase C - OpenTakeoff bridge

- Implement a narrow adapter contract for OpenTakeoff line/polygon/count proposals.
- Keep coordinate conversion explicit and testable.
- Do not shell out to `npx` from core logic; an optional runner/service owns process lifecycle.
- Preserve upstream `method`, confidence, scale/origin evidence, and original boundary where supplied.

### Phase D - vector/layer evidence improvements

- Extend PDF evidence with richer path/style/layer metadata where available.
- Prefer CAD/PDF layer evidence and vector boundaries over raster inference.
- Keep existing `pypdf`/Poppler path usable when browser/OpenTakeoff components are absent.

### Phase E - optional segmentation

- Define a generic segmentation-provider protocol.
- SAM 2 may satisfy that protocol in a separate optional environment.
- A segmentation result is only a proposal mask/polygon and is never self-approving.

### Phase F - estimator workflow/export

- Add takeoff review UI alongside (not inside) terrain Point Cart semantics.
- Export an audit-friendly quantity table and correction/evaluation dataset.
- Add marked-plan export only after coordinate/render equivalence is proven.

### Phase G - ConstructDrawingAI idea review

Only after Phases A-C are stable and tested, inspect ConstructDrawingAI documentation/architecture for capabilities not already present. Record each independently reimplemented idea with its rationale and our own design. Do not copy source code, tests, prompts, schemas, or non-trivial implementation text from the PolyForm Noncommercial repository.

## Validation strategy

1. Existing baseline/M1/M2/Civil tests must stay green.
2. New deterministic takeoff tests are added to the frozen Civil test count.
3. Use synthetic fixtures only in GitHub.
4. CI evidence is required before claiming repository-level success.
5. Real Example Road/Bluebeam comparison remains an external estimator-validation gate and is not committed to this private repo unless the owner explicitly authorizes the source material.

## Non-goals for the first implementation

- Replacing Bluebeam Revu.
- Automatically approving AI takeoffs.
- Treating an LLM label as geometry evidence.
- Shipping SAM 2 model weights.
- Vendoring full OpenTakeoff, PDF.js, SAM 2, or ConstructDrawingAI trees.
- Claiming AGTEK/Bluebeam interoperability without a real downstream validation record.
