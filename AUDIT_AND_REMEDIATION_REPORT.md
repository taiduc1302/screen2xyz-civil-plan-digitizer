# Audit and Remediation Report — 2026-07-17

Branch `feat/overnight-v0.2-planning-ocr-lab` (draft PR #2 → `main`).
Independent senior-engineer audit, verification, and remediation pass,
followed by a same-day second verification pass (§17).

## 1. Executive summary

The repository's headline claims are **true and independently reproduced**:
a completely fresh OCR evaluation run on 2026-07-17 reproduced the retained
evidence byte-for-byte (42/42 exact valid readings, 18/18 rejections, zero
false accepts/rejects, 6/6 duplicate and 6/6 stale detections), the retained
metrics recompute exactly from raw evidence, the evidence manifest verifies
with zero errors, and the full test suite passes. The code is defensive,
deterministic, and network-free. The material findings were privacy-related:
the project owner's personal name in two tracked documents (fixed), an
identity-revealing commit-author e-mail in early Git history (documented
blocker; cannot be fixed without a prohibited history rewrite), and the
absence of an automated repository-wide sanitization check (added as test
T-PRI-004). Release-readiness documentation (SECURITY, CONTRIBUTING,
DATA_PROVENANCE, THIRD_PARTY_NOTICES, README restructure) was added.

## 2. Initial repository state

- Working tree clean; branch up to date with `origin/feat/overnight-v0.2-planning-ocr-lab` at `2cc8530`.
- Sole remote `origin` = `https://github.com/taiduc1302/screen2xyz.git` (private).
- Branch is 9 commits ahead of the merge base with `main` (`a8afa5a`); the diff matches PR #2's description: planning docs, the synthetic OCR laboratory (`src/screen2xyz_lab`), 42-file test/fixture/evidence tree, 60 fixture PNGs, retained evidence.
- 193 tracked files: Markdown/CSV docs, 12 Python modules (~2,000 LOC), 3 PowerShell adapters, 6 test modules, 61 PNGs (60 fixture images + 1 OCR probe; largest ~12 KB). Binary files are all intentional fixture/evidence images with locked hashes.
- Ignored-only local dirs: `.venv/`, `.lab_work/`, `__pycache__/`, plus an untracked empty `.agents/` directory. No accidental tracked files, temp files, broken symlinks, or malformed names found.

## 3. Scope reviewed

All tracked files; full Git history text; all 12 source modules line-by-line; all 6 test modules; adapters; fixture and evidence trees; guardrails registers; control/planning docs; PNG chunk structure (allowlist `IHDR/sRGB/gAMA/pHYs/IDAT/IEND` — no textual metadata possible).

## 4. Commands and tests executed

| Command | Result |
|---|---|
| `tests\run_all.py` (before changes) | 41 tests, 41 passed, exit 0 |
| `python -m screen2xyz_lab.cli verify-evidence` | `PASS`, 0 errors |
| Recompute `calculate_metrics` from retained `ground_truth.csv` + `classifications.json` + `raw_ocr_readings.csv` | Recomputed dict `==` retained `metrics.json` |
| `python -m screen2xyz_lab.cli evaluate --output .lab_work/audit-fresh-run-a` (fresh OCR of all 60 PNGs) | `classifications.json`, `raw_ocr_projection.json`, `accepted_points.csv`, `points_source_xyz.txt` **byte-identical** to retained evidence |
| `tests\run_all.py` (after changes) | 42 tests, 42 passed, exit 0 |
| Sensitive-term and secret sweep over tracked content and full history | See §5 / §9 |

## 5. Findings by severity

**Blocker/Critical:** none.

**High**
- H1 (privacy): The project owner's personal name appeared in
  `docs/charter/Screen2XYZ_Project_Charter_v0.1.md` and three rows of
  `docs/decisions/Screen2XYZ_Decision_Log_v0.1.md`. **Fixed** (generalized to
  "Project Owner").
- H2 (privacy, unfixable here): Commits `a89701b` and `b6cd219` carry an
  author e-mail of the form `<initials+surname>@<employer-name>.local`,
  revealing both a personal identity and the employer's company name in
  permanent Git metadata. Removing it requires a history rewrite or a
  fresh-history export, both outside this engagement's authorization.
  **Documented** as the primary public-release blocker.

**Medium**
- M1: No automated check prevented employer/person identifiers or absolute
  personal paths from re-entering tracked content (the existing privacy scan
  covered retained evidence only). **Fixed**: new test T-PRI-004
  (`tests/test_repository_sanitization.py`) scans every tracked non-image
  file; suite count raised 41 → 42 with matrix and traceability updates.
- M2: No SECURITY, CONTRIBUTING, DATA_PROVENANCE, or THIRD_PARTY_NOTICES
  documentation; README lacked setup, repository map, and a licensing-
  readiness statement, and its synthetic-benchmark numbers could be misread
  as real-world accuracy. **Fixed** (new docs; README restructured with an
  explicit synthetic-only disclaimer).

**Low (documented, intentionally not changed)**
- L1: `metrics.py` freezes denominators (42/18/6/6/60) and `pipeline.py`
  returns `scenario_count: 60`; correct for frozen fixture v0.1 and locked by
  spec, but must be parameterized before any fixture v0.2.
- L2: `compare_runs` records fixture/manifest-image hashes identically for
  both runs (recording, not comparison); harmless but the
  `deterministic_artifact_count` of 69 includes 63 self-equal entries.
- L3: The local working copy lives inside a cloud-synced employer directory;
  path never appears in tracked content, but sync conflicts could corrupt
  `.git`. Recommend relocating the clone.
- L4: `run_all.py`'s recorded `Command:` string names the historical task's
  output path; cosmetic.

## 6. Fixes completed

Name generalization (H1); repository sanitization test T-PRI-004 plus test
matrix row and count updates (M1); SECURITY.md, CONTRIBUTING.md,
DATA_PROVENANCE.md, THIRD_PARTY_NOTICES.md, README restructure with
licensing-readiness and synthetic-only disclaimers (M2); this report.

## 7. Files changed

Modified: `README.md`, `docs/charter/Screen2XYZ_Project_Charter_v0.1.md`,
`docs/decisions/Screen2XYZ_Decision_Log_v0.1.md`,
`docs/testing/Screen2XYZ_Test_Matrix_v0.1.csv`, `tests/run_all.py`,
`tests/test_guardrails_traceability_evidence.py`, `tests/README.md`.
Added: `tests/test_repository_sanitization.py`, `SECURITY.md`,
`CONTRIBUTING.md`, `DATA_PROVENANCE.md`, `THIRD_PARTY_NOTICES.md`,
`AUDIT_AND_REMEDIATION_REPORT.md`. Nothing under `runs/evidence/` or
`test_data/` was touched.

## 8. Independently verified benchmark results

Every retained claim reproduced from a clean state on 2026-07-17: 42/42
exact valid readings; 18/18 expected-invalid rejections; 0 false accepts; 0
false rejects; 6/6 duplicate and 6/6 stale detection; parser known-clean
13/13; repeatability 0 differences; manifest `PASS` with 0 errors; fresh OCR
run byte-identical to retained artifacts. Ground truth and expectations are
generated deterministically from a seed and the parser never consults them
(verified in code: `parser.py` takes raw text only; `validate_runtime_fixture`
explicitly excludes evaluator fields from the runtime manifest). The sample
is 60 synthetic images on one machine — the results support "the pipeline is
deterministic and correct on its own fixture," nothing more.

## 9. Security and privacy assessment

No secrets, tokens, credentials, connection strings, personal e-mails, phone
numbers, or absolute personal paths in any tracked file or in history file
content. Input validation, subprocess use (fixed argument lists,
non-interactive, timeouts), CSV formula-escaping, atomic copy-on-write
evidence, and privacy scanning are all implemented and tested. Remaining
exposure: H2 (history author metadata) and L3 (clone location).
Classification: **safe for a private repository; safe for controlled
demonstration; NOT safe for public release** until H2 is resolved.

## 10. Licensing and redistribution assessment

No licence file exists by explicit owner decision; all rights reserved.
All data is internally generated synthetic content; no third-party code,
fonts, or datasets are redistributed (registers verified; the system font is
used in place only). Nothing blocks private use. Public redistribution is
blocked by (a) no licence selected, (b) H2, and (c) OS-component licence
evidence recorded as "not independently identified" — acceptable for
use-in-place, but should be re-reviewed before any public claim.

## 11. Public-release readiness

Not ready, by design and by decision. Required before any public release:
resolve H2 (fresh-history export is the practical option), owner licence
selection, a fresh privacy/legal review, and removal of private PR/handoff
links if the repository visibility changes.

## 12. Build Week readiness

Strongest story: **"a provably deterministic, evidence-sealed OCR-to-XYZ
extraction pipeline"** — the discipline (byte-reproducible runs, sealed
manifests, honest rejection taxonomy) is the differentiator, not the OCR.
Works end-to-end today: synthetic screenshot → OCR → parse → validate →
classify → XYZ export, fully reproducible. Scaffolding only: everything
real-source or downstream. Do **not** claim real-screenshot accuracy,
Kubla compatibility, or estimating capability. Blockers for a public
submission: those in §11. Missing for a credible demo: a live capture path
and a minimal viewer UX. Smallest credible next milestone: opt-in interactive
window capture of a cooperating local viewer app, evaluated against the same
evidence framework (extends `S2XYZ` gates, no new scope).

