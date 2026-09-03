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

## Verifying a markup you wrote (blocking, applies to every agent)

After writing ANY markup to a host document, call
`create_markup_thumbnail(uniqueMarkupId=...)` on it and **look at the returned
image**. It renders that markup in place on the sheet, from the live document,
with the host's own computed quantity. One call, no coordinate arithmetic.

Numeric self-consistency is not placement. Area totals reconciling, zero mutual
overlap, a clean `polygon_health` and sum-equals-union prove a polygon is valid,
never that it is on the feature the drawing draws. On 2026-09-03 thirteen
markups passed every one of those checks while tracing curb-return arcs, leader
lines and gas lines, and were deleted. The project's ratio to that point was 105
write calls against 1 visual check, with the owner supplying the missing eyes by
pasting screenshots.

Two methods that share a flaw agreeing is not validation: a raster trace matched
another raster trace to 0.03 % and both were wrong the same way. An independent
check must come from a different kind of evidence - a printed dimension, the
drawing's own vector geometry, or the render.

Do not report a markup as done, verified, or read back until its thumbnail has
been looked at.

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
