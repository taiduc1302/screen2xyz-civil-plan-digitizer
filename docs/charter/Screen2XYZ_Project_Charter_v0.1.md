# Screen2XYZ — Terrain Capture & Earthwork POC

## A. Project Charter v0.1

| Field | Value |
|---|---|
| Document | Project Charter |
| Project | Screen2XYZ — Terrain Capture & Earthwork POC |
| Version | v0.1 |
| Date | 2026-07-14 |
| Status | Draft for Review |
| Approval status | Not yet approved |
| Project owner | Project Owner (name withheld from repository records) |
| Current lifecycle stage | Project initiation and controlled planning |
| Intended classification | Source-of-truth document after explicit approval |
| Product classification | Source-agnostic proof of concept |
| Output classification | Conceptual and preliminary estimating data only |

### Charter purpose

This charter establishes the initial purpose, boundaries, workstreams, decision gates, risks, assumptions, governance documents, and next actions for the Screen2XYZ project. It authorizes planning only. It does not authorize application coding or public claims of technical performance.

### Controlled statement types

The project will use the following labels in planning, run reviews, and public documentation:

- **Verified fact:** supported by authoritative documentation or saved evidence.
- **Observed test result:** measured in a recorded test with identified inputs, method, and results.
- **Assumption:** treated as provisionally true for planning but not yet verified.
- **Proposal:** a recommended design or process that has not yet been approved or implemented.
- **Open question:** an unresolved item requiring a decision or evidence.
- **Known limitation:** a confirmed restriction or boundary of the current approach.

### Charter authority and change control

- This v0.1 document is a draft until the project owner explicitly approves it.
- After approval, changes must be versioned and recorded in the Decision Log.
- If this charter conflicts with a later document, the approved source-of-truth hierarchy governs.
- Older approved versions will be retained and marked `Superseded`; they will not be silently overwritten.
- Major scope, legal-boundary, accuracy, output-classification, or public-claim changes require a decision record.

## B. Project Objective

Design, implement, validate, document, and publicly present a source-agnostic proof-of-concept desktop application that can:

1. let a user define a permitted on-screen reading area and sampling configuration;
2. capture visible latitude, longitude, and elevation text from that area;
3. recognize, parse, validate, and normalize the readings;
4. reject or flag malformed, missing, duplicated, or implausible readings;
5. export traceable CSV or XYZ point data;
6. optionally transform coordinates into a user-selected coordinate reference system; and
7. prepare a controlled dataset for preliminary terrain modelling and earthwork assessment in Kubla.

Success means demonstrating a repeatable, evidence-backed workflow within defined test conditions. Success does not mean proving universal accuracy, obtaining rights to third-party data, or replacing authoritative survey, licensed LiDAR, engineering judgment, or professional quantity verification.

## C. Problem Statement

Preliminary terrain studies may require transferring many visible point readings into structured data. Manual transcription is slow, repetitive, and vulnerable to typing, unit, coordinate-order, and duplication errors. Existing automation can also be unsafe or unreliable when it is tied to one service, assumes fixed screen layouts, ignores data rights, or produces untraceable outputs.

The project will investigate whether a configurable screen-capture and OCR workflow can reduce manual transcription effort while preserving user control, traceability, measurable quality checks, and strict data-use boundaries. The POC must make its uncertainty visible and must support rejection and review instead of silently converting unreliable readings into terrain data.

## D. Intended Users

### Primary users

- Construction estimators preparing conceptual or preliminary earthwork studies.
- Preconstruction staff evaluating early terrain information.
- Civil-construction technology and automation practitioners testing workflow feasibility.
- Technical users who understand coordinate systems, units, and the limitations of non-survey data.

### Secondary users

- QA reviewers assessing recognition, parsing, transformation, and export evidence.
- Developers reproducing the POC with synthetic or properly licensed data.
- Managers reviewing whether the workflow merits controlled further development.

### User responsibility

Users are responsible for confirming that their source, data, screen capture, processing, storage, and downstream use are permitted. The application does not grant data rights or certify professional suitability.

## E. Primary Use Case

A user opens an authorized source that visibly displays latitude, longitude, and elevation values. The user configures a screen region, reading layout, coordinate format, units, sampling grid, timing, output schema, and validation limits. The application guides or performs controlled sampling, captures only the configured on-screen area, recognizes the visible values, and produces a reviewable table of accepted and rejected readings.

After review, the user exports CSV or XYZ data, optionally converts the coordinates into an appropriate projected CRS, and prepares the points for a controlled Kubla import. The resulting terrain and earthwork outputs are used only for conceptual and preliminary estimating unless independently validated against authoritative survey, LiDAR, or another accepted source.

### Minimum traceability expected from the use case

Each run should eventually record, subject to privacy and data-use decisions:

