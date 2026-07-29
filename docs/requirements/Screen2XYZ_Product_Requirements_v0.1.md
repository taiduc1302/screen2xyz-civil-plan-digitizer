# Screen2XYZ Product Requirements v0.1

| Field | Value |
|---|---|
| Task | S2XYZ-CODEX-003 |
| Status | G3 conditionally passed; bounded implementation corrections authorized under additive G4 closeout |
| Scope | Scoped synthetic OCR lab only |
| Environment | Current Windows computer |
| Document version | v0.1 |
| Output classification | Conceptual and preliminary estimating data only. |

## 1. Normative scope

`MUST` and `MUST NOT` identify mandatory requirements for this run. All requirements are proposals until Gate G3 is recorded. No statement below is an observed test result.

The supported coordinate representation is decimal degrees in EPSG:4326. Canonical export axis order is `X=longitude`, `Y=latitude`. Elevation is metres and the vertical reference is `SYNTHETIC_LOCAL`. These are run-scoped choices, not universal product decisions.

## 2. Configuration requirements

| ID | Requirement | Verification |
|---|---|---|
| S2XYZ-REQ-CFG-001 | The lab MUST load a versioned machine-readable configuration containing schema version, fixture version, seed, exactly three ordered condition IDs (`baseline`, `scale_125`, `scale_150`), their scale/font values, language, labels, CRS, axis order, elevation unit, vertical reference, coordinate/elevation precision, permitted numeric ranges, input root, and output root. A canonical configuration hash MUST be retained. | Configuration tests and sidecar evidence |
| S2XYZ-REQ-CFG-002 | Missing or conflicting CRS, axis order, elevation unit, vertical reference, labels, precision, seed, or path constraints MUST fail before OCR or final output. | Negative configuration tests |
| S2XYZ-REQ-CFG-003 | Configuration and code MUST contain no named-service preset, real-source coordinate, service-specific screen coordinate, URL, or network input. | Static review and tests |

## 3. Synthetic fixture requirements

| ID | Requirement | Verification |
|---|---|---|
| S2XYZ-REQ-SYN-001 | The fixture MUST contain exactly 60 uniquely identified, deterministically ordered, mutually exclusive scenarios. Each of `baseline`, `scale_125`, and `scale_150` MUST contain 12 ordinary valid, 2 additional valid negative-elevation, 2 malformed/missing, 2 duplicate, and 2 sequence-adjacent stale scenarios: 20 per condition, 42 expected-valid and 18 expected-invalid overall. Counts and condition profiles MUST be frozen before OCR. | Fixture validation and manifest |
| S2XYZ-REQ-SYN-002 | Ground truth MUST be stored separately from OCR/runtime records, generated from a fixed seed, hashed, and inaccessible to OCR, parser, validator, duplicate/stale classifier, and exporter until evaluation joins by scenario ID. | Separation test and code review |
| S2XYZ-REQ-SYN-003 | Rendered text MUST visibly use English labels `lat`, `lon`, and `elev`; include positive and negative longitude, positive and negative elevation, spacing and symbol variation, malformed latitude, missing elevation, duplicate, and stale cases; and use only local synthetic values. | Screenshot manifest and scenario coverage test |
| S2XYZ-REQ-SYN-004 | Each image MUST be PNG, at most 10,000 pixels in either dimension, at most 10 MiB, stored under the registered fixture root, named from a constrained scenario ID, and accompanied by a SHA-256 hash. | Input-boundary tests and manifest |

## 4. Image and OCR requirements

| ID | Requirement | Verification |
|---|---|---|
| S2XYZ-REQ-INP-001 | Required input MUST be generated image files. The lab MUST NOT capture a real source, a full desktop, another application, or a named service. | Static and runtime input checks |
| S2XYZ-REQ-INP-002 | Optional live-region smoke testing is a separate activity against the local synthetic display only. If an interactive safe desktop is unavailable it MUST be recorded as `Not executed` and MUST NOT affect lab completion. | Run report |
| S2XYZ-REQ-OCR-001 | Actual local OCR MUST consume image pixels. Fixture values, filenames, expected values, and ground truth MUST NOT substitute for OCR text. | Adapter integration test and evidence |
| S2XYZ-REQ-OCR-002 | For every scenario, the lab MUST retain scenario ID, relative image path, image hash, exact raw OCR UTF-8 bytes as base64 plus SHA-256, a separately named presentation-safe display field, OCR status, engine identity/version evidence, locale, duration, and a bounded stable error code where applicable. Free-form exception detail MUST NOT enter retained CSV evidence. | Raw OCR schema validation |
| S2XYZ-REQ-OCR-003 | OCR MUST be local and MUST NOT require network, cloud processing, telemetry upload, or a named mapping source. An individual OCR operation MUST time out after 30 seconds and the full run after 30 minutes rather than wait indefinitely. | Dependency review and timeout tests |

