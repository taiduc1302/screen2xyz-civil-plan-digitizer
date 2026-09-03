# Fill and hatch layers on plan sheets, traced as regions

`src/screen2xyz_civil/fill_layers.py`, 2026-09-03. Built for the two places
the corridor band method could not go - the Example Road junction intersection on
sheets 04 and 06 - and validated on sheet 05 against polygons hand-traced and
read back from Revu.

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

## Validation, sheet 05, 1+240.1 to 1+367.5

Clipped to the same station range as the host polygons `KHCGMKMCPQKXUBKD-4`,
`HXNWQOKORQZHJQMK-4`, `YOQSPGDLICKOKKFO-4` (read back with `get_markup_shape`):

| | traced | host | |
|---|---|---|---|
| widening (hatched ring) | 1 008.4 | 1 005.8 | +0.26% |
| mill and overlay | 562.3 | 559.0 | +0.59% |
| paved works | 1 584.3 | 1 564.9 | +1.2% (union includes the hatch edge strip and filled label boxes) |

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

**The intersection zone 1+183.4-1+240.0, previously `UNSEARCHED`, is now
measured:** paved works 1 326.0, widening 315.4, mill and overlay 1 001.8 sq m,
including the Example Avenue stubs sheet 04 draws (2+017.0 to 2+060.2 - its own
matchlines at raw y 1424.3 and 934.6, from its 2+020 / 2+040 ticks at raw y
1390.4 / 1163.5). Overlays and the manifest are in the Example Road pilot folder,
`07 Claude Operator Pilot/fill_layers/`.

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
band = clip_polygon_x(res["mill_overlay"][0]["polygon_raw"], x_at_1240, x_at_1183_4)
polygon_area_m2(band, vp)
```

numpy only; no scipy, no shapely. 6-9 s per sheet at 90 DPI.