- run ID and date/time;
- application version;
- configuration version or hash;
- coordinate format and source CRS;
- elevation unit and vertical-datum status;
- sampling plan;
- accepted and rejected reading counts;
- validation and transformation settings;
- output file identity;
- test or user notes; and
- applicable limitations.

## F. Out-of-Scope Items

The following are out of scope for the public POC unless a later approved charter change states otherwise:

- Automatically opening, navigating, or logging in to a named third-party mapping service.
- A named-service preset or hardcoded interface coordinates for a named service.
- Circumventing CAPTCHA, access controls, authentication, rate limits, account restrictions, robots controls, or technical protections.
- Concealing automation or attempting to make automation appear human.
- Extracting non-visible backend, network, API, DOM, application-memory, or database data.
- Redistributing captured third-party datasets without confirmed rights.
- Providing legal advice or certifying that a source's terms permit capture or reuse.
- Survey-grade positioning, legal survey work, or certification of horizontal or vertical accuracy.
- Final design, construction layout, machine control, payment quantities, final tender quantities, drainage design, or regulatory submissions.
- Automatic engineering approval of coordinate systems, vertical datums, surfaces, boundaries, or earthwork results.
- Replacing estimator review, survey review, or engineering judgment.
- Guaranteed compatibility with every screen layout, language, font, DPI setting, coordinate format, or Kubla version.
- Production-scale unattended scraping, cloud crawling, or multi-user service operation.
- Publishing real third-party captured data as repository sample data without an approved licence record.

## G. Technical Workstreams

| ID | Workstream | Planned responsibility | Initial output |
|---|---|---|---|
| TW-01 | Configuration and user controls | Define source-agnostic capture regions, text-field zones, sampling patterns, timing, units, formats, CRS, validation settings, and stop controls. | Configuration specification |
| TW-02 | Screen capture | Capture only user-selected visible screen regions with predictable DPI and scaling behaviour. | Capture interface design |
| TW-03 | Sampling orchestration | Define cursor movement or user-guided sampling, stable-reading detection, retries, pause, resume, and emergency stop. | Sampling state model |
| TW-04 | OCR and field recognition | Recognize visible latitude, longitude, elevation, signs, decimal separators, degree symbols, and units without relying on a named platform. | OCR evaluation plan |
| TW-05 | Parsing and normalization | Convert supported coordinate and elevation text into an internal canonical schema while retaining raw text. | Parsing specification |
| TW-06 | Validation and quality control | Detect malformed values, range violations, stale/stationary readings, missing fields, duplicates, outliers, and unsupported ambiguity. | Validation rules catalogue |
| TW-07 | Coordinate transformation | Transform accepted horizontal coordinates using a declared source and target CRS; preserve transformation metadata. | CRS specification |
| TW-08 | Vertical reference handling | Record elevation units and known vertical datum; block or warn when datum status is unknown or incompatible. | Vertical-reference policy |
| TW-09 | Data model and export | Define raw, accepted, and rejected records; export stable CSV/XYZ schemas with traceability. | Data dictionary and export schema |
| TW-10 | Kubla preparation | Determine point-file requirements, CRS/units expectations, import steps, and review checkpoints. | Kubla workflow specification |
| TW-11 | Run logging and reproducibility | Record configuration, versions, counts, errors, timings, and evidence sufficient to reproduce tests. | Run ledger schema |
| TW-12 | Packaging and release | Define installation, dependencies, licence, security limits, sample data, and reproducible release process. | Release specification |

## H. Testing Workstreams

No testing has been executed at v0.1. The following workstreams are proposed.

| ID | Test workstream | Minimum coverage | Proposed evidence |
|---|---|---|---|
| QW-01 | Synthetic test interface | Known coordinate/elevation values, configurable layouts, fonts, delays, errors, and stationary states. | Versioned test fixture and ground-truth file |
| QW-02 | OCR accuracy | Fonts, font sizes, contrast, screen scaling, DPI, anti-aliasing, decimal separators, symbols, and units. | Character/field recognition results |
| QW-03 | Coordinate parsing | Decimal degrees and any other approved formats; signs; hemispheres; coordinate order; boundary values. | Unit and integration test results |
| QW-04 | Elevation parsing | Positive/negative values, decimals, units, missing units, and malformed text. | Unit and integration test results |
| QW-05 | Sampling-grid behaviour | Grid origin, spacing, ordering, screen bounds, cursor accuracy, settling, pause/resume, and stop behaviour. | Screen-coordinate comparison log |
| QW-06 | Data quality controls | Duplicates, missing readings, stale readings, malformed readings, outliers, retries, and rejection reasons. | Accepted/rejected ground-truth comparison |
| QW-07 | Coordinate transformation | Known control points, axis order, source/target CRS, units, transformation metadata, and error tolerances. | Comparison with an authoritative transformation reference |
| QW-08 | Export integrity | Required columns, data types, precision, ordering, delimiter, encoding, null handling, and deterministic output. | Schema validation and file hashes |
| QW-09 | Kubla compatibility | Import success, unit/CRS interpretation, point placement, surface creation, and repeatable workflow. | Kubla import record and screenshots |
| QW-10 | Accuracy assessment | Recognition rate, rejection rate, coordinate error, elevation error, duplicate rate, missing-point rate, processing time, and repeatability. | Versioned test report |
| QW-11 | Failure recovery | OCR failure, screen change, obstructed field, invalid config, interrupted run, write failure, and safe restart. | Failure-injection results |
| QW-12 | Regression testing | Previously passed fixtures and workflows after every material change. | Automated regression report |
| QW-13 | Authoritative comparison | Comparison of selected outputs against licensed survey, LiDAR, or other authoritative data where permitted. | Validation report with provenance and limitations |

