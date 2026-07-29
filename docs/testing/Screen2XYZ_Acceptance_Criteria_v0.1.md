# Screen2XYZ Acceptance Criteria v0.1

| Field | Value |
|---|---|
| Task | S2XYZ-CODEX-003 |
| Status | Executed; AC-001 through AC-015 passed |
| Scope | Synthetic OCR laboratory only |
| Observed result | 41/41 mapped automated tests passed; retained evidence manifest verified with zero errors |
| Output classification | Conceptual and preliminary estimating data only. |

These criteria elaborate the normative AC IDs in Product Requirements. A criterion passes only with the named observed evidence; document existence alone is insufficient for implementation acceptance.

| ID | Acceptance condition | Required evidence |
|---|---|---|
| AC-001 | Complete configuration canonicalizes and hashes; each missing/conflicting mandatory field fails before OCR with nonzero bounded run status. | `test_results.txt`, sidecar config hash |
| AC-002 | Exactly 60 mutually exclusive scenarios match three 20-row conditions and the 42/18 partition; fixed seed, unique IDs/order, relative image paths/hashes, and expected/runtime separation verify. | `ground_truth.csv`, fixture/runtime manifests, fixture tests |
| AC-003 | Every scenario invokes actual local pixel OCR; raw UTF-8 text is retained reversibly with engine/language/status/duration; expected values never enter adapter/runtime input; failures/timeouts are explicit. | `raw_ocr_readings.csv`, adapter tests, preflight and run evidence |
| AC-004 | All clean, spacing/symbol, label/order, sign, elevation, malformed, precision, negative-zero, extra-number, ambiguity, and control-character parser tests pass. Known-clean parser rate is 100%. | Parser tests and `metrics.json` |
| AC-005 | Metadata/ranges, scenario vocabulary, input/OCR short-circuit, all codes, and deterministic primary precedence match requirements in every test. | Validator tests and rejected records |
| AC-006 | All stale/duplicate sequence rules and references pass; actual fixture results are stale 6/6 and duplicate 6/6. | Temporal tests, rejected records, metrics |
| AC-007 | Required CSV files match exact UTF-8/BOM/delimiter/minimal-quote/escape/CRLF/final-line/header/type/order/null rules; raw evidence is reversible/formula-safe; no expected leak; every reject retained. | Export tests and four CSV files |
| AC-008 | XYZ values/order/precision are exact; sidecar name/schema/hash/metadata/limitations/classification are exact; no transform/import claim appears. | XYZ/sidecar tests and artifacts |
| AC-009 | Config, boundary, corrupt-image, timeout, interruption, write, and manifest failures return bounded nonzero status; no partial final exists; successful rerun is idempotent and prior evidence unchanged. | Failure-injection tests and hashes |
| AC-010 | Every committed input is registered synthetic; network/privacy/metadata/contamination/retention scans pass; live status is `Executed` with safe evidence or `Not executed`. | Registers, privacy/scope scans, report |
| AC-011 | `metrics.json` validates against the exact 16-key schema/formulas/denominators/units/targets/statuses and reports failed IDs; timing uses monotonic nearest rank. | Metrics tests and JSON |
| AC-012 | Equivalent runs have zero classification, raw-OCR projection, and deterministic-whitelist hash differences. | Repeatability comparison and metrics |
| AC-013 | Static review finds no named-service preset, real data, prohibited automation, public licence/release, unsupported claim, enabled transform/cursor/live adapter, or unproved downstream compatibility; exact notices are present. | Scope and notice scans, independent review |
| AC-014 | Requirements, ACs, planned tests, and evidence paths remain unique and fully mapped with no mandatory orphan. | Traceability validation and RTM |
| AC-015 | Every required artifact exists/parses, versions/commands/tests/exit codes are sanitized, and a sorted relative SHA-256 manifest written last verifies. | Evidence tests and manifest |

## Numerical target interpretation

Targets do not replace the full criteria. A completed valid run can miss a numerical target, but the target is then `missed`, the run is reported as completed with failed targets, and no product acceptance is inferred. False accepts, failed cases, OCR failures, and rejected records must remain visible.