## 5. Parser requirements

| ID | Requirement | Verification |
|---|---|---|
| S2XYZ-REQ-PAR-001 | The parser MUST require exactly one case-insensitive `lat`, `lon`, and `elev` label. No OCR label alias is accepted in v0.1. It MAY tolerate ASCII spacing, colon/equal separators, the pipe delimiter used by the controlled fixture, degree symbols or the exact `deg` designator, line breaks, tabs, and an optional `m` suffix, but MUST reject an absent, duplicate, unlabelled, or ambiguous field rather than infer coordinate order. | Parser unit tests |
| S2XYZ-REQ-PAR-002 | Latitude and longitude MUST use signed dot-decimal syntax with at most six fractional digits; elevation MUST use signed dot-decimal syntax with at most two. A single ASCII hyphen, Unicode minus, en dash, or em dash immediately after a required label and immediately before digits (with optional intervening ASCII whitespace) MAY normalize to the canonical ASCII negative sign while exact raw OCR remains unchanged. Shorter values are zero-padded, negative zero canonicalizes to positive zero, and excess precision rejects without rounding. Leading/trailing numeric zeros are permitted. Non-finite values, comma decimals, exponent notation, extra numeric fields, NUL, C0 controls other than CR/LF/TAB, and C1 controls MUST reject. | Parser unit tests |
| S2XYZ-REQ-PAR-003 | Raw OCR text and parsed tokens MUST remain separate. The parser MUST NOT mutate retained raw OCR text or consult expected values. | Unit and code review |

## 6. Validation and classification requirements

| ID | Requirement | Verification |
|---|---|---|
| S2XYZ-REQ-VAL-001 | Latitude MUST be within inclusive `[-90, 90]`; longitude within inclusive `[-180, 180]`; elevation MUST be finite and within configured synthetic bounds `[-500.00, 9000.00]` metres. EPSG:4326, `longitude_latitude`, metres, and `SYNTHETIC_LOCAL` are mandatory. | Boundary and metadata tests |
| S2XYZ-REQ-VAL-002 | A reading is accepted only if configuration and metadata are valid, all required fields parse, all ranges pass, and the canonical triplet is neither stale nor duplicate. Every other reading MUST be retained as rejected. | Integration tests |
| S2XYZ-REQ-VAL-003 | Scenario rejection codes MUST include `INPUT_BOUNDARY_FAILURE`, `OCR_FAILURE`, `OCR_TIMEOUT`, `MISSING_LAT`, `MISSING_LON`, `MISSING_ELEV`, `MALFORMED_LAT`, `MALFORMED_LON`, `MALFORMED_ELEV`, `EXCESS_PRECISION_LAT`, `EXCESS_PRECISION_LON`, `EXCESS_PRECISION_ELEV`, `AMBIGUOUS_ORDER`, `EXTRA_NUMERIC_FIELD`, `CONTROL_CHARACTER`, `OUT_OF_RANGE_LAT`, `OUT_OF_RANGE_LON`, `OUT_OF_RANGE_ELEV`, `STALE_READING`, and `DUPLICATE_READING`. All applicable scenario codes and one deterministic primary code MUST be retained. Run-fatal codes are separate. | Vocabulary and negative tests |
| S2XYZ-REQ-VAL-004 | Scenario primary-code precedence MUST be: input-boundary failure; OCR failure/timeout; missing field; malformed/excess-precision/ambiguous/control-character error; range error; sequence-adjacent stale; non-adjacent duplicate; accept. Input/OCR failure short-circuits parsing and MUST NOT add derived missing-field codes. Rejected readings MUST NOT update accepted-value history. | Precedence tests |
| S2XYZ-REQ-DED-001 | An otherwise valid canonical triplet MUST be `STALE_READING` only when the immediately preceding processed sequence row was accepted and has the same triplet. It is rejected and references that adjacent accepted scenario. `A accepted -> invalid -> A` is not stale. | Stale tests |
| S2XYZ-REQ-DED-002 | An otherwise valid canonical triplet matching any earlier accepted triplet, but not qualifying as sequence-adjacent stale, MUST be `DUPLICATE_READING`, rejected, and reference the first accepted matching scenario. Thus `A -> B -> A` and `A -> invalid -> A` are duplicate. Repeated rejected stale rows do not update history. | Duplicate tests |

