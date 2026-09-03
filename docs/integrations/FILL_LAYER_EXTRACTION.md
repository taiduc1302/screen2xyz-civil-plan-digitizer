# Fill and hatch layers on plan sheets, traced as regions

`src/screen2xyz_civil/fill_layers.py`, 2026-09-03.

> **Read this first. The raster trace this document describes is not safe for a
> boundary, and the "validation" below is not one.** It was checked against
> another raster trace of the same drawing and agreed to 0.03 %. Both were wrong
> the same way: at 90 DPI the colour mask breaks wherever a black dashed line
> lies over the grey fill, so the edge sat 3-5 pt outside the drawn line and
> dropped up to 20 pt (1.8 m) into the pavement. Two methods that share a flaw
> agreeing is not validation. Use this module to **find** what is on a sheet and
> how much of each pattern there is; take a **boundary** from the drawing's own
> vector geometry. Every polygon it produces must be rendered with
> `create_markup_thumbnail` and looked at before it is trusted - see
> `PLAN_SHEET_LAYER_METHOD.md` step 10.

## Why a second method

`PLAN_SHEET_LAYER_METHOD.md` reads a layer as a band: per render column, the
top and bottom of the colour. It measured sheets 03, 04 and 05 and it is exact
on a straight corridor. It has no answer where two roads' fills meet in plan,
and it cannot give scattered patches their own boundaries. Both were left
"not done, stated plainly" in the Sheet 03 ledger.

A region has no such limit. Render the viewport with anti-aliasing off, mask
the exact colour, heal the cuts, label the connected regions, trace each
boundary along pixel edges, simplify, return in the raw frame.

## What the sheets actually are

