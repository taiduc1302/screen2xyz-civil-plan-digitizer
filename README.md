# Screen2XYZ - civil takeoff research preview

Related experimental source for **Applied AI for Estimating, issue 4**:
*AI Takeoff Markups in Bluebeam Through MCP.*

A local, review-first **single-sheet** workflow for PDF evidence, geometry
proposals, traceable takeoff records and an MCP host such as Claude Code.
This is research code, not a production estimator or certified survey system.

## What is here

- PDF text/vector and layer inspection, rendered-sheet evidence and geometric QA;
- source-SHA-bound sessions and a separately registered editable working PDF;
- line/area proposals, scale state, questions, evidence and a scope ledger;
- a runnable stdio MCP gateway with proposal/review support;
- a Bluebeam working-copy/markup-plan bridge and explicit read-back requirements;
- synthetic regression tests for the pipeline and its failure cases.

The existing Tk point/terrain digitizer is a separate workflow. This branch is
not a fully wired multi-sheet bid-set takeoff application. One sheet, one
compatible scale context and one session writer remain important limits.

## Install and inspect

Use an isolated Windows environment with Python 3.14:

```powershell
git clone --branch task/plan-layer-extraction https://github.com/taiduc1302/screen2xyz-civil-plan-digitizer.git
cd screen2xyz-civil-plan-digitizer
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-civil.txt
$env:PYTHONPATH = (Resolve-Path .\src)
.\.venv\Scripts\python.exe -m screen2xyz_civil doctor
.\.venv\Scripts\python.exe tests_civil\run_civil_tests.py
```

PDFium/Pillow provide the pilot's portable rendering path. Optional OCR,
OpenTakeoff, Revu and the AI host are separate installations; a green unit suite
does not establish that those live applications work on a reader's machine.
Review dependency licences in `THIRD_PARTY_NOTICES.md` and the requirements file.
No model credentials or real drawing files are bundled.

## Run safely

Start with an owned, deliberately synthetic drawing. Follow
[the operator runbook](docs/integrations/CLAUDE_CODE_MARKUP_OPERATOR.md) and
[the disposable Revu acceptance gate](docs/integrations/BLUEBEAM_21_10_MEASUREMENT_ACCEPTANCE.md).
Older version-specific commands in those notes must be checked against the
actual installed connector's advertised schema; they are not a promise about
every later connector release.

Keep the source immutable. Register a separate Revu working copy, independently
verify scale at the feature, review the rendered geometry, and compare against
independent drawing evidence. A retrieved length only proves what path the tool
measured, not that it follows the intended feature. Keep `QA CHECK / DO NOT SUM`
geometry out of totals. Estimator approval is a human action.

## Validation and publication

Run `python tools/publication_check.py` to check the tracked public source and
`python -m unittest discover -s publication_snapshot_tests -v` to test that guard.
See [PUBLIC_RELEASE_AUDIT.md](PUBLIC_RELEASE_AUDIT.md) for executed checks, test
counts, source-package scope and the separate GitHub historical-cache limitation.

The real project input folder and project-specific operator records are not part
of this publication. Only synthetic tests and reviewed generic implementation
remain. Old clones must not be pushed back after the history cleanup.

This source is **related implementation work**, not the article's exact 21-markup
synthetic demonstration, and it does not establish live Revu create/save/read-back
success. [Reader guide](docs/public/ISSUE_4_READER_GUIDE.md).

## Rights and attribution

Original authorship and third-party notices are preserved. No new project-wide
licence is granted by this cleanup; this Civil/MCP branch retains its existing
all-rights-reserved status. Other branches may carry their own existing licence.
Public visibility is not a claim of unrestricted reuse or employer endorsement.

Conceptual and preliminary estimating data only.
