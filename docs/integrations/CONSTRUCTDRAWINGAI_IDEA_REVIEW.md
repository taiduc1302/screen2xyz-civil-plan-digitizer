# ConstructDrawingAI idea review - clean-room architecture comparison

Reviewed snapshot: `A-SHOJAEI/ConstructDrawingAI@0b2e6c0acedfe475728d92d2066b7e75df7bc61a`

License boundary: ConstructDrawingAI is PolyForm Noncommercial 1.0.0. This review therefore treats it as an external research reference only. No ConstructDrawingAI source implementation, tests, prompts, schemas, or non-trivial code text were copied into Screen2XYZ. The comparison was made from the upstream README and architecture/design documentation (`docs/ARCHITECTURE.md`, `docs/CIR.md`, `docs/GRAPH_MAPPING.md`, `docs/PERCEPTION.md`, `docs/BENCHMARKS.md`, and `docs/HANDOFF.md`) plus repository structure names.

## What the external design emphasizes

At a high level, the documentation describes:

- a shared intermediate representation between ingest, perception, semantic grounding, takeoff engines, and agent workflows;
- source-linked confidence/provenance for extracted entities;
- explicit graph relationships in addition to detected objects;
- a semantic grounding layer rather than letting detector class names become business logic;
- separate synthetic/pipeline and held-out real evaluation boards;
- explicit coordinate-frame contracts at tiling/stitching seams;
- dataset/license provenance and separation of code from datasets/model weights;
- an agent layer that can surface uncertainty and draft RFIs instead of hiding missing facts.

Those are architectural ideas, not imported implementations.

## Comparison with Screen2XYZ before this integration

Screen2XYZ already had several equivalent or stronger controls for its civil/terrain domain:

| Concept | Existing Screen2XYZ state |
|---|---|
| Human review gate | Existing Civil Plan Digitizer already requires explicit approve/reject/edit actions. |
| Calibration audit | Existing `CivilProject` calibration has revision history and invalidates stale downstream state. |
| Source identity | Source manifest retains file hash and drawing metadata; local/private workflow is explicit. |
| Candidate provenance | Existing point candidates carry source method, confidence, reasons, alternatives, and review state. |
| Synthetic benchmark caveat | Existing benchmark explicitly says synthetic rule fixtures are not real-drawing accuracy. |
| Atomic/versioned handoff | Existing exports and manifests already use stable ids, hashes, and atomic writes. |

The main gaps were not another detector. They were **quantity-domain structure around those controls**.

## Missing ideas that were useful for civil takeoff

### 1. One normalized quantity record across engines - implemented

`src/screen2xyz_civil/takeoff.py` now provides one civil `TakeoffMeasurement` representation for manual, local-vector, OpenTakeoff, LLM-assisted, and future segmentation proposals.

It owns:

- line / polygon / count geometry;
- civil rule id and unit;
- explicit review state;
- machine provenance and confidence;
- immutable original proposal geometry;
- human correction history;
- explicit blocker flags;
- scale-gated quantity math;
- non-summable reference geometry.

This gives the takeoff workflow the same detector-independent seam that the terrain workflow already had for points.

### 2. Evidence links and relationship graph - implemented independently

Civil takeoff needs more than a shape. The estimator must be able to ask why it exists and which drawing fact supports it.

`src/screen2xyz_civil/takeoff_context.py` adds lightweight, vendor-neutral:

- `TakeoffEvidenceRef` for legend, callout, dimension, vector, text, detail, specification, bid item, human review, or engine evidence;
- optional pixel-exact source locator and source hash/reference;
- explicit data classification (`PROJECT_PRIVATE`, `SYNTHETIC_OWNED`, `OPEN_LICENSED`, `HUMAN_RULE`, `UNKNOWN`);
- typed `TakeoffRelation` edges such as `SUPPORTS`, `CONTRADICTS`, `DERIVED_FROM`, `ASSOCIATED_WITH`, and `CONTINUES_ON`;
- `evidence_for()` traversal for estimator/audit views.

This is intentionally smaller than a general construction-document graph. It addresses civil takeoff traceability without replacing the existing Civil project model.

### 3. Withheld uncertainty as a first-class record - implemented independently

A serious failure mode in estimating AI is a silent miss. A machine saying "I cannot resolve where ditch regrade becomes relocation" is safer than committing one confident total.

`TakeoffQuestion` now records:

- page and optional location;
- reason code;
- plain-language uncertainty;
- required next action;
- related takeoff/evidence ids;
- severity;
- explicit resolution/dismissal history.

The `.s2t.json` workspace persists these questions and an open `ERROR` question linked to a takeoff blocks its approval. Resolution is audited before approval can continue.

This directly supports cases already observed in the King Road review such as `PARTIAL` ditch reaches, mixed regrade/relocation traces, and obscured culvert endpoints.

### 4. Synthetic vs real evaluation separation - strengthened independently

The repo already warned that its synthetic benchmark is not real accuracy. `src/screen2xyz_civil/takeoff_eval.py` makes that distinction programmatic for the takeoff domain:

- `SYNTHETIC` and `REAL` boards are explicit;
- a synthetic result refuses an accuracy-claim assertion;
- rule classification and quantity-error metrics are separate;
- bounding-box IoU is explicitly labelled a coarse localization diagnostic, not polygon IoU;
- coverage accounts separately for **proposed**, **withheld**, and **silent-missed** expected items.

That last metric is important for estimator trust: a disclosed question is not scored the same as an undisclosed omission.

### 5. License/data-lane awareness - partially implemented

The takeoff evidence model now distinguishes private project evidence from synthetic-owned, human-rule, and open-licensed evidence. `training_evidence()` excludes `PROJECT_PRIVATE` and `UNKNOWN` records by default.

This is deliberately a data-export guard, not a legal conclusion. It prevents the convenient but dangerous default of mixing private tender drawings into a reusable/public training corpus.

## Useful ideas intentionally deferred

### Few-shot project legend adaptation

The upstream documentation describes adapting bespoke project symbols from a few legend examples. This is highly relevant to civil plans because hatch/symbol conventions vary by consultant.

Deferred until we have a stable evidence-to-rule dataset. The preferred Screen2XYZ design would be a **legend exemplar registry** attached to the takeoff context, with explicit human-confirmed mappings and optional embedding/model adapters behind it. It should not silently learn a legend mapping from one ambiguous sample.

### Full connectivity / sheet graph

Potential civil relationships include:

- driveway -> driveway culvert -> ditch;
- road-widening hatch -> typical road structure detail;
- callout -> detail sheet;
- matchline -> continuation sheet;
- utility structure -> pipe/run;
- legend key -> all corresponding plan regions.

The new typed relation layer is the minimal foundation. A general automatic sheet/connectivity graph is deferred until actual civil use cases prove which edges improve takeoff coverage.

### Gigapixel tiling and stitching contract

The external docs make an important general point: coordinate/stitching errors become count/quantity errors. Screen2XYZ already has explicit pixel/calibration contracts and the OpenTakeoff bridge now has a named coordinate conversion. Full tiled perception is not yet required for the current vector-first civil path.

If large-sheet model inference is added, tiling must have one audited composition/dedup seam with deterministic round-trip tests before its output can enter quantity review.

### Dataset registry and held-out real board

The next major accuracy milestone should not be more synthetic fixtures. It should be a private, permissioned civil evaluation registry containing estimator-reviewed cases with source/version/hash, allowed-use classification, discipline/sheet type, expected takeoff rules, and reviewed geometry/quantities.

No private tender drawing should be committed to Git. The registry should refer to local/controlled assets and record provenance separately.

## Resulting Screen2XYZ takeoff stack

```text
Civil source + existing project calibration
        |
        +--> text/vector evidence (existing local PDF path)
        +--> optional OpenTakeoff measurement proposal
        +--> optional raster segmentation proposal
        |
        v
TakeoffMeasurement                 <- one quantity contract
        |
        +--> TakeoffEvidenceRef     <- why / where did this come from?
        +--> TakeoffRelation        <- what supports/continues/associates it?
        +--> TakeoffQuestion        <- what was deliberately withheld?
        |
        v
Estimator review / correction / explicit approval
        |
        +--> .s2t.json audit workspace
        +--> correction/evaluation records
        +--> synthetic vs real evaluation board
        +--> later marked-plan / Bluebeam / estimating handoff
```

## Clean-room conclusion

The most useful external idea was not a particular model. It was treating extracted drawing facts, relations, provenance, and evaluation as separate contracts. Screen2XYZ now has that structure for **civil quantities** while keeping its existing review-first controls and without importing ConstructDrawingAI code.
