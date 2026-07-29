# Screen2XYZ Architecture Specification v0.2

| Field | Value |
|---|---|
| Task | S2XYZ-CODEX-003 |
| Status | Conditionally authorized at G4 for the scoped synthetic OCR lab only |
| Architecture scope | Current-machine synthetic OCR laboratory only |
| Product status | Experimental lab, not an accepted functional product or production architecture |
| Output classification | Conceptual and preliminary estimating data only. |

## 1. Architecture objective

Implement the smallest reversible pipeline that proves locally generated text is rendered to pixels, consumed by actual local OCR, retained as raw evidence, parsed and validated without ground-truth substitution, classified for duplicates/stale readings, exported deterministically, and evaluated against ground truth only after runtime classification.

## 2. Observed environment and selected stack

| Component | Selected identity | Reason and boundary |
|---|---|---|
| Deterministic core | CPython 3.14.6 standard library | Available and verified in an isolated `.venv`; no project package or model needed |
| Isolation | `.venv` created with `--without-pip`, `include-system-site-packages=false` | Zero installed distributions; `.venv` is ignored and not committed |
| Windows adapter host | Windows PowerShell 5.1.26100.8875, `-NoProfile -NonInteractive` | Active child-process host and executable version rechecked before G4; provides current-machine access to OS APIs behind a process boundary |
| Renderer | `System.Drawing`/GDI+ with OS-provided Arial regular | Actual generated PNG probe passed; font is used in place and not redistributed |
| OCR | `Windows.Media.Ocr`, `en-US`, OS-managed on Windows build 10.0.26200.0 | Actual generated-image recognition returned raw text; no cloud/model download |
| Tests | Python `unittest` | Standard library, deterministic discovery, no dependency installation |

Official documentation states `Windows.Media.Ocr` desktop support requires package identity. The observed unpackaged PowerShell path is therefore an experimental current-machine adapter, not evidence of supported production hosting or general Windows compatibility.

## 3. Planned repository components

```text
src/screen2xyz_lab/
  __init__.py
  config.py
  fixture.py
  models.py
  parser.py
  validator.py
  temporal.py
  exporters.py
  metrics.py
  evidence.py
  pipeline.py
  cli.py
src/screen2xyz_lab/adapters/
  render_windows.ps1
  ocr_windows.ps1
tests/
  test_*.py
```

The PowerShell files are adapters, not general desktop automation. They accept controlled local JSON/files and do not move a cursor, capture another application, access a URL, or use a named-service preset.

## 4. Required pipeline and information separation

1. `FixtureGenerator` creates deterministic scenario definitions and evaluator-only ground truth from seed `20260715`.
2. `SyntheticRenderer` receives only the permitted render job, creates a PNG, and returns its relative path/hash/dimensions.
3. `RuntimeManifestBuilder` emits scenario ID, sequence, condition, image relative path/hash, and configuration hash. It excludes visible source text, expected values, expected classification, and reference expectations. Runtime validation reads only canonical configuration and this evaluator-free manifest; it does not read render jobs, ground truth, or reconstruct expected scenarios.
4. `ImageSource` resolves each runtime-manifest path under the registered fixture root and enforces PNG/path/size/dimension/hash/chunk limits immediately before OCR. An individual input-boundary failure rejects that scenario without reading evaluator data.
5. `OcrEngine` consumes image pixels through the Windows adapter and returns raw text/status/identity/duration.
6. `ReadingParser` consumes raw text only and produces tokens/canonical decimals or stable errors.
7. `ReadingValidator` applies metadata and numeric rules.
8. `TemporalClassifier` uses ordered runtime state only to produce accepted, stale, or duplicate outcomes.
9. `Exporter` emits separate accepted/rejected and source-coordinate demonstration artifacts.
10. `MetricsCalculator` is the only component allowed to join observed classifications to evaluator-only ground truth.
11. `EvidencePublisher` writes sanitized evidence and the manifest last.

No expected value may flow backward into steps 2-9.

## 5. Replaceable interfaces

### 5.1 `SyntheticRenderer`

Input: scenario ID, permitted visible synthetic text, condition profile, target relative path. Output: relative PNG path, byte length, dimensions, DPI, font family/style/size, and SHA-256. It fails if the font is unavailable, the target escapes its root, or output verification fails.

### 5.2 `ImageSource`

`GeneratedFileImageSource` is the only enabled adapter. `ScreenRegionImageSource` exists as a disabled interface returning `NOT_EXECUTED_SCOPE`. It MUST NOT capture a desktop or real application in this run.

### 5.3 `OcrEngine`

Input: verified local PNG relative path. Output JSON: schema version, status, raw UTF-8 text, engine identity/version evidence, language, duration, bounded error code. The Python caller enforces a 30-second child-process timeout, maps adapter exit `20` to a pre-OCR input-boundary rejection, and treats other nonzero or invalid JSON as OCR failure.

### 5.4 `ReadingParser`

Label-driven case-insensitive `lat`/`lon`/`elev` parsing uses `decimal.Decimal`, exact precision, no rounding, explicit negative-zero normalization, the bounded post-label OCR minus-glyph normalization, and the Product Requirements control-character allowlist. Exact raw OCR remains unchanged and the parser never infers coordinate order.