### Measurement principles

- Test datasets will have saved ground truth wherever practical.
- A test result is not accepted without identified inputs, configuration, application version, expected result, actual result, and evidence.
- Accuracy thresholds will be defined in Product Requirements before implementation is authorized.
- Failed and rejected readings will be reported, not discarded from the evidence.
- A Kubla import alone will not prove coordinate or elevation accuracy.

## I. Legal and Data-Use Workstream

### Objective

Establish enforceable project guardrails that keep the software source-agnostic and separate the application's capability from the user's rights to capture or use data.

### Required activities

1. Create a Data and Legal Guardrails document.
2. Define a source-permission checklist covering terms, licence, copyright, database rights, privacy, confidentiality, redistribution, automation, and commercial use.
3. Approve public demonstration sources before use.
4. Maintain a dataset and licence register for every test or published dataset.
5. Define prohibited features and review the public repository for violations before release.
6. Define retention and redaction rules for screenshots, logs, coordinates, and source identifiers.
7. Prepare user-facing notices that the software does not grant data rights.
8. Obtain qualified legal review if a planned use remains uncertain or commercially material.

### Approved direction for public demonstrations

Public demonstrations should use one or more of the following, with saved provenance and licence evidence:

- synthetic data generated specifically for the project;
- a locally hosted synthetic test interface;
- government open data whose licence permits the intended use; or
- another dataset with confirmed rights for capture, transformation, publication, and redistribution.

### Legal boundary

This project process can document licences and technical controls, but it cannot provide a legal determination. Unclear permissions must remain unresolved until appropriate evidence or advice is obtained.

## J. Documentation and Public-Release Workstream

### Internal controlled documentation

- Project Charter, Product Strategy, Product Requirements, Architecture Specification, Data and Legal Guardrails, Test Plan, Test Matrix, Data Dictionary, Decision Log, Risk Register, Run Ledger, and Codex handoff reports.
- Every material claim will link to saved evidence or be labelled as an assumption, proposal, open question, or limitation.
- Codex implementation claims will be checked against changed files and test evidence.

### GitHub release documentation

The public repository is expected to include, after release approval:

- factual README and scope statement;
- installation and configuration instructions;
- architecture overview;
- synthetic or properly licensed sample data;
- test method and summarized evidence;
- CSV/XYZ schema and examples;
- Kubla workflow with limitations;
- security, privacy, legal, and data-use notices;
- licence and third-party dependency notices;
- changelog and release tags; and
- clear statement: `Conceptual and preliminary estimating data only.`

### LinkedIn article and portfolio case study

Public content will describe the problem, design decisions, controlled test method, measured results, limitations, and lessons learned. It will not identify a prohibited source workflow, imply universal accuracy, advertise rights to third-party data, or claim that the POC replaces survey or professional verification.

### Public-release evidence rule

No public performance, speed, cost, accuracy, or Kubla-workflow claim may be published unless it is supported by saved evidence and reviewed against the approved public-claims register.

## K. Proposed Development Phases

