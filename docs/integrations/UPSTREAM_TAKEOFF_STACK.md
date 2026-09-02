# Open-source takeoff integration stack

This branch evaluates external open-source components that may strengthen the Civil Plan Digitizer. Nothing here is approved for production use solely by being listed.

## 1. OpenTakeoff

- Upstream: `Kentucky-ai/opentakeoff`
- Upstream branch: `main`
- Snapshot reviewed: `d5b9ba5b766911143a35fa36926a6ca3bfba794b`
- License: Apache-2.0
- Role: primary candidate for plan measurement engine and AI/MCP interaction layer.
- Useful capabilities: PDF plan loading, explicit scale gate, vector access, line/polygon/surface/count measurements, shape editing, annotations/RFIs, audit/provenance, marked-PDF/DXF export, and PDF-layer-aware workflows.
- Proposed integration: keep OpenTakeoff separable as an upstream dependency/fork and add civil-specific condition/rule adapters rather than copying its entire source tree into this repository.

## 2. Mozilla PDF.js

- Upstream: `mozilla/pdf.js`
- Upstream branch: `master`
- Snapshot reviewed: `74515c623c1a0a555e6ca684c435202bf3a91752`
- License: Apache-2.0
- Role: PDF rendering/parsing/vector/text foundation where browser-side PDF access is needed.
- Proposed integration: dependency only; do not vendor the full repository unless a specific patched fork becomes necessary.

## 3. SAM 2

- Upstream: `facebookresearch/sam2`
- Upstream branch: `main`
- Snapshot reviewed: `2b90b9f5ceec907a1c18123530e92e794ad901a4`
- License: Apache-2.0
- Role: optional raster segmentation fallback for areas that cannot be recovered reliably from vector/CAD information.
- Proposed integration: isolated optional service/module. Vector-first civil drawings should not depend on SAM 2 for primary geometry.

## 4. ConstructDrawingAI

- Upstream: `A-SHOJAEI/ConstructDrawingAI`
- Upstream branch: `main`
- Snapshot reviewed: `0b2e6c0acedfe475728d92d2066b7e75df7bc61a`
- License: PolyForm Noncommercial 1.0.0
- Role: research/reference only for architecture, evaluation ideas, and structured drawing interpretation.
- Restriction: do not copy or integrate its source code into a commercial/internal company workflow without a separate commercial license.

## Recommended architecture

```text
Civil plan PDF
  -> PDF/vector/text extraction (OpenTakeoff + PDF.js capabilities)
  -> civil interpretation layer (our rules + LLM/vision)
  -> measurement engine (OpenTakeoff line/polygon/count/edit APIs)
  -> optional raster segmentation fallback (SAM 2)
  -> human review/correction
  -> correction/provenance dataset
  -> marked PDF / quantities / downstream estimating exports
```

## Civil-specific rule layer to build here

Examples from current King Road validation:

- `ANCHOR - DO NOT SUM` is QA/reference geometry only and never a bid quantity.
- `ROAD WIDENING (FULL ROAD STRUCTURE)` requires an area takeoff when the hatch exists.
- `DITCH INFILL` is a separate area from ditch relocation/regrading.
- `0.30m GRAVEL SHOULDER` should be represented as a measured linear feature plus stated width, or as an area where required by the bid item.
- Driveway culverts are measured along the pipe centerline, not by the driveway width dimension.
- Existing gravel driveway reinstatement is a closed area polygon and must not be approximated by a generic rectangle when the drawing boundary is irregular.
- `PARTIAL`, `MIXED`, `UNRESOLVED`, or similar statuses must block silent finalization.

## Integration policy

1. Preserve upstream repository names, commit SHAs, licenses, and notices.
2. Prefer forks/submodules/dependencies over wholesale source copying.
3. Keep commercial-compatible code paths separate from research-only references.
4. Human corrections must remain first-class records so they can become evaluation/training data.
5. No automatic quantity is final until scale, geometry, classification, and scope mapping pass estimator QA.
