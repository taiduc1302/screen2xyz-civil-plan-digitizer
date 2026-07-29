# Screen2XYZ Privacy and Threat Review v0.1

| Field | Value |
|---|---|
| Task | S2XYZ-CODEX-003 |
| Status | G2/G4 conditionally passed; scoped controls exercised in retained evaluation |
| Method | Scoped qualitative threat review |
| Data boundary | Locally generated synthetic data and screenshots only |
| Output classification | Conceptual and preliminary estimating data only. |

## Assets to protect

- Repository credentials and GitHub authentication.
- User identity, device identity, paths, environment, and other local metadata.
- Synthetic fixture integrity and separation of expected from observed values.
- Raw OCR and rejected-reading evidence.
- Retained run evidence, hashes, and Git history.
- The truthfulness of capability, accuracy, live-capture, and downstream-compatibility claims.

## Trust boundaries

1. Fixture generator to renderer: expected visible synthetic text is allowed only here.
2. Renderer to image manifest: only image identity, relative path, hash, condition, and sequence cross forward.
3. Image manifest to OCR: no expected value or visible source string crosses this boundary.
4. OCR to parser/validator/classifier: raw OCR is untrusted input.
5. Runtime records to evaluator: only this evaluator may join ground truth after classification.
6. Local evidence to Git/GitHub: only registered, sanitized, reviewed artifacts cross this boundary.

## Threat register

| ID | Threat | Impact | Control | Residual status |
|---|---|---|---|---|
| THR-001 | Ground truth leaks into OCR/runtime classification | Invalid experiment and false accuracy | Separate roots/schemas; runtime manifest excludes expected fields; separation tests; evaluator-only join | Mitigated for the retained run by passing separation tests |
| THR-002 | Real or service-specific data contaminates fixture/evidence | Rights, privacy, and scope breach | Fixed-seed generator; no URL/network inputs; static scans; visual review; stop/quarantine/escalate | Mitigated for this run by registered synthetic provenance and passing privacy checks |
| THR-003 | Full-screen capture includes notifications or unrelated applications | Personal/confidential disclosure | Live capture optional; synthetic crop only; no full-desktop retention; `Not executed` when unsafe | Avoided when not executed |
| THR-004 | Evidence exposes username, hostname, home path, token, environment variable, IP/MAC, or serial | Privacy/security disclosure | Environment allowlist; relative paths; secret/path scans; sanitized error records | Mitigated for retained evidence by sanitized allowlists and passing privacy checks |
| THR-005 | Raw OCR triggers CSV formula or control-character handling | Unsafe downstream review or corrupted parsing | RFC-4180 quoting; formula-safe representation; parser rejects controls; no shell interpolation | Mitigated by passing parser and export tests |
| THR-006 | Path traversal or oversized/corrupt image escapes controlled root or consumes resources | File disclosure, denial, or unbounded run | Constrained IDs/extensions; resolved-root check; size/dimension limits; subprocess and run timeouts | Mitigated by passing boundary and recovery tests |
| THR-007 | Partial or overwritten outputs appear complete | Misleading evidence or loss of prior evidence | New run roots; same-directory temp writes; flush/close/replace; manifest last; nonzero failure | Mitigated by passing recovery tests and verified manifest-last evidence |
| THR-008 | OCR engine or dependency performs network/telemetry activity | Data disclosure or non-reproducible service dependency | OS-local engine selection; no URLs; no cloud package; dependency review; no runtime downloads | Mitigated for the scoped current-machine adapter; broader platform behavior remains outside scope |
| THR-009 | Copied font/model/binary is redistributed without authority | Licence/compliance exposure | Use OS-provided components in place; do not commit binaries/models/fonts; register evidence | Controlled by review |
| THR-010 | Reviewer mistakes generated-image OCR for live capture or downstream validation | Unsupported capability claim | Exact run report wording; live status field; claim scan; required classification notice | Mitigated by exact `Not executed` status and final review with zero Blocker or Major |
| THR-011 | Duplicate/stale expected labels drive classifier | Inflated quality metrics | Ordered canonical runtime state only; invalid rows do not update state; ground truth evaluator-only | Mitigated by passing temporal and ground-truth-separation tests |
| THR-012 | Accidental sensitive commit is erased through unilateral history rewrite | Evidence loss and incident amplification | Stop and escalate; preserve prior evidence; no unilateral shared-history rewrite | Process control |

## Abuse and misuse cases

- Adapting the lab into a named-service scraper is prohibited.
- Feeding a real screenshot by renaming it as a fixture is prohibited and blocked by provenance review, not guaranteed solely by code.
- Treating EPSG:4326 degrees as projected metres is prohibited.
- Using `SYNTHETIC_LOCAL` elevation for engineering or survey decisions is prohibited.
- Removing rejected records to improve metrics is prohibited.
- Presenting a missed target as a pass, or weakening thresholds after execution, is prohibited.
- Claiming Kubla readiness from an XYZ file without an evidenced import is prohibited.

## Privacy-safe logging standard

Use stable scenario IDs, relative repository paths, hashes, bounded error codes, versions, and durations. Do not record command environment dumps or full exception objects when they may contain local paths. Test transcripts, tracebacks, and tool errors must be sanitized and inspected before commit.

## Review conclusion

**Observed scoped result.** The synthetic-only lab exercised the listed controls through a 41-test suite, retained sanitized evidence, verified its final evidence manifest, and passed independent final review with zero unresolved Blockers or Majors. This is not a security certification or legal determination. Any real-source, cloud, public-release, or interactive desktop scope requires a new review.
