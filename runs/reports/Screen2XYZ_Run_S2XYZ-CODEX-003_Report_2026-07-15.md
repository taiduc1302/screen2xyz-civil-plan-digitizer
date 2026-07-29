# Screen2XYZ Run Report - S2XYZ-CODEX-003

| Field | Value |
|---|---|
| Task ID | S2XYZ-CODEX-003 |
| Date | 2026-07-15 |
| Starting branch | `main` |
| Starting commit | `a8afa5a678fefa183f1c4b7a3648416cff24f39a` |
| Task branch | `feat/overnight-v0.2-planning-ocr-lab` |
| Report status | Completed; draft pull request #2 open and unmerged; `OWNER_HANDOFF` posted |
| Live-capture status | Not executed |
| Output classification | Conceptual and preliminary estimating data only. |

## 1. Overall result

The repository-state reconciliation, v0.2 strategy/requirements/guardrails/architecture/test-planning baseline, frozen 60-image synthetic fixture, experimental actual-OCR laboratory, two retained OCR runs, deterministic comparison, metrics, environment evidence, full 41-test evidence finalization, independent final review, draft pull request, and owner handoff are complete. The retained evaluation met every frozen run-scoped target, all 41 mapped automated tests passed, the retained evidence manifest verified with zero errors, and final review found zero unresolved Blockers or Majors. Draft pull request [#2](https://github.com/taiduc1302/screen2xyz/pull/2) remains open, draft, and unmerged.

No accepted production application, real-source workflow, live-capture result, coordinate transformation, downstream import result, terrain or earthwork calculation, repository licence, public release, or authoritative validation was produced.

## 2. Control-state reconciliation

- Verified that pull request #1 had been owner-accepted and merged into `main` at `a8afa5a678fefa183f1c4b7a3648416cff24f39a`.
- Corrected stale control text without claiming that a separate S2XYZ-AUDIT-002 existed.
- Recorded the orchestration bridge as accepted and S2XYZ-CODEX-003 as the active task.
- Preserved historical commits and evidence without amendment, rebase, force-push, or deletion.

## 3. Owner authorizations used

- OD-002 and DEC-006 authorize the conditionally gated S2XYZ-CODEX-003 run.
- Every passed gate records exactly: `Conditionally approved by the project owner through S2XYZ-CODEX-003 for the scoped synthetic OCR lab only.`
- DEC-007 records conditional passage of G1-G3.
- DEC-008 records conditional passage of G4.
- DEC-009 and the additive G4 correction record authorize corrected baseline `83b569b2d0e6fce4253aaca0f93708826a02aaf2` after independent re-review found zero Blocker or Major.
- The authorization is run-scoped and does not imply product, production, legal, dataset, licence, release, compatibility, or risk acceptance.

## 4. Read-only subagents used

The parent agent remained the only repository writer. Read-only specialists covered:

1. Product Strategy and Requirements;
2. Data, Privacy, and Legal Guardrails;
3. Architecture and Dependency Review;
4. QA, Metrics, and Test Design;
5. implementation correction closeout across architecture, guardrails, and QA;
6. Independent Final Review across architecture/source-of-truth, guardrails/privacy/provenance, and QA/evidence/handoff.

Their gate and correction dispositions are retained under `runs/evidence/S2XYZ-CODEX-003/reviews/`. Every identified Blocker and Major was corrected and independently re-reviewed before retained execution.

The three final read-only reviewers inspected checkpoint `76adc932b7dd0e2532e18e2b169c10f357192957` against accepted base `a8afa5a678fefa183f1c4b7a3648416cff24f39a`. Consolidated disposition was 0 Blockers and 0 Majors. One architecture-description Minor was corrected outside retained evidence. One historical line-ending provenance Minor is preserved and clarified below rather than rewriting sealed gate evidence. The consolidated record is `runs/reports/Screen2XYZ_Final_Independent_Review_S2XYZ-CODEX-003_2026-07-15.md`.

## 5. Gate results and evidence

| Gate | Result | Primary evidence |
|---|---|---|
| G1 | Conditionally passed | `runs/evidence/S2XYZ-CODEX-003/gates/G1_Product_Strategy.md` |
| G2 | Conditionally passed | `runs/evidence/S2XYZ-CODEX-003/gates/G2_Data_and_Legal_Guardrails.md` |
| G3 | Conditionally passed | `runs/evidence/S2XYZ-CODEX-003/gates/G3_Product_Requirements.md` |
| G4 | Conditionally passed | `runs/evidence/S2XYZ-CODEX-003/gates/G4_Scoped_Implementation_Authorization.md` |
| G4 additive correction | Conditionally passed | `runs/evidence/S2XYZ-CODEX-003/gates/G4_Scoped_Implementation_Correction_Authorization.md` |

## 6. Selected stack and dependency evidence

| Component | Selected observation |
|---|---|
| Python | CPython 3.14.6 standard library |
| Isolation | Repository-local `.venv`, created with `--without-pip`; include-system-site-packages false |
| Installed distributions | 0, dynamically revalidated |
| PowerShell child host | 5.1.26100.8875 |
| Operating system | Windows 10.0.26200.0 on the current computer |
| .NET Framework | Release 533509; mscorlib assembly 4.0.0.0; file 4.8.9337.0 |
| Renderer | System.Drawing/GDI+ |
| Font | Arial regular, 1,045,720 bytes, SHA-256 `b3658eadae55e682b5f69eb64c439c1ecc8f196c0bb8d4756d145d13bc86476a` |
| OCR | Windows.Media.Ocr, semantic version not exposed, language `en-US` |
| Direct third-party project dependencies | None |

No package-manager file, downloaded model, incorporated third-party binary, repository licence, or public redistribution authorization was added.

## 7. Implementation summary

The experimental current-machine lab implements:

- deterministic synthetic scenario generation with seed `20260715`;
- 60 generated PNGs across 32 px, 40 px, and 48 px conditions;
- a runtime-only manifest separated from render jobs and evaluator ground truth;
- strict local PNG/path/size/dimension/hash/chunk boundaries;
- actual OCR through a bounded local adapter;
- exact raw OCR retention as UTF-8 base64 and SHA-256;
- label-driven Decimal parsing with bounded OCR minus-glyph normalization;
- metadata, completeness, precision, and range validation;
- deterministic duplicate and sequence-adjacent stale classification;
- accepted/rejected CSV, source-coordinate XYZ demonstration, and metadata sidecar;
- exact 16-metric calculation and failed-case retention;
- frozen 69-item two-run repeatability comparison;
- atomic writes, copy-on-write evidence, transaction rollback, bounded run/child timeouts, and manifest-last finalization;
- privacy, scope, traceability, provenance, schema, recovery, and claim-boundary tests.

It does not implement live capture, cursor movement, GUI automation, real-source operation, coordinate transformation, downstream automation/import, terrain calculation, or earthwork calculation.

## 8. Fixture and dataset provenance

The registered `DS-SYN-001` fixture contains exactly 60 locally generated synthetic scenarios: 42 expected-valid and 18 expected-invalid. It contains 36 ordinary valid, 6 additional negative-elevation valid, 6 malformed/missing, 6 duplicate, and 6 stale scenarios. The fixed seed is `20260715`.

Control hashes:

- `fixture_config.json`: `8c7fee7a45923df2eca26ab165603ae339b6725b509b96638a08b9cd695f1a96`
- `render_jobs.json`: `8feb09ef905a76fdf04c081e1448f0034834dbb194e74b513377c660d1510ab2`
- `ground_truth.csv`: `09b8907e4f2d8a72dade67b982966494e06e67ecc0283f0e629c85c057fb6c37`
- `fixture_manifest.json`: `6418c7c881648d6efc1abb328be944fcefe59e50287c0bec4486c436c7f39361`

Every image hash is retained in the fixture manifest. No real, personal, confidential, proprietary, copied-interface, or external elevation data was added.

## 9. Exact retained OCR metrics

| Required metric | Exact retained result | Status |
|---|---:|---|
| Latitude field exact match | 42/42 = 1.000000 | Report only |
| Longitude field exact match | 42/42 = 1.000000 | Report only |
| Elevation field exact match | 42/42 = 1.000000 | Report only |
| Complete three-field exact match, baseline | 14/14 = 1.000000 | Met (target at least 0.95) |
| Complete three-field exact match, all valid | 42/42 = 1.000000 | Met (target at least 0.90) |
| Parser success on frozen known-clean corpus | 13/13 = 1.000000 | Met |
| End-to-end accepted-reading correctness | 42/42 = 1.000000 | Report only |
| Rejected-reading rate | 18/60 = 0.300000 | Report only |
| Expected-invalid rejection | 18/18 = 1.000000 | Met |
| False accepts | 0/18 | Met |
| False rejects | 0/42 | Report only |
| Duplicate detection | 6/6 = 1.000000 | Met |
| Stale detection | 6/6 = 1.000000 | Met |
| Accepted coordinate error | latitude mean/max 0.0/0.0 degrees; longitude mean/max 0.0/0.0 degrees; 42 eligible | Report only |
| Accepted elevation error | mean/max 0.0/0.0 metres; 42 eligible | Report only |
| OCR recognition timing | total 1,001 ms; mean 16.683333 ms; p50 16 ms; p95 23 ms; max 24 ms; 60 readings | Report only |
| Repeatability difference | 0/60 classification; 0/60 raw projection; 0/69 deterministic hashes | Met |

The timing values are adapter-reported recognition durations. They do not include all process-startup and parent-run wall time.

Diagnostics: 0 OCR failures, 0 OCR timeouts, and no failed scenario IDs.

## 10. Targets and failed cases

All frozen run-scoped targets were met. `failed_cases.json` contains an empty failed-case list. No test, target, ground truth, expected classification, or denominator was weakened after execution.

## 11. Exact material commands executed and exit codes

| Purpose | Exact command | Exit |
|---|---|---:|
| GitHub authentication | `& 'C:\Program Files\GitHub CLI\gh.exe' auth status` | 0 |
| Fetch | `git fetch --all --prune` | 0 |
| Update accepted base | `git switch main` then `git pull --ff-only origin main` | 0 / 0 |
| Create task branch | `git switch -c feat/overnight-v0.2-planning-ocr-lab` | 0 |
| Create isolation | `py -3.14 -m venv --without-pip .venv` | 0 |
| Fixture verification | `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m screen2xyz_lab.cli generate` | 0 |
| Retained Run A | `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m screen2xyz_lab.cli evaluate --output .lab_work\retained-ocr-run-a` | 0 |
| Retained Run B | `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m screen2xyz_lab.cli evaluate --output .lab_work\retained-ocr-run-b` | 0 |
| Publish comparison | `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m screen2xyz_lab.cli publish --run-a .lab_work\retained-ocr-run-a --run-b .lab_work\retained-ocr-run-b` | 0 |
| Environment evidence | `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m screen2xyz_lab.cli environment` | 0 |
| Final full tests | `$env:PYTHONPATH='src'; $env:PYTHONDONTWRITEBYTECODE='1'; & '.\.venv\Scripts\python.exe' tests\run_all.py --output .lab_work\S2XYZ-CODEX-003-test-results.txt` | 0 |
| Evidence finalization | `$env:PYTHONPATH='src'; & '.\.venv\Scripts\python.exe' -m screen2xyz_lab.cli finalize-evidence --test-results .lab_work\S2XYZ-CODEX-003-test-results.txt` | 0 |
| Evidence verification | `$env:PYTHONPATH='src'; & '.\.venv\Scripts\python.exe' -m screen2xyz_lab.cli verify-evidence` | 0 |
| Whitespace validation | `git diff --check` | 0 |
| Evidence checkpoint commit | `git commit -m "test: retain synthetic OCR evaluation evidence"` | 0 |
| Evidence checkpoint push | `git push origin feat/overnight-v0.2-planning-ocr-lab` | 0 |
| Open draft pull request | `& 'C:\Program Files\GitHub CLI\gh.exe' pr create --repo taiduc1302/screen2xyz --draft --base main --head feat/overnight-v0.2-planning-ocr-lab --title 'feat: add Screen2XYZ v0.2 planning baseline and synthetic OCR lab' --body-file '.lab_work\S2XYZ-CODEX-003-pr-body.md'` | 0 |
| Post owner handoff | `& 'C:\Program Files\GitHub CLI\gh.exe' pr comment 2 --repo taiduc1302/screen2xyz --body-file '.lab_work\S2XYZ-CODEX-003-owner-handoff.md'` | 0 |

Focused remediation suite:

```powershell
$env:PYTHONPATH='src;tests'; $env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest -q test_config_fixture.ConfigFixtureTests test_exports_recovery.ExportRecoveryTests.test_T_EXP_001_csv_dialect test_exports_recovery.ExportRecoveryTests.test_T_EXP_003_xyz_schema test_exports_recovery.ExportRecoveryTests.test_T_EXP_004_sidecar_schema test_exports_recovery.ExportRecoveryTests.test_T_REC_001_atomic_write_failure test_exports_recovery.ExportRecoveryTests.test_T_REC_002_config_corruption_and_idempotency test_exports_recovery.ExportRecoveryTests.test_T_REC_003_run_fatal_separation test_metrics_repeatability.MetricsRepeatabilityTests.test_T_MET_001_sixteen_formulas test_metrics_repeatability.MetricsRepeatabilityTests.test_T_MET_002_schema_and_zero_denominator test_ocr_parser.OcrParserTests.test_T_OCR_003_timeouts_and_local_host test_ocr_parser.OcrParserTests.test_T_PAR_001_labels_variants_and_order test_ocr_parser.OcrParserTests.test_T_PAR_002_precision_signs_and_controls test_ocr_parser.OcrParserTests.test_T_PAR_003_raw_immutability test_guardrails_traceability_evidence.GuardrailTraceabilityEvidenceTests.test_T_PRI_001_privacy_scan
```

Observed focused result: 19 tests passed, exit `0`. The separately strengthened non-perfect `T-MET-001` test passed, exit `0`. The final complete suite then passed 41/41 tests in 14.727 seconds with 0 failures, 0 errors, and 0 skipped.

After the final-review description correction, `T-SCOPE-004`, `T-SCOPE-005`, and `T-TRC-001` passed together, 3/3 with exit `0`. Both independent focused reviewer closeouts returned 0 Blockers and 0 Majors; the architecture Minor was closed and the preserved provenance nuance was accepted as truthfully disclosed.

## 12. Files created and modified

Created groups:

- Repository byte controls: `.gitattributes` preserves the frozen fixture and retained evidence line endings so reviewed SHA-256 values survive checkout.
- Phase A: Product Strategy, Product Requirements, Data Dictionary, Requirements Traceability Matrix, Data/Legal Guardrails, Dataset Register, Dependency Register, Privacy/Threat Review, and Risk Register.
- Phase B: Architecture Specification, Architecture Decision Record, Test Plan, 41-row Test Matrix, 15 Acceptance Criteria, and Synthetic Fixture Specification.
- Laboratory: `src/screen2xyz_lab/` package with configuration, models, fixture, pipeline, parser, validator, temporal classifier, exporters, metrics, evidence, CLI, and three Windows adapters.
- Tests: six test modules, helpers, the exact 41-test runner, and test documentation.
- Fixture: configuration, render jobs, ground truth, runtime manifest, README, and `images/S001.png` through `images/S060.png`.
- Examples and expected outputs: synthetic lab documentation and representative parser cases.
- Evidence: preflight, gate, review, fixture, OCR, accepted/rejected, XYZ/sidecar, metrics, repeatability, failure, environment, dependency, test, and manifest artifacts under `runs/evidence/S2XYZ-CODEX-003/`.
- Public/control/handoff: local run guide, Kubla preparation note, Owner Summary, draft next task, this run report, and the final independent review report.

Modified files relative to the accepted base:

- `.gitignore` and `README.md`.
- `docs/Screen2XYZ_Master_Index_v0.1.md`, `docs/control/NEXT_ACTION.md`, `docs/control/OWNER_DECISIONS.md`, `docs/control/PROJECT_STATE.md`, and `docs/decisions/Screen2XYZ_Decision_Log_v0.1.md`.
- `examples/README.md`, `src/README.md`, `test_data/expected_outputs/README.md`, `test_data/synthetic/README.md`, and `tests/README.md`.

All other task files are additions relative to the accepted base. Git storage for the newly added `test_data/synthetic/s2xyz_fixture_v0.1/ground_truth.csv` preserves its required CRLF bytes; its reviewed working content and registered SHA-256 were unchanged by that storage correction.

The complete final file-level change list is reproducible with:

```powershell
git diff --name-status a8afa5a678fefa183f1c4b7a3648416cff24f39a...HEAD
```

## 13. Evidence locations

- Retained run root: `runs/evidence/S2XYZ-CODEX-003/`
- Metrics: `runs/evidence/S2XYZ-CODEX-003/metrics.json`
- Raw OCR: `runs/evidence/S2XYZ-CODEX-003/raw_ocr_readings.csv`
- Accepted/rejected: `runs/evidence/S2XYZ-CODEX-003/accepted_points.csv` and `rejected_readings.csv`
- Repeatability: `runs/evidence/S2XYZ-CODEX-003/repeatability_comparison.json` and `repeatability/`
- Environment/dependencies: `environment.json` and `dependency_inventory.txt`
- Tests: `test_results.txt` (41/41 passed; exit 0)
- Integrity: `evidence_manifest_sha256.txt` (verified `PASS` with zero errors)
- Gates/reviews: `gates/` and `reviews/`
- Report: `runs/reports/Screen2XYZ_Run_S2XYZ-CODEX-003_Report_2026-07-15.md`
- Final independent review: `runs/reports/Screen2XYZ_Final_Independent_Review_S2XYZ-CODEX-003_2026-07-15.md`
- Draft pull request: `https://github.com/taiduc1302/screen2xyz/pull/2`
- Owner handoff comment: `https://github.com/taiduc1302/screen2xyz/pull/2#issuecomment-4983908499`

## 14. Security, privacy, data, and licence findings

- Runtime code contains no network client, source-service preset, live-capture implementation, cursor controller, or coordinate transformer.
- Retained runtime/environment records use bounded schemas and contain no absolute personal path, credential, token, environment dump, or machine identity.
- Every fixture is registered as locally generated synthetic project data.
- No external elevation dataset or copied interface asset was added.
- Relevant component versions and licence-evidence dispositions are recorded without claiming legal approval.
- No repository licence was selected; public redistribution and release remain unauthorized.

## 15. Limitations and regression risk

- Current computer only; broader Windows compatibility is unverified.
- Generated PNG inputs only; live capture is `Not executed`.
- The fixed fixture is intentionally narrow and may not predict robustness under different visual conditions.
- OCR engine semantic version is not exposed.
- Recognition timing excludes child-process startup and whole-run wall time.
- Source XYZ uses geographic degrees and is not proven suitable for Kubla or another downstream import.
- The additive G4 gate's historical `byte-identical` wording is imprecise for the committed `957210e` ground-truth blob: that blob used LF while the reviewed fixture and registered hash used required CRLF. Parsed/newline-normalized content is identical, current Git bytes match the registered CRLF hash, and the sealed historical gate was not rewritten.
- No transformation, import, terrain, earthwork, production, authoritative, licence, or public-release result exists.

Regression risk is moderate within the experimental lab: the implementation is small and covered by 41 mapped tests, but it relies on current-machine OS OCR, font, and framework components. The frozen fixture, environment fingerprint, hashes, repeatability projection, and copy-on-write evidence make changes detectable.

## 16. Kubla status

Documentation only. Import status is `Not executed`; no compatibility claim is made. Geographic degree coordinates are not proven suitable.

## 17. Owner decisions required

None to complete the already authorized S2XYZ-CODEX-003 run. Any later robustness, live-capture, real-source, transformation, import, product, licence, or release work requires a separately reviewed authorization.

## 18. Proposed next version

No version advancement is approved. `prompts/drafts/NEXT_CODEX_TASK.md` proposes a review-only v0.2 synthetic robustness extension; it is explicitly not approved and does not begin a later phase.

## 19. Exactly one recommended next action

The project owner reviews draft PR #2 and decides whether to accept it or request revisions without merging or beginning the next project phase.

Conceptual and preliminary estimating data only.
