# Civil Plan Digitizer Worklog

## 2026-07-28T21:41:40-07:00 — Repository audit and authorization

- Phase: Priority 0 repository safety.
- Files changed: governance/bootstrap documents only.
- Git: fresh private-repository clone; clean `main` at
  `3958eeafc0450d2b8339bfeee13103053e9242dc`; created
  `feature/civil-plan-digitizer-overnight`; default branch not modified.
- Architecture: standard-library Python/Tkinter with isolated baseline, M1,
  and M2 packages. Civil work will use a new sibling package.
- Independent review: three read-only agents audited architecture, baseline
  QA, and the first vertical slice; the parent task remains the sole writer.
- Tests:
  - baseline 42/42 PASS under Python 3.12 and process-scoped PowerShell bypass;
  - M1 34/34 PASS;
  - M2 deterministic 498/498 PASS;
  - M2 Windows integration 16/16 PASS on synthetic targets;
  - retained evidence verification PASS, zero errors.
- Issue found: the locally created `.venv` initially used unsupported Python
  3.10, producing four OCR execution-policy failures and 53 M2 parse/import
  errors. These were environment artifacts, not repository regressions.
- Resolution: upgraded the ignored `.venv` to installed Python 3.12; preserve
  Python 3.14 as the documented/CI target.
- Governance issue: project control files were stale after PR #5 merged.
- Resolution: reconcile current merged M2 state and record the owner’s new
  Civil Plan Digitizer authorization before functional changes.
- Privacy: no proprietary drawings were accessed, copied, uploaded, or
  committed.
- Next: implement the pure domain model, calibration transform, workflow,
  persistence, and deterministic tests.

## 2026-07-28T21:51:19-07:00 — Calibrated manual domain core

- Phase: Priority 1 domain and export vertical slice.
- Files changed: new `src/screen2xyz_civil/` contracts, models, transform,
  source intake, workflow, persistence, QA, and export modules; new
  `tests_civil/` suite.
- Implemented: two-point scale; screen-Y inversion; arbitrary East-axis
  orientation; local origin offsets; round-trip transform; optional
  second-distance verification; calibration revisions; manual
  Existing/Design/Contour points; edit/approve/reject/duplicate merge;
  schema migration; atomic save/reopen; QA; versioned approved-only AGTEK
  package with source-path redaction and hashes.
- Tests: Civil 37/37 PASS; package/test compile PASS.
- Issue found: none in the new deterministic core.
- Privacy: synthetic test data only; source local path is excluded from handoff
  manifests.
- Next: implement the estimator review workspace, launcher integration, and
  headless UI/layout coverage.

## 2026-07-28T21:57:12-07:00 — Estimator review workspace

- Phase: Priority 1 UI completion and product integration.
- Files changed: Civil Tk workspace/layout/CLI, dedicated PowerShell launcher,
  Screen2XYZ launcher menu, CI, launcher tests, and expanded civil tests.
- Implemented: local PNG open; crop drag; scale/origin/East calibration;
  second distance check; canvas pan/zoom; point overlays; synchronized review
  table; selected-point crop preview; confidence/reason display; edit, move,
  approve, reject, mark-review, merge, and confirmed manual delete; save/open;
  QA; reviewed package export; A/R/E/D/M/arrow/Escape shortcuts; persistent
  preliminary warning.
- Tests: Civil 46/46 PASS; Civil compile PASS; launcher tests 9/9 PASS; Tk
  workspace construction/headless withdrawal smoke PASS.
- Issue found: none in UI import/construction smoke.
- Limitation: guaranteed visual source intake is PNG at this milestone; local
  PDF and OCR adapters are next.
- Next: add vector PDF render/text boxes, bounded local OCR with boxes,
  candidate normalization/classification, symbol association, and UI review
  ingestion.

## 2026-07-28T22:15:18-07:00 — Local extraction and preliminary surfaces

