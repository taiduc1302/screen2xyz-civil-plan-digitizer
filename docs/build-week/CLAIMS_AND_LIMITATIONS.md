# Claims and Limitations

## Claims we can make (each traceable to retained evidence)

- Deterministic OCR→XYZ pipeline with byte-reproducible runs on the sealed
  60-image baseline (42/42 exact, 18/18 rejected, 0 false accepts/rejects;
  two independent re-runs byte-identical).
- 15/15 exact triplets across the varied 24-scenario M1 evaluation set,
  0 false rejects (synthetic, one machine).
- Immutable raw OCR retention; corrections stored separately; mandatory
  explicit human approval; approved-only exports; hashed provenance for
  every run.
- No network, no background capture, no auto-approval — enforced by tests,
  not just policy.
- 76/76 deterministic tests passing; sealed evidence manifest verifies with
  zero errors.

## Claims we must NOT make

- Any real-world, real-drawing, or real-screenshot accuracy.
- Production readiness, survey-grade output, or any authoritative datum
  (user-image vertical reference is recorded as `UNSPECIFIED_LOCAL`).
- Takeoff, estimating, CAD, Bluebeam, Civil 3D, or Kubla capability.
- Cross-machine or cross-language OCR robustness.
- That AI assistance reviewed or improved results (no live AI call has
  ever run here).

## Known limitations (say them before anyone asks)

- Synthetic evidence only; OCR is the OS engine on one Windows machine.
- Glyph confusion (`O`→`0`) produced a plausible wrong value in our own
  evaluation — retained deliberately; human review is the mitigation.
- Any unlabelled extra number in view causes rejection by design.
- en-US labels and decimal points only; PNG only; no window capture yet.
- Private repository; no licence selected; not authorized for public
  release (historical Git author metadata must be resolved first).
