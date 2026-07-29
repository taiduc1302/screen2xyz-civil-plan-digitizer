# Screen2XYZ Test Plan v0.1

| Field | Value |
|---|---|
| Task | S2XYZ-CODEX-003 |
| Status | Executed; 41/41 tests passed and retained evidence manifest verified |
| Test object | Experimental current-machine synthetic OCR laboratory |
| Test data | Locally generated synthetic values and screenshots only |
| Output classification | Conceptual and preliminary estimating data only. |

## 1. Objectives

Verify the deterministic fixture, real local OCR, raw-evidence preservation, parser, validator, stale/duplicate rules, exact schemas, atomic behavior, metrics, repeatability, privacy/data controls, and truthful scope. Testing characterizes a bounded experiment; it does not validate a product, real source, survey accuracy, earthwork, live capture, or downstream import.

## 2. Entry criteria

- G1, G2, and G3 recorded as conditionally passed.
- Architecture Specification, ADR, this Test Plan, Test Matrix, Acceptance Criteria, and Fixture Specification exist.
- Actual generated-image OCR preflight and sanitized environment/dependency/font evidence are retained.
- Repository-local `.venv` has no system-site packages and zero installed distributions.
- No Blocker/Major architecture, guardrail, or QA finding remains before G4.

No laboratory implementation or execution begins until G4 is recorded.

## 3. Environment

- Windows build 10.0.26200.0, x64, current computer only.
- Python 3.14.6 standard library in `.venv` created with `--without-pip`.
- Windows PowerShell 5.1.26100.8875 for the selected child-process adapter host. An earlier long-lived host reported 5.1.26100.8655 and is retained only as historical preflight evidence.
- System.Drawing/GDI+ and Arial regular used in place.
- Windows.Media.Ocr with `en-US`, semantic version not exposed.
- No third-party application package, OCR model, package-manager file, or runtime network dependency.

## 4. Test levels

### 4.1 Static and document validation

Validate unique requirements/RTM/test mappings, exact classification notice, prohibited-content absence, synthetic registrations, dependency versions/evidence, no absolute personal paths/secrets, no real screenshot/data, and no named-service preset or unproved claim.

### 4.2 Unit tests

Cover configuration canonicalization, fixture counts/IDs, coordinate and elevation parsing, order/labels, precision/negative zero, ranges, rejection vocabulary/precedence, stale/duplicate sequences, CSV/XYZ/sidecar serialization, metric formulas/schema, hashing, manifest, and atomic failure.

### 4.3 Adapter integration tests

Generate locally rendered PNGs, verify hashes/dimensions/metadata, invoke actual Windows OCR through the adapter, retain raw output, test invalid input/nonzero status, and enforce the 30-second child timeout. Ground truth is unavailable to the adapter.

### 4.4 End-to-end evaluation

Run the exact 60-scenario pipeline twice using identical configuration, generated images, engine identity, and ordered manifest. Join ground truth only in evaluation. Save accepted/rejected artifacts, all 16 metrics, failed scenario IDs, timing, and repeatability differences.

### 4.5 Failure and recovery tests

Exercise missing configuration metadata, path escape, corrupt/oversize image, OCR failure/timeout, malformed/missing values, ambiguous order, out-of-range values, output write failure, interruption/idempotent rerun, manifest-last policy, and prior-evidence non-overwrite.

## 5. Mandatory coverage

The Test Matrix covers:

- coordinate and elevation parser tests;
- coordinate-order and range validation;
- malformed and missing readings;
- duplicate and stale readings, including `A->A`, `A->B->A`, and `A->invalid->A`;
- deterministic fixture and ground-truth separation;
- exact CSV, XYZ, metadata-sidecar, and output-order schemas;
- atomic write/write-failure behavior;
- actual OCR at `baseline`, `scale_125`, and `scale_150`;
- exact 60-row class allocation;
- two identical repeatability runs;
- basic total and per-reading performance;
- privacy, provenance, dependency, secret/path, notice, and prohibited-content scans.

## 6. Metric method

Implement the Product Requirements' exact 16 keys and Data Dictionary schema. Expected-valid is 42 and expected-invalid is 18. Baseline expected-valid is 14. Integer target consequences are frozen before execution:

- parser known-clean: all 13 frozen cases pass;
- false accepts: 0/18;
- baseline complete exact match: 14/14;
- all-valid complete exact match: at least 38/42;
- invalid rejection: 18/18;
- duplicate classification: 6/6;
- stale classification: 6/6;
- repeatability differences: zero.

Calculate target status from exact integer fractions before six-decimal display rounding. Nearest-rank p50/p95 uses sorted monotonic millisecond durations and one-based rank `ceil(p*n)`.

## 7. Two-run protocol

1. Generate/verify the deterministic fixture once.
2. Run evaluation into a fresh local staging root `run_a` and validate all artifacts.
3. Run the same evaluation into fresh `run_b` with the same code/config/images/engine.
4. Compare scenario classifications, raw-OCR deterministic projections, and the frozen 69-item whitelist (configuration, ground truth, runtime manifest, 60 PNG hashes, raw projection, classifications, accepted CSV, rejected CSV, XYZ, and sidecar deterministic projection).
5. Publish a consolidated retained evidence set only after validation; include repeatability comparison.
6. Write the evidence manifest last.

No output is altered to improve metrics. Timing and other excluded nondeterministic fields remain recorded but are not byte-equality targets.

## 8. Evidence and exit codes

`test_results.txt` records exact commands, test names/counts, exit codes, and failures without absolute personal paths. The evaluation evidence includes every required filename in `S2XYZ-REQ-EVD-001`. Supporting checks are recorded as named test-ID results in `test_results.txt`; supporting artifacts include fixture/runtime manifests, repeatability comparison, and failed-case details.

An automated test command exits nonzero on any test failure. Evaluation may exit zero with numerical target misses only when execution/evidence are otherwise valid; those misses produce `Completed with failed targets` internally and are listed in the report. A run-fatal/evidence-integrity failure exits nonzero and is `Blocked`.

## 9. Test result classifications

- `PASS`: observed result matches exact expected behavior.
- `FAIL`: test executed and differs from expected.
- `NOT_EXECUTED`: test did not run, with reason.
- `NOT_APPLICABLE`: requirement does not apply under a documented zero denominator or scope boundary.

No proposed or planned item is recorded as observed.

## 10. Exit criteria

- Every mandatory test except `T-LIVE-001` executes. `T-LIVE-001` satisfies its obligation by recording either safe `Executed` evidence or exactly `Not executed`. Any other mandatory `NOT_EXECUTED` result prevents completion, produces `Blocked`, and fails exit criteria. `NOT_APPLICABLE` is permitted only for an explicitly defined zero denominator or scope case and cannot replace required execution.
- Parser tests pass 100%; any failure is reported.
- Exact metrics and target statuses are machine-readable.
- All expected-invalid, false accept, failed target, rejected, OCR failure, and repeatability differences are retained.
- No Blocker/Major final-review finding remains.
- Evidence parses, hashes verify, manifests are complete, and Git excludes `.venv`, caches, and unrelated binaries.

Observed automated result: 41 tests passed, with 0 failures, 0 errors, 0 skipped, and exit code 0. All frozen numerical targets were met. The retained manifest verification returned `PASS` with zero errors. The independent final branch review remains a separate handoff condition.

## 11. Optional live capture and downstream status

Live-region capture is optional and separate. Unless a safe interactive local synthetic window is intentionally tested, the run report says exactly `Not executed`. No downstream import or compatibility test is performed; the source-coordinate XYZ demonstration remains unproven for such use.