| Phase | Target version | Purpose | Required outputs | Coding status |
|---|---|---|---|---|
| P0 — Initiation | v0.1 | Establish charter, governance, boundaries, and project structure. | Approved Charter, initial registers, Master Index | Not permitted |
| P1 — Strategy and intended use | v0.1 | Define user value, use cases, non-goals, success measures, and feasibility questions. | Product Strategy | Not permitted |
| P2 — Guardrails and requirements | v0.1 | Approve legal/data-use boundaries, functional/non-functional requirements, acceptance criteria, and output classification. | Guardrails, Product Requirements, Data Dictionary draft | Not permitted |
| P3 — Architecture and test design | v0.2 | Select architecture, interfaces, dependencies, synthetic test design, test matrix, and evidence method. | Validated Architecture, Test Plan, Test Matrix, threat/privacy review | Not permitted until gate approval |
| P4 — First functional prototype | v0.3 | Implement the smallest controlled vertical slice against synthetic fixtures. | Prototype, source, automated tests, run report | Permitted only after G4 |
| P5 — Tested prototype | v0.4 | Expand formats and environments, fix defects, measure quality, and run regression tests. | Validated test report, limitations, updated risk register | Permitted |
| P6 — Kubla workflow demonstration | v0.5 | Validate controlled export, coordinate preparation, Kubla import, and preliminary terrain workflow. | Kubla workflow evidence and validation report | Permitted |
| P7 — Release candidate | v0.9 | Sanitize, document, package, licence, and audit the public repository and claims. | Release candidate, public-claims register, release audit | Permitted |
| P8 — Public POC | v1.0 | Publish only after technical, data-use, documentation, and reputational gates pass. | Public repository, release notes, factual article/case study | Permitted |

## L. Decision Gates Between Phases

| Gate | Decision | Minimum pass criteria | If not passed |
|---|---|---|---|
| G0 — Charter approval | Start controlled project planning. | Scope, output classification, governance, and owner approval recorded. | Revise Charter; do not progress. |
| G1 — Strategy approval | Accept the target problem and intended use. | Primary use case, users, value, non-goals, success measures, and feasibility questions approved. | Refine or stop the concept. |
| G2 — Boundary approval | Accept legal/data-use operating limits. | Prohibited behaviours, source-permission process, public-demo source classes, privacy rules, and escalation path approved. | Do not collect real-source data or design source-specific automation. |
| G3 — Requirements baseline | Freeze requirements for architecture. | Functional and non-functional requirements, schemas, errors, review workflow, measurable acceptance criteria, and traceability approved. | Revise requirements; no architecture sign-off. |
| G4 — Implementation authorization | Permit first application code. | Approved Architecture v0.2, Test Plan, Test Matrix, synthetic ground truth, dependency review, failure states, and reversible Codex prompt are complete. | No application coding. |
| G5 — Prototype acceptance | Advance from v0.3 to systematic testing. | Vertical slice works under defined synthetic conditions; changed files and test evidence audited; limitations recorded. | Patch, redesign, or stop. |
| G6 — Tested-prototype acceptance | Permit Kubla workflow validation. | Approved metrics meet defined thresholds; regressions addressed; rejected cases and limitations documented. | Continue testing or revise scope. |
| G7 — Kubla workflow acceptance | Begin release-candidate work. | Controlled import is repeatable; CRS/units/datum treatment documented; output remains preliminary; evidence saved. | Correct export/workflow or narrow claims. |
| G8 — Public-release approval | Publish v1.0 and public content. | Repository sanitization, licence register, security/privacy review, evidence-backed claims, documentation, and final owner approval complete. | Do not publish; resolve findings. |

## M. Major Technical Risks

| ID | Risk | Potential impact | Initial control | Status |
|---|---|---|---|---|
| TR-01 | OCR misreads signs, decimals, digits, or symbols. | Incorrect coordinates or elevations. | Preserve raw text; confidence/rejection rules; synthetic ground truth; manual review. | Open |
| TR-02 | Screen DPI, scaling, zoom, or window movement changes field locations. | Capture of wrong regions or missed readings. | Configurable regions; calibration checks; layout-change detection; DPI test matrix. | Open |
| TR-03 | The displayed reading updates slowly or remains stale while sampling continues. | Repeated or spatially mismatched points. | Stability state, timing controls, stale-reading detection, retries, duplicate checks. | Open |
| TR-04 | Cursor position and displayed terrain position are not equivalent. | Horizontal point error. | Calibrated synthetic interface; cursor evidence; authoritative comparison; explicit accuracy limits. | Open |
| TR-05 | Coordinate order, format, hemisphere, or CRS is interpreted incorrectly. | Large spatial displacement. | Explicit format/CRS configuration; range rules; control-point tests; block ambiguous inputs. | Open |
| TR-06 | Elevation unit or vertical datum is unknown or mixed. | Invalid surface and volume results. | Mandatory metadata; warnings/blocks; no silent datum conversion. | Open |
| TR-07 | Duplicate, missing, or irregularly spaced points distort terrain interpolation. | Misleading surface and earthwork quantities. | Coverage metrics; duplicate/rejection reporting; visual review; sampling QA. | Open |
| TR-08 | Coordinate transformation introduces axis-order, unit, grid, or library errors. | Mislocated output. | Established CRS library; pinned versions; known control points; metadata export. | Open |
| TR-09 | CSV/XYZ formatting or precision is incompatible with Kubla. | Import failure or altered point values. | Version-specific import test; schema validation; round-trip comparisons. | Open |
| TR-10 | Kubla surface settings produce materially different earthwork results. | False confidence in quantities. | Record settings/boundaries; sensitivity tests; comparison to a controlled reference. | Open |
| TR-11 | OCR or UI dependencies are unstable, unavailable, or difficult to package. | Non-repeatable builds or installation failure. | Dependency evaluation, version pinning, fallback analysis, clean-environment test. | Open |
| TR-12 | Logs or screenshots expose sensitive or restricted source content. | Privacy, confidentiality, or data-use breach. | Data minimization, redaction, retention rules, test fixtures, release sanitization. | Open |
| TR-13 | Error handling permits partial or corrupted output to appear valid. | Unsafe downstream use. | Atomic writes, run status, schema validation, failure injection, visible warnings. | Open |
| TR-14 | Results vary materially between identical runs. | Poor repeatability and low trust. | Deterministic settings where possible; repeated-run metrics; environment capture. | Open |
| TR-15 | A source layout change breaks the configured workflow. | Failed or incorrect capture. | Source-agnostic configuration, calibration, preview, validation, fail-closed behaviour. | Open |

