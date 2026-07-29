# Screen2XYZ Data Dictionary v0.1

| Field | Value |
|---|---|
| Task | S2XYZ-CODEX-003 |
| Status | G3 conditionally passed; bounded implementation corrections authorized under additive G4 closeout |
| Scope | Synthetic OCR lab schemas only |
| Encoding | UTF-8 without BOM; CSV uses comma delimiter, `QUOTE_MINIMAL` behavior, doubled embedded quotes, CRLF records, and a final CRLF |
| Output classification | Conceptual and preliminary estimating data only. |

## 1. Canonical conventions

| Item | Canonical value |
|---|---|
| Scenario identifier | `S` followed by three decimal digits, unique within fixture version |
| Coordinate format | Signed decimal degrees |
| Horizontal CRS | `EPSG:4326` |
| Axis declaration | `longitude_latitude` |
| X/Y mapping | `X=longitude`, `Y=latitude` |
| Latitude precision | Six decimal places |
| Longitude precision | Six decimal places |
| Elevation unit | `m` |
| Elevation precision | Two decimal places |
| Vertical reference | `SYNTHETIC_LOCAL` |
| Decimal separator | `.` |
| Missing CSV value | Empty field only where the schema marks nullable |
| Boolean text | lowercase `true` or `false` |
| Hash | lowercase SHA-256 hexadecimal |
| Stable row ordering | fixture `sequence` ascending |

Raw OCR text is untrusted and is never normalized in place. Normalized decimals are serialized with the fixed precision above. Degrees are not converted to distance and no horizontal or vertical accuracy is implied.

## 2. Configuration object

| Key | Type | Required | Constraint |
|---|---|---:|---|
| `schema_version` | string | yes | `1.0` for this run |
| `fixture_version` | string | yes | immutable semantic identifier |
| `seed` | integer | yes | non-negative fixed seed |
| `conditions` | ordered array | yes | exactly `baseline`, `scale_125`, `scale_150`, with fixed scale/font values and no duplicate |
| `language` | string | yes | `en-US` |
| `labels` | object | yes | `lat`, `lon`, `elev` |
| `source_crs` | string | yes | `EPSG:4326` |
| `axis_order` | string | yes | `longitude_latitude` |
| `elevation_unit` | string | yes | `m` |
| `vertical_reference` | string | yes | `SYNTHETIC_LOCAL` |
| `coordinate_precision` | integer | yes | `6` |
| `elevation_precision` | integer | yes | `2` |
| `elevation_min_m` | decimal | yes | `-500.00` |
| `elevation_max_m` | decimal | yes | `9000.00` |
| `input_root` | relative path | yes | inside registered synthetic fixture root |
| `output_root` | relative path | yes | inside the current run/evaluation root |
| `ocr_timeout_seconds` | integer | yes | `30` |
| `run_timeout_seconds` | integer | yes | `1800` |

`config_sha256` is calculated over a canonical JSON serialization with sorted object keys, UTF-8 encoding, and no insignificant whitespace.

## 3. Scenario model

| Field | Type | Nullable | Definition |
|---|---|---:|---|
| `scenario_id` | string | no | Stable unique ID matching `^S[0-9]{3}$` |
| `sequence` | integer | no | Unique, ascending processing order |
| `condition_id` | enum | no | `baseline`, `scale_125`, or `scale_150` |
| `scenario_class` | enum | no | One mutually exclusive value: `valid`, `valid_negative_elevation`, `malformed_missing`, `duplicate`, or `stale` |
| `expected_disposition` | enum | no | `ACCEPT`, `REJECT_MALFORMED`, `REJECT_MISSING`, `REJECT_DUPLICATE`, or `REJECT_STALE` |
| `expected_primary_code` | string | yes | Empty only for expected accepted rows |
| `expected_latitude` | decimal | yes | Expected normalized value where applicable |
| `expected_longitude` | decimal | yes | Expected normalized value where applicable |
| `expected_elevation_m` | decimal | yes | Expected normalized value where applicable |
| `visible_text` | string | no | Exact synthetic text supplied only to the renderer; never to OCR/parser/classifier |
| `reference_scenario_id` | string | yes | Accepted scenario referenced by duplicate/stale cases |
| `variation_id` | string | no | Spacing/symbol/text pattern identifier |
| `synthetic_only` | boolean | no | Always `true` in this run |

