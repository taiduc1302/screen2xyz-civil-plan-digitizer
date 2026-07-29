# Repository Working Rules

These rules apply to all future coding agents working in this repository.

- Preserve previous evidence and never delete or overwrite prior run evidence.
- Use copy-on-write development: create new artifacts or versions instead of modifying retained evidence in place.
- Work on task-specific branches and keep changes limited to the approved task scope.
- Follow approved requirements and architecture. If either is absent, incomplete, or unapproved, do not invent it.
- Do not invent test results, validation outcomes, evidence, or completed capabilities.
- Keep the application source-agnostic; do not make a particular data source a required operating assumption.
- Do not add service-specific scraping presets.
- Do not bypass CAPTCHA, rate limits, access controls, or other technical protections.
- Use only synthetic, locally generated, government open, or appropriately licensed public demonstration data.
- Do not add proprietary, copied, or unlicensed datasets or interface assets.
- Treat all results as conceptual and preliminary unless authoritative validation exists.
- Keep run transcripts, reports, and evidence traceable to their task and branch.
- Do not claim functionality has been implemented or tested without reproducible supporting evidence.

## Parent-agent orchestration

Future Codex runs must:

- Read `docs/control/PROJECT_STATE.md` and `docs/control/NEXT_ACTION.md` before beginning work.
- Use GitHub and repository files, rather than chat transcripts, as the current project state.
- Use read-only subagents for independent planning, audit, QA, and review.
- Wait for all subagents and consolidate their findings before acting on them.
- Keep the parent agent as the only file writer during a run.
- Avoid asking the user to manually copy information already present in the repository.
- Ask the project owner only for genuine product, legal, risk, or release decisions.
- Update `docs/control/PROJECT_STATE.md` and `docs/control/NEXT_ACTION.md` after every accepted run.
- Never move past a project gate without recorded authorization.
- Never invent completed work, tests, evidence, approvals, or results.