- Phase: Priorities 2–5 integrated local processing and estimator QA.
- Implemented: selected-page PDF inspection/rendering; approximate vector-text
  boxes; PDF path extraction; bounded Windows OCR word/line boxes; numeric
  normalization; slope/date/scale/station and metadata filtering; explainable
  Existing/Design/ambiguous classification; cross/oval/dot/leader symbol
  proposals; multi-signal associations with alternatives; estimator review
  ingestion; reviewed boundaries, exclusions, breaklines, and no-cross lines.
- Added: deterministic, separate Existing and Design preliminary TIN previews;
  long/steep triangle flags; click-to-disable triangles; point-sample cut/fill
  preview (explicitly not a volume calculation); XYZ, NEZ, local-coordinate
  GeoJSON, DXF, and breakline exports; acceptance- and boundary-gated
  preliminary LandXML.
- Dependencies: pinned `pypdf==6.14.2` for PDF inspection. Poppler is detected
  as a host-installed renderer and is not redistributed. CI installs the
  optional PDF dependency only after the dependency-free baseline/M1/M2 suites.
- Tests: Civil 87/87 PASS; package/test compile PASS; one actual bounded
  Windows Media OCR run on a synthetic PNG PASS (1 line, 7 words, 45 chars).
- Privacy: all integration material was generated synthetically and processed
  locally. No drawings, source paths, OCR images, or capture artifacts were
  uploaded or committed.
- Known limitations: PDF text boxes are approximate; vector path symbol
  recognition is first-pass; breaklines are treated as no-cross barriers
  rather than inserted constrained TIN edges; cut/fill is sampled deltas, not
  a quantity or volume result.
- Next: add the synthetic benchmark harness, complete user/operator
  documentation, and run the entire repository regression and sanitization
  gates.

## 2026-07-28T22:20:48-07:00 — Benchmark and operator handoff

- Phase: Priority 6 documentation and synthetic measurement.
- Added: reproducible `CPD-SYNTH-BENCH-001` rule-level benchmark and a test
  proving its deterministic digest; operator guide, architecture, detection
  rules, AGTEK handoff workflow, per-project QA checklist, limitations, results,
  and future roadmap; current root README and master index.
- Synthetic benchmark: 105/105 exact expected rule classes, 50/50 target symbol
  associations in a controlled layout with distractors, 81/81 exact numeric
  parses, 121 transform round trips with maximum error
  `1.5888218580782548e-14` pixels, and identical classification output across
  100 iterations.
- Tests: Civil 88/88 PASS.
- Claim boundary: the benchmark does not run OCR or use a real drawing.
  Real-plan OCR/vector accuracy, estimator time, survey accuracy, and
  downstream acceptance remain unmeasured and are stated next to the results.
- Next: run the complete post-feature baseline, M1, M2, M2 Windows
  integration, civil, evidence, compile, diff, and privacy/sanitization gates.

## 2026-07-28T22:25:41-07:00 — Final local regression and handoff

- Branch: `feature/civil-plan-digitizer-overnight`; private local commits only;
  no push, merge, default-branch modification, or release.
- PASS: baseline 42/42 (4.014 s), M1 34/34, M2 deterministic 498/498
  (11.236 s), Civil 88/88, retained evidence with zero errors, compile, civil
  Tk workspace construction, and privacy/sanitization 11/11.
- PASS: actual bounded Civil Windows Media OCR on committed synthetic S001:
  `SUCCESS`, 1 line, 7 words, 45 characters, `en-US`.
- NOT CLEAN: M2 Windows integration ran 15/16 on two complete attempts. The
  unchanged number-typed-coordinate hint case captured a content-bearing frame
  but Windows OCR returned `EMPTY_TEXT`. Eight isolated executions passed five
  and failed three.
- Diagnostic: a bounded 250 ms DWM presentation delay in the disposable
  synthetic target did not improve the pass rate (3/5 in that sample). The
  experiment was completely removed and produced no commit or source diff.
  The existing M2 assertion was not weakened and M2 product code was not
  changed.
- Interpretation: the deterministic M2 suite is clean; the owner-machine
  Windows OCR integration gate is host-dependent/flaky in this final run and
  remains an explicit pre-merge review item.
