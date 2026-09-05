# Open problems after the DEMO-001 pilot (2026-09-04)

What the layer-first method does not yet do, in the order a next contributor should take them. Evidence for each lives in the pilot's ledger (private, not in this repository).

1. **Reading drawing text.** Callouts, stations and table cells are glyph outlines on text layers; no OCR in the pipeline. Done = structured text with positions from a sheet (a curb-return table, a drainage table) without a human.
2. **Legend to layer dictionary.** The per-set record is confirmed by a person. Done = `legend_dictionary(pdf)` matching legend swatches (colour, hatch angle, pitch, stipple) to plan layers, validated on a layered set and a flat one.
3. **Region boundary from surrounding drawn lines.** Fill regions have no outline; the boundary is the enclosing face of the chained lines around a seed. Done = polygonize the arrangement, name the layer of each side, report open sides as pattern extent.
4. **The flat-vector regime.** A re-printed set has vectors and no layer names. Done = the same ledger from pen/linetype/symbol signatures + legend + callouts; report where it breaks.
5. **Markup migration across sheet revisions.** Done = copy markups from a base page to an addendum's revised page using `sheet_diff` windows, flagging the ones inside changed geometry.
6. **Tool debt.** M2 integration test timeout headroom on slow CI runners (test harness only); orphaned modules; rotated stipple grids not caught by the lattice gate; curved clips sampled by control points only.
7. **Research.** Cross-consultant CAD layer dictionary mined from an archive of layered PDFs; few-shot symbol recognition from a sheet's own legend for flattened sets.
