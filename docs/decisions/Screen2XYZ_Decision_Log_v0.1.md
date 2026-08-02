# Screen2XYZ - Decision Log

| Field | Value |
|---|---|
| Document | Decision Log |
| Version | v0.1 |
| Date | 2026-07-18 |
| Status | Current - Controller Maintained |

## DEC-001 - Charter v0.1 approval

| Field | Recorded decision |
|---|---|
| Decision | Approve `Screen2XYZ_Project_Charter_v0.1.md` as written. |
| Approval date | 2026-07-14 |
| Approved by | Project Owner |
| Gate result | G0 Passed |
| Scope authorized | Controlled planning, project-control documents, administrative repository scaffolding, and repository review. |
| Historical scope boundary | Functional coding, dependencies, prototype implementation, architecture selection, real-source data collection, and unsupported claims were outside that task. |

## DEC-002 - Repository bootstrap acceptance

| Field | Recorded decision |
|---|---|
| Decision | Accept S2XYZ-CODEX-000 as verified completed. |
| Evidence | S2XYZ-AUDIT-000 |
| Audited commit | `a89701b5ef18d7aa8ef7f68c29fa23f421669474` |
| Finding | 24 administrative files, 134 insertions, zero deletions, and no functional or prohibited content. |

## DEV-001 - Pre-G0 administrative scaffold

| Field | Recorded disposition |
|---|---|
| Event | Administrative repository scaffold was created before Gate G0 approval. |
| Classification | Process deviation, not functional implementation. |
| Resolution | Charter v0.1 was approved and the repository bootstrap passed file-level audit. |
| Status | Closed - accepted procedural deviation |
| Closure date | 2026-07-14 |
| Historical control | The historical bootstrap commit must not be rewritten. |

## DEC-003 - Governance baseline audit and integration

| Field | Recorded decision |
|---|---|
| Decision | Accept S2XYZ-CODEX-001 as independently audited and verified completed. |
| Audit date | 2026-07-15 |
| Audit method | Three parallel read-only reviewers plus parent-agent evidence consolidation under S2XYZ-CODEX-002. |
| Governance baseline commit | `b6cd2198722bd53e291354d2c02eaad33b4b3bb1` |
| Audit result | Verified completed; no material governance, scope, prohibited-content, or repository-integrity finding. |
| Integration result | Local `main` was fast-forwarded from `a89701b5ef18d7aa8ef7f68c29fa23f421669474` to the governance baseline commit without rewriting history. |
| GitHub connection result | The predecessor repository was configured as `origin`; controlled baseline branches were pushed and matched local refs. |

## DEC-004 - Repository-based parent-agent orchestration

| Field | Recorded decision |
|---|---|
| Decision | Adopt GitHub and repository control files as the primary operational bridge between ChatGPT Project HQ and Codex. |
| Controlling-state rule | Chat history is supporting context, not the controlling project state. |
| Writer rule | The parent agent is the only file writer during a run. |
| Subagent rule | Specialized subagents are read-only unless a later approved decision changes this rule. |
| Branch rule | Each task uses one controlled task-specific branch and one consolidated report. |
| Parallel-write rule | Parallel write-heavy work is prohibited unless a later approved decision permits it. |

## DEC-005 - S2XYZ-CODEX-002 acceptance and pull request #1 merge

| Field | Recorded decision |
|---|---|
| Decision | Accept the S2XYZ-CODEX-002 orchestration bridge after review through the connected workflow and authorize merge of pull request #1. |
| Approved by | Project Owner |
| Decision date | 2026-07-15 |
| Integration result | Pull request #1 merged into `main` at `a8afa5a678fefa183f1c4b7a3648416cff24f39a`. |
| Audit clarification | No separate S2XYZ-AUDIT-002 task was created or completed; earlier projected references are superseded by this explicit owner disposition. |
| Effect | The repository-based orchestration bridge is accepted and is the active operating model. |

## DEC-006 - Conditional S2XYZ-CODEX-003 authorization

| Field | Recorded decision |
|---|---|
| Decision | Authorize S2XYZ-CODEX-003 and conditional passage of G1-G4 only when each gate's required documents, evidence, read-only reviews, and Blocker/Major resolution conditions are satisfied. |
| Approved by | Project Owner |
| Decision date | 2026-07-15 |
| Required gate wording | `Conditionally approved by the project owner through S2XYZ-CODEX-003 for the scoped synthetic OCR lab only.` |
| Authorized implementation | After G4 only: actual OCR on locally generated synthetic screenshots; parsing, validation, duplicate/stale detection, deterministic source-coordinate CSV/XYZ demonstration export, metrics, tests, and retained evidence. |
| Run-scoped technical context | Current Windows environment; English labels; decimal degrees; EPSG:4326; explicit longitude/latitude axis handling; elevation metres; `SYNTHETIC_LOCAL`; no cursor or real-source automation. |
| Deferred interfaces | Coordinate transformation and cursor control remain future replaceable interfaces only. |
| Prohibited | Real third-party data, service-specific automation, public release, repository licence selection, authoritative or survey-grade claims, downstream automation/import compatibility claims, and merge of the active branch or pull request. |
| Decision scope | Run-scoped evaluation authorization, not universal product, production architecture, legal, dataset, licence, release, or risk acceptance. |