The fixture contains exactly 20 scenarios per condition: 12 `valid`, 2 `valid_negative_elevation`, 2 `malformed_missing`, 2 `duplicate`, and 2 `stale`. Expected-valid means `expected_disposition=ACCEPT` (42 total). Expected-invalid means any other expected disposition (18 total). A stale scenario is sequence-adjacent to its accepted reference; a duplicate is not sequence-adjacent to its first accepted reference.

## 4. `ground_truth.csv`

This file is evaluator-only data and MUST NOT be passed to the runtime pipeline.

| Column | Type | Nullable | Notes |
|---|---|---:|---|
| `scenario_id` | string | no | Join key |
| `sequence` | integer | no | Stable order |
| `condition_id` | string | no | Rendering condition |
| `scenario_class` | string | no | Expected class family |
| `expected_disposition` | string | no | Expected final disposition |
| `expected_primary_code` | string | yes | Empty for accepted case |
| `expected_latitude` | fixed decimal | yes | Six decimals where applicable |
| `expected_longitude` | fixed decimal | yes | Six decimals where applicable |
| `expected_elevation_m` | fixed decimal | yes | Two decimals where applicable |
| `reference_scenario_id` | string | yes | Expected duplicate/stale reference |
| `condition_scale_percent` | integer | no | Declared rendering scale |
| `font_size_px` | integer | no | Declared source text size |
| `variation_id` | string | no | Controlled variation |
| `synthetic_only` | boolean | no | `true` |
| `fixture_version` | string | no | Fixture version |
| `config_sha256` | hash | no | Configuration identity |

## 5. `raw_ocr_readings.csv`

This file contains runtime observations and MUST NOT contain any `expected_*` column or the renderer's `visible_text`.

| Column | Type | Nullable | Notes |
|---|---|---:|---|
| `scenario_id` | string | no | Derived from bounded input manifest, not OCR |
| `sequence` | integer | no | Manifest order |
| `condition_id` | string | no | Manifest condition |
| `image_relpath` | relative path | no | Never an absolute user path |
| `image_sha256` | hash | no | Input image hash |
| `config_sha256` | hash | no | Configuration identity |
| `ocr_engine` | string | no | Local engine identity, or exact `not_invoked` when an input-boundary failure stops before OCR |
| `ocr_engine_version` | string | yes | Version evidence if exposed; `not_exposed` for the selected engine, or `not_applicable` when OCR was not invoked |
| `ocr_language` | string | no | `en-US` |
| `ocr_status` | enum | no | `SUCCESS`, `FAILURE`, `TIMEOUT`, or `NOT_INVOKED` only for a pre-OCR input-boundary rejection |
| `raw_text_utf8_b64` | base64 string | yes | Exact OCR result encoded from UTF-8 bytes; empty only when no text was returned |
| `raw_text_sha256` | hash | yes | SHA-256 of the exact decoded UTF-8 bytes; empty only when no text was returned |
| `raw_text_display` | string | yes | Presentation-only: CR/LF/TAB become literal `\\r`/`\\n`/`\\t`; a leading formula marker is prefixed with apostrophe; never parsed or hashed as raw evidence |
| `duration_ms` | integer | no | Non-negative elapsed time |
| `ocr_error_code` | enum | yes | Empty on success; otherwise `OCR_FAILURE`, `OCR_TIMEOUT`, or `INPUT_BOUNDARY_FAILURE` when status is `NOT_INVOKED`; no free-form stack or path detail |

## 6. Runtime classification record

| Field | Type | Nullable | Definition |
|---|---|---:|---|
| `scenario_id` | string | no | Scenario key |
| `sequence` | integer | no | Processing order |
| `raw_text_utf8_b64` | base64 string | yes | Preserved exact OCR text |
| `raw_text_sha256` | hash | yes | Exact raw text identity |
| `parsed_latitude` | fixed decimal | yes | Six decimals when parsed |
| `parsed_longitude` | fixed decimal | yes | Six decimals when parsed |
| `parsed_elevation_m` | fixed decimal | yes | Two decimals when parsed |
| `source_crs` | string | no | `EPSG:4326` |
| `axis_order` | string | no | `longitude_latitude` |
| `elevation_unit` | string | no | `m` |
| `vertical_reference` | string | no | `SYNTHETIC_LOCAL` |
| `classification` | enum | no | `ACCEPTED` or `REJECTED` |
| `primary_code` | string | yes | Empty for accepted rows |
| `all_codes` | string array serialized with `|` | yes | Stable precedence order |
| `reference_scenario_id` | string | yes | Duplicate/stale accepted reference |