## 13. Remaining risks

H2 and L1–L4 above; single-machine validity; Windows-only adapters;
`main` still contains only planning docs until PR #2 is accepted.

## 14. Recommended next milestone

Owner accepts PR #2 as the private technical baseline, then authorizes a
scoped live-capture task (G-gated) per §12.

## 15. Local commits created

- `536e860` security: generalize identity references and add tracked-content sanitization scan
- `e358c16` docs: add release-readiness documentation and restructure README
- `b304512` docs: record 2026-07-17 independent audit and remediation
- Second pass (§17): strengthen T-PRI-004 path scanning; record the M1
  milestone proposal in `docs/control/NEXT_ACTION.md`; refresh
  `docs/control/PROJECT_STATE.md`; update this report.

## 16. Final recommendation

**A. Ready to merge into main as the private technical baseline.**
(Merge remains the owner's action; nothing in this audit blocks it. Public
release remains separately prohibited until §11 items are resolved.)

## 17. Second-pass verification (2026-07-17, same day)

A second independent pass re-verified the first audit before push:

- PR #2 confirmed: draft, OPEN, MERGEABLE, base `main`, head this branch,
  165 changed files (+6304/−96), no unresolved review threads; the branch is
  genuinely the PR content.
- A second fresh OCR evaluation again reproduced `classifications.json`,
  `raw_ocr_projection.json`, `accepted_points.csv`, `rejected_readings.csv`,
  `points_source_xyz.txt`, and `raw_ocr_readings.csv` content;
  `raw_ocr_readings.csv` differs only in the per-reading `duration_ms`
  timing column, which is expected and is exactly why the repeatability
  comparison whitelists the timing-free `raw_ocr_projection.json` instead.
- Failure paths verified: output-collision and path-traversal invocations of
  `evaluate` exit 30 with structured JSON errors and leave the tree clean.
- Fixture integrity: 60 rows (42 ACCEPT / 6 stale / 6 duplicate / 3
  malformed / 3 missing); all 42 expected-valid triplets unique. Three image
  pairs (S004/S020, S024/S040, S044/S060) are **intentionally
  byte-identical**: in each condition the stale copy and the duplicate copy
  of the same base value share render variation V4, and the pipeline still
  classifies them differently (STALE vs DUPLICATE) purely from temporal
  order — evidence that classification depends on sequence context, not
  image content.
- T-PRI-004 strengthened to also scan tracked file *paths* (including image
  names) for prohibited identifiers, not just file contents.
- The recommended next milestone (M1: opt-in still-image capture review
  lab) is now specified with acceptance criteria in
  `docs/control/NEXT_ACTION.md` — the single source of truth for M1 —
  replacing the sketch in §12/§14.
- Final suite: 42 tests, 42 passed, exit 0; `verify-evidence` PASS with 0
  errors; sealed evidence unchanged; working tree clean.

Recommendation A is unchanged.
