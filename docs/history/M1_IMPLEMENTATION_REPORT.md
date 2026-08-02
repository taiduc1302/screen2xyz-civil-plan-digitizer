# M1 Implementation Report — Opt-In Still-Image Capture Review Lab

> Historical process record from the private predecessor repository; retained for provenance only.

Date: 2026-07-17. Branch `feat/m1-opt-in-capture-review-lab`, based on
baseline merge commit `d740fad` (PR #2 → `main`).

## 1. Executive result

The M1 core is complete and working: an explicitly user-selected PNG flows
through the unchanged baseline pipeline into a local review interface with
immutable raw OCR, separated corrections, mandatory explicit approval, and
approved-only deterministic exports with a hashed provenance package. The
controlled evaluation met its target (15/15 exact triplets, 100% ≥ 90%)
with zero false rejects, zero automatic approvals, and zero unapproved
exports. One deliberate challenge case produced a false accept at the
classify stage (OCR read a letter `O` as `0`) and is retained as evidence
for why human review is mandatory.

## 2. Baseline merge commit

`d740fade17a8a616e9a608e58c2556974636c38c` (PR #2 merged into `main`).

## 3. Objective and 4. Implemented scope

Objective per `docs/control/NEXT_ACTION.md` (M1 definition). Implemented:
`src/screen2xyz_m1/` — `intake.py` (secure PNG validation), `session.py`
(candidate/review/approval state and exports), `ui.py` (Tkinter review
interface), `cli.py` (`review`, `generate-eval`, `evaluate`), `assist.py`
(disabled-by-default external-AI boundary), `evaluation.py` + Windows
renderer adapter (24-scenario controlled evaluation), plus 34 stable tests
in `tests_m1/` and retained evidence in `runs/evidence/S2XYZ-M1-001/`.

## 5. Explicit non-goals

Window/region capture (deferred; the PNG path is the M1 core), real
drawings, coordinate transformation, CAD/Bluebeam/Civil 3D/Kubla
integration, terrain reconstruction, production packaging, background
capture of any kind, live external-AI calls.

## 6. Architecture changes

Additive only. The baseline package `screen2xyz_lab` is reused unchanged
(OCR adapter, parser, validator, temporal classifier, exporters, evidence
utilities); `screen2xyz_m1` layers intake, review state, and UI on top. No
baseline file was modified. Corrections deliberately re-enter the same
parser as OCR text, so human input obeys identical validation rules.

## 7. Interface choice and rationale

Tkinter (option 1 of the decision order): available in the venv (Tk 8.6),
standard-library only, no dependencies, no localhost server, adequate for a
single-user table-plus-detail review surface.

## 8. Input and consent model

An image enters only through an explicit file-picker selection (UI) or an
explicit CLI path argument. Intake enforces: regular file, `.png`
extension, PNG signature, complete chunk-walk (truncation/trailing-data
rejection), ≤25 MB, ≤8192×8192, ≤40 MP, before any OCR. The source is
read-only; only its basename, hash, and dimensions are recorded. No
background or continuous capture exists (test-enforced absence of screen
capture and network APIs).

## 9. Review and approval model

Raw OCR is written once per candidate (`raw/<id>.json`) and never mutated.
Original parsed values persist after correction; corrections are stored in
separate fields with their own validation codes. Approval is a per-candidate
explicit action and is refused while validation codes are unresolved.
Rejection is always available. There is no code path that approves or
exports automatically.

## 10. Output and provenance model

Runs write only to `.lab_work/m1_runs/<run_id>/` (Git-ignored; collision
refused): immutable raw records, `candidates.json`, `run_summary.json`
(includes `external_ai_used`), `approved_points.csv` / `.xyz`
(approved-only, sequence-ordered, formula-safe), and
`evidence_manifest_sha256.txt` over all artifacts. Atomic writes throughout.
Vertical reference recorded as `UNSPECIFIED_LOCAL`.

## 11. Optional GPT-5.6 feature status

**Boundary only; no live integration.** `assist.ReviewAssistant` is the
provider seam; `NullAssistant` (default) reports assistance disabled;
`OpenAIAssistantBoundary` requires explicit opt-in and then fails closed
with `AssistantUnavailable`. Requests may carry only sanitized OCR text,
parsed values, and reason codes (dataclass-enforced; tested). Remaining
integration step: implement a provider against current official OpenAI API
documentation, keyed via the `S2XYZ_ASSIST_API_KEY` environment variable,
after explicit owner authorization. No live GPT execution occurred and none
is claimed.

## 12. Files changed

Added: `src/screen2xyz_m1/` (8 files), `tests_m1/` (6 files),
`test_data/synthetic/m1_eval_v0.1/` (24 images + config/truth/manifest),
`runs/evidence/S2XYZ-M1-001/` (3 files),
`docs/public/Screen2XYZ_M1_Guide_v0.1.md`, `docs/build-week/` (6 files),
this report. Modified: `README.md`,
`docs/control/AUTONOMOUS_EXECUTION_STATE.md`, `docs/control/PROJECT_STATE.md`.
Baseline source, tests, and sealed evidence: untouched.

## 13.–15. Tests, baseline regression, baseline evidence

- M1 stable suite: **34/34 passed** (0 failures/errors/skips, exit 0);
  deterministic, mocked OCR, no network, no interaction, no API key.
- Baseline suite after M1 work: **42/42 passed**, exit 0.
- Baseline evidence: `verify-evidence` **PASS, 0 errors**;
  `runs/evidence/S2XYZ-CODEX-003/` byte-identical (nothing under it was
  touched).

## 16.–18. Evaluation methodology, metrics, failure categories

Methodology: 24 deterministic scenarios (seed 20260718) rendered by a new
GDI+ adapter varying canvas 800–3200 px, contrast, glyph softness
(down/up-scale), layouts (four formats), numberless and numeric noise,
signs, precision, malformed/missing/out-of-range/duplicate/stale/ambiguous
cases; expected outcomes fixed before OCR. Scores the automatic classify
stage; review behaviour is covered by unit tests.

Actual metrics (retained in `runs/evidence/S2XYZ-M1-001/m1_eval_metrics.json`):

| Metric | Result |
|---|---|
| Exact triplets (expected-valid) | **15/15 = 100%** (target ≥90%: met) |
| False rejects | 0 |
| Expected-invalid rejected | 8/9 |
| False accepts (classify stage) | 1 — M015, challenge case |
| Rejected-code mismatches | 1 — M013 |
| Automatic approvals / unapproved exports | 0 / 0 |

Failure categories: (a) **glyph-confusion false accept** — M015's letter
`O` inside digits was read as `0`, yielding a plausible wrong value; this
is the exact risk the mandatory human-review step mitigates, retained
deliberately. (b) **render-condition OCR variability** — M013 (`10 m` on an
1800-px canvas) was read as `IO m`, so it was rejected as `MALFORMED_ELEV`
rather than `STALE_READING`; still safely rejected (stale detection is
proven 6/6 in baseline evidence and by unit tests).

## 19. Privacy and security result

No network code (test-enforced), no screen-capture APIs (test-enforced),
no secrets, source images never copied or tracked, run outputs Git-ignored,
absolute personal paths absent from tracked content (baseline T-PRI-004
still passes over the final tree), formula-injection protection active in
all CSV/state outputs.

## 20. Known limitations

Windows-only; en-US `LAT`/`LON`/`ELEV` labels; decimal points only;
unlabelled extra numbers cause rejection; OCR glyph confusion can produce
plausible wrong values (hence mandatory review); single-machine evidence;
UI is minimal (no image preview pane yet); window/region capture deferred.

## 21. Demo instructions

See `docs/build-week/DEMO_SCRIPT.md` and the guide's quick start. Shortest
path: `python -m screen2xyz_m1.cli review`, select any PNG from
`test_data/synthetic/m1_eval_v0.1/images/`, review, correct one value,
approve, export, then open the run directory.

## 22. Commit list

Recorded in the M1 pull request description and final handoff (hashes
assigned at commit time on this branch).

## 23. Merge recommendation

Merge into `main` once the M1 gates pass: the core is functional, honest,
review-mandatory, and leaves the baseline untouched.

## 24. Recommended next milestone

M2 — explicit single-window capture feeding the same review lab (see
`docs/control/NEXT_ACTION.md` after merge).

Conceptual and preliminary estimating data only.
