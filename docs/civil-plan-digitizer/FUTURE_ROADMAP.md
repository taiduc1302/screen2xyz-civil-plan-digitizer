# Civil Plan Digitizer Future Roadmap

Nothing in this roadmap is a current compatibility or release claim.

## Gate 1 — authorized real-plan validation

- Define a local-only labelled dataset protocol and reviewer agreement rules.
- Measure OCR, numeric filtering, symbol detection, association, class
  confusion, coordinate residuals, false-export rate, and estimator review
  time.
- Add regression fixtures derived only from redistributable synthetic
  recreations, never proprietary pages.

## Gate 2 — estimator ergonomics

- Add page thumbnails, multi-page project registration, crop/exclusion
  templates, undo/redo, bulk review, filters, and candidate sorting.
- Add richer before/after calibration diagnostics and control-point residuals.
- Add a project-level QA dashboard and explicit reviewer sign-off fields.

## Gate 3 — extraction quality

- Support rotation-aware OCR crops and multiple installed OCR languages.
- Expand bounded PDF graphics-state handling and symbol families.
- Add sheet-local pattern learning that produces reasons and remains
  review-only.
- Add contour text/line proposals without inferring elevations silently.

## Gate 4 — surface correctness

- Replace barrier-only breakline handling with tested constrained triangulation.
- Add topology validation, triangle repair tools, and section/profile views.
- Add independently validated gridded/triangulated cut/fill volumes only after
  estimator requirements and numerical acceptance tolerances are approved.

## Gate 5 — downstream validation

- Test AGTEK, Civil 3D, Kubla, DXF, CSV, and LandXML in explicitly versioned
  non-production projects.
- Record import mapping, units, coordinate order, warnings, discrepancies, and
  repeatable acceptance evidence.
- Promote only the formats that pass their own human/downstream gates.

## Gate 6 — productization and release

- Decide supported Windows/Python versions and package optional dependencies.
- Add signed installer/update posture, crash recovery, accessibility, and
  security/privacy threat review.
- Resolve licence selection, Poppler distribution posture, third-party notices,
  commit-history privacy, support, and public-release authorization.
