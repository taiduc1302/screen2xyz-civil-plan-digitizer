# Security Policy

## Status

Screen2XYZ is a private, pre-release proof-of-concept. There is no supported
production deployment, no network surface, and no public release. Security
issues should be raised directly with the repository owner through a private
channel (repository issues remain private while the repository is private).

## Scope and threat model

The implemented laboratory:

- runs entirely on the local machine; the source code contains no network
  client, and an automated test (T-PRI-003) fails if one is introduced;
- treats raw OCR output as untrusted text: control characters are rejected,
  CSV output is formula-escaped (`exporters.formula_safe_display`), and raw
  text is retained as base64 plus SHA-256 rather than interpolated;
- validates every input image against a manifest (relative path, size cap,
  exact dimensions, SHA-256, and an allowlist of PNG chunk types) before OCR
  (`pipeline.validate_image`);
- runs OCR and rendering in bounded, non-interactive PowerShell child
  processes with timeouts;
- writes evidence atomically, copy-on-write, and refuses to overwrite
  retained artifacts;
- scans retained evidence for credentials, identity assignments, network
  addresses, and absolute personal paths (`evidence.privacy_findings`,
  tests T-PRI-001 and T-PRI-004).

## Known limitations

- The threat review (`docs/guardrails/Screen2XYZ_Privacy_and_Threat_Review_v0.1.md`)
  covers only the synthetic, current-machine scope. Real-source capture,
  cloud services, or public release each require a new review.
- Git history metadata (commit author identity on two early commits) is
  employer-identifying and cannot be removed without a history rewrite; see
  `AUDIT_AND_REMEDIATION_REPORT.md`. This blocks public release of the
  repository as-is.