## 7. Output and review requirements

| ID | Requirement | Verification |
|---|---|---|
| S2XYZ-REQ-EXP-001 | CSV MUST use UTF-8 without BOM, comma delimiter, `QUOTE_MINIMAL` behavior (quote only fields containing comma, double quote, CR, or LF), doubled embedded quotes, CRLF line endings, a final CRLF, stable headers, empty nullable fields, dot decimals, and scenario order. Exact raw OCR is stored only as base64 plus hash; `raw_text_display` escapes CR/LF/TAB visibly and is prefixed with an apostrophe only when its first character is `=`, `+`, `-`, or `@`. Every rejected reading is retained. | Schema and injection tests |
| S2XYZ-REQ-EXP-002 | `ground_truth.csv`, `raw_ocr_readings.csv`, `accepted_points.csv`, and `rejected_readings.csv` MUST follow the Data Dictionary. `raw_ocr_readings.csv` MUST contain no expected values. | Schema tests and separation test |
| S2XYZ-REQ-EXP-003 | `points_source_xyz.txt` MUST contain only accepted points in deterministic scenario order as `longitude latitude elevation_m` with fixed precision. It is a source-coordinate demonstration, not a proven Kubla-ready file. | Golden-output tests |
| S2XYZ-REQ-EXP-004 | `points_source_xyz_metadata.json` MUST record schemas, hashes, configuration, EPSG:4326, `X=longitude/Y=latitude`, metres, `SYNTHETIC_LOCAL`, engine/runtime identity, limitation text, and exactly `Conceptual and preliminary estimating data only.` Its `artifact_sha256` object MUST contain exactly the relative name and hash of `points_source_xyz.txt`. | Sidecar schema test |
| S2XYZ-REQ-EXP-005 | Final deterministic artifacts MUST use practical atomic writes. A write failure MUST return nonzero, leave no partial final artifact, and never overwrite retained prior-run evidence. | Injected write-failure tests |
| S2XYZ-REQ-REV-001 | The lab MAY emit classified demonstration output only after classification into its versioned evidence root. A future non-lab product export MUST require explicit user review and confirmation; that workflow is deferred and not implemented here. | Architecture and scope review |

## 8. Privacy, recovery, performance, repeatability, and claims

