# Screen2XYZ Product Strategy v0.1

| Field | Value |
|---|---|
| Task | S2XYZ-CODEX-003 |
| Status | G1 conditionally passed for the scoped synthetic OCR lab only |
| Scope | Current-Windows, locally generated synthetic OCR lab only |
| Product baseline | v0.2 planning and synthetic evaluation |
| Document version | v0.1 |
| Output classification | Conceptual and preliminary estimating data only. |

## Controlled interpretation

This strategy narrows the approved Charter to one reversible feasibility experiment. It does not authorize real-source operation, production design, public release, survey or construction use, coordinate transformation, cursor control, earthwork calculation, or a Kubla import claim.

Statements are classified as **Verified fact**, **Observed test result**, **Assumption**, **Proposal**, **Open question**, or **Known limitation**. No OCR quality result is an observed fact until the retained S2XYZ-CODEX-003 evidence is generated.

## Strategy statements

### S2XYZ-PS-001 - Problem

**Proposal.** Determine whether visible English `lat`, `lon`, and `elev` text in locally generated synthetic screenshots can be processed by actual local OCR, parsed, safely classified, and exported with reproducible evidence on the current Windows computer.

### S2XYZ-PS-002 - Users

**Proposal.** The primary user for this lab is a technical evaluator or QA reviewer assessing feasibility and evidence. Secondary users are the project owner and a developer reproducing the lab. Construction estimators are eventual stakeholders, not operators of this synthetic experiment.

### S2XYZ-PS-003 - Scoped use case

**Proposal.** The end-to-end use case is:

`fixed-seed ground truth -> rendered visible text -> generated screenshot -> actual OCR -> retained raw text -> parse -> validate -> duplicate/stale classification -> accepted/rejected demonstration output -> metrics and evidence`

Ground truth must not supply runtime OCR or classification values. It is joined only during evaluation.

### S2XYZ-PS-004 - Value hypothesis

**Assumption.** A small, source-agnostic vertical slice can retire uncertainty about OCR, parsing, rejection, deterministic export, and evidence practices before any broader product work. It does not estimate earthwork or validate real-source accuracy.

### S2XYZ-PS-005 - Intended scope

**Verified fact.** The project owner authorized these run-scoped constraints:

- current Windows environment only;
- locally generated synthetic values and screenshots only;
- English visible labels `lat`, `lon`, and `elev`;
- decimal degrees in EPSG:4326 with explicit longitude/latitude handling;
- elevation in metres with vertical reference `SYNTHETIC_LOCAL`;
- at least three recorded text-size/scale conditions;
- actual local OCR, retained raw OCR, fail-closed parsing and validation;
- deterministic source-coordinate CSV and XYZ demonstration output;
- local tests, metrics, retained evidence, and an unmerged draft pull request.

### S2XYZ-PS-006 - Non-goals

**Known limitation.** This run does not implement or establish:

- real-source capture, named-service presets, navigation, scraping, or backend extraction;
- cursor control, GUI workflow, unattended operation, or required live screen capture;
- CRS transformation, vertical-datum conversion, or authoritative geospatial validation;
- Kubla automation, import success, suitability, or compatibility;
- terrain modelling or earthwork calculation;
- survey-grade, construction-ready, production-ready, or universal compatibility;
- a repository licence, dependency redistribution approval, or public release.

### S2XYZ-PS-007 - Success

**Proposal.** The run is successful when all mandatory planning documents and traceability exist, G1-G4 are evidenced in order, actual OCR processes the exact 60-scenario fixture containing valid and intentionally invalid cases, required tests and metrics execute, raw failures and rejected readings are retained, deterministic artifacts reproduce, and an independent review finds no unresolved Blocker or Major issue.

Meeting the numerical OCR targets is reported separately. A valid experiment may complete with failed targets; it must not weaken or reinterpret the targets.

### S2XYZ-PS-008 - Failure

**Proposal.** The planning portion fails if a required document or decision is absent, a mandatory requirement is untraceable, or a Blocker/Major finding remains. The lab is blocked if actual OCR cannot run, if ground truth leaks into runtime values, if synthetic provenance cannot be demonstrated, or if evidence cannot be written safely. A completed experiment that misses a target is classified `Completed with failed targets`, not blocked and not fully successful.

### S2XYZ-PS-009 - Feasibility questions

**Open question.** The run will measure the selected local OCR approach, exact rendering conditions, OCR error modes, processing time, repeatability, and target attainment. The run-scoped coordinate precision, classification semantics, and schemas are defined in Product Requirements and the Data Dictionary. No owner decision is currently required because these are conservative and reversible within the authorized experiment.

## Alternatives considered at strategy level

| Alternative | Disposition | Reason |
|---|---|---|
| Manual transcription only | Retained as an external baseline concept; not measured in this run | It does not test the authorized OCR feasibility question. |
| Fixture values supplied directly to the parser | Rejected | It would not be actual OCR and would invalidate the experiment. |
| Real third-party screenshots | Rejected | Outside the synthetic-only authorization and introduces rights/privacy risk. |
| Cloud OCR or network service | Rejected for this run | Local processing minimizes data exposure and named-service dependency. |
| Local generated-image OCR | Selected strategy | It is source-agnostic, bounded, reproducible, and reversible. |

## Outcome measures

| Measure | Strategy target |
|---|---:|
| Parser unit tests | 100% pass |
| False accepts of expected-invalid scenarios | 0 |
| Complete exact match, baseline valid scenarios | at least 95% |
| Complete exact match, all valid scenarios | at least 90% |
| Expected-invalid rejection | at least 95% |
| Duplicate classification | 100% |
| Stale classification | 100% |
| Repeat classification and designated deterministic-output hashes | 100% identical |

Metric denominators and deterministic artifact scope are normative in Product Requirements and the Test Plan.

## Gate G1 readiness criteria

G1 is ready for a parent decision only when this document is complete, a read-only Product Strategy/Requirements reviewer has assessed it against the Charter and controlling prompt, every Blocker and Major strategy finding is resolved, and the decision cites exact evidence. The reviewer does not approve the gate.
