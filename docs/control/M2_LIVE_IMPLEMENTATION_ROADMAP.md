# M2-Live Implementation Roadmap

Status: M2-000 planning deliverable. This document authorizes no production
implementation. The owner must approve this planning package and record every
hard gate below before a future `feat/m2-live-region-watch-impl` branch may be
created. Cross-document constants, enums, limits, and protocol operations come
only from
[`M2_LIVE_DATA_CONTRACTS.md` §0](../requirements/M2_LIVE_DATA_CONTRACTS.md).

## Acceptance gates

| Gate | Requirement | Status at planning handoff |
|---|---|---|
| G-A | Official API research complete and limitations explicit | Complete in the research document; no target-specific support claim |
| G-B | Disposable S1-S6 measurements recorded honestly | Complete for the documented synthetic/current-machine environment; S7 is not included |
| G-C | Architecture selected from the available evidence, with alternatives and limits | Complete in the architecture document |
| G-D | Owner approves the UX journey, countdown snapshot, preview/arming flow, and full mini controller | **Closed 2026-07-18: OD-M2-6** |
| G-E-SYNTHETIC | Automated synthetic-target compatibility gate (three trials, two backends, machine-readable oracles) passes; authorizes implementation, the PR #4 merge, and a Draft implementation PR (OD-M2-9) | **PASSED 2026-07-18: 6/6 trials; provisional backend printwindow_clientonly** |
| G-E-REAL | Owner-machine real-target validation (consolidated `validate-real-target` run) with the live content confirmation; mandatory before final implementation-PR merge and any real-target support claim | **Pending owner-machine execution** |
| G-F | Capture/data-use permission: scope recorded (OD-M2-8); the live per-session confirmation is required immediately before each **real, non-synthetic** capture session | **Scope recorded 2026-07-18; live confirmation applies at G-E-REAL and real-target manual acceptance** |
| G-G | Owner records the remaining implementation defaults and execution boundary: scope, retention/disk, stability, cursor, and roadmap/prompt | **Closed 2026-07-18: OD-M2-1/3/4/5/7** |

Gate ordering (revised per OD-M2-9, 2026-07-18): G-D, G-G, and
**G-E-SYNTHETIC** authorize M2-002..M2-011 implementation, the PR #4 merge,
and a Draft implementation PR. **G-E-REAL** (the former owner-run M2-001
trial, now delivered as the consolidated `validate-real-target` command plus
the live G-F confirmation) moves to the end: it blocks the final
implementation-PR merge and every real-target support claim, and is never
marked passed without actual owner-machine execution. A failed
G-E-SYNTHETIC on both MVP backends triggers the Windows Graphics Capture /
C# fallback plan instead of the PowerShell-worker milestone.

## Milestones

Complexity: S (< half day), M (about one day), L (multi-day). `technical`
means a future coding agent after authorization; `owner` means a person at the
authorized machine. Test IDs below are planned acceptance work, not executed
results.