## 7. `accepted_points.csv`

| Column | Type | Nullable |
|---|---|---:|
| `scenario_id` | string | no |
| `sequence` | integer | no |
| `condition_id` | string | no |
| `image_relpath` | relative path | no |
| `image_sha256` | hash | no |
| `config_sha256` | hash | no |
| `longitude` | fixed decimal(6) | no |
| `latitude` | fixed decimal(6) | no |
| `elevation_m` | fixed decimal(2) | no |
| `source_crs` | string | no |
| `axis_order` | string | no |
| `elevation_unit` | string | no |
| `vertical_reference` | string | no |
| `classification` | string | no; `ACCEPTED` |

## 8. `rejected_readings.csv`

| Column | Type | Nullable |
|---|---|---:|
| `scenario_id` | string | no |
| `sequence` | integer | no |
| `condition_id` | string | no |
| `image_relpath` | relative path | no |
| `image_sha256` | hash | no |
| `config_sha256` | hash | no |
| `raw_text_utf8_b64` | base64 string | yes |
| `raw_text_sha256` | hash | yes |
| `raw_text_display` | string | yes |
| `parsed_longitude` | fixed decimal(6) | yes |
| `parsed_latitude` | fixed decimal(6) | yes |
| `parsed_elevation_m` | fixed decimal(2) | yes |
| `classification` | string | no; `REJECTED` |
| `primary_code` | rejection code | no |
| `all_codes` | pipe-delimited rejection codes | no |
| `reference_scenario_id` | string | yes |

## 9. Scenario rejection and run-fatal vocabularies

| Precedence | Scenario codes |
|---:|---|
| 1 | `INPUT_BOUNDARY_FAILURE` |
| 2 | `OCR_FAILURE`, `OCR_TIMEOUT` |
| 3 | `MISSING_LAT`, `MISSING_LON`, `MISSING_ELEV` |
| 4 | `MALFORMED_LAT`, `MALFORMED_LON`, `MALFORMED_ELEV`, `EXCESS_PRECISION_LAT`, `EXCESS_PRECISION_LON`, `EXCESS_PRECISION_ELEV`, `AMBIGUOUS_ORDER`, `EXTRA_NUMERIC_FIELD`, `CONTROL_CHARACTER` |
| 5 | `OUT_OF_RANGE_LAT`, `OUT_OF_RANGE_LON`, `OUT_OF_RANGE_ELEV` |
| 6 | `STALE_READING` |
| 7 | `DUPLICATE_READING` |

The scenario primary code is the first applicable code in the table and then lexical order within a row. `all_codes` retains all applicable codes in the same order. Input/OCR errors short-circuit and do not create derived missing codes.

Run-fatal codes are `RUN_CONFIG_INVALID`, `RUN_OUTPUT_WRITE_FAILURE`, `RUN_MANIFEST_WRITE_FAILURE`, and `RUN_TIMEOUT`. They appear only in bounded run/test status evidence with a nonzero exit and never in `rejected_readings.csv`.

## 10. `points_source_xyz.txt`

- One accepted point per line.
- Space-delimited ASCII-compatible UTF-8 text.
- Exact shape: `<longitude:6> <latitude:6> <elevation_m:2>`.
- Scenario order ascending; no header.
- X is longitude, Y is latitude, Z is elevation in metres.
- Values remain geographic degrees and `SYNTHETIC_LOCAL`; no transformation is performed.

This file is not proven suitable for Kubla import and is not described as Kubla-ready.

## 11. `points_source_xyz_metadata.json`

Required top-level keys are:

`schema_version`, `task_id`, `fixture_version`, `config_sha256`, `source_crs`, `axis_order`, `x_field`, `y_field`, `z_field`, `elevation_unit`, `vertical_reference`, `coordinate_precision`, `elevation_precision`, `ocr_engine`, `ocr_engine_version`, `ocr_language`, `accepted_count`, `rejected_count`, `artifact_sha256`, `output_classification`, `limitations`, and `deterministic_projection`.

`artifact_sha256` contains exactly `{"points_source_xyz.txt":"<lowercase-sha256>"}`; the sidecar never hashes itself. `output_classification` MUST equal `Conceptual and preliminary estimating data only.` The limitations MUST state that no coordinate transformation or live-source capture was performed and that Kubla suitability was not tested.

