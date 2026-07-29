# Screen2XYZ Risk Register v0.1

| Field | Value |
|---|---|
| Task | S2XYZ-CODEX-003 |
| Status | Executed baseline; active monitoring remains |
| Scale | Likelihood and impact: Low, Medium, High |
| Output classification | Conceptual and preliminary estimating data only. |

| ID | Risk | Type | Likelihood | Impact | Response and evidence | Owner | Residual status |
|---|---|---|---|---|---|---|---|
| RSK-001 | Actual OCR cannot run through the selected current-machine adapter | Technical | Medium | High | Pre-G4 generated-image diagnostic; fail blocked without silent fixture substitution | Parent agent | Mitigated for the frozen current-machine fixture: both 60-scenario runs completed; broader support remains unverified |
| RSK-002 | OCR misses signs, decimals, or labels at one or more scales | Quality | Medium | High | Three controlled conditions; raw OCR retention; exact-match metrics; no target weakening | Parent agent | Mitigated for the frozen fixture: 42/42 valid readings matched exactly; broader visual conditions remain untested |
| RSK-003 | Invalid reading is falsely accepted | Safety/quality | Low-Medium | High | Fail-closed grammar/ranges/metadata; false-accept target zero; negative tests | Parent agent | Mitigated for the frozen suite: 0/18 false accepts; monitoring remains |
| RSK-004 | Duplicate or stale semantics are ambiguous | Requirements | Low | High | Normative precedence and accepted-history rules; dedicated tests | Parent agent | Mitigated in the scoped lab: duplicate and stale results were each 6/6 and mapped tests passed |
| RSK-005 | Ground truth contaminates runtime output | Evidence integrity | Low-Medium | High | Structural separation; runtime schema excludes expected values; separation tests | Parent agent | Mitigated by structural separation and passing ground-truth-separation tests |
| RSK-006 | Synthetic provenance cannot be demonstrated | Data/compliance | Low | High | Fixed seed/config; dataset register; relative manifest and hashes | Parent agent | Mitigated by the registered fixed-seed fixture, relative hashes, and verified evidence manifest |
| RSK-007 | Environment evidence leaks identity, secrets, or paths | Privacy/security | Medium | High | Strict allowlist; sanitized transcripts; secret/path scan | Parent agent | Mitigated for retained evidence by allowlisted environment records and passing privacy checks; monitoring remains |
| RSK-008 | OS component/font licence is overstated or binary is redistributed | Licence | Low | Medium-High | Register as OS-provided/not redistributed; do not claim legal approval; no binaries in Git | Parent agent | Mitigated for this run: OS-provided components are inventoried, not redistributed, and no legal approval is claimed |
| RSK-009 | OS OCR behavior changes across builds or lacks supported unpackaged-host guarantees | Architecture | Medium | Medium-High | Current-machine-only ADR; record OS build; replaceable adapter; no production claim | Parent agent | Open; conditionally tolerable under the owner-authorized current-machine scope only after G4 evidence |
| RSK-010 | Partial output or failed write is treated as complete | Evidence integrity | Low-Medium | High | Atomic writes, nonzero failures, manifest last, write-failure injection | Parent agent | Mitigated by passing recovery tests and a verified manifest written last |
| RSK-011 | Generated-image test is described as live capture | Claims | Low | High | Explicit `Generated images`/`Not executed` fields and independent claim review | Parent agent | Mitigated in current artifacts by exact `Not executed` status and final review with zero Blocker or Major |
| RSK-012 | XYZ geographic degrees are assumed to be Kubla-compatible or projected | Downstream misuse | Medium | High | Sidecar/notes state X/Y/Z and limitations; no import claim; documentation-only note | Project owner | Open downstream risk |
| RSK-013 | Numerical targets are missed | Feasibility | Medium | Medium | Complete valid experiment; report failed targets without weakening them; propose next controlled task | Project owner | Closed for the retained fixture: every frozen target was met; future runs must reassess |
| RSK-014 | Runtime exceeds practical overnight bounds or hangs | Operations | Low-Medium | Medium | 30-second per-image and 30-minute run timeouts; checkpointing; nonzero timeout evidence | Parent agent | Mitigated for both retained runs; no OCR timeout or hang occurred |
| RSK-015 | Global packages leak into the selected environment | Reproducibility/supply chain | Medium | Medium | `.venv` without system-site packages; no application packages; inventory from venv only | Parent agent | Mitigated by an isolated zero-distribution `.venv` and retained final inventory |
| RSK-016 | Real, personal, employer, client, or service-specific data enters evidence | Data/privacy/legal | Low | High | Synthetic-only generator; no network/URL input; quarantine and escalation; pre-commit review | Project owner | Mitigated for this run by synthetic registration and passing privacy checks; monitoring remains |
| RSK-017 | Public or survey-grade claims exceed evidence | Professional/claims | Low | High | Exact classification notice; prohibited-claim scan; draft PR remains unmerged/private | Project owner | Mitigated in current artifacts and final review; release remains prohibited |
| RSK-018 | Prior retained evidence is deleted or overwritten | Governance | Low | High | Copy-on-write run paths; AGENTS rules; manifest; Git review | Parent agent | Mitigated by copy-on-write retained runs and a verified sealed manifest; monitoring remains |

## Escalation threshold

Any unresolved High-impact legal/data-rights/privacy/safety issue, any irreversible architecture or release decision, any actual contamination, or any need for a real source stops the run and requires project-owner direction. Ordinary reversible implementation findings remain within the conditional authorization.