| ID | Requirement | Verification |
|---|---|---|
| S2XYZ-REQ-PRI-001 | Committed images, values, and raw OCR MUST be registered locally generated synthetic data. Evidence MUST omit secrets, credentials, environment-variable dumps, usernames, hostnames, domain names, absolute personal paths, network addresses, hardware serials, and unrelated package inventories. | Evidence inspection and secret scan |
| S2XYZ-REQ-PRI-002 | Retained run evidence MUST be copy-on-write and immutable after manifesting. Temporary files, caches, `.venv`, and local adapters MAY be cleaned only when they are untracked and not retained evidence. | Run guide and repository review |
| S2XYZ-REQ-REC-001 | Invalid configuration MUST fail before OCR. Corrupt images and OCR failures MUST become explicit rejected records when scenario identity is safe. Interrupted reruns MUST be idempotent for designated deterministic outputs. | Failure and rerun tests |
| S2XYZ-REQ-REC-002 | Unexpected real, personal, employer, client, confidential, proprietary, service-specific, or credential data MUST stop the run, remain outside Git, and be escalated; history MUST NOT be rewritten unilaterally. | Threat review and process test |
| S2XYZ-REQ-REC-003 | Run-fatal codes MUST be separate from scenario rejections: `RUN_CONFIG_INVALID`, `RUN_OUTPUT_WRITE_FAILURE`, `RUN_MANIFEST_WRITE_FAILURE`, and `RUN_TIMEOUT`. A run-fatal condition MUST short-circuit, return nonzero, write only bounded status/test evidence where safe, and MUST NOT be inserted into `rejected_readings.csv`. A failed output cannot be represented as successfully published evidence. | Run-failure tests |
| S2XYZ-REQ-PER-001 | The lab MUST record per-image OCR time and total, mean, p50, p95, and maximum processing time. Results are current-machine characterization only; there is no product performance acceptance threshold. | Metrics validation |
| S2XYZ-REQ-MET-001 | `metrics.json` MUST implement exactly the 16 canonical keys, formulas, denominators, units, target operators, zero-denominator handling, and object shapes defined in section 9 and the Data Dictionary. Target status MUST be calculated from exact integer fractions before any six-decimal display rounding. | Metrics calculation and schema validation |
| S2XYZ-REQ-REP-001 | Two runs with identical code, engine identity, and inputs MUST match the frozen 69-item deterministic whitelist: canonical fixture configuration; ground truth; fixture manifest; all 60 screenshot hashes; a raw-OCR projection containing scenario/image identity, status, exact raw-text base64/hash, and bounded error code but no duration; scenario classifications; accepted/rejected CSV; XYZ; and the exact sidecar deterministic projection. Environment, durations, timestamps, absolute paths, and run IDs are excluded. | Two-run comparison |
| S2XYZ-REQ-CLS-001 | Every report, README, example, demonstration export metadata, and public-facing draft created by this run MUST state exactly `Conceptual and preliminary estimating data only.` No survey, construction, authoritative, earthwork, live-capture, public-release, universal-compatibility, or Kubla compatibility claim is permitted. | Static content scan |
| S2XYZ-REQ-TRC-001 | The RTM MUST map every mandatory requirement to at least one acceptance criterion, test ID, and planned evidence path. No mandatory requirement may be orphaned and no observed result may be entered before execution. | RTM validation |
| S2XYZ-REQ-EVD-001 | A completed evaluation MUST publish exactly the required evidence set: `ground_truth.csv`, `raw_ocr_readings.csv`, `accepted_points.csv`, `rejected_readings.csv`, `points_source_xyz.txt`, `points_source_xyz_metadata.json`, `metrics.json`, `environment.json`, `dependency_inventory.txt`, `test_results.txt`, and `evidence_manifest_sha256.txt`, plus explicitly documented supporting artifacts. | Evidence completeness test |
| S2XYZ-REQ-EVD-002 | `evidence_manifest_sha256.txt` MUST list lowercase SHA-256 and repository-relative path for each retained evidence file in ordinal path order, excluding itself. It MUST be written last after all listed artifacts are closed and verified. | Manifest test |
| S2XYZ-REQ-EVD-003 | `environment.json`, `dependency_inventory.txt`, and `test_results.txt` MUST use the privacy allowlist, record relevant exact versions/commands/tests/exit codes without secrets or absolute personal paths, and distinguish observed results from limitations or `Not executed`. | Evidence sanitation and schema tests |

## 9. Canonical metric definitions

`expected-valid` means the 42 rows whose `expected_disposition` is `ACCEPT`. `expected-invalid` means the 18 malformed/missing, duplicate, or stale rows. Duplicate/stale rows are not part of field/complete exact-match denominators. A zero denominator produces `not_applicable`, never a pass. Rates are decimal numbers in `[0,1]` plus integer numerator/denominator.

