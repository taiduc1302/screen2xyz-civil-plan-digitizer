# Civil Plan Digitizer Decisions

## CPD-001 — Isolated sibling package

Decision: implement under `src/screen2xyz_civil/` with a dedicated launcher
and the existing Screen2XYZ launcher menu.

Reason: the repository already isolates the baseline, M1, and M2 workflows.
M2 has a capture-specific controller and a large Tk application without a
plugin API. A sibling package preserves those proven paths while remaining
part of the Screen2XYZ product launcher.

## CPD-002 — Manual-first, review-first core

Decision: complete a reliable manual image workflow before automatic
detection. Automatic candidates are never approved implicitly.

Reason: estimators retain a useful workflow when PDF text extraction or OCR is
unavailable, and review state remains auditable.

## CPD-003 — Local coordinate basis

Decision: store an origin pixel, metres per pixel, a normalized East basis,
and an optional East/North offset. Derive the North basis as a 90-degree
counter-clockwise rotation in a screen-Y-inverted coordinate system.

Reason: an explicit orthonormal basis is deterministic, testable, and avoids
ambiguous screen/PDF rotation conventions.

## CPD-004 — Source and precision

Decision: source pixel/PDF coordinates are immutable. Easting, Northing, and
surface values retain full internal precision; rounding occurs only at
display/export. Calibration is revisioned and changes mark exports stale.

## CPD-005 — Dependencies and adapters

Decision: keep the guaranteed manual PNG core on the Python standard library.
Pin `pypdf==6.14.2` for optional PDF structure, text, and vector-path access.
Use a host-installed Poppler executable for PDF page rendering without
redistributing it. Use Windows Media OCR through a bounded local adapter.
Adapters must report an actionable unavailable state and remain mockable.

Reason: this satisfies local-processing and privacy requirements without
network upload. The pinned Python dependency and host Poppler licence/deployment
posture are recorded in the dependency register and notices.

## CPD-006 — Preliminary surfaces

Decision: implement a basic, feature-flagged local TIN preview only after
reviewed point export is stable. Boundaries/exclusions are explicit user data.
No engineering breakline is inferred. Existing and Design surfaces stay
separate. Breaklines/no-cross lines are first-pass barriers, cut/fill remains a
point-sample preview, and preliminary LandXML requires a reviewed boundary and
explicit acceptance.

## CPD-007 — Product claims

Decision: use “AGTEK-ready CSV preset” and “handoff package,” not validated
interoperability. Every UI/export surface carries the preliminary,
not-certified warning until real downstream validation is recorded.
