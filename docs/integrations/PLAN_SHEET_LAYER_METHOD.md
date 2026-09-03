# Plan-sheet layer method

How to get quantities off a civil plan sheet so that the numbers survive review.

Written after the Example Road Sheet 03 pass of 2026-09-03. Three earlier attempts at
the same quantities each produced a plausible, wrong answer. The steps below are
ordered the way they have to happen, and each one names the failure it prevents.
Code support: `src/screen2xyz_civil/plan_layers.py`, tests in
`tests_civil/test_plan_layers.py`.

---

## 0. Look at the sheet

Render the page to PNG and **actually view it** before writing a line of analysis.

This is first because skipping it cost the most. Two full sessions reasoned about
"the road-widening band" purely through text search and coordinate arithmetic and
placed it in the wrong half of the sheet. One render answered it in seconds.

Render at a low DPI for the whole sheet to orient, then crop and re-render at
200-700 DPI for anything being measured.

## 1. Read the legend, and read it as the sheet's own dictionary

The legend defines what each fill and hatch means **on this drawing set**. Do not
assume from experience.

On Example Road the legend's first swatch is a solid light-grey box meaning *40 mm
mill and overlay*. An earlier pass searched for a mill-and-overlay **hatch**, found
none, and recorded the item `NOT_PRESENT` - while the solid grey fill covering the
entire roadway was exactly that item, and the largest area on the sheet.

## 2. Establish the viewports before measuring anything

A plan-and-profile sheet carries at least two measurement contexts with different
scales - typically an isotropic plan (1:250 / 1:250) and an anisotropic profile
(1:250 horizontal, 1:50 vertical).

Record each as a `Viewport` and run `single_viewport_check` on every polygon and
polyline **before** writing it to the host.

The failure this prevents: a polygon written with profile-region coordinates
returned a host area exactly 5.00x smaller than the independent calculation. That
was recorded for two days as an unexplained "x5 Bluebeam artifact". It was not a
host defect at all - the host correctly applied the profile viewport's vertical
scale to geometry that had been drawn there by mistake, and the "independent"
check had assumed the plan viewport's isotropic scale. Both numbers were right for
their own viewport and both were meaningless for the bid.

`0.0881944 / 0.0176389 = 5.00` exactly. If a discrepancy is a clean ratio, suspect
the scale context before suspecting the software.

## 3. Calibrate stations from at least three chainage labels

Use `fit_station_frame`. It refuses fewer than three samples and refuses a fit
whose worst sample is more than 0.5 m off the line, because that is what a
mis-read label looks like.

Note that a page's own text layer may be unreadable by a PDF library while the
viewer's OCR layer reads it fine. Take the labels from whichever source actually
returns them, then check the fit.

## 4. Census the colours over the *whole* viewport, with anti-aliasing off

Render with anti-aliasing disabled so page content keeps exact colours, then take
an exact-colour histogram of the **entire** viewport.

Two failures this prevents:

* With anti-aliasing on, every edge invents intermediate colours and no colour
  mask is reliable.
* Sampling a guessed sub-window hides layers. The first Sheet 03 census covered
  about 55 % of the plan viewport by height. The fills happened to be inside it,
  but a third of the linework - ditches, slopes, right-of-way - was outside and
  simply never appeared.

Match every significant colour to a legend entry. A colour you cannot name is
either a layer you have not accounted for or a false trail; resolve it either way.

## 5. Take outer boundaries from fills, inner boundaries from drawn lines

A solid fill has a clean edge; use it. A **sparse hatch does not** - its outer
tips zigzag, and an envelope built from them is both noisy and systematically
wrong at tapers.

Where the drawing draws the boundary as a line, use that line. On Sheet 03 the two
widening strips have their own grey polylines along the existing-pavement edge,
each ending in a short cap that meets the fill edge to within 0.4 pt. Two
independent sources closing on each other is the confirmation.

## 6. Validate against printed dimensions before writing

Find the drawn centreline, take the offsets of every candidate boundary line from
it with `offsets_from_centreline`, and match them against the printed callouts
using `check_against_printed`.

On Sheet 03 this tied the outer boundary to `OFFSET: 6.2 m` (measured 6.16) and
`OFFSET: 7.3 m R` (measured 7.20), the tie-in to `O/S 5.16 m L` (measured 5.19),
and the two driveways to their `9.70m` / `8.90m` dimension arrows (measured 9.69
and 8.89 - one centimetre each).