| # | Metric key | Denominator and calculation | Target |
|---:|---|---|---:|
| 1 | `latitude_field_exact_match` | expected-valid rows; numerator has parsed latitude exactly equal at six decimals | Report |
| 2 | `longitude_field_exact_match` | expected-valid rows; numerator has parsed longitude exactly equal at six decimals | Report |
| 3 | `elevation_field_exact_match` | expected-valid rows; numerator has parsed elevation exactly equal at two decimals | Report |
| 4 | `complete_three_field_exact_match` | report `baseline` over 14 expected-valid baseline rows and `all_valid` over all 42; numerator has all three fields exact regardless of final disposition | baseline 14/14; all-valid at least 38/42 |
| 5 | `parser_success_known_clean` | passing known-clean parser cases / executed known-clean parser cases | 100% |
| 6 | `end_to_end_accepted_reading_correctness` | expected-valid rows actually `ACCEPTED` with all three fields exact / 42 | Report |
| 7 | `rejected_reading_rate` | rows actually `REJECTED` / 60 | Report |
| 8 | `expected_invalid_rejection` | expected-invalid rows actually rejected / 18 | 18/18 (at least 95% and 17/18 is 94.44%) |
| 9 | `false_accept_count` | count of expected-invalid rows actually accepted | 0/18 |
| 10 | `false_reject_count` | count of expected-valid rows actually rejected | Report |
| 11 | `duplicate_detection` | expected duplicate rows correctly classified `DUPLICATE_READING` / 6 | 6/6 |
| 12 | `stale_detection` | expected stale rows correctly classified `STALE_READING` / 6 | 6/6 |
| 13 | `coordinate_error_accepted` | expected-valid accepted rows with nonnull parsed and expected coordinates; separate absolute latitude/longitude errors in degrees with count, mean, and max | Report |
| 14 | `elevation_error_accepted` | expected-valid accepted rows with nonnull parsed and expected elevation; absolute error in metres with count, mean, and max | Report |
| 15 | `processing_time` | monotonic milliseconds: total plus per-reading count, mean, nearest-rank p50/p95, and max | Report only |
| 16 | `repeatability_difference` | count classification differences over 60, raw-OCR projection differences over 60, and hash differences over the declared deterministic whitelist | zero differences |

Targets and exact integer pass counts are frozen before OCR and MUST NOT be weakened after observing results. Pass/fail status is calculated using the exact integer fraction; the six-decimal JSON rate is display/reporting precision and MUST NOT change status.

## 10. Completion classifications

- `Completed`: all mandatory work executed, evidence valid, and all target thresholds met.
- `Completed with failed targets`: all mandatory work executed and evidence valid, but one or more numerical targets missed.
- `Blocked`: mandatory execution or trustworthy evidence could not be completed.

These laboratory classifications do not imply an accepted product or authoritative validation.

For the controlling final response, both a valid `Completed` experiment and a valid `Completed with failed targets` experiment map to `Planning and synthetic OCR lab completed`; any failed targets are listed separately. This does not imply product acceptance.

## 11. Normative acceptance criteria

| ID | Pass condition |
|---|---|
| AC-001 | A valid canonical configuration loads and hashes; every missing/conflicting mandatory key fails before OCR with nonzero run status. |
| AC-002 | Exactly 60 mutually exclusive scenarios and three specified conditions are generated with the frozen 42/18 allocation, fixed seed, unique IDs, relative paths, hashes, and ground-truth separation. |
| AC-003 | Every image is consumed by the local OCR adapter, every raw observation uses the exact reversible schema, no expected value enters runtime input, and failure/timeout is explicit. |
| AC-004 | All clean, variant, malformed, ambiguity, control-character, excess-precision, negative-zero, coordinate-order, and elevation parser tests pass. Parser known-clean success is 100%. |
| AC-005 | Metadata, numeric ranges, scenario error vocabulary, short-circuit, all-code retention, and primary-code precedence match sections 5-6 in every test. |
| AC-006 | `A->A`, `A->B->A`, `A->invalid->A`, repeated rejected rows, and OCR-failure sequences match the normative stale/duplicate rules; fixture duplicate and stale results are each 6/6. |
| AC-007 | All required CSV files match exact headers/types/order/encoding/BOM/delimiter/quoting/CRLF/final-CRLF rules, preserve reversible raw OCR evidence, contain no expected-value leak, and retain all rejected rows. |
| AC-008 | XYZ is deterministic `longitude latitude elevation_m`; `points_source_xyz_metadata.json` matches its exact schema/hash, records source metadata/limitations/classification, and makes no import claim. |
| AC-009 | Config, image, timeout, interruption, and injected write failures return bounded nonzero status; no partial final output is exposed; successful reruns are idempotent. |
| AC-010 | All committed data are registered synthetic; privacy/contamination/retention/network controls pass static and evidence scans; optional live status is exactly `Executed` with safe evidence or `Not executed`. |
| AC-011 | `metrics.json` validates against the exact 16-key schema and frozen denominators/targets, reports every failed case, and uses the defined nearest-rank timing method. |
| AC-012 | Two equivalent runs have zero classification, raw-OCR projection, and deterministic-whitelist hash differences; excluded nondeterministic fields are documented. |
| AC-013 | Static review finds no named-service preset, real-source data, prohibited automation, unsupported claims, public licence/release, transform/cursor implementation, or unproved Kubla compatibility; every required classification notice is exact. |
| AC-014 | Every mandatory requirement ID is unique and maps to at least one defined AC, defined planned test, and exact repository-relative evidence path; no mandatory orphan exists. |
| AC-015 | All required evidence artifacts exist, parse, are sanitized, contain exact relevant versions/commands/tests/exit codes, are hashed by a manifest written last, and distinguish failed/not-executed work honestly. |