* The grey "solid" fill (#E5E5E5) is **not a vector path** - `get_drawings`
  returns no such fill. It is a PDF tiling pattern, rendered at 90 DPI as
  65 x 36 px cells with one-pixel seams wherever the cell grid misses the
  pixel grid. On sheet 05 the naive mask came out as 1 190 pieces.
* The road-widening X-hatch (#7F7F7F strokes, 0.84 pt) is drawn **over** the
  same grey. Grey = every paved surface in the works; grey under hatch =
  full-structure widening; grey without hatch = mill and overlay. The hatch
  lines run to the edge line; the pattern fill under them stops a pixel or two
  short of it.
* Linework crosses the fill everywhere - centreline, lane lines, station
  ticks, leaders, white label boxes.

## Method

1. `render_viewport` - exact RGB of the declared PLAN viewport (raw frame in,
   displayed-frame clip built from it; rotation 0 and 180 only).
2. `close(mask, 2)` heals seams and linework; `fill_holes(mask, 12 sq m)` closes
   label boxes and reports what it filled (`HOLES_FILLED`).
3. `hatch_closing_radius` = half the median gap between hatch lines along a
   row (17 px on this set, so 9). Seven leaves the widening in four pieces
   full of holes; eleven over-rounds by 2.5%.
4. `split_pavement` returns three region sets: **paved works** (grey or
   hatched), **widening** (the hatched ring), **mill and overlay** (grey not
   hatched). Their areas add up by construction.
5. Every region carries two areas - polygon and painted pixels - and the
   difference is accounted for by colour: pixels under linework and hatch are
   the fill (the road does not stop under a lane line), white inside is a
   label box or a real opening (`WHITE_INSIDE_REGION`, blocking). A residual
   over 3% is `TRACE_DISAGREES_WITH_PAINT`, blocking.
6. `clip_polygon_x` cuts a region at a station; `render_overlay` draws the
   regions over the sheet. The overlay is the acceptance check.

7. **Patterns, by exact colour.** The sheet 04 legend swatches, censused with
   anti-aliasing off, render as: ROAD WIDENING (FULL ROAD STRUCTURE) X-hatch
   `(127,127,127)`; FULL DEPTH ASPHALT REMOVAL AND REPLACEMENT `(178,178,178)`;
   DITCH INFILL `(0,127,0)`. `(128,128,128)` (landing pads) and `(153,153,153)`
   are on the sheet and not in the legend, and are carried as *unidentified*.
   One grey level is the whole difference between two pay items, and it is
   enough: every secondary hatch is closed on its own radius and taken out of
   both the widening and the mill-and-overlay, so a region is counted once
   under the pattern drawn on it (`other_hatched`). Every region also reports
   `pattern_fractions` - what else is drawn inside it - and `dominant_pattern`.
8. **`polygon_health` on every region at extraction.** The repository's own
   pre-write gate, so an outline the host would refuse is refused here and
   left out of every total (`POLYGON_UNHEALTHY`, `REGIONS_EXCLUDED_UNHEALTHY`).
   A 4-connected region that touches itself at a corner traces as one loop
   through that corner twice, which the gate calls a self-intersection;
   `split_pinches` cuts such loops into simple lobes first.

## Validation, sheet 05, 1+240.1 to 1+367.5

Clipped to the same station range as the host polygons `KHCGMKMCPQKXUBKD-4`,
`HXNWQOKORQZHJQMK-4`, `YOQSPGDLICKOKKFO-4` (read back with `get_markup_shape`):

| | traced | host | |
|---|---|---|---|
| widening (hatched ring) | 1 006.1 | 1 005.8 | **+0.03%** |
| mill and overlay + full-depth patch | 483.1 + 77.1 = 560.2 | 559.0 | +0.2% |
| paved works | 1 584.4 | 1 564.9 | +1.2% (union includes the hatch edge strip and filled label boxes) |

**The host's mill-and-overlay polygon on sheet 05 contains 77 sq m drawn as
FULL DEPTH ASPHALT REMOVAL AND REPLACEMENT** (raw x 757-928, y 1190-1249, the
differently hatched patch near 1+340-1+355). That is a separate pay item
(`FULL_DEPTH_ASPHALT_RR`), recorded NOT_PRESENT on sheet 03 and never searched
on 05. Reported to the session that owns the markup.

## What it found on sheet 04

The clean segment 1+140.4-1+183.4 was already measured. The host's three
polygons there **overlap each other** - their edges are sawtooth, ~100 spikes
22-31 pt deep and 2 pt wide, reaching into each other's bands. Rasterised at
90 DPI the overlap read 45.9 sq m; the session that owns the markups then
computed it vector-exact (shapely on the host paths): M&O `AYDIZHWCVEPKQAFZ-3`
intersects widening N by 12.59 sq m and widening S by 21.58 sq m, **34.17 sq m
double-counted**, union of the three 647.20 sq m, and `polygon_health` refuses
all three (`POLYGON_SELF_INTERSECTS`). The traced paved works in the same
x-extent = 657.8 sq m (+1.6% on the union). The traced split is widening
258.1 / M&O 392.0; the host records 249.89 / 431.47. Total right, split
double-counted. Both host quantities are flagged NOT FINAL in the ledger;
nobody has written a correction, and whichever session does will say so first.

The owning session rewrote the three clean-segment polygons the same day
(widening N 144.37, S 113.74, M&O 385.53, no overlaps). The trace gives
widening 257.4 and M&O 392.0 there; the 6.5 sq m on M&O is five fragments under
1.4 sq m each on the station-tick line that the owning session left out as
unconfirmed, which is the right call.

> **Retracted 2026-09-03, same day.** Every polygon below was written to Revu,
> passed `polygon_health`, reconciled on area, had zero mutual overlap and
> sum-equals-union - and was then rendered against the base PDF with
> `create_markup_thumbnail` and found to be tracing curb-return arcs, callout
> leader lines and gas lines rather than pavement. **All 13 were deleted and the
> intersection zone is `UNSEARCHED` again.** The numbers in this section must not
> be used. The raster colour-mask trace fails in a curb-return-dense zone, and no
> numeric check can catch a boundary that is wrong but internally consistent.
> The corridor bands on sheets 03 and 04 were rebuilt from the drawing's vector
> geometry for the same reason (the raster edge sat 3-5 pt outside the drawn edge
> and dropped up to 20 pt into the pavement where a black dashed line broke the
> mask), costing 16-21 % on three widening polygons, and two gravel-shoulder
> lengths were 2.2x and 2.6x over. Use vector content for a boundary; use the
> colour census only to find what is on a sheet.

**The intersection zone 1+183.4-1+240.0, previously `UNSEARCHED`, is now
measured, by pattern:** paved works 1 328.5 sq m = widening 285.5 + mill and
overlay 777.8 + **full-depth asphalt removal and replacement 194.3** (four
patches at the curb returns) + grey-128 4.7 (the grey of utility symbols -
culvert bodies, flow arrows - not pavement) + grey-153 26.9 (the stipple on
the pedestrian asphalt pads, a scope item of its own, not legended), including
the Example Avenue stubs sheet 04 draws
(2+017.0 to 2+060.2 - its own matchlines at raw y 1424.3 and 934.6, from its
2+020 / 2+040 ticks at raw y 1390.4 / 1163.5). Sheet 06's second drawing of the
same intersection gives full-depth 179.9 and widening 223.2 over its own,
narrower, extent - the two drawings agree on what is there. Overlays and the
manifest are in the Example Road pilot folder, `07 Claude Operator Pilot/fill_layers/`.

## Sheet 06 and the 04/06 division

Sheet 06 is the same intersection drawn again with Example Avenue horizontal and
Example Road between two "SEE SHEET 04" matchlines. Its whole-sheet trace
(paved works 1 292.1 sq m) is a **second drawing of ground already on sheet
04** and must not be summed. What sheet 06 adds is the Example Avenue pavement
beyond sheet 04's matchlines, to the printed tie-ins:

| Example Avenue band | paved works | widening | mill and overlay |
|---|---|---|---|
| 2+012.1 - 2+017.0 (south) | 53.5 | 0.4 | 52.2 |
| 2+060.2 - 2+066.7 (north) | 69.2 | 0.0 | 68.7 |

from sheet 06's own 2+000..2+080 ticks at raw x 1439.2 / 1212.4 / 984.9 /
758.9 / 532.1 (11.34 pt/m). The rule - sheet 04 owns the intersection, sheet
06 owns only the ends - is a convention; it is stated in the manifest so the
estimator can move the line, not discover it.

## Writing a traced region to Revu

Two facts learned on 2026-09-03 while the owning session wrote the sheet 05
split:

* **One ring per Polygon markup.** A two-ring SVG path (`M ... H M ... H`)
  is accepted silently: Revu drops the second `M` and bridges the rings into
  one self-intersecting polygon, caught only on read-back (area did not
  reconcile, shapely `is_valid=False`). A region with a hole, or an item the
  drawing splits in two, is written as separate markups - the way driveways
  N/S already are. `FillRegion.holes_raw` therefore never goes into a path;
  a holed region is written as its outer ring plus a note, or split by hand.
* **`polygon_health` wants the ring open.** A ring that repeats its first
  vertex at the end (shapely's convention), or carries two consecutive equal
  vertices (the host rounds to 0.1 pt), has a zero-length edge; that edge
  touches its neighbours at a shared point and the touch test reported it as
  a self-intersection on five polygons shapely called valid. Fixed by
  normalising the ring in `bluebeam_bridge` (`_normalise_ring`) before any
  edge test; the regression tests carry both shapes.

## What it does not decide

Which region is paid as which item. On this set the names follow the sheet
03 legend; sheet 04 and 06 carry landing pads, driveways and ditch infill in
their own patterns, and a hatched region near a curb return may be a landing
pad, not widening (`HATCH_OUTSIDE_FILL` says where hatch sits on no grey). The
regions are what is painted; the operator reads the legend and the overlay
and records the mapping with its evidence.

## Running it

```python
from screen2xyz_civil.plan_layers import Viewport
from screen2xyz_civil.fill_layers import split_pavement, clip_polygon_x, polygon_area_m2, render_overlay
CX = 0.0881944444444444
vp = Viewport("PLAN", 444, 785, 1759, 1515, CX, CX)          # sheet 04, raw frame
res = split_pavement(pdf, 3, vp)                              # hatch radius derived
render_overlay(pdf, 3, vp, res["_widening"] + res["_mill_overlay"], out_png)
parts = clip_polygon_x(res["mill_overlay"][0]["polygon_raw"], x_at_1240, x_at_1183_4)
sum(polygon_area_m2(p, vp) for p in parts)          # or clip_area_m2(...)
```

`clip_polygon_x` returns a **list of simple rings**. A concave region cut
across its mouth is two or more pieces; the first version (Sutherland-Hodgman)
returned one ring that bridged them along the cut line - right area, invalid
boundary - and the session writing the sheet 04 intersection caught it with
shapely. Chains inside the band are now linked through their crossing points
paired in y order along each cut line, and every piece passes `polygon_health`.

numpy only; no scipy, no shapely. 6-9 s per sheet at 90 DPI.