**A measurement that cannot be tied to a printed dimension is a hypothesis.** Say
so in the markup rather than presenting it as a quantity.

## 7. Separate similar symbols by shape, not by neighbourhood

Ditch flow arrows and vegetation scallops are both small curved glyphs sitting
along the verge. Use `classify_glyph`: on this set the arrow runs about 4.0
wide-to-high and the scallop about 1.9.

Read together they gave a "south ditch" of 123 m. Separated, the ditch is 22 m and
the vegetation is 102 m - a different item entirely, and one no takeoff had.

## 8. Break symbol chains at gaps - the gap is the information

Use `split_runs`. A gap in a chain of symbols normally means the feature is
interrupted: a driveway crossing, a structure, a culvert.

Fitting one line through all eight south-ditch arrows gave 22.18 m. The arrows
actually fall in two runs either side of a 12.3 m gap, and that gap is exactly the
south driveway crossing where the culvert carries the ditch. Spanning it would
have overstated the ditch by 2.6x - and would have overwritten a previous
session's 8.59 m, which was correct.

## 9. Resolve sheet overlaps before summing anything

Adjacent sheets do not necessarily share a matchline station. Measure both
matchlines and run `sheet_overlap_report`.

Sheets 03 and 04 have matchlines at STA ~1+157 and ~1+137.8 - about 20 m drawn
twice. Everything in that band was cut at an agreed STA 1+140 and the remainder
marked separately as `OVERLAP - DO NOT SUM`. Discrete features that fall inside
the overlap (here: both driveways, both driveway culverts and a landscape area)
are the real double-count risk, because each sheet's reviewer assumes the other
covered them.

## 10. Write, read back, then LOOK AT THE MARKUP ON THE DRAWING

**Blocking. One call. No arithmetic. Never skip it.**

```
mcp__Bluebeam__create_markup_thumbnail(uniqueMarkupId="<id>")
```

It returns a PNG of that markup drawn in place on the sheet, rendered by the
host from the live document, with the host's own computed quantity printed on
it. Look at the image and answer one question: **does the boundary sit on the
feature the drawing draws?**

Full order:

1. Run `single_viewport_check` and the repository's `polygon_health`.
2. Write to the host.
3. Read the quantity **back from the host** and compare with an independent
   shoelace / polyline computation via `cross_check_quantity`.
4. **`create_markup_thumbnail` on every markup written, and look at each one.**
   Not a sample. Not "the overlay PNG looked right at a glance" - that is a
   different image, made by the same code that made the mistake.

### Why this is blocking, in numbers

Across the whole Example Road project up to 2026-09-03 there were **105 write
calls to the host and 1 call to `create_markup_thumbnail`.** The owner supplied
the missing eyes: roughly thirty of his fifty-seven turns in the working
session were pasted screenshots of Revu. Every one of those was a round trip
this step would have closed in one call.

### The thumbnail has one blind spot: it auto-zooms

`create_markup_thumbnail` frames the markup's own extent. For an extended
polygon that is exactly right. For a **point marker it fills the frame with the
marker and shows nothing around it**, and on a 100 m band it cannot resolve an
edge error of one line width.

On 2026-09-03 all three storm manhole count markers passed the host thumbnail
and two of them were sitting in the title block. Pair the thumbnail with
`markup_view.render_over_drawing`, which draws the read-back path over the base
PDF in a window you choose: default margin for a point marker so its
surroundings show, small margin and 15-20x for one stretch of a long band.

### A read-back only proves something if it returns by a different path

Writing through one API and reading back through the same one is
self-consistent by construction: it proves the host stored what you sent, and
nothing else. On 2026-09-03 a set of markers was written through the
view-frame API, read back through the view-frame API, rendered from those
values, and every step agreed - while all five sat in the profile instead of
the plan. The write, the read and the render shared the frame error, so no
check among them could fail.

That is the third self-consistent wrong answer this project has produced. The
other two: area totals that reconciled on polygons whose boundary was in the
wrong place, and `create_markup_thumbnail` on point markers, which auto-zooms
until only the marker is in frame. All three had the same shape - **the check
could not have failed.**

So verify across paths, not within one. Read the geometry back with
`get_markup_shape` (raw frame) and render from that; or pin a position against
a source the write never touched, the way `search` returns text geometry from
the page content. And use `host_frame` rather than open-coding the flip: the
two Bluebeam APIs disagree by rotation, on y for an unrotated page and on x
for a 180-rotated one.