## N. Major Professional and Reputational Risks

| ID | Risk | Potential consequence | Initial control | Status |
|---|---|---|---|---|
| PR-01 | Public material is interpreted as a third-party service scraper. | Terms, legal, employer, or platform concerns. | No named-service workflow/preset; source-agnostic language; sanitized demonstrations. | Open |
| PR-02 | Project appears to conceal the origin or rights of captured data. | Loss of trust and possible rights dispute. | Dataset/licence register; separate software capability from data rights; publish only approved samples. | Open |
| PR-03 | Preliminary results are presented as survey-grade or construction-ready. | Unsafe reliance and professional credibility damage. | Mandatory output classification and limitations in UI, files, README, and article. | Open |
| PR-04 | Speed, cost, or accuracy claims exceed the evidence. | Misleading portfolio claims. | Public-claims register; evidence links; review before publication. | Open |
| PR-05 | A demonstration exposes employer, client, project, or personal information. | Confidentiality breach. | Synthetic/publicly licensed inputs; redaction; release audit. | Open |
| PR-06 | Repository code enables prohibited bypass or hidden automation. | Misuse and reputational damage. | Architecture boundary, code review, security review, prohibited-feature checklist. | Open |
| PR-07 | Earthwork outputs are used for tender, payment, or operational decisions without verification. | Financial or construction harm. | Explicit prohibited uses; user acknowledgement; export metadata; verification workflow. | Open |
| PR-08 | The project implies legal approval of data capture or reuse. | False assurance and liability exposure. | Clear user-responsibility statement; qualified legal review when needed. | Open |
| PR-09 | A LinkedIn or portfolio description omits failed tests or major limitations. | Misrepresentation of competence or product maturity. | Publish measured results with limitations and negative findings. | Open |
| PR-10 | AI-generated implementation reports are accepted without inspection. | False completion claims and hidden defects. | Mandatory transcript, diff, test, and evidence audit after every Codex run. | Open |

## O. Initial Assumptions

Every item below is explicitly an assumption and requires confirmation, testing, or a decision.

| ID | Explicit assumption | Required verification |
|---|---|---|
| AS-001 | **Assumption:** The first POC will target a Windows desktop environment. | Confirm target OS and supported versions in Product Requirements. |
| AS-002 | **Assumption:** The authorized source visibly displays latitude, longitude, and elevation as readable text. | Define supported display patterns and test fixtures. |
| AS-003 | **Assumption:** A user can identify and configure fixed screen regions for the required fields. | Validate configuration approach against synthetic layouts. |
| AS-004 | **Assumption:** The displayed values correspond predictably to a cursor position or another user-defined sample location. | Measure this relationship in the controlled test environment. |
| AS-005 | **Assumption:** A sampling delay and stability rule can distinguish updated readings from stale readings. | Run latency and stationary-reading tests. |
| AS-006 | **Assumption:** Initial coordinate input will include decimal degrees; any additional formats will require explicit approval. | Confirm formats and acceptance criteria. |
| AS-007 | **Assumption:** Elevation units will be explicitly known or the reading will be rejected/flagged. | Define metadata and fail-closed rules. |
| AS-008 | **Assumption:** The user will know or supply the source horizontal CRS. | Define how CRS is selected and validated. |
| AS-009 | **Assumption:** Vertical-datum conversion will not be performed unless authoritative datum information and an approved method are available. | Approve vertical-reference policy. |
| AS-010 | **Assumption:** A local synthetic test interface can reproduce the essential reading behaviour without using a named external service. | Specify and approve the synthetic fixture. |
| AS-011 | **Assumption:** An established coordinate-transformation library can satisfy the required transformations within defined tolerances. | Evaluate dependencies and control-point results. |
| AS-012 | **Assumption:** Kubla can accept a point-based CSV or XYZ workflow suitable for the POC. | Confirm the exact Kubla version, schema, CRS, units, and import procedure. |
| AS-013 | **Assumption:** The initial datasets will be small enough for a desktop POC and manual QA review. | Define point-count and performance targets. |
| AS-014 | **Assumption:** The first public demonstration can use synthetic or appropriately licensed open data. | Select a dataset and save licence/provenance evidence. |
| AS-015 | **Assumption:** The project can use open-source or otherwise permissible dependencies within the intended public licence. | Complete dependency and licence review. |
| AS-016 | **Assumption:** The project owner will manually approve every phase gate and public release. | Establish approval fields in the Decision Log. |
| AS-017 | **Assumption:** OCR confidence alone will not be treated as proof of field correctness. | Define multi-rule validation and manual review requirements. |
| AS-018 | **Assumption:** The application will operate in a visible, user-controlled session with pause and stop controls. | Confirm interaction and safety requirements. |
| AS-019 | **Assumption:** The POC will optimize for traceability and correctness before throughput. | Approve product priorities and performance criteria. |
| AS-020 | **Assumption:** Project documentation and public technical artifacts will be maintained in English, while project-owner planning and review may be conducted in Russian. | Confirm documentation-language policy. |

