# Where every line of work stands, 2026-09-06

A re-check of all the sessions that have touched this repository and of what
each of them actually landed on the remote. Verified from GitHub and from the
session records, not from memory; every count below comes from a command whose
form is given beside it.

**What this cannot see.** Only the remote and the session metadata. A working
copy on someone's own machine is invisible from here, so "on GitHub" below
means exactly that and nothing about what may still be uncommitted elsewhere.

## Sessions

Eleven sessions carry this project's name. All but the two marked live are
completed or idle, and every one of them is `environment_kind: bridge` except
this one.

| session | model | state | last activity |
| --- | --- | --- | --- |
| `screen2xyz-civil-plan-digitizer чат обзор` | Opus | idle, unreachable since 2026-09-04 | 2026-09-04 17:59 |
| `screen2xyz-civil-plan-digitizer обзор` (x6) | Sonnet | 5 archived, 1 idle | 2026-09-02 … 2026-09-06 04:14 |
| `screen2xyz-civil-plan-digitizer review` | Sonnet | archived | 2026-09-02 20:54 |
| `Reconcile and finalize the Example Road RFI…` | Sonnet | idle, unreachable | 2026-09-04 20:25 |
| this session | Opus | running | — |

The session the owner named as the main one has been unreachable
(`computer_unreachable`) since 2026-09-04 21:48. Commits after that carry no
`Co-Authored-By` trailer and a different message style, so the branch is being
driven by something other than that chat.

## Branches

`git log --oneline origin/<branch> --not origin/main origin/task/plan-layer-extraction origin/feature/claude-markup-operator-real3 | wc -l`

| branch | head | last | commits found nowhere else |
| --- | --- | --- | --- |
| `main` | `05ed2c5` | 09-03 | — |
| `task/plan-layer-extraction` | `cb19d41` | 09-05 | 173 ahead of main |
| `feature/claude-markup-operator-real3` | `c5951f4` | 09-03 | 126 ahead of main |
| `chore/issue-pr-workflow` | `b897bf7` | 09-03 | 0 (content in main) |
| `feature/assisted-c03-validation` | `dcf2cf0` | 07-29 | 0 |
| `integration/open-source-takeoff-stack` | `709460d` | 09-02 | 0 |
| `feature/v2-unified-capture` | `2fe7e50` | 08-02 | **12** |
| `feature/v2.5-proven-release` | `2e7ab40` | 08-02 | **24** |
| `feature/v2.6-real-viewer-capture` | `4e9d40a` | 08-02 | **25** |
| `feature/v2.7-agtek-field-fixes` | `812f7c4` | 08-18 | **37** |
| 14 `feature/claude-markup-operator-*` | `709460d` | 09-02 | 0 each |

## What that means

**Nothing is lost.** Every branch listed is on the remote. No session's work
sits only in a local clone as far as the remote can tell.

**The 14 duplicate branches are safe to delete.** All fourteen point at exactly
`709460d`, the same commit as `integration/open-source-takeoff-stack`, and the
containment check returns 0 — every commit reachable from them is also reachable
from `main`, `task/plan-layer-extraction` or `feature/claude-markup-operator-real3`.
Deleting them removes no history. (`git push --delete` returned HTTP 403 from
this environment on 2026-09-03; it needs a token with delete rights.)

**One line never reached `main`: the v2.x capture chain.** 37 commits, stacked
as PR #2 → #3 → #4 → #5 and last touched 2026-08-18, sitting behind an unmerged
`feature/assisted-c03-validation` (PR #1). The civil / plan-layer work does not
descend from it — `feature/assisted-c03-validation` is fully contained in the
live branches, but everything from `feature/v2-unified-capture` onward is not.
Two parallel lines of work, and the older one is parked.

**PR #12 is closed, not merged, yet its content is in `main`.** `git diff` of
`.github/ISSUE_TEMPLATE` and `.github/pull_request_template.md` between the
branch and `main` is empty, and `main`'s `05ed2c5` names "(#12)" — so the squash
went in and the pull request was closed rather than merged. Nothing to recover,
but the PR list under-reports what landed.

**Repository size: 34.31 MiB packed** (`git count-objects -vH`), most of it the
tracked pilot material and generated probe evidence added on 2026-09-04/05.
Drawings do not regenerate; the probe JSON and renders do.

## Pull requests

| # | state | base ← head |
| --- | --- | --- |
| 12 | closed (content in `main`) | `main` ← `chore/issue-pr-workflow` |
| 10 | open, draft | `main` ← `task/plan-layer-extraction` |
| 9, 6 | closed (CI-only drafts) | — |
| 8 | open, draft | `integration/open-source-takeoff-stack` ← `feature/claude-markup-operator-real3` |
| 7 | open, draft | `feature/assisted-c03-validation` ← `integration/open-source-takeoff-stack` |
| 5, 4, 3, 2 | open, draft | the v2.x chain |
| 1 | open, draft | `main` ← `feature/assisted-c03-validation` |

Nine pull requests are open; only two have a branch that moved this month.

## Open audit findings

Five measured defects stand against `task/plan-layer-extraction`, unchanged at
`cb19d41` — `layer_chains.py`, `pdf.py`, `agent_session.py` and
`tests/test_repository_sanitization.py` have not been touched since the audit.
See `PLAN_LAYER_EXTRACTION_FINDINGS.md` beside this file, and PR #10's
consolidated comment. Two of them change a quantity.