### Numeric self-consistency is not placement

Area totals reconciling, zero mutual overlap, `polygon_health` clean, sum equal
to union, agreement with the manifest - all of these prove a polygon is
**valid**. None of them can tell you it is in the **right place**.

Thirteen Sheet 04 intersection markups passed every one of those checks and
traced curb-return arcs, callout leader lines and gas lines instead of pavement.
All thirteen were deleted. The corridor bands passed the same checks while
running 3-5 pt outside the drawn edge and dropping up to 20 pt (1.8 m) into the
pavement wherever a black dashed line broke the colour mask, which cost 16-21 %
on three widening polygons. Sheet 04's gravel shoulders were over by 2.2x and
2.6x from the same cause, and a length item takes the error directly.

### Two methods agreeing is not validation when they share a flaw

A raster trace was checked against another raster trace and agreed to 0.03 %.
Both were wrong the same way, because both read the same broken colour mask.
An independent check has to come from a **different kind of evidence**: a
printed dimension, the drawing's own vector geometry, or the render.

### Prefer the drawing's own vector geometry to a raster colour mask

The colour census is for *finding* what is on a sheet. For a **boundary**, use
the vector content where it exists: the pavement fill is emitted as many small
filled quads whose union gives an exact smooth edge, and hatch strokes are
clipped exactly at the band edge, so their extreme ends lie on the boundary.
Rebuilding Sheets 03 and 04 that way put the edge within 0.22 m of the printed
`6.90m` half-width, where the raster boundary sat outside it.

## 11. Keep provenance off the drawing

The host renders the `label` field onto the sheet. Long provenance text there
covers the drawing. Keep `label` empty or minimal, put a short basis in `subject`,
and the full reasoning in the scope ledger.

## 12. Do not overwrite a prior measurement without a drawing-based reason

Twice in this work an existing number turned out to be right and a re-measure
turned out to be wrong. Confirming an earlier figure independently is a result
worth recording. Replace a number only when a printed dimension or a drawn
boundary says the old one is wrong - and record which.

---

## Order of work for a new sheet

```
render + view  ->  legend  ->  viewports  ->  stations  ->  colour census
   ->  boundaries (fill edges + drawn lines)  ->  validate vs printed dims
   ->  symbol layers (split by shape, break at gaps)  ->  matchline/overlap
   ->  viewport + health checks  ->  write  ->  read back  ->  cross-check
   ->  create_markup_thumbnail ON EVERY MARKUP AND LOOK  ->  ledger
```

The last step before the ledger is the one that gets skipped and the one that
catches what nothing else catches. A sheet is not finished until every markup
written on it has been looked at as the host draws it.

## What still needs a human

Nothing above decides scope. Which pay item a measured area belongs to, whether a
disputed extent counts as reinstatement, and which sheet owns an overlap band are
estimator decisions. The method's job is to make the geometry and the arithmetic
defensible so those decisions are made on real numbers.

## Addendum: the render-clip flip is not the same transform as the data flip

Found while starting cross-section work on Sheet 09. `page.get_drawings()`
returns geometry in the page's own content-stream space; `page.get_pixmap(clip=...)`
expects a rectangle in the *displayed* space, and a 180-degree-rotated page
does not relate the two by the same single axis flip.

The established relation for this drawing set's 180-rotated pages is
`raw_x = x_gd`, `raw_y = 1684 - y_gd` (y flips, x does not) - this is the
frame every markup coordinate in this project uses, and it is correct for
reading and writing geometry.

**It is not the frame `get_pixmap(clip=...)` wants.** The displayed clip
needs `disp_x = 2384 - x_gd` (x flips) with `disp_y = 1684 - y_gd` (y flips,
same as before) - i.e. **both** axes invert for rendering, only one inverts
for data. Using the data-space x directly as a render clip renders the
mirror-image region of the page. On an 850-pt-wide panel next to its twin,
that silently shows the *other* cross-section under the label you asked for.

Confirmed on Sheet 09: a clip built from `x_gd` directly rendered the panel
labelled `1+160`; the same `x_gd` range rendered through `disp_x = 2384 -
x_gd` correctly showed `1+080`. Station text is otherwise the giveaway - it
will not garble from a render bug, but it will name the wrong section.

**Render every panel and check its own printed label before trusting what is
in it**, on every sheet, every time - this is `PLAN_SHEET_LAYER_METHOD.md`
step 0 applied per-panel, not just per-sheet, and it is what caught this.
