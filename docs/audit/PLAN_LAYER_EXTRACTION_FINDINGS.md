# Findings against `task/plan-layer-extraction` @ `19018cd`

Audited 2026-09-03 against the branch head `19018cd` ("feat: chain a layer's
fragments into continuous lines"), 567 tests, CI green. The branch is the live
line of work; this file is read-only evidence about it, produced from a
different session. Nothing here was pushed to that branch.

Every number below is printed by `docs/audit/plan_layer_probes.py`, which
builds its own PDFs inline. Run it against a checkout of the branch:

```
python docs/audit/plan_layer_probes.py --src <checkout>/src
```

**Every finding now has a patch.** Two files, and you apply **one or the
other**, never both — they overlap:

- `docs/audit/all_findings_A_B_C_D_E.patch` — all five findings plus the
  retired sanitization scan, 11 regression tests, `EXPECTED_TEST_COUNT`
  629 → 640.
- `docs/audit/layer_chains_findings_C_and_D.patch` — only the two that change
  a quantity, 5 tests, 629 → 634. The smaller thing to take if the rest is
  not wanted yet.

See "A patch for C and D" and "A patch for all five" at the end of this file.

## Scope of this pass

Read: `plan_layers.py`, `fill_layers.py`, `vector_fill.py`, `pattern_edge.py`,
`sheet_pass.py`, `symbols.py`, `layer_chains.py`, `cad_layers.py`,
`host_frame.py`, `markup_view.py`, and the frame and QA paths of `pdf.py`,
`agent_session.py`, `mcp_gateway.py`, `scope_ledger.py`.

Not read, and therefore not covered: `cross_sections.py`, `earthwork.py`,
`feature_identity.py`, `bluebeam_bridge.py`, `takeoff_context.py`, and the
1052 test methods that back them.

The branch's own reasoning is sound where this pass could check it - the
painted-versus-traced area pair, refusing an area in an anisotropic viewport,
refusing an unhandled rotation, and the reason `vector_fill` exists at all are
all right, and the docstrings record real measurements rather than guesses.
The four findings below are arithmetic, not judgement.

---

## A - A CropBox offset displaces every vector-derived coordinate

`vector_fill.raw_frame` and `fill_layers.RenderFrame.pixel_to_raw` convert
PyMuPDF display coordinates to the raw markup frame with `page.rect.height`
and `page.rect.width`. PyMuPDF's `page.rect` is the **CropBox**; a PDF
annotation's `/Rect` is in user space, which is anchored to the **MediaBox**.
The two agree only while the CropBox equals the MediaBox with its corner at
the origin.

A line drawn at user-space `(100,100)-(100,200)`:

| page | `raw_frame` result | truth | error |
| --- | --- | --- | --- |
| CropBox == MediaBox, rot 0 | `(100.0, 100.0) (100.0, 200.0)` | same | `(0, 0)` |
| CropBox inset 20/30, rot 0 | `(80.0, 70.0) (80.0, 170.0)` | `(100,100) (100,200)` | `(-20, -30)` |
| CropBox inset 20/30, rot 180 | `(80.0, 70.0) (80.0, 170.0)` | `(100,100) (100,200)` | `(-20, -30)` |

The error is exactly the CropBox origin, `(-cropbox.x0, -cropbox.y0)`.

Why it has not shown up: it is a pure translation, so **lengths and areas are
unaffected** - only placement moves. And it is zero on a sheet whose CropBox
equals its MediaBox, which is presumably true of 24-047-04, or the traced
boundaries would not have landed on the drawn edges at all.

Why it still matters: a re-issued or addendum sheet that has been cropped
picks it up silently, and nothing catches it. `agent_session` validates
vertices against `page_width_points` / `page_height_points`, which come from
`pdf.py`'s **MediaBox** read - so a polygon shifted by the CropBox origin is
*smaller* than the declared frame and passes the bounds check. Fail-open. The
session also then declares a page size that does not describe the frame its
own geometry is in.

Two separate defects, both cheap:

1. `pdf.py:88-89` reads `page.mediabox` for `width_points`/`height_points`.
   Every renderer that matters - PDFium, Revu, PyMuPDF - rasterises the
   **CropBox clipped to the MediaBox**. This is the fix carried by `29a1d31`
   on `feature/claude-markup-operator-real3` (`_effective_page_size`), which
   applies to this file unchanged.
2. The display-to-raw conversions need the CropBox origin added back, or an
   explicit refusal when `page.rect != page.mediabox` until they do. A
   refusal is the safer of the two and is one `if`.

There is no test on the branch covering a CropBox that differs from the
MediaBox: `git grep -il cropbox tests_civil/` returns nothing.

## B - `RenderFrame` assumes the pixmap begins exactly at the requested clip

`render_viewport` stores `display_x0=clip[0]`, `display_y0=clip[1]` and
`points_per_pixel = 72/dpi`. `get_pixmap` snaps the clip **outward to whole
pixels**, so the pixmap's first pixel is at `pix.irect.x0 / zoom`, not at
`clip[0]`:

| dpi | clip | requested px | actual px | origin error |
| --- | --- | --- | --- | --- |
| 90 | `(100.3, 200.7, 300.3, 400.7)` | 250.000 x 250.000 | 251 x 251 | `(-0.30, -0.70)` pt |
| 90 | `(100.0, 200.0, 300.0, 400.0)` | 250.000 x 250.000 | 250 x 250 | `(0, 0)` pt |
| 150 | `(100.3, 200.7, 300.3, 400.7)` | 416.667 x 416.667 | 418 x 417 | `(-0.46, -0.06)` pt |

`points_per_pixel` is exact; only the origin is wrong, by up to one whole
pixel - 0.8 pt at 90 DPI, about 0.07 m at 1:250. It biases a traced boundary
in one direction rather than averaging out, and it is a component of the
3-5 pt offset `vector_fill.py`'s docstring records, though not the whole of
it. Zero when the viewport happens to land on pixel boundaries, which is why
it hides.

Fix: take the origin from the pixmap - `display_x0 = pix.irect.x0 / zoom` -
instead of from the request.

## C - A shape drawn as two polylines loses one of them

`dedupe_fragments` calls two fragments coincident copies when **both
endpoints** match within `DUPLICATE_TOL = 0.5` pt. It never looks at the path
between them. Two fragments that share both ends and take different routes -
an island or a pavement patch outlined as a top side and a bottom side, a
circle as two arcs, an arc and its chord - are one fragment as far as this
test is concerned.

```
top side 43.32 pt + bottom side 43.32 pt = 86.65 pt of drawn line
-> fragments_used=1 duplicates_removed=1 total_length=43.32 pt
-> UNDER-COUNT 43.32 pt (50%), with no finding raised
```

The only trace is the `duplicates_removed` counter. It is not a finding, it
does not block, and nothing downstream reads it. This is a length item coming
back short with a clean QA report - the shape of the reconciliation problem
the operator is chasing.

Fix: require the paths to agree, not only the ends - compare length, or the
midpoint, or sample a few interior points, before calling it a duplicate.

## D - The auto gap tolerance is the maximum gap on a small layer

`nearest_gap_stats` returns `gaps[min(n-1, int(n * 0.9))]` as `p90`. For any
`n <= 10` that index is the last element, so the reported 90th percentile
**is the maximum**:

```
n=  5 -> p90 = gaps[4] = 5, max = 5      <-- p90 IS the max
n=  8 -> p90 = gaps[7] = 8, max = 8      <-- p90 IS the max
n= 10 -> p90 = gaps[9] = 10, max = 10    <-- p90 IS the max
n= 20 -> p90 = gaps[18] = 19, max = 20
n=404 -> p90 = gaps[363] = 364, max = 404
```

`gap_tol` defaults to `1.5 x p90`, so on a small layer the tolerance becomes
1.5x the largest gap on the layer and everything welds together. Five
fragments - a run of four dashes plus one separate line 254 pt away:

```
gap_stats = {'median': 2.0, 'p90': 254.0, 'max': 254.0, 'count': 5.0}
auto gap_tol = 381.00 pt
chains = 1 (correct: 2)   total_length = 310.00 pt (drawn line = 50.00 pt)
```

The 254 pt of empty page between the two lines is counted as line: 310 pt
reported against 50 pt drawn, a 6.2x over-count, with no branch warning
because each end had exactly one candidate. The module's own docstring says
"the 90th percentile is the linetype's gap and everything beyond it is a real
break" - which is the right idea, defeated by the index.

At 404 fragments the index lands at the 90.1st percentile and the defect is
invisible, which is why sheet 04's pavement edge behaves.

Fix: interpolate, or use `gaps[max(0, math.ceil(0.9 * n) - 1)]`, and refuse
an automatic tolerance derived from fewer than some minimum number of gaps.

---

## E - Scope coverage is reported but no longer enforced

`scope_ledger.py` is present, and `mcp_gateway.takeoff_qa` attaches
`qa["scope"] = scope_summary(session)`. But `AgentTakeoffSession.qa_summary`
does not consult it, so an `UNSEARCHED` rule raises no issue: `takeoff_qa` can
return `issues: []` while whole rules were never looked for, and
`bluebeam_plan()` no longer carries the scope block at all.

On `feature/claude-markup-operator-real3` the same ledger raises a
`SCOPE_NOT_SEARCHED` ERROR from `qa_summary` while any rule is `UNSEARCHED`,
which is what makes I7 (scope completeness) fail closed rather than merely
being visible in a report someone has to read. The wiring is a few lines and
is the difference between "the coverage is in the output" and "the coverage
gate stops the export".

## What this does not claim

None of this was run against a King Road sheet, a live Revu, or a real
OpenTakeoff install. A, B, C and D are arithmetic reproduced on synthetic
input; whether each one is *currently* biting a given sheet depends on that
sheet's CropBox, viewport alignment, and layer fragment counts, which only
the operator with the file can tell. E is read from the source of both
branches, not measured.

---

## A patch for C and D

`docs/audit/layer_chains_findings_C_and_D.patch` — 124 insertions, 11
deletions across three files, against `task/plan-layer-extraction` at
`cb19d41`. `git apply --check` is clean on that head.

```
git checkout task/plan-layer-extraction
git apply docs/audit/layer_chains_findings_C_and_D.patch
PYTHONPATH=src python tests_civil/run_civil_tests.py
```

**C — `dedupe_fragments` now compares the path, not only the ends.** Two new
helpers, `_point_at` and `_paths_agree`: after the existing endpoint match
(kept as the cheap pre-filter, in both orientations) the two fragments must
also agree in length and at three interior samples, all within the same
`DUPLICATE_TOL`. A plotted copy matches everywhere; the far side of an
island, the other half of a circle and an arc against its chord do not.

**D — the automatic tolerance no longer comes from a sample too small to
have a percentile.** `MIN_GAP_SAMPLE = 10`: under that many measured gaps
the basis is the median rather than the p90, because below ten the p90 *is*
the largest gap on the layer. The percentile index is also corrected to
nearest-rank, `gaps[ceil(0.9n) - 1]`, though on its own that changes nothing
except when `0.9n` is a whole number — the substantive half of this fix is
the sample guard, not the index.

Measured with the probe script, before and after, on the same input:

| | before (`cb19d41`) | after |
| --- | --- | --- |
| C: two polylines A→B | `fragments_used=1`, 43.32 pt of 86.65 | `fragments_used=2`, 86.65 pt |
| C: under-count | 43.32 pt (50%) | 0.00 pt (0%) |
| D: auto `gap_tol` | 381.00 pt | 3.00 pt |
| D: chains | 1 (correct: 2) | 2 |
| D: total length | 310.00 pt against 50.00 drawn | 56.00 pt |

**Five regression tests** in `tests_civil/test_layer_chains.py`, and
`EXPECTED_TEST_COUNT` 629 → 634. Three of them cover C — the island keeps
both sides, an arc and its chord stay separate, and a reversed plotted copy
is *still* deduped, so the path check does not cost the branch the dedupe it
relies on. Two cover D — a full layer still reads 7.5 pt from its linetype
exactly as before, and a five-fragment layer no longer takes its tolerance
from its largest gap.

**What was run.** The whole frozen Civil suite, in this Linux container,
against the branch head with and without the patch: 613 → 618 executed, 0
failures either way, and the same 14 errors in both — all of them missing
optional dependencies here (`mcp`, the OCR stack behind `sheet_text`,
`openpyxl`), identical sets by `diff`. The patch adds five tests and changes
nothing else that this environment can see. It has **not** been run on
Windows CI, and nothing here was pushed to `task/plan-layer-extraction`.

---

## A patch for all five

`docs/audit/all_findings_A_B_C_D_E.patch` — 363 insertions, 21 deletions
across nine files, against `e6eef78`, `git apply --check` clean. It contains
the C and D patch above **and** the rest, so apply this one *or* that one,
never both.

```
git apply docs/audit/all_findings_A_B_C_D_E.patch
PYTHONPATH=src python tests_civil/run_civil_tests.py   # 640
PYTHONPATH=src python tests/run_all.py
```

**A — the declared page size becomes the rendered box.** `pdf.py` gains
`_effective_page_size` (the CropBox clipped to the MediaBox, falling back to
the MediaBox) and `inspect_pdf` uses it, so `page_width_points` describes the
frame the geometry is actually in. And `fill_layers.render_viewport` now
**refuses** a page whose CropBox is not its MediaBox rather than returning
coordinates that are out by the CropBox origin — fail-closed, because the
error is a pure translation that leaves every length and area right and only
moves the markup, and the session's bounds check cannot see it.

**B — the render frame takes its origin from the pixmap.**
`display_x0 = pix.irect.x0 / zoom` instead of `clip[0]`. `get_pixmap` snaps
the clip outward to whole pixels, so the old origin was up to one pixel out
— 0.8 pt at 90 DPI, about 0.07 m at 1:250 — always in the same direction.

**E — coverage fails QA instead of sitting beside it.**
`AgentTakeoffSession.qa_summary` now reads the ledger and raises a
`SCOPE_NOT_SEARCHED` ERROR, counted and blocking, while any rule is
`UNSEARCHED`. The gateway still attaches `scope`; the difference is that
`takeoff_qa` can no longer return `issues: []` for a sheet with whole rules
never searched.

**The retired sanitization scan is scoped, not retired.**
`tests/test_repository_sanitization.py` gains `_EXEMPT_PREFIXES = ("pilot/",)`
and drops the `assertTrue(True); return` body, so `T-PRI-004` reports PASS
because it passed rather than because it scanned nothing. Measured in this
container: 725 tracked files, **486 scanned**, 239 exempt under `pilot/`. A
planted identifier outside `pilot/` **fails** the test; the same string
inside `pilot/` passes. That is the guard working, on both sides.

**Six more regression tests** — four in a new `tests_civil/test_page_frame.py`
(a cropped page reports the rendered box, an uncropped one is unchanged, the
fill renderer refuses a cropped page, the frame origin lands on a pixel
boundary) and two in `tests_civil/test_scope_ledger.py` (QA refuses a sheet
with unsearched rules, and stops objecting once every rule is accounted).
Eleven new tests in total with C and D, `EXPECTED_TEST_COUNT` 629 → 640.

**What was run.** The frozen Civil suite on `e6eef78` with and without the
whole patch: 613 → 624 executed, zero failures either way, the same 14 errors
in both and identical by `diff`. And `tests/run_all.py`, which owns
`T-PRI-004` and rejects skips: 42 tests, 40 passed, 0 failures, 0 skipped,
4 errors — the same four before and after, all optional dependencies missing
here. Not run on Windows CI. Nothing pushed to `task/plan-layer-extraction`.