### 5.5 `ReadingValidator`

Requires EPSG:4326, `longitude_latitude`, metres, `SYNTHETIC_LOCAL`, complete parsed fields, and inclusive configured ranges. Missing run metadata is run-fatal before OCR; scenario range/malformed errors are retained rejections.

### 5.6 `TemporalClassifier`

State contains accepted canonical triplets with first accepted scenario plus the immediately preceding processed outcome. A same-triplet reading is stale only when the prior processed row was its accepted reference; otherwise an earlier accepted match is duplicate. Rejected rows never update accepted history.

### 5.7 `Exporter`

Writes exact CSV, XYZ, sidecar, metrics, and evidence schemas. `points_source_xyz.txt` is X=longitude, Y=latitude, Z=elevation metres in source geographic coordinates. No downstream import suitability is inferred.

### 5.8 `MetricsCalculator`

Accepts immutable observed records and separate ground truth, calculates the exact 16 metrics, retains failed IDs, and never changes classification. Ground truth is not imported by runtime modules.

### 5.9 Deferred interfaces

Coordinate transformation, cursor control, and live-capture interfaces are deliberately deferred and absent from this laboratory. No GIS, CRS conversion, cursor, automation, GUI, or real-capture library is selected. Any future interface requires a separately approved architecture change.

## 6. Adapter contracts

All adapter commands use absolute paths internally only after Python resolves and validates a repository-relative input. Arguments are passed as process argument arrays, never shell-interpolated source text. Standard output contains one UTF-8 JSON object; standard error is bounded and sanitized before evidence. Exit codes are:

- `0`: success with schema-valid JSON;
- `20`: input/path/boundary failure, mapped by the caller to `NOT_INVOKED` and `INPUT_BOUNDARY_FAILURE` rather than an OCR-engine failure;
- `21`: renderer failure;
- `22`: OCR engine/recognition failure;
- `23`: adapter output/schema failure;
- caller timeout: `OCR_TIMEOUT` and child termination.

No adapter accepts URL, host, service, desktop-window, cursor, or network parameters.

## 7. Fail-closed behavior

- Invalid/missing configuration, CRS, axis order, elevation unit, vertical reference, seed, conditions, or roots: stop before OCR with `RUN_CONFIG_INVALID`.
- Path escape, unexpected extension, oversize image, dimension limit, metadata/chunk violation, or hash mismatch with safe identity: reject `INPUT_BOUNDARY_FAILURE`; retain `ocr_status=NOT_INVOKED`, `ocr_engine=not_invoked`, and do not imply that OCR ran.
- OCR nonzero, invalid JSON, or engine failure: reject only `OCR_FAILURE`.
- OCR child timeout: reject only `OCR_TIMEOUT`.
- Missing/duplicate/ambiguous labels, extra numeric fields, prohibited controls, or unparseable values: reject with stable parser codes.
- Out-of-range values: reject with stable range codes.
- Transform, screen capture, or cursor request: reject as outside scope before work.
- Output/manifest failure: stop nonzero; do not publish partial evidence as complete.

The implementation never fills a missing OCR field from a filename, render job, or ground truth.

## 8. Determinism and atomic publication

- Fixed seed, exact condition order, stable scenario order, Decimal canonicalization, and invariant dot decimal.
- UTF-8 without BOM and exact line endings/quoting defined in the Data Dictionary.
- Canonical JSON uses sorted keys, compact separators, and final LF.
- Same-directory temporary file, flush, close, hash/parse verification, and deadline check before atomic `os.replace` for each final artifact.
- Every staging-construction and publication failure removes the bounded staging directory so a fresh deterministic rerun is not blocked by an orphan.
- A new versioned output root is required; retained prior evidence is never overwritten.
- The evidence manifest is written last and excludes itself.
- The named deterministic whitelist and raw-OCR projection are compared across two runs.

## 9. Privacy, data, and security controls

- Generated local PNG input only; no URL, socket, network request, cloud OCR, or runtime download.
- Bounded file types, names, roots, byte size, dimensions, scenario count, child timeout, and total timeout.
- Raw OCR retained reversibly as base64/hash; display text is formula-safe and never parsed.
- Environment and dependency evidence uses the approved allowlist and relative paths.
- Generated PNG metadata is absent or inspected against the allowlist before commit.
- Unexpected real/personal/confidential/service-specific data stops and is kept outside Git.

## 10. Recovery and run states

The CLI returns `0` only when its requested operation completes and required artifacts validate. Nonzero run-fatal states are bounded. Fixture generation is deterministic and may verify an existing identical fixture, but it does not overwrite retained evidence. Evaluation writes to a fresh staging directory and only exposes the declared output root after successful publication. Failed tests and target misses remain evidence.

## 11. Limitations

- Current observed computer only; not a production-support commitment.
- Generated-image OCR only; live capture status is `Not executed` unless separately and safely evidenced.
- OS OCR engine semantics may vary by Windows build and is not versioned independently.
- No coordinate transformation or authoritative comparison.
- No downstream import, terrain, or earthwork test.
- No repository licence or public release.
