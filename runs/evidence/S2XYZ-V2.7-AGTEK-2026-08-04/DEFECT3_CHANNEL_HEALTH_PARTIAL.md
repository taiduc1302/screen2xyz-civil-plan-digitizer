# Defect 3 — channel health and partial-row evidence

Date: 2026-08-04  
Branch: `feature/v2.7-agtek-field-fixes`  
Baseline: `9ebe7f0`

## RED reproduction

`tests_app/test_channel_health_partial.py` was added before the implementation.
Against the prior code its three initial tests failed because:

- `ZoneHealthSnapshot` had no per-channel state;
- the default engine paused under the old global `3`-failure rule and could not
  name a channel that had never succeeded after 10 attempts;
- strict capture exposed only the underlying OCR message, and no opt-in partial
  Z path, nullable database field, or export Status column existed.

Raw RED output is retained in
`.lab_work/v2_7_red/defect3_channel_health_partial_red.log`.

## Implemented behavior

- Every mapped channel is attempted on each poll. Success and failure counts,
  last successful text, last failure reason, and consecutive failures are tracked
  independently.
- Both the main status line and overlay receive a summary such as
  `X ok 2 / fail 0 | Y ok 2 / fail 0 | Z ok 0 / fail 2`, together with last
  success and last failure details. `Zones are reading normally` is emitted only
  when no mapped channel failed in the current attempt.
- A channel that has never succeeded pauses after 10 failed attempts by default,
  naming the channel and its most recent reason. A channel that previously
  succeeded also pauses after 10 consecutive failures.
- Missing-Z rows are strict by default. The operator must explicitly select
  `Allow partial rows with missing Z (flagged)` before a session starts.
- An opted-in partial row stores SQL `NULL` for Z and
  `PARTIAL_MISSING_Z` in `points.capture_status`. XLSX/CSV exports include a
  Status column and leave Z empty. Advanced estimator export refuses partial
  rows until they are reviewed.
- Existing v2.6 databases are migrated from `z REAL NOT NULL` to nullable Z and
  preserve prior rows as `COMPLETE`.
- Automatic partial capture still requires two stable XY confirmations and emits
  only changed XY pairs; a persistent missing Z does not create repeated rows.

## GREEN verification

- Focused health/store/export/operations tests: 20/20.
- Full application suite: 71/71 in 140.068 s.
- Civil suite: 113/113 in 5.388 s.
- M2 suite: 498/498 in 25.583 s.
- Tk functional smoke: passed.

The Tk smoke generated files, but its screenshot helper captured the focused
desktop rather than the Tk windows. Those images are not treated as visual QA;
only the functional smoke result is claimed.