## P. Open Questions

| ID | Open question | Why it matters | Target decision stage |
|---|---|---|---|
| OQ-001 | Which Windows versions, display configurations, and monitor arrangements must the POC support? | Defines capture APIs and the DPI test matrix. | P1–P2 |
| OQ-002 | Should sampling be automated cursor movement, user-guided point capture, or both? | Materially changes usability, risk, and architecture. | P1 |
| OQ-003 | What exact on-screen field layouts and update behaviours are in scope? | Defines configuration and OCR design. | P1–P2 |
| OQ-004 | Which coordinate formats must be supported in v0.3 and v1.0? | Defines parser and test scope. | P2 |
| OQ-005 | What are the required source and target CRS choices? | Affects transformation and Kubla placement. | P2 |
| OQ-006 | How will unknown or mixed vertical datums be handled? | Directly affects terrain and earthwork validity. | P2 |
| OQ-007 | What exact CSV and XYZ schemas will be authoritative? | Required for deterministic export and audit. | P2 |
| OQ-008 | Which Kubla product/version and import workflow will be used? | Compatibility may vary by version and settings. | P1–P2 |
| OQ-009 | What does `Kubla-compatible` mean: successful import only, correct surface placement, or repeatable earthwork comparison? | Prevents a weak or ambiguous acceptance claim. | P1 |
| OQ-010 | What measurable thresholds define acceptable OCR, parsing, elevation, coordinate, duplicate, missing-point, repeatability, and performance results? | Required before coding and testing. | P2 |
| OQ-011 | What authoritative survey, LiDAR, or control dataset can be used for later comparison? | Needed to quantify real-world error. | P1–P3 |
| OQ-012 | What maximum point count, grid density, and run duration are required? | Defines performance and review feasibility. | P2 |
| OQ-013 | What manual confirmation is required before export and Kubla use? | Controls unsafe output. | P2 |
| OQ-014 | Should screenshots be saved, redacted, hashed only, or not retained? | Affects traceability, privacy, and data-use risk. | P2 |
| OQ-015 | What local-data retention and deletion policy is required? | Affects privacy and reproducibility. | P2 |
| OQ-016 | Which open-source licence is intended for the public repository? | Constrains dependencies and reuse. | P2–P3 |
| OQ-017 | Which public demonstration dataset and licence will be used? | Required for safe publication. | P1–P3 |
| OQ-018 | Is a graphical interface required for v0.3, or can the first vertical slice use a simpler controlled interface? | Changes implementation scope. | P1 |
| OQ-019 | What failure states must stop the run versus warn and continue? | Defines fail-safe behaviour. | P2 |
| OQ-020 | Who will independently review technical evidence and public claims, if anyone besides the project owner? | Improves release credibility and governance. | P1 |

## Q. Proposed Project Source-of-Truth Documents

The hierarchy below follows the mandatory project order. Each document becomes authoritative only after explicit approval.