## 12. Planned test catalogue

| Test ID | Planned intent |
|---|---|
| T-CFG-001 | Load/canonicalize/hash the complete configuration and exact three conditions. |
| T-CFG-002 | Reject each absent/conflicting mandatory configuration key before OCR. |
| T-FIX-001 | Validate exact 60-row mutually exclusive allocation and stable IDs/order. |
| T-FIX-002 | Prove ground-truth fields are absent from runtime OCR/classifier input. |
| T-FIX-003 | Validate labels, signs, text variations, conditions, and fixture hashes. |
| T-INP-001 | Enforce PNG extension, path root, ID, byte, dimension, and hash boundaries. |
| T-LIVE-001 | Validate the mandatory live-status record (`Executed` or `Not executed`). |
| T-OCR-001 | Prove generated image pixels pass through actual local OCR. |
| T-OCR-002 | Validate reversible raw OCR, hash, identity, timing, and bounded status schema. |
| T-OCR-003 | Verify local/no-network boundary and OCR/run timeout behavior. |
| T-PAR-001 | Exercise exact labels, separators, whitespace, symbols, ambiguity, and order. |
| T-PAR-002 | Exercise signs, precision, negative zero, malformed numbers, and controls. |
| T-PAR-003 | Prove raw text is unchanged and expected values are inaccessible. |
| T-VAL-001 | Exercise ranges and mandatory metadata. |
| T-VAL-002 | Exercise accepted/rejected integration and complete retention. |
| T-VAL-003 | Validate scenario and run-fatal vocabularies. |
| T-VAL-004 | Validate short-circuit and deterministic primary/all-code precedence. |
| T-DED-001 | Exercise all normative stale sequences. |
| T-DED-002 | Exercise all normative duplicate sequences and references. |
| T-EXP-001 | Validate exact CSV dialect and formula-safe display/reversible raw fields. |
| T-EXP-002 | Validate all CSV schemas and expected-value separation. |
| T-EXP-003 | Validate XYZ values, order, precision, and source-coordinate semantics. |
| T-EXP-004 | Validate exact metadata sidecar schema, artifact hash, and limitations. |
| T-REC-001 | Inject atomic output failure and verify no partial final artifact. |
| T-REC-002 | Exercise configuration/image/interruption/rerun recovery. |
| T-REC-003 | Exercise run-fatal codes, status record, short-circuit, and exit codes. |
| T-PRI-001 | Scan environment/evidence for secrets, identities, and absolute personal paths. |
| T-PRI-002 | Verify copy-on-write retention and manifest coverage. |
| T-PRI-003 | Verify contamination, no-network, and escalation controls. |
| T-MET-001 | Validate all 16 calculations, denominators, targets, timing, and failed cases. |
| T-MET-002 | Validate exact `metrics.json` schema and zero-denominator behavior. |
| T-REP-001 | Compare two identical runs across the complete deterministic whitelist. |
| T-SCOPE-001 | Scan configuration/code for service presets, URLs, and network inputs. |
| T-SCOPE-002 | Verify generated-image-only input and no real capture. |
| T-SCOPE-003 | Verify selected OCR/dependencies do not require runtime network/cloud. |
| T-SCOPE-004 | Verify future review/transform/cursor interfaces remain disabled/deferred. |
| T-SCOPE-005 | Scan notices and unsupported/prohibited claims. |
| T-TRC-001 | Parse and validate unique requirements and complete RTM mappings. |
| T-EVD-001 | Verify the complete required artifact set and exact filenames. |
| T-EVD-002 | Recalculate the sorted manifest and verify manifest-last policy. |
| T-EVD-003 | Validate privacy-safe environment/dependency/test result content and exit codes. |
