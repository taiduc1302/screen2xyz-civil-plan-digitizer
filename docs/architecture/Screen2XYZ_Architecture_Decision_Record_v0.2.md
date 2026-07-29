# Screen2XYZ Architecture Decision Record v0.2

| Field | Value |
|---|---|
| ADR status | Selected at G4 for the scoped current-machine synthetic OCR lab only |
| Decision scope | S2XYZ-CODEX-003 current-machine synthetic OCR lab only |
| Decision | Python 3.14 standard-library core plus replaceable Windows PowerShell adapters for System.Drawing rendering and Windows.Media.Ocr |
| Output classification | Conceptual and preliminary estimating data only. |

## Context

G1-G4 conditionally passed for this scoped lab. The lab needs actual OCR of locally generated PNGs, deterministic parsing/export/testing, minimal dependency/licence surface, local-only processing, and reversible interfaces. The environment has CPython 3.14.6, Windows PowerShell 5.1, System.Drawing/GDI+, Windows.Media.Ocr with `en-US`, and no .NET SDK, Tesseract, or ImageMagick. An isolated `.venv` contains zero installed distributions.

A retained preflight recognized the generated text `LAT: 49.123456 LON: -123.654321 ELEV: -42.75 m` through actual Windows OCR in 11 ms, returned exit 0, produced a controlled nonzero missing-input exit, and passed a subprocess-timeout diagnostic. This is capability evidence on one computer, not quality or product evidence.

## Options

### Option A - Windows.Media.Ocr through Windows PowerShell 5.1

**Selected conditionally.** Advantages: already present, local, actual OCR, no package/model download, no third-party project package, small replaceable process contract. Risks: Windows-only; semantic OCR version not exposed; official documentation says desktop support requires package identity; the observed unpackaged host is experimental and cannot support a production/general claim.

### Option B - Tesseract command-line OCR

**Not selected for this run.** It is a realistic replaceable local OCR alternative, but the executable is absent. Obtaining a Windows build would introduce binary provenance, Leptonica/transitive components, language trained data, hashes, licence evidence, and redistribution decisions. Installing it opportunistically would expand the run without necessity.

### Option C - Python-native neural/ONNX OCR package

**Not selected for this run.** It would introduce large transitive packages, native wheels, model downloads/caches, Python 3.14 compatibility uncertainty, model provenance/licences, and a broader attack/reproducibility surface. It is disproportionate to the bounded lab.

### Option D - Compiled C# desktop host

**Not selected for this run.** No .NET SDK is installed. Installing an SDK or packaging identity solely for this lab is unnecessary environment expansion. It may be revisited for a supported future Windows host.

## Decision

Use Python 3.14.6 standard library for configuration, fixture logic, Decimal parsing, validation, temporal classification, deterministic output, metrics, evidence, CLI, and `unittest`. Use Windows PowerShell 5.1 adapters for local System.Drawing rendering and Windows.Media.Ocr only. Pin direct third-party project dependencies to the empty set; do not add a package-manager file.

The decision passes architecture review only if the dependency register, preflight evidence, fixture/test specifications, and failure contracts are complete and no Blocker/Major remains. If the adapter fails during the full lab, report the failure; do not silently substitute ground truth or pivot to an unreviewed OCR dependency.

## Consequences

Positive:

- Small dependency and licence surface.
- Actual offline OCR with retained raw text.
- Deterministic logic is isolated from Windows APIs.
- Renderer and OCR remain replaceable.
- No admin, cloud, runtime download, or model cache.

Negative/limitations:

- Current-machine and Windows-only.
- Unpackaged OCR host is outside the documented supported desktop hosting model.
- OS updates can change OCR behavior.
- Arial and OS components are used in place under the installed OS; none is redistributed.
- This is not a public/production architecture decision.

## Reversibility

All Windows behavior is behind JSON/process interfaces. A future approved task may replace the renderer or OCR host while retaining the core schemas/tests. This run does not select that future replacement or approve packaging/public distribution.

## Evidence

- `runs/evidence/S2XYZ-CODEX-003/preflight/environment_preflight.txt`
- `runs/evidence/S2XYZ-CODEX-003/preflight/ocr_probe_generated.png`
- `runs/evidence/S2XYZ-CODEX-003/preflight/ocr_probe_observation.json`
- `docs/guardrails/Screen2XYZ_Dependency_and_Licence_Register_v0.1.csv`
