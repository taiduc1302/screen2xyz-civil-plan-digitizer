# Technical Overview

## Architecture

```
user-selected PNG ──> intake (signature/chunk/size/dimension validation, SHA-256)
        │
        ▼
Windows.Media.Ocr (out-of-process PowerShell adapter, bounded, offline)
        │  raw text preserved immutably (base64 + SHA-256 in baseline; JSON record in M1)
        ▼
deterministic parser (exact Decimal, labelled LAT/LON/ELEV, stable error codes)
        ▼
validator (range checks) ──> temporal classifier (duplicate/stale by sequence)
        ▼
review session (corrections stored separately; explicit approve/reject)
        ▼
approved-only exports (formula-safe CSV, XYZ) + hashed provenance package
```

Two packages: `screen2xyz_lab` (sealed baseline: fixture generation, OCR
evaluation, metrics, evidence sealing) and `screen2xyz_m1` (intake, review
state, Tkinter UI, controlled evaluation) which reuses the baseline
pipeline unchanged. Standard library only; no third-party packages; no
network code (test-enforced).

## Evidence discipline

- Baseline benchmark: 60 synthetic PNGs, 42/42 exact readings, 18/18
  rejections, two independent re-runs **byte-identical** to sealed
  artifacts; evidence sealed by a SHA-256 manifest that verifies with zero
  errors (`verify-evidence`).
- M1 evaluation: 24 deliberately varied scenarios (size, contrast, blur,
  noise, malformed/duplicate/stale/ambiguous); 15/15 exact triplets, 0
  false rejects; the deliberate `O`→`0` false accept is retained as
  evidence (`runs/evidence/S2XYZ-M1-001/`).
- Every run (including user runs) produces a hash manifest; retained
  evidence directories are immutable by convention and test.

## Testing

76 deterministic tests (42 baseline + 34 M1): parser goldens, input
boundaries, atomic/copy-on-write evidence, privacy/sanitization scans of
tracked content and paths, review-state rules (immutable raw OCR, separate
corrections, approval required, rejected excluded), formula-injection
protection, no-network/no-capture source scans.

## Safety boundaries

Explicit selection only; no background capture, cursor control, or
keylogging; approval cannot be bypassed or automated; optional AI
assistance is a disabled-by-default seam that can only produce advisory
notes from sanitized text. Windows-only today by design (OS-provided OCR).