| Priority | Proposed filename | Purpose | Initial version/status |
|---:|---|---|---|
| 1 | `Screen2XYZ_Project_Charter_v0.1.md` | Purpose, scope, governance, phases, gates, risks, assumptions, and status. | v0.1 Draft for Review |
| 2 | `Screen2XYZ_Product_Requirements_v0.1.md` | Functional/non-functional requirements, user workflow, acceptance criteria, and traceability. | Not created |
| 3 | `Screen2XYZ_Architecture_Specification_v0.1.md` | Components, interfaces, state model, data flow, dependencies, failure handling, security, and deployment. | Not created |
| 4 | `Screen2XYZ_Data_and_Legal_Guardrails_v0.1.md` | Data rights, permitted/prohibited behaviour, privacy, licences, demonstrations, and repository restrictions. | Not created |
| 5A | `Screen2XYZ_Test_Plan_v0.1.md` | Test strategy, environments, evidence, metrics, thresholds, and regression process. | Not created |
| 5B | `Screen2XYZ_Test_Matrix_v0.1.xlsx` | Test cases, fixtures, expected values, results, evidence, and status. | Not created |
| 6 | `Screen2XYZ_Decision_Log_v0.1.md` | Approved decisions, alternatives, rationale, owner, date, and affected versions. | Not created |
| 7 | `Screen2XYZ_Run_Ledger_v0.1.xlsx` | Codex run IDs, inputs, versions, changes, tests, results, failures, and next action. | Not created |
| 8 | `Screen2XYZ_Latest_Approved_Codex_Handoff.md` | Pointer to the latest approved run audit and controlled project state. | Not created |

### Supporting controlled documents

| Proposed filename | Purpose | Initial status |
|---|---|---|
| `Screen2XYZ_Product_Strategy_v0.1.md` | Value proposition, users, use cases, alternatives, success measures, and feasibility. | Not created |
| `Screen2XYZ_Data_Dictionary_v0.1.md` | Canonical record model, field definitions, types, units, nulls, provenance, and rejection codes. | Not created |
| `Screen2XYZ_Risk_Register_v0.1.xlsx` | Technical, legal, security, professional, schedule, and release risks. | Not created |
| `Screen2XYZ_Public_Claims_Register_v0.1.xlsx` | Proposed public claims, evidence, caveats, approval, and publication location. | Not created |
| `Screen2XYZ_Dataset_and_Licence_Register_v0.1.xlsx` | Dataset origin, owner, licence, allowed uses, restrictions, and evidence. | Not created |
| `Screen2XYZ_Requirements_Traceability_Matrix_v0.1.xlsx` | Requirements mapped to architecture, tests, evidence, and releases. | Not created |
| `Screen2XYZ_Master_Index_v0.1.md` | Current controlled versions, status, owners, and superseded documents. | Not created |
| `Screen2XYZ_Kubla_Workflow_v0.1.md` | Version-specific import, settings, validation, limitations, and evidence. | Not created |
| `Screen2XYZ_Change_Log.md` | Version history and release changes. | Not created |
| `Screen2XYZ_Run_<NNN>_Report_<YYYY-MM-DD>.md` | Audited evidence for each Codex implementation run. | Created only after a run |

## R. Recommended Chat Structure

Each chat should have one controlled purpose. Approved outputs should be copied into the Master Control chat or referenced through a dated handoff summary; chat history alone is not a source of truth.

| Chat | Purpose | Main controlled outputs |
|---|---|---|
| 00 — Master Control & Source of Truth | Maintain current stage, approvals, Master Index, conflicts, action register, and handoffs. | Charter, Master Index, Decision Log, current-status summaries |
| 01 — Product Strategy & Requirements | Define users, use cases, value, alternatives, requirements, non-functional requirements, success metrics, and acceptance criteria. | Product Strategy, Product Requirements |
| 02 — Legal, Data Use & Public Boundaries | Review data rights, source permission, privacy, prohibited behaviour, dataset licences, and public-demo limits. | Data and Legal Guardrails, Dataset and Licence Register |
| 03 — Systems Architecture | Design source-agnostic components, data flow, state machine, interfaces, dependencies, error handling, and security. | Architecture Specification, architecture decisions |
| 04 — Synthetic Test Lab & QA | Define ground truth, fixtures, test plan, test matrix, metrics, thresholds, regression, and authoritative comparison. | Test Plan, Test Matrix, QA reports |
| 05 — Codex Prompt Development | Build narrow, measurable, reversible implementation prompts after G4. | Approved Codex prompts |
| 06 — Codex Run Audit & Patch Planning | Inspect transcripts, diffs, changed files, tests, evidence, failures, regressions, and next patches. | Run reports, Run Ledger, handoff pointer, patch prompts |
| 07 — CRS, CSV/XYZ & Kubla Workflow | Validate schemas, transformations, units, datum handling, import, surface settings, and preliminary results. | Data Dictionary, Kubla Workflow, compatibility evidence |
| 08 — GitHub Release & Documentation | Prepare sanitized repository structure, README, licences, installation, examples, limitations, and release audit. | Release candidate documentation |
| 09 — LinkedIn & Portfolio Case Study | Prepare factual, evidence-backed public content after technical validation. | Article, post, case study, Public Claims Register |

### Chat handoff rule

Every handoff should state:

- date and project version;
- current approved source-of-truth files;
- objective completed or attempted;
- decisions made and their IDs;
- files created or changed;
- evidence produced;
- unresolved questions and risks;
- prohibited assumptions;
- exact next action; and
- whether approval is required.

## S. Initial Action Register

| ID | Action | Owner | Priority | Dependency | Expected output | Status |
|---|---|---|---|---|---|---|
| ACT-001 | Review and explicitly approve, revise, or reject Project Charter v0.1. | Project owner | Critical | None | G0 decision record | Pending |
| ACT-002 | Create the Project Master Index and register the approved Charter version. | Project controller | High | ACT-001 | `Screen2XYZ_Master_Index_v0.1.md` | Pending |
| ACT-003 | Complete Product Strategy: user, problem, alternatives, value, intended use, non-goals, and success measures. | Product Strategy chat + project owner | Critical | ACT-001 | `Screen2XYZ_Product_Strategy_v0.1.md` | Pending |
| ACT-004 | Resolve high-impact product open questions OQ-002, OQ-008, OQ-009, OQ-010, OQ-011, and OQ-018. | Project owner | Critical | ACT-003 | Recorded decisions | Pending |
| ACT-005 | Draft Data and Legal Guardrails before any real-source test data is collected. | Legal/Data Use chat | Critical | ACT-001 | `Screen2XYZ_Data_and_Legal_Guardrails_v0.1.md` | Pending |
| ACT-006 | Select a synthetic public-demo concept and identify candidate properly licensed open data. | Product + Legal/Data Use chats | High | ACT-003, ACT-005 | Dataset candidates and licence evidence | Pending |
| ACT-007 | Draft measurable Product Requirements and acceptance criteria. | Product Strategy & Requirements chat | Critical | ACT-003, ACT-005 | `Screen2XYZ_Product_Requirements_v0.1.md` | Pending |
| ACT-008 | Define the canonical internal record, rejection codes, CSV schema, and XYZ schema. | Requirements + Architecture chats | High | ACT-007 | `Screen2XYZ_Data_Dictionary_v0.1.md` | Pending |
| ACT-009 | Confirm Kubla version, required import schema, coordinate/units workflow, and acceptance definition. | Kubla Workflow chat + project owner | High | ACT-003 | Kubla requirements note | Pending |
| ACT-010 | Design source-agnostic architecture only after requirements baseline. | Systems Architecture chat | Critical | G3 | `Screen2XYZ_Architecture_Specification_v0.1.md` | Blocked by G3 |
| ACT-011 | Create synthetic ground-truth specification, Test Plan, Test Matrix, and thresholds. | Synthetic Test Lab & QA chat | Critical | ACT-007, ACT-010 draft | Test artifacts | Blocked |
| ACT-012 | Prepare the first Codex implementation prompt with copy-on-write and audit requirements. | Codex Prompt Development chat | High | G4 prerequisites | Approved implementation prompt | Blocked by G4 |
| ACT-013 | Establish Decision Log, Risk Register, Run Ledger, Requirements Traceability Matrix, and Public Claims Register. | Project controller | High | ACT-001 | Controlled templates | Pending |
| ACT-014 | Define the independent review approach for evidence and public claims. | Project owner | Medium | ACT-003 | Review decision | Pending |

## T. Current Project Status Summary

**Date:** 2026-07-14  
**Provisional stage:** P0 — Initiation  
**Provisional version:** v0.1 planning baseline  
**Gate status:** G0 not yet passed  
**Overall status:** Draft planning package awaiting project-owner review

### Verified project-control facts

- The project concept and mandatory operating rules have been defined by the project owner.
- This Project Charter v0.1 has been prepared as a draft for review.
- Application coding is not authorized at the current gate.

### Technical implementation status

- No application capability is claimed as implemented.
- No OCR, sampling, parsing, export, coordinate transformation, or Kubla workflow is claimed as tested.
- No performance, accuracy, cost, time-saving, or compatibility result is available.
- No synthetic test fixture, authoritative comparison dataset, or accepted public demonstration dataset has been approved.

### Current limitations

- Intended workflows, requirements, formats, thresholds, target environment, Kubla version, and authoritative validation method remain unresolved.
- Data-use guardrails are described at charter level but have not yet been developed into an approved operational document.
- The source-of-truth package is incomplete until the documents in Section Q are created and approved in sequence.

### Immediate recommendation

Approve or revise this Charter first. Then move to the Product Strategy & Requirements chat to define intended value, use cases, alternatives, measurable success criteria, and the highest-impact open questions. Do not begin architecture selection or application coding until the required decision gates are passed.

---

## Approval Record

| Field | Value |
|---|---|
| Decision | Pending |
| Approved by | Pending |
| Approval date | Pending |
| Decision Log ID | Pending |
| Approved version | Pending |
| Notes | Pending |

