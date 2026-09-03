# Why the traced markups were bad, and what fixed them

Written 2026-09-03 after the owner opened the live Revu file, looked at the
markups against the drawing and said the lines did not sit on the drawn lines.
He was right. This records what was actually wrong, why it survived every check
the project had, and what changed.

---

## 1. The single wrong premise

`fill_layers.py` opens with:

> the grey "solid" fill (#E5E5E5) is **not a vector path** - `get_drawings`
> returns no such fill. It is a PDF tiling pattern

That is false for this drawing set. On DEMO-001-04 `get_drawings()` returns **278
paths whose fill colour is the grey**, and their union has long, smooth,
continuous edges - one run measured **1131.84 pt unbroken** along the pavement
edge. The premise was checked once, on one sample, and then inherited.

Everything downstream followed from it:

- `render_viewport()` rasterises the sheet at **90 DPI**;
- `split_pavement()` masks that raster by exact colour;
- boundaries are traced along **pixel edges** and simplified.

A pixel-edge boundary can only ever land on a pixel boundary. At 90 DPI one
pixel is 0.8 pt, about 7 cm on the ground at 1:250. That alone would be
tolerable. What is not tolerable is the failure mode: **wherever another element
is drawn on top of the fill - the black dashed edge-of-pavement line, the survey
dots, a label box - the colour mask has a hole there**, and the traced boundary
detours around the hole instead of running through it.

Measured on the Sheet 04 clean segment: the traced boundary sat 3-5 pt outside
the drawn edge on average and **dropped up to 20 pt (about 1.8 m) into the
pavement** at each dash.

## 2. Why every check passed anyway

The project had, and ran, all of these:

| check | what it proves | why it missed this |
|---|---|---|
| `polygon_health` | the ring is simple, not spiked | a wrong boundary is still a simple ring |
| pairwise overlap = 0 | items do not double-count | two wrong neighbours can tile perfectly |
| sum == union | no gaps between items | same |
| area reconciles to the manifest | arithmetic is consistent | the manifest came from the same trace |
| host read-back matches | the write round-tripped | proves storage, not placement |

Every one of those is **internally consistent**. Not one of them compares the
markup against the drawing. The method document already said to render and look
(steps 0 and 10) - what actually happened was looking at the *tracer's own*
overlay PNG, which is drawn from the same coordinates by the same code, at a
zoom where a 20 pt notch is two pixels.

**The check that works**: render the base PDF at high zoom and draw the markup
path *as read back from the host* over it. Nothing else in this list can catch a
boundary that is wrong but self-consistent.

## 3. What the numbers looked like

Objective signature of a raster trace - vertex count and mean segment length for
a simple corridor band:

| markup | pts | mean segment | verdict |
|---|---|---|---|
| Sheet 04 widening N, raster-traced | **131** | **8.3 pt** | traced from pixels |
| Sheet 04 widening N, vector-derived | 11 | 93.6 pt | follows the drawing |
| Sheet 03 widening N | 7 | 326.8 pt | never raster-traced |
| Sheet 03 ditch N | 9 | 95.3 pt | never raster-traced |
| Sheet 05 widening N | 29 | 103.9 pt | traced, but at drawing-vertex scale |

A hundred-plus vertices at 8 pt spacing on a straight band is the tell.

The same defect hit a **length** item even harder, because a zigzag adds length
directly: Sheet 04's two gravel shoulders read 95.72 m and 111.73 m over a
segment that is **43.00 m** long - out by 2.2x and 2.6x.

## 4. Why Sheet 03 came out fine, and why it still took many passes

Sheet 03 was never raster-traced. Its markups are 2-13 point paths built from
drawn features and printed dimensions, so their lines sit where they should.

The many passes it took were spent on a different class of problem entirely -
**reading the drawing, not tracing it**:

- the mill-and-overlay legend swatch is a solid fill, not a hatch, so the item
  was recorded `NOT_PRESENT` while 978 sq m of it lay on the sheet;
- geometry was drawn once with profile-viewport coordinates, giving an area
  exactly 5.00x out, blamed for two days on a "Bluebeam artifact";
- a driveway polygon swallowed the landscaped area beside it;
- ditch flow arrows and vegetation scallops were read as one feature.

Those are interpretation errors. They are fixed by legend discipline, viewport
checks and printed-dimension cross-checks - all of which now exist. They are
**not** what went wrong on Sheets 04/05, and the tooling built to prevent them
does nothing about boundary quality.

## 5. What the drawing actually offers

For each thing a takeoff needs, the vector content already carries it:

| needed | vector source |
|---|---|
| edge of pavement | union of the grey-filled paths; sample at 2 pt, simplify at 0.3 pt |
| widening / mill-overlay interface | ends of the X-hatch strokes - the hatch is clipped exactly at the band edge, so its endpoints lie *on* the boundary |
| full-depth asphalt R&R | the RGB-178 hatch strokes, same logic |
| structures to count | `symbols.find_circles` (already vector, and it worked) |
| cross-section surfaces | `cross_sections` (already vector, and it worked) |

Note the pattern: **the two modules that read vectors produced correct results
the first time; the module that rasterises did not.**

## 6. Validation that the new boundaries are right

Sheet 04 prints `6.90m` centreline-to-edge on both sides, so 13.80 m expected.

- vector-derived edges: **14.02 m** (0.22 m over, about one line width)
- raster-traced edges: outside that, and the widening bands were 26 % high

Second, independent formulation as a cross-check - mill-and-overlay taken as the
*unhatched gap* rather than as the difference of two hatch envelopes - gives
115.10 / 389.40 / 88.99 against the written 114.41 / 390.10 / 89.07. Two
different readings of the same drawing agree to 0.7 sq m.

## 7. What still blocks a clean job

1. **Nothing in the repository builds geometry from the fill vectors.** The
   working method exists only as a scratch script. It belongs in the codebase.
2. **The band model cannot describe an intersection.** North band / middle /
   south band breaks where two roads cross, where four curb returns interrupt
   the edge, and where the hatch runs across the full width (Sheet 05 at
   1+320-1+345, the whole of Sheet 04 east of 1+183.4).
3. **A Bluebeam polygon markup holds one ring.** No holes, no multi-part; a
   region with a patch cut out of it has to be several markups.
4. **There is no automated placement check.** The render-and-compare that caught
   this was done by hand. It should be a callable that takes a markup path and
   returns how much of it lies on the layer it claims.
5. **The file has still never been saved.** Every correction in this document
   lives only in the open Revu session.
