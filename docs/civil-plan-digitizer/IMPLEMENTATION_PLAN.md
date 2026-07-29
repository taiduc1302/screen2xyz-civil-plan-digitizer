# Civil Plan Digitizer Implementation Plan

Status: implemented and locally stabilized on
`feature/civil-plan-digitizer-overnight`; owner review and external human gates
remain.

All coordinates and elevations generated from PDF or image sources are
preliminary and require estimator or survey review. They are not certified
survey data.

## Completed scope

1. Preserved the sealed baseline, M1, M2, and retained evidence.
2. Added an isolated `screen2xyz_civil` package and deterministic civil test
   suite.
3. Delivered a dependency-free manual image workflow:
   source, crop, scale, verification, origin, East axis, manual points,
   review, save/reopen, and approved-only exports.
4. Added explainable numeric classification, duplicate/conflict QA, and the
   versioned AGTEK handoff package.
5. Added local adapters for vector PDF text, raster OCR with word boxes,
   symbols, association, and preliminary surfaces. Optional adapters must fail
   closed when their local executable is unavailable.
6. Added a review-first Tk workspace and product launcher integration.
7. Ran civil, baseline, M1, M2 deterministic, integration, evidence, compile,
   and sanitization validation; recorded the one recurring host-OCR
   integration flake without weakening or editing the preserved M2 assertion.

## Architecture boundary

The civil package is a sibling of `screen2xyz_lab`, `screen2xyz_m1`, and
`screen2xyz_m2`. It may reuse stable atomic-write, hash, manifest, and
formula-safe CSV helpers. It does not change retained evidence or place civil
state in the M2 live-capture controller.

## Core acceptance map

| Capability | Implemented module |
|---|---|
| Source and crop | `source.py`, `ui/app.py` |
| Scale/origin/orientation | `transform.py`, `models.py` |
| Manual point review | `workflow.py`, `ui/app.py` |
| Save/reopen/migrate | `persistence.py` |
| Approved-only export | `exports.py` |
| QA and duplicates | `qa.py` |
| Vector PDF | `pdf.py` using local Poppler when available |
| Raster OCR | `ocr.py` plus bounded local Windows adapter |
| Explainable classification | `detection.py` |
| Preliminary TIN | `surface.py`, feature flagged in the UI |

## Post-feature validation disposition

- PASS: baseline 42/42; M1 34/34; M2 deterministic 498/498; Civil 88/88.
- PASS: retained-evidence verification with zero errors.
- PASS: compile; civil Tk construction; privacy/sanitization 11/11.
- PASS: actual bounded civil Windows OCR on committed synthetic S001
  (1 line, 7 words, 45 characters).
- NOT CLEAN: M2 Windows integration ran 15/16 twice. The unchanged
  `NumberTypeCoordinateHintIntegrationTests` received a content-bearing crop
  but Windows OCR intermittently returned `EMPTY_TEXT`. In eight isolated
  executions it passed five and failed three. A bounded compositor-delay
  diagnostic did not improve the rate and was removed completely.
- NOT EXECUTED: real authorized plans and AGTEK/Civil 3D/Kubla/LandXML
  downstream acceptance.

## Quality gates

- No unreviewed point is exported by default.
- Existing and Design points remain separate.
- Source pixels remain immutable; local coordinates are derived.
- Calibration changes create revisions and stale prior exports.
- No automatic approval, guessed elevation, geodetic claim, or inferred
  engineering breakline.
- Only synthetic fixtures are committed.
- Real drawing, AGTEK, Civil 3D, Kubla, and LandXML validation remain explicit
  human/downstream gates.
