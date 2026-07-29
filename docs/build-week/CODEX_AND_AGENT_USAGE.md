# Codex and Agent Usage

An accurate record of how AI tools contributed, grounded in repository
history. Human ownership is constant: the project owner defined scope,
authorized every gate, and remains the only approver of merges, releases,
and exported data.

## Codex (OpenAI) — baseline construction

The v0.1–v0.2 baseline was built through gate-controlled Codex runs
(recorded as tasks `S2XYZ-CODEX-000` … `S2XYZ-CODEX-003` in
`docs/control/`, `runs/reports/`, and the Git history up to PR #2):
repository bootstrap and governance; the planning/requirements/guardrails/
architecture documentation set; the deterministic synthetic fixture and
renderer; the OCR laboratory pipeline (parser, validator, temporal
classifier, exporters, metrics, evidence sealing); the original 41-test
suite; and the sealed 42/42 // 18/18 evaluation evidence with two-run
byte-level repeatability. The orchestration model (read-only reviewer
subagents, evidence gates, owner decision records) is documented in
`AGENTS.md` and `docs/control/ORCHESTRATION_WORKFLOW.md`.

## Claude (Fable 5, Anthropic) — independent review and M1

Fable was used for the 2026-07-17 work: two independent audit passes that
re-verified every baseline claim from a clean state
(`AUDIT_AND_REMEDIATION_REPORT.md`), privacy sanitization and the
tracked-content scan test, release-readiness documentation, release
management of PR #2, and the M1 implementation (intake, review session,
Tkinter UI, controlled evaluation, 32-test suite) with its own adversarial
self-review.

## GPT-5.6 — planned assistance boundary only

No live GPT execution has occurred in this repository. M1 ships a
disabled-by-default provider seam (`screen2xyz_m1.assist`) under which a
GPT-backed reviewer note could be added; it can never approve, export, or
see image bytes. Any live integration is a separate, owner-authorized step.

## Why this matters for Build Week

The repository demonstrates a working pattern for *controlled* AI in
engineering workflows: AI builds and reviews under gates and evidence
seals, humans keep the approval authority, and every claim traces to
reproducible artifacts rather than to the agent that produced them.
