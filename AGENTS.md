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

A read-back only proves something if it returns by a **different path** than
the write. Same-API round trips are self-consistent by construction. A set of
markers was once written, read back and rendered entirely through one frame's
API, agreed at every step, and sat on the wrong half of the sheet. Verify
across paths: read geometry back with `get_markup_shape` and render from that,
or pin a position against something the write never touched. Use
`screen2xyz_civil.host_frame` rather than open-coding a coordinate flip.

## Where a boundary comes from (blocking)

**A boundary is a drawn line, never the extent of a fill pattern, and never
the thing that identified the item.**

A hatch pen draws two different things. The region's **outline** is emitted as
a polyline - one drawing object carrying several path items - while every hatch
stroke is its own single-item object. Colour and width cannot tell them apart;
the object structure can. Take the outline object for the boundary and use the
single strokes only to decide which side is which.

The corollary is the rule that cost the most: **never let the filter that finds
an item also define its edge.** An angle filter that kept 30-60/120-150 degrees
correctly identified the hatch and silently discarded the horizontal outline,
so the boundary could only ever be the hatch envelope. The filter that found
the item hid its line.

Two habits that follow:

* **An analysis box is not a feature boundary.** A markup stopped at the edge
  of an analysis window is short by however far the feature runs past it - 19
  sq m on one sheet 04 item alone. `fill_layers` now reports
  `REGION_TOUCHES_THE_ANALYSIS_EDGE`; widen and re-trace, or cut at a station
  chosen from the drawing.
* **Check every drawn line near the edge, not only the one you decided is the
  interface.** Where a drawn line exists, taking the ragged fill edge instead
  costs area and puts a diagonal where the drawing has a straight run.
* Arcs are arcs. A curb return traced as an axis-aligned staircase is wrong in
  shape even when the area is right.

`polygon_health` refuses an evenly oscillating outline
(`BOUNDARY_CHASES_A_PATTERN`); no other check sees it, because the sawtooth
stays under the sliver ratio and the area reconciles with itself.
`pattern_edge.flatten_to_envelope` only removes the sawtooth - it leaves the
boundary on a pattern extreme, not on the drawn line - so use it only where the
drawing genuinely draws no boundary.

## Name what identified the feature, and what fixed its edge (blocking)

Two failures had the same shape and neither was visible in any coordinate. An
angle filter kept 30-60/120-150 degrees, correctly found the hatch, and
silently discarded the region's **outline** drawn in the same pen - so the edge
could only ever be the hatch envelope. Five arcs were identified by a
least-squares radius of 10.00 m against a printed 10.0 at 0.01 pt rms, and one
was the storm line and two were gas: utilities are laid concentric with the
curb, so they share its centre and radius.

`feature_identity.identification_report` makes this a gate rather than a note.
Declare two things separately:

* `identified_by` - what told you this is the feature. A `LEGEND_SWATCH`, a
  `CALLOUT_LEADER` whose arrow ends on it, or a `DRAWING_TABLE` row.
* `boundary_from` - what told you where its edge runs. A `DRAWN_OUTLINE`
  object, a `PRINTED_STATION_OFFSET`, or a table row.

`PEN_ONLY` and `GEOMETRIC_FIT` narrow a field of candidates and never identify
anything on their own. A boundary from a pen is refused outright, and so is a
claim where one thing you **derived** is the sole basis for both identity and
edge - that is the specific mistake that hid the outline. A printed source
shared between the two is fine: a table's row label and its length column are
two independently checkable facts, not one derivation used twice.

Before walking any line between two known ends, confirm what lies between them.
A walk that reaches the far endpoint is still wrong if it crossed something
that is not the feature, and it must report failure rather than a partial
length if it does not arrive. `fill_layers` regions declare
`PEN_ONLY`/`PEN_ONLY` about themselves and therefore arrive refused; attach the
legend swatch or callout, take the edge from the drawing's outline object, and
re-declare.

**And before building a tool, check that the thing you are about to measure is
the thing the drawing means.** The four printed curb points on DEMO-001-04 are
the outer limits of curb work on either side of the Example Avenue mouth, not the two
ends of one run - there is no curb between them. A tracer built to join each
pair would have measured the intersection mouth. Exact endpoints and a verified
transform are not the same as knowing what lies between them.

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