`deterministic_projection` contains exactly these keys: `schema_version`, `fixture_version`, `config_sha256`, `source_crs`, `axis_order`, `x_field`, `y_field`, `z_field`, `elevation_unit`, `vertical_reference`, `coordinate_precision`, `elevation_precision`, `ocr_engine`, `ocr_engine_version`, `ocr_language`, `accepted_count`, `rejected_count`, `points_source_xyz_sha256`, `output_classification`, and `limitations`. It is serialized as canonical UTF-8 JSON without BOM, sorted keys, compact separators, and final LF. Timestamps, timings, host identifiers, absolute paths, and run IDs are excluded.

## 12. `metrics.json`

Top-level keys are `schema_version` (`"1.0"`), `scenario_count` (`60`), `expected_valid_count` (`42`), `expected_invalid_count` (`18`), `metrics`, and `diagnostics`. The `metrics` object contains exactly the following 16 category keys, matching Product Requirements section 9:

1. `latitude_field_exact_match` rate object.
2. `longitude_field_exact_match` rate object.
3. `elevation_field_exact_match` rate object.
4. `complete_three_field_exact_match` with `baseline` and `all_valid` rate objects.
5. `parser_success_known_clean` rate object.
6. `end_to_end_accepted_reading_correctness` rate object.
7. `rejected_reading_rate` rate object.
8. `expected_invalid_rejection` rate object.
9. `false_accept_count` count object.
10. `false_reject_count` count object.
11. `duplicate_detection` rate object.
12. `stale_detection` rate object.
13. `coordinate_error_accepted` error object with `eligible_count`, `latitude_degrees`, and `longitude_degrees` statistics.
14. `elevation_error_accepted` error object with `eligible_count` and `metres` statistics.
15. `processing_time` timing object.
16. `repeatability_difference` difference object.

A rate object has exactly `numerator` (integer), `denominator` (integer), `rate` (JSON number rounded to six decimals or null), `target_operator` (`gte`, `eq`, or null), `target_value` (number or null), and `status` (`met`, `missed`, `report_only`, or `not_applicable`). Denominator zero requires null rate and `not_applicable`. Target status is calculated from the exact integer fraction before six-decimal display rounding.

A count object has exactly `count`, `population`, `target_operator`, `target_value`, and `status`. A statistics object has exactly `count`, `mean`, and `max`, with null mean/max when count is zero. Coordinate units are degrees and elevation units are metres.

The timing object has `unit="ms"`, `total_ms`, and `per_reading` with `count`, `mean`, `p50_nearest_rank`, `p95_nearest_rank`, and `max`. Durations come from a monotonic timer. Nearest rank sorts ascending and selects rank `ceil(p*n)` using one-based rank.

`repeatability_difference` has exactly `classification_differences`, `classification_population=60`, `raw_ocr_projection_differences`, `raw_ocr_population=60`, `deterministic_hash_differences`, `deterministic_artifact_count`, `target=0`, and `status`.

The `diagnostics` object is not a seventeenth quality metric. It records `ocr_failure_count`, `ocr_timeout_count`, and the list of failed scenario IDs for transparent failure reporting. The controlling 16 numbered metric definitions remain normative.

## 13. Privacy-safe environment and manifest records

`environment.json` MAY contain OS product/build, architecture, PowerShell version, Python version, OCR engine identity/version evidence, OCR language, relevant rendering conditions, and task/commit identifiers. It MUST NOT contain username, hostname, domain, home path, absolute repository path, IP/MAC, serial number, environment variables, token, credential, or unrelated package list.

`evidence_manifest_sha256.txt` uses relative paths and lowercase SHA-256, sorted by ordinal relative path. It excludes itself, transient caches, `.venv`, and prior-run evidence and is written last.

## 14. Deterministic comparison whitelist

The repeatability comparison includes canonical `fixture_config.json`, `ground_truth.csv`, `fixture_manifest.json`, every generated PNG hash in manifest order, the raw-OCR deterministic projection (scenario ID, sequence, condition, image path/hash, OCR status, exact raw-text base64/hash, bounded error code; no duration), full scenario classifications, `accepted_points.csv`, `rejected_readings.csv`, `points_source_xyz.txt`, and the canonical `deterministic_projection` from `points_source_xyz_metadata.json`.

It excludes environment data, durations, timestamps, absolute paths, run IDs, test transcript ordering outside deterministic tests, and the evidence manifest. Exclusion does not permit classification or raw-OCR differences to be hidden; those are counted explicitly.
