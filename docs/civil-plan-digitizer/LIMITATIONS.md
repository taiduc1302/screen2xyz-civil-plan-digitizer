# Civil Plan Digitizer Limitations

The implementation is a local preliminary estimating tool. It is not a survey,
engineering design, legal boundary, certified terrain, or quantity system.

## Validation limits

- Only deterministic synthetic fixtures and one synthetic Windows OCR
  integration image were exercised in this feature run.
- No proprietary or real authorized civil plan was used.
- No AGTEK, Civil 3D, Kubla, or other downstream import was executed.
- No estimator productivity, real-drawing recall/precision, survey accuracy,
  or earthwork quantity accuracy was measured.
- Python 3.14 is the documented/CI target; local development validation used
  installed Python 3.12.10.

## Source and extraction limits

- The fully dependency-free source path is PNG. PDF use requires `pypdf` and a
  local Poppler renderer.
- PDF text boxes are approximate and derived from text transforms; complex
  fonts, clipping, forms, nested transforms, or unusual rotations may reduce
  placement accuracy.
- PDF vector parsing handles a bounded subset of paths and first-pass
  cross/oval/leader cues. It is not a CAD entity or layer interpreter.
- Windows Media OCR language availability and quality depend on the host.
- OCR can confuse digits, decimal marks, minus signs, and letters; normalization
  never makes those results authoritative.
- Rotated, curved, crowded, rasterized, low-resolution, or overlapping labels
  can require fully manual entry.

## Coordinate limits

- Calibration is a local planar similarity transform from screen pixels.
- No geodetic CRS, map projection, datum, geoid, grid-to-ground correction,
  sheet warp, perspective correction, or multi-page registration is inferred.
- A wrong scale, origin, unit, or East direction can shift every derived point.
- PDF/display rendering and source revision changes can invalidate calibration.

## Detection and review limits

- Confidence is heuristic, sheet-agnostic, and not calibrated against a real
  dataset.
- Symbol conventions vary between consultants and jurisdictions.
- Utility/slab/metadata filters are conservative but incomplete.
- Duplicate detection uses configured spatial/elevation tolerances and may need
  estimator judgment.
- The UI does not provide multi-user locking, permissions, signatures, or a
  centralized audit service.

## Surface and export limits

- The TIN is a deterministic estimator preview, not an engineering surface.
- Breaklines/no-cross lines currently remove crossing triangles; constrained
  edge insertion and topology repair are not implemented.
- Triangle filters may leave holes and need visual review.
- Cut/fill is a set of Design-vertex elevation samples against Existing
  triangles; it is explicitly not a volume calculation.
- DXF, GeoJSON, XYZ, NEZ, CSV, and LandXML are local-coordinate handoff
  presets. Downstream compatibility is not certified.
- LandXML is feature-flagged, boundary-gated, and preliminary.

## Operational and release limits

- The application is Windows/Tkinter oriented and is not packaged or signed.
- Poppler licensing/deployment must be addressed by any distributor; the
  repository does not redistribute it.
- The repository has no selected public licence and is not authorized for
  public release.
- Source paths are redacted from exports, but project files intentionally
  retain the local source path and must be protected.
