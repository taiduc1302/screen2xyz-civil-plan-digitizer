# Issue 4: code and workflow reader guide

**Applied AI for Estimating**

*AI Takeoff Markups in Bluebeam Through MCP: What Worked, What Fooled Me,
and How I Check It*

This page points readers to related experimental implementation work. It is not
an assertion that the full article demonstration has been packaged, reproduced
on another machine, or approved for estimating use.

## Which code is which?

The repository landing branch contains the Civil Plan Digitizer baseline: local
point/terrain review and exports. It is not the complete MCP takeoff pilot.

The separate `task/plan-layer-extraction` branch contains the related MCP and
vector-takeoff work. The source links below are pinned to the snapshot inspected
on 2026-09-22, `a99b2b24e536a4a3a3a5dd2fcc7e4aa469bc030b`, so they do not silently
change when a working branch moves.

| Area | Source entry point |
|---|---|
| AI host tool gateway | [mcp_gateway.py](https://github.com/taiduc1302/screen2xyz-civil-plan-digitizer/blob/a99b2b24e536a4a3a3a5dd2fcc7e4aa469bc030b/src/screen2xyz_civil/mcp_gateway.py) |
| Source-bound session and proposal records | [agent_session.py](https://github.com/taiduc1302/screen2xyz-civil-plan-digitizer/blob/a99b2b24e536a4a3a3a5dd2fcc7e4aa469bc030b/src/screen2xyz_civil/agent_session.py) |
| PDF evidence extraction | [pdf.py](https://github.com/taiduc1302/screen2xyz-civil-plan-digitizer/blob/a99b2b24e536a4a3a3a5dd2fcc7e4aa469bc030b/src/screen2xyz_civil/pdf.py) |
| Drawing-layer and filled-path processing | [plan_layers.py](https://github.com/taiduc1302/screen2xyz-civil-plan-digitizer/blob/a99b2b24e536a4a3a3a5dd2fcc7e4aa469bc030b/src/screen2xyz_civil/plan_layers.py) |
| Bluebeam working-copy and markup-plan bridge | [bluebeam_bridge.py](https://github.com/taiduc1302/screen2xyz-civil-plan-digitizer/blob/a99b2b24e536a4a3a3a5dd2fcc7e4aa469bc030b/src/screen2xyz_civil/bluebeam_bridge.py) |
| Host coordinate frames | [host_frame.py](https://github.com/taiduc1302/screen2xyz-civil-plan-digitizer/blob/a99b2b24e536a4a3a3a5dd2fcc7e4aa469bc030b/src/screen2xyz_civil/host_frame.py) |

These are navigation links, not a line-by-line code certification. Read the
[draft integration review](https://github.com/taiduc1302/screen2xyz-civil-plan-digitizer/pull/10)
and its outstanding findings before trying the branch. A draft PR description or
a past green test run is not proof that every issue is fixed on the linked commit.

## What this does not establish

A generated markup-plan JSON is not proof of a native Revu measurement.
A visible MCP tool is not proof of native scaled Length/Area creation. A unit test
cannot replace a disposable create/save/read-back check on the operator's actual
Revu and connector versions. Numerically consistent geometry can still trace the
wrong feature; rendered visual review and independent evidence remain necessary.

No verified downloadable package for the article's exact 21-markup synthetic
sheet, original source drawing and live Revu read-back record was established by
this publication review. Do not substitute an AI-generated cover image or an
invented CSV for that evidence. The article's demonstration numbers are not an
accuracy benchmark for this repository.

## Trying related code

First read [the publication audit](../../PUBLIC_RELEASE_AUDIT.md) and check the
licensing and data boundary. Work on an isolated local checkout and use an owned,
synthetic drawing. Do not upload private drawing material to this repository.
Follow the chosen branch's own dependency requirements, not the baseline's.

Keep the source PDF immutable and register a separate editable Revu working copy.
Independently verify the scale in the measurement region. Treat proposals and
computed quantities as preliminary, keep QA/reference geometry out of totals,
and leave estimator approval to a person.

## Accurate wording for an article link

> Related experimental code and workflow notes are collected here. The reader
> guide separates the Civil baseline from the MCP takeoff branches and explains
> the remaining validation limits. This is research code, not a production-ready
> estimating tool or a packaged reproduction of the demonstration.

This wording does not override unresolved privacy, source-rights or release
checks. A public GitHub page is not automatically an open-source licence.