- Privacy: repository scan passed; all new tests/benchmarks use synthetic
  data. No drawing, crop, OCR cache, credential, source local path, or generated
  handoff was committed or uploaded.
- Human gates remaining: authorized representative real-plan accuracy;
  estimator acceptance; AGTEK/Civil 3D/Kubla import; preliminary LandXML
  acceptance; packaging/licensing; default-branch merge and public release.

## 2026-07-29 — Standalone assisted C03 stabilization

- Phase: review-first real-drawing validation and export hardening on
  `feature/assisted-c03-validation`.
- Repository safety: all work remained in the standalone local repository.
  The protected hackathon checkout and default branch were not modified; no
  remote was configured and no push was attempted.
- Implemented: estimator Point Cart fields and sorting; undo/redo and bulk
  actions; selected export; reviewed contour lines/vertices; sheet/revision
  inference; configurable project elevation range; asynchronous PDF/OCR
  indexing; capture-at-cursor; Safe/Rapid policies; duplicate click guards;
  integer-fragment and competing-label rejection; scrollable review pane.
- OCR: added a bounded local Tesseract adapter that sweeps 15/20/25 degrees,
  inverse-maps TSV boxes, deduplicates overlap, and falls back to Windows
  Media OCR. No cloud service or network path was added.
- Real local check: the private C03 page calibrated at approximately
  0.168919 m/source-pixel; the independent distance check passed at
  approximately 0.34% error. Local multi-angle OCR indexed 1,007 word boxes,
  with 76 capturable suggestions, 170 rejected evidence items, and 761
  non-elevation boxes. One suggestion was visually matched to its raster crop,
  explicitly approved, saved, and reopened. These counts are diagnostic, not
  accuracy metrics.
- Defect found: a custom PDF font's embedded text mapping disagreed with a
  visible grade glyph.
- Resolution: discarded the unapproved point, lowered confidence for custom
  PDF encodings, made the raster crop prominent, and validated the local OCR
  path against the visible glyph before approval.
- Export hardening: removed all `screen2xyz_civil` imports of legacy product
  packages; added standalone deterministic/atomic I/O; handoffs now build in
  a hidden staging root and publish only after XLSX/CSV/XYZ/NEZ round-trip
  verification. Injected late failure leaves no final or staging folder and
  restores project export history.
- Workbook QA: eight sheets, numeric coordinate/elevation cells, filters,
  freeze panes, contour vertices, formula-safe text, redacted source path, and
  generated-file round-trip checks.
- Tests: Civil 113/113 PASS; civil compile PASS; synthetic benchmark retained
  exact deterministic scores. Full repository regression and sanitized
  packaging are the next gates.
- Privacy: the private PDF, project, OCR cache, and raster crops remain ignored
  local files. No proprietary image or extracted drawing content was placed
  in documentation, Git, or user-facing outputs.

## 2026-07-29 — Final standalone regression

- PASS: baseline 42/42, M1 34/34, M2 deterministic 498/498, M2 Windows
  integration 16/16, Civil 113/113, retained-evidence verification, and
  compile.
- PASS: synthetic rule benchmark remained exact and repeatable.
- PASS: the ignored private C03 project generated 19 reviewed handoff
  artifacts; workbook/CSV/XYZ/NEZ round-trip validation passed and the package
  contained no exported absolute local path.
- Test environment note: the baseline Windows OCR suite requires
  process-scoped `PSExecutionPolicyPreference=Bypass` on this machine. Without
  it, PowerShell policy blocks the local adapter before OCR; this is an
  environment gate, not an application result.
- Commit: `2a80876` (`feat: complete assisted civil point cart and local OCR`).
- Remaining gates: representative labelled real-plan accuracy, estimator
  acceptance, downstream AGTEK/Civil 3D/Kubla import, packaging/licensing,
  and any future merge or release authorization.
- Next: create and inspect a sanitized source ZIP and validation report. Keep
  all private drawings, projects, caches, and handoff data outside the package.
