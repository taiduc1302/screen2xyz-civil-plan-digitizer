# Cross-section sheets: surfaces and earthwork from the PDF vectors

`src/screen2xyz_civil/cross_sections.py`, 2026-09-03. Applied to DEMO-001-09 and
DEMO-001-10, the only sheets in the Example Road set that carry the third dimension
the two largest tender items need.

## What the sheets are made of

Measured on DEMO-001-09 panel 1+080 and true of every panel on both sheets:

| Stroke | Width | What it is |
|---|---|---|
| grid | 0.12 pt | 28.35 pt apart vertically, 141.7 pt apart horizontally |
| surfaces | 0.84 pt | design line (drawn 2-3 times, ~1.1 pt apart, to look heavy), existing ground (dashes of 0.1-11.3 pt, each its own object), pavement structure boxes, P/L verticals |
| labels | 0.36 / 1.14 pt | every station, elevation, offset and crossfall - **outlined glyph strokes, not text** |

The only text on either sheet is the consultant's address. Nothing else on
them can be read as text by any tool.

**The grid verifies the scale.** 28.35 pt is 0.5 m at 1:50 to four figures;
141.7 pt is 5 m at 1:100. Every panel reports `SCALE_VERIFIED_BY_GRID` against
the declared `Cx = 0.0352778`, `Cy = 0.0176389` within 0.1%. A sheet whose grid
disagreed would refuse to measure (`SCALE_GRID_MISMATCH`, blocking).

## Method

1. **Panels from the grid.** Long 0.12 pt horizontals, joined only where pieces
   touch (a label breaks each grid line into three), grouped by x-extent and
   split at y gaps. Seven verticals per panel; the middle one is the
   centreline. Eight panels on 09, six on 10.
2. **Section frame.** Every surface is returned as (offset from centreline,
   height above the lowest grid line) in points, positive to the right *as
   displayed*. This hides the rotation: on this set's 180° pages the data frame
   flips y only while the render clip flips both axes (see the addendum in
   `PLAN_SHEET_LAYER_METHOD.md`); other rotations are refused, not guessed.
3. **Design surface** = upper envelope of the long 0.84 pt strokes, after
   averaging the 2-3 copies each is drawn as. Everything in that class sits at
   or below the finished surface. The extracted edge-of-pavement and centreline
   elevations match the printed ones on every panel checked (1+080: 113.15 /
   113.27 / 113.16 against printed 113.15 / 113.30 / 113.16).
4. **Subgrade** = lower envelope of the same strokes: the bottom of the drawn
   structure under the pavement, the surface itself elsewhere. Structure depth
   comes out at 0.63 m on all fourteen panels. Sampled a thousandth of a point
   either side of every stroke end so the envelope steps vertically at a box
   edge - sampling only on the ends ran it diagonally to the next sample and
   invented about 0.7 sq m of cut per inner box edge.
5. **Existing ground** = the dashes, traced. Each dash is a segment; the tracer
   walks from a dash to the unused dash that best continues it (nearest, same
   direction), so a stray short stroke of the design line nearby is passed
   over rather than spliced in. The runs that together cover the most width
   without overlapping are the ground.
6. **Gaps in the dashes.** The consultant does not draw existing ground where it
   coincides with the new pavement. A gap whose ends both sit within 0.05 m of
   the design is closed along the design (`EXISTING_FOLLOWS_DESIGN`, zero
   area). A gap that is not on the design is closed straight and flagged
   (`EXISTING_GROUND_GAP`); over 1 m it blocks.
7. **Areas** per panel through `earthwork.section_areas_between_surfaces`,
   per-axis factors applied before any area. Two pairs: to the finished
   surface and to subgrade.
8. **Station is not read.** Outlined, no OCR on the machine, and panel order is
   not a station sequence - DEMO-001-09 skips 1+200. `render_panel` writes a
   thumbnail with the three surfaces drawn over the panel; the operator names
   each from its thumbnail and `measure_sections` refuses a volume until every
   panel it uses is named. The overlay is also the check: red must sit on the
   heavy line, blue on the dashes, green on the box bottoms.

## Results, DEMO-001-09 and -10, 2026-09-03

Stations read from the fourteen thumbnails (in the Example Road pilot folder,
`07 Claude Operator Pilot/cross_sections/`, with the manifest JSON):

09: 1+080 1+100 1+120 1+140 1+160 1+180 **1+220** 1+240 (no 1+200 drawn)
10: 1+260 1+280 1+300 1+320 1+340 1+360

Average end area, 1+080 to 1+360, 280 m:

| Surface | Cut m³ | Fill m³ |
|---|---|---|
| to finished surface | 131 | 744 |
| **to subgrade** | **1 117** | **488** |

Findings on the volume: `RANGE_NOT_EXTRAPOLATED` (nothing before 1+080 or after
1+360, and neither the Example Avenue leg nor site 2 have sections) and
`SECTION_SPACING_TOO_WIDE` for the 40 m between 1+180 and 1+220.

Against the tender: 31.04 Common Excavation is 2 160 m³ for the whole project.
1 117 m³ to subgrade on this 280 m is the right order and cannot be reconciled
further from these two sheets. Which surface a pay item is measured to is the
specification's call; both are reported and `measure_sections` makes the
caller say which. Cut and fill are never netted. 31.06 is in tonnes and needs
a sourced density before `tonnes_from_volume` will convert anything.

## Running it

```python
from screen2xyz_civil.cross_sections import extract_panels, render_panel, measure_sections
CX, CY = 0.0352777777777778, 0.0176388888888889
s09 = extract_panels(pdf, 8, declared_metres_per_point_x=CX, declared_metres_per_point_y=CY)
for p in s09["_panels"]:
    render_panel(pdf, 8, p, out / f"09_p{p.index}.png")   # name each from its thumbnail
volume = measure_sections([s09, s10], stations, surface="subgrade")
```

`SectionSheetSpec` holds the measured stroke widths and grid steps; another
consultant's set needs its own, the way another set needs its own title-block
baseline in `sheet_pass`.

## What this does not do

- Read stations or elevations. It could, with OCR or a glyph template set; the
  digits on these sheets cover only 0-8 so a template set cannot be learned
  from them alone.
- Decide the pay-item surface, the density, or whether the tendered quantity
  is right.
- Cover any station these sheets do not draw.