## DEC-007 - Conditional passage of G1, G2, and G3

| Field | Recorded decision |
|---|---|
| Decision | Pass G1 Product Strategy, G2 Data and Legal Guardrails, and G3 Product Requirements in order after required documents, read-only specialist reviews, parent validation, and resolution of every Blocker/Major finding. |
| Decision date | 2026-07-15 |
| Authorization | `Conditionally approved by the project owner through S2XYZ-CODEX-003 for the scoped synthetic OCR lab only.` |
| G1 evidence | `runs/evidence/S2XYZ-CODEX-003/gates/G1_Product_Strategy.md` |
| G2 evidence | `runs/evidence/S2XYZ-CODEX-003/gates/G2_Data_and_Legal_Guardrails.md` |
| G3 evidence | `runs/evidence/S2XYZ-CODEX-003/gates/G3_Product_Requirements.md` |
| Review evidence | Product Strategy/Requirements, Data/Privacy/Legal, and QA/Metrics read-only review records under `runs/evidence/S2XYZ-CODEX-003/reviews/` |
| Boundary | Architecture/test planning may proceed. No implementation is authorized until G4 separately passes. No broader product, real-source, public-release, legal-rights, production, or compatibility approval is inferred. |

## DEC-008 - Conditional passage of G4

| Field | Recorded decision |
|---|---|
| Decision | Pass G4 after architecture, ADR, test design, fixture specification, actual local OCR preflight, dependency/data evidence, read-only specialist reviews, parent validation, and resolution of every Blocker/Major finding. |
| Decision date | 2026-07-15 |
| Authorization | `Conditionally approved by the project owner through S2XYZ-CODEX-003 for the scoped synthetic OCR lab only.` |
| Gate evidence | `runs/evidence/S2XYZ-CODEX-003/gates/G4_Scoped_Implementation_Authorization.md` |
| Review evidence | Final G4 Architecture/Dependency, QA/Test Design, and Data/Dependency review records under `runs/evidence/S2XYZ-CODEX-003/reviews/` |
| Authorized work | Implement and test only the locally generated synthetic-image OCR pipeline, raw evidence, parser/validator, stale/duplicate classifier, deterministic source-coordinate demonstration export, metrics, and retained evidence. |
| Boundary | No real-source operation, named-service preset, cursor/GUI automation, live-capture claim, transformation, downstream compatibility claim, terrain/earthwork work, production architecture, licence/public release, or merge authorization. |

## DEC-009 - Additive G4 implementation correction authorization

| Field | Recorded decision |
|---|---|
| Decision | Accept the bounded pre-evaluation correction baseline after independent re-review and authorize retained execution of the same scoped synthetic OCR laboratory. |
| Decision date | 2026-07-15 |
| Authorization | `Conditionally approved by the project owner through S2XYZ-CODEX-003 for the scoped synthetic OCR lab only.` |
| Corrected baseline | `83b569b2d0e6fce4253aaca0f93708826a02aaf2` |
| Gate evidence | `runs/evidence/S2XYZ-CODEX-003/gates/G4_Scoped_Implementation_Correction_Authorization.md` |
| Review result | Independent architecture, data/guardrail, and QA closeout reviews found zero unresolved Blocker or Major after remediation. |
| Effect | Retained two-run actual OCR evaluation on the frozen locally generated 60-image fixture may proceed. |
| Boundary | No target, expected classification, prohibited-work boundary, product acceptance, production claim, real-source scope, licence/release decision, compatibility claim, or merge authorization changed. |

## DEC-010 - Baseline/M1 integration and M2-000 planning transition

| Field | Recorded decision |
|---|---|
| Recorded date | 2026-07-18 |
| Verified integration state | PR #2 merged at `d740fade17a8a616e9a608e58c2556974636c38c`; PR #3 merged at `9339aa18ed56d1326597358f02547a374bc1d44e`, now the M2-000 planning base. |
| Current task | Prepare and independently review a planning-only M2-Live research, requirements, architecture, UX, data-contract, test, guardrail, roadmap, and implementation-prompt package on `plan/m2-live-region-watch`. |
| Authorized repository actions | Preserve the dirty continuation state; remediate planning findings; run existing regressions/evidence/sanitization gates; commit logically; push; open one Draft PR to `main`. |
| Planning handoff | Draft PR #4 opened against `main` after four logical planning commits and passing independent/automated closeout; it remains Draft and unmerged for owner review. |
| Gates not granted | UX approval G-D, target compatibility G-E, capture/data-use permission G-F, and scope/defaults/roadmap gate G-G remain pending. S7 has not run against the intended target. |
| Prohibited | Production M2 code, implementation-branch creation, unauthorized or confidential capture content, gate inference, merge, and production/readiness claims. |
| Detailed decisions | Historical M2 decisions were completed before the v2 unification work. |
