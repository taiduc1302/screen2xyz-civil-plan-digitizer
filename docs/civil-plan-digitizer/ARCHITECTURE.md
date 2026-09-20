# Civil Plan Digitizer Architecture

## Safety boundary

`screen2xyz_civil` is an isolated sibling of the sealed baseline,
`screen2xyz_m1`, and `screen2xyz_m2`. The civil package now owns its atomic
write, hash/manifest, formula-safe CSV, persistence, and export helpers; it
does not import the legacy product packages. It does not modify retained
evidence or place civil state in the live-region watcher.

All extraction is local. The state model distinguishes immutable source
coordinates from derived local coordinates. Automatic candidates cannot enter
an approved state.

## Pipeline

```text
local PDF/PNG
  -> selected page render and reviewed crop
  -> PDF text/vector paths or bounded local OCR boxes
  -> numeric normalization and exclusion filters
  -> symbol proposals and multi-signal associations
  -> review-required CivilPoint records
  -> calibration transform and estimator review
  -> QA and approved-only versioned exports
  -> optional separate preliminary Existing/Design TIN previews
```

The manual path begins at estimator review and remains usable when optional
PDF/OCR adapters are unavailable.

## Modules

| Module | Responsibility |
|---|---|
| `contracts.py` | Closed enums, schema version, thresholds, descriptions |
| `models.py` | Project, point, crop, calibration, geometry, serialization |
| `source.py` | Bounded PNG identity and dimensions |
| `pdf.py` | PDF inspection, selected-page rendering, approximate text boxes, path extraction |
| `ocr.py`, `adapters/` | Swappable OCR contract, multi-angle Tesseract, and Windows Media fallback |
| `detection.py` | Normalization, exclusions, symbols, associations, explainable classes |
| `transform.py` | Scale/origin/East basis and invertible pixel/local transform |
| `workflow.py` | State transitions, review invalidation, geometry operations |
| `qa.py` | Counts, duplicates/conflicts, calibration and export blockers |
| `surface.py` | Deterministic, feature-flagged preliminary TIN and sampled cut/fill |
| `exports.py`, `estimator_exports.py`, `advanced_exports.py` | Staged approved-only handoff, estimator XLSX, round-trip checks, and advanced local formats |
| `io_utils.py` | Standalone atomic files, deterministic CSV/JSON, hashes, manifest |
| `persistence.py` | Atomic project save/open and schema migration |
| `ui/` | Tkinter estimator review workspace |

## Coordinate model

The calibration stores metres per source pixel, an origin pixel, local
East/North offsets, and a normalized positive-East basis. Screen Y is inverted
before applying the orthonormal basis. North is the 90-degree
counter-clockwise companion basis. This is a local planar coordinate frame,
not a geodetic transformation.

Source pixel and PDF-space boxes remain unchanged. Derived East/North values
are recomputed on calibration revision. Full floating-point precision is kept
internally; display and export apply explicit formatting.

## State and review invariants

- Source files are never edited.
- Candidate ingestion always yields `REVIEW_REQUIRED` or
  `AUTO_HIGH_CONFIDENCE`, never `APPROVED`.
- Approval requires calibration and a terrain-relevant class.
- Point edits, moves, reclassification, or association changes return the
  point to review.
- Recalibration preserves prior calibration records and makes exports stale.
- Approved Existing and Design points are never silently combined.
- A handoff is built and verified below a hidden staging root, then published
  by one same-volume directory rename; a failure leaves no partial final.
- Source local paths do not appear in export manifests.

## Optional dependency boundary

`pypdf==6.14.2` is pinned for PDF structure/text/path access. A host-installed
Poppler `pdftoppm` is used for local rendering and is not redistributed.
Tesseract, when installed, runs a bounded 15/20/25-degree local sweep and maps
TSV boxes back into crop coordinates. Windows Media OCR runs in a bounded
local PowerShell process as fallback. Adapter absence produces an actionable
error; it does not disable manual entry.

## Surface boundary

The pure-Python Bowyer-Watson TIN is deterministic for reviewed points. It
filters triangles against the reviewed boundary, exclusions, no-cross lines,
and breakline barriers, and honors disabled triangle IDs. It does not infer
breaklines or guarantee constrained Delaunay insertion. LandXML remains
acceptance-gated and labelled preliminary.