| ID | Objective and deliverable | Likely files | Prohibited | Depends on | Planned tests / acceptance | Recovery / rollback | Cx | Actor |
|---|---|---|---|---|---|---|---|---|
| M2-000 | Review and approve this planning-only package; record G-D, G-F, and G-G decisions | planning docs only | production code, implied S7 pass | G-A, G-B, G-C | Cross-document review; current baseline/M1 regression and sanitization gates | revise or close planning PR; no runtime state exists | S | owner |
| M2-001 | Run the disposable S7 tool once for each `present`, `absent`, and `occluded` trial; record each backend's API/visual verdict and decide OD-M2-2 | ignored `.lab_work/m2_research/`; sanitized result record only after owner review | confidential/proprietary content; committed screenshots; continuous capture; bypassing protections | approved M2-000, G-D, **G-F** | MA-1: three complete trial records with no trial-invalid outcome; at least one owner-accepted readable backend; cross-backend geometry/DPI agreement or factual API failure; limitations recorded | default temporary previews are ephemeral non-evidence; `--save` publishes unique no-overwrite ignored local raw gate evidence only with its sanitized record and SHA-256 manifest; revise architecture or abandon direction | S | owner |
| M2-002 | Scaffold the isolated package; PMv2 bootstrap before coordinate APIs; explicit target selection; environment/topology snapshot | `src/screen2xyz_m2/{__init__,dpi,targets,environment}.py`, new `tests_m2/` | capture loop, OCR, edits to baseline/M1 packages | **G-D, G-E, G-F, G-G** | Implement applicable T-M2L-001/019/028 model cases; no worker integration test yet | revert only this milestone's code; prior evidence untouched | M | technical |
| M2-003 | Implement generic source model, closed sign/parser rules, and bounded ignored profiles | `sources.py`, `parsing.py`, `profiles.py` | service-specific presets; private baseline parser imports | M2-002 | Implement T-M2L-001..005 and T-M2L-019 | revert milestone commit | M | technical |
| M2-004 | Implement the bounded worker/client protocol `m2w.1`: exact commands `INIT`, `REGION_SNAPSHOT`, `PREVIEW`, `ARM`, `DISARM`, `RECORD_START`, `CAPTURE`, `PAUSE`, `RESUME`, `HEALTH`, `STOP`, `SHUTDOWN`; lifecycle, revision/mode/generation matching, backend/content diagnostics, message caps | `adapters/capture_worker_windows.ps1`, `worker.py` | UI; `PW_RENDERFULLCONTENT`; generic `status`; second evidence capture; unbounded lines/PNGs | M2-003 | Implement T-M2L-020..027, T-M2L-030/032/033 worker integrations, and T-M2L-041 | invalidate → terminate/force-kill → reap → drain buffered diagnostics → close stdin/stdout/stderr → signal/join readers → backoff/fresh INIT; revert milestone commit | L | technical |
| M2-005 | Implement the non-overlapping scheduler, restart/timeout policy, stability engine, retention precedence, and bounded first-candidate evidence ownership | `scheduler.py`, `stability.py` | UI polish; stale-value substitution; size-pressure eviction | M2-004 | Implement T-M2L-006..010, T-M2L-031/040, and the non-UI scheduler harness for T-M2L-038 | Pause/block on the context-specific §0 failure policy; revert milestone commit | M | technical |
| M2-006 | Implement atomic crops, canonical JSONL journal, checkpoint, exact recovery warnings/fail-closed rules, retention modes, and disk thresholds | `journal.py`, `recovery.py` | exports; deleting orphan or prior evidence | M2-005 | Implement T-M2L-012..014 | journal wins; preserve artifacts; corrective runs are new runs | M | technical |
| M2-007 | Implement the setup, frozen region snapshot, one-frame preview, ARM/Start flow, recording/final screens, and always-available mini controller with Pause/Resume, Stop, and Emergency Stop | `ui/*.py` | periodic capture outside RECORDING; overlapping worker requests; hidden stop controls | M2-005, M2-006 | Complete T-M2L-011/029/034..039 and UX §4 synthetic smoke checks | emergency stop completes within the §0 bound; revert milestone commit | L | technical |
| M2-008 | Implement deterministic exports, manifest, strict XYZ filter, and optional cursor metadata (default off unless OD-M2-5 changes it) | `exports.py` | coordinate transformation; authoritative/downstream compatibility claims | M2-006, M2-007 | Implement T-M2L-015..017 and MA-7 synthetic dry run | rebuild from canonical journal; revert milestone commit | M | technical |
| M2-009 | Run controlled integration evaluation using a locally generated scripted target with flicker, ambiguity, capture-failure, stabilization, and crash-recovery cases; retain a new immutable evidence run | evaluation module; new `runs/evidence/S2XYZ-M2-009/` | touching/deleting prior evidence; real-source data; invented metrics | M2-008 | Planned M2 suite and full regressions pass; evidence manifest verifies; metrics reported exactly | never delete accepted evidence; remediation creates a new run/task ID | M | technical |
| M2-010 | Execute T-M2L-042 and MA-2..MA-8, including the bounded 30-minute soak, on the owner-authorized environment and content; record sanitized outcomes and limitations | ignored local run; reviewed acceptance report | running before G-F; committing screenshots/raw titles; generalizing one-machine results | M2-009, renewed **G-F** confirmation | Every manual/performance step passes or is explicitly failed/blocked; no inferred result | stop safely; leave PR Draft; remediate with a new evidence run | M | owner |
| M2-011 | Independent adversarial review, remediation, release-readiness report, and owner merge decision | scoped fixes and report | scope growth; self-merge; production/readiness overclaim | M2-010 | Full regression, evidence, sanitization, diff-scope, and independent review gates | leave PR Draft or close; preserve all evidence | M | technical + owner |

## Per-milestone quality gate

After every future implementation milestone, record reproducible output for:

- baseline `tests/run_all.py` (currently 42 tests) and M1
  `tests_m1/run_m1_tests.py` (currently 34 tests);
- the then-current frozen M2 suite, without claiming a count before it exists;
- `python -m screen2xyz_lab.cli verify-evidence`;
- repository sanitization, `git diff --check`, scoped-diff review, and proof that
  ignored capture outputs are not staged;
- an explicit check that prior retained evidence is byte-for-byte untouched.

Any failure stops the milestone. The demo-critical dependency is
M2-002 -> M2-007, but no demo schedule weakens G-D/G-E/G-F/G-G, evidence
integrity, or the source-agnostic design. Existing sealed baseline/M1 evidence
remains separate from and does not validate M2-Live.
