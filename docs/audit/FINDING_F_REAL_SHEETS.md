# Finding F — the automatic gap tolerance reads the wrong mode of a bimodal distribution

Measured 2026-09-08 against `task/plan-layer-extraction` at `fb7065c`, using
the tracked pilot drawing `pilot/24-047/working/IssuedForTender_BASE.pdf`.
Reproduce with:

```
PYTHONPATH=src python docs/audit/real_sheet_gap_probe.py \
    src pilot/24-047/working/IssuedForTender_BASE.pdf
```

Findings A–E were established on synthetic PDFs. This one is the first
measured on the actual tender drawing, and it changes what I said about D.

## What it is

`chain_fragments` derives its tolerance as `gap_tol = 1.5 x p90` of the
nearest endpoint gaps. On these sheets the gap distribution is **bimodal**:

- the linetype's own gap, ~2.94 pt (0.26 m at 1:250), thousands of them;
- the jump between separate runs of the same layer, 150–1000 pt.

The p90 lands in the upper mode. The tolerance built from it then welds
across the jumps, and because a chain's length is measured through the
points it concatenates, every welded jump is counted as line.

`E_Ditbtm` and `P_Ditch bottom` are unimodal (p90 ~= median ~= 4.26 pt) and
are unaffected — which is why nothing looked wrong before.

## Measured, on the drawing

Welds larger than `max(4 x median gap, 20 pt)` — i.e. far larger than the
linetype could explain. 11 of 39 layers:

| page | layer | median gap | `gap_tol` | welds | large | largest weld | phantom length |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 7 | `E_Dittop` | 2.94 pt | 1010.52 pt | 54 | 51 | **64.60 m** | **1127.97 m** |
| 2 | `E_Dittop` | 2.94 | 222.57 | 36 | 34 | 15.22 m | 266.24 m |
| 10 | `E_Dittop` | 2.94 | 432.27 | 23 | 19 | 30.15 m | 200.77 m |
| 2 | `P_Ditch top` | 2.94 | 251.19 | 25 | 25 | 14.93 m | 194.86 m |
| 11 | `E_Dittop` | 2.93 | 244.81 | 21 | 20 | 20.74 m | 190.38 m |
| 5 | `E_Dittop` | 2.94 | 432.31 | 18 | 18 | 30.15 m | 178.03 m |
| 3 | `P_Ditch top` | 2.94 | 1451.78 | 3 | 3 | **78.50 m** | 109.34 m |
| 3 | `E_Dittop` | 2.94 | 187.30 | 18 | 15 | 14.77 m | 107.74 m |
| 4 | `E_Dittop` | 2.94 | 187.03 | 22 | 22 | 11.02 m | 99.45 m |
| 10 | `P_Ditch top` | 2.91 | 253.98 | 13 | 13 | 15.30 m | 82.69 m |
| 7 | `P_Ditch top` | 156.54 | 798.55 | 29 | 1 | 61.86 m | 61.86 m |

**2,619 m of blank paper counted as ditch line across those layers.**

The single clearest case is `P_Ditch top` on `page_index` 3, where the
whole layer can be checked against its own drawn ink because every weld is
a jump rather than a dash:

```
printed fragments                21
sum of the fragments' lengths   576.12 pt  = 50.81 m   <- drawn
chains_on_layer total_length   1815.98 pt  = 160.16 m  <- reported
                                                   +109.35 m of blank paper
gap_stats = {median: 2.94, p90: 967.85, max: 967.85, count: 6}
gap_tol   = 1451.78 pt  on a sheet about 1700 pt wide
```

## This corrects what I said about finding D

D was reported as "the p90 index is the maximum while n <= 10", with
`MIN_GAP_SAMPLE = 10` as the fix. That is real, and it is the **only** one
of the eleven layers above that the patch repairs — `page_index` 3, the
6-gap layer. The other ten have samples of 13 to 201 gaps, sail past the
sample guard, and keep their tolerance.

So D is the small-sample special case of F, and
`docs/audit/all_findings_A_B_C_D_E.patch` does not fix F. I would rather
say that plainly than let the patch look more complete than it is.

## A correction to my own first measurement

My first pass measured "excess over the sum of the fragments' own lengths"
and found 39 of 44 layers over-counting by a median of 46%. That metric is
wrong: for a dashed linetype the gaps *are* part of the line, so bridging
them is correct and the excess is expected. `E_Ditbtm`'s +42% is the dash
pattern being correctly restored, not an error. The table above uses the
size of each individual weld instead, which is the distinction that
matters.

## Direction for a fix — not a one-liner

The median is the linetype gap on every layer in the table, so a
median-derived tolerance stops the welding: `E_Dittop` on `page_index` 7
goes from +116% to 0.0%. But it is not a universal answer — on
`P_Ditch top` at `page_index` 7 the median is itself 156.54 pt, because
most of that layer's gaps really are large, and a median basis still welds.

The tolerance wants the *linetype* mode — the smallest dense cluster of
gaps — not any single order statistic over a mixed population. That is a
real change to `nearest_gap_stats`, and it needs the branch author's
judgement about what a layer with no dense cluster should do. My reading is
that it should refuse an automatic tolerance and say so, rather than pick
one; but that is a design call, not mine to make.

## What this does not claim

No bid quantity is shown to be wrong. The one recorded figure I could
compare — `E_Dittop` at 271.4 m in `SCOPE_LEDGER_Sheet03_page3_2026-09-02.md`
— is within ~1% of the drawn ink (274.51 m on `page_index` 4) and nowhere
near the chained 373.97 m, which is consistent with that number having been
taken by another route.

The exposure is live rather than historical: the operator call documented in
`docs/control/NEXT_ACTION.md:45` and in the night brief is
`chains_on_layer(doc, page_index, layer, metres_per_unit=20/226.8)` — no
`gap_tol`, so the automatic tolerance is what a future measurement gets.

Nothing was pushed to `task/plan-layer-extraction`.

## A measured direction, and why it is not yet a patch

`docs/audit/linetype_mode_prototype.py` replaces the p90 with the gap
population the **median** belongs to: the split is the first step of 3x or
more *above* the median, so it can never fall inside the low mode and
collapse the tolerance onto its floor. Measured over the same 42 layers:

| | current | prototype |
| --- | ---: | ---: |
| blank paper welded | 2,619 m | **0 m** |
| layers refused a tolerance | 0 | 0 |
| layers whose tolerance is unchanged | — | 30 of 42 |

An earlier version that searched the whole range for the largest step
scored the same 0 m of phantom but refused a tolerance on 9 layers that
work today and drove 3 more onto the 0.5 pt floor, which would silently
stop them chaining at all. Anchoring the split above the median fixes that;
the phantom figure alone would not have caught it.

### The open question — why this is a direction and not a fix

On `E_Dittop` at `page_index` 7 the prototype's tolerance produces **338
chains from 339 fragments**: essentially nothing joins, and the total lands
exactly on the drawn ink (972.8 m against 972.7 m). The layer has 106 gaps
at 2.9 pt, so a 4.41 pt tolerance should be joining dashes — and it does
not. Whatever those 2.9 pt gaps are, `_links` refuses them for a reason
that is not the tolerance: mutual-best matching, the 25 degree angle test,
or the lateral band.

So the prototype removes the over-count without establishing that what is
left is right. The true length of that layer is somewhere between the raw
ink and a correctly chained figure, and I have not pinned it down.

### A second behaviour found on the way

Chaining is **not monotonic** in `gap_tol` on this layer:

```
tol    4.41 pt -> 338 chains,  972.82 m
tol   10.00 pt -> 337 chains,  973.59 m
tol   20.70 pt -> 336 chains,  975.26 m
tol   50.00 pt -> 258 chains, 1231.58 m
tol 1010.52 pt -> 285 chains, 2103.23 m   <- more tolerance, MORE chains
```

A larger tolerance changes which pairs are mutual-best, so it can break
chains apart rather than merge them. That makes "raise the tolerance until
it looks right" an unsound way to tune a layer by hand, which is worth
knowing independently of finding F.

## Exposure, closed against the authoritative reconciliation

`f5c813e` adds `King_Road_Tender_Reconciliation_v019.xlsx`, which the
readiness audit names as the file that supersedes v018 and carries the live
takeoff quantities. Searched in full:

- **No reference to `E_Dittop` or `P_Ditch top` anywhere in the workbook.**
  The layers finding F distorts are not used as a quantity source at all.
- The one layer-sourced ditch quantity cites `E_Ditbtm`: item 32.30's
  `Takeoff_Source` records "865 m = ALL existing ditch bottoms `E_Ditbtm` on
  sheets 03-06 (343.3 + 177.3 + ...)". That first figure, 343.3 m, is what
  this code path returns for `E_Ditbtm` on `page_index` 2 — so the tier was
  produced by `chains_on_layer`, and `E_Ditbtm` is one of the unimodal
  layers whose tolerance neither the defect nor the prototype changes.
- `Basis_for_Bid` for 32.30 is 345 lin.m (the City's schedule quantity)
  regardless, per decisions D-14 and D-20.

So F is narrower than "a forward risk on 32.30": the quantities that exist
come from the layers it does not touch, and the layers it does touch are
used for nothing. It bites only if a future measurement reaches for a ditch
**top** layer - `E_Dittop` or `P_Ditch top` - which is exactly where the
automatic tolerance welds hundreds of points of blank paper.

## The open question, answered — and it corrects the prototype's premise

I said the prototype's tolerance "should be joining" `E_Dittop`'s 106 gaps
at 2.9 pt and that something in `_links` was wrongly refusing them. That was
wrong, and the correction matters more than the original claim.

Instrumenting `_links` on that layer: of 678 fragment ends, 355 have no
neighbour within 4.41 pt at all, **321 have one but fail the 25 degree
test**, and 2 pass. The angles are not near zero, where a dash continuing
its own line would sit - they cluster at 90 and 180 degrees.

The coordinates say why:

```
fragment 1: (1521.2, 394.3) -> (1521.1, 400.1)   vertical, 5.82 pt
fragment 5: (1459.6, 388.3) -> (1459.6, 399.9)   vertical, 11.64 pt
fragment 0: (1553.3, 400.3) -> (1526.9, 400.1)   horizontal, 26.40 pt
```

The two verticals are 2.94 pt apart and both end on the same horizontal
line. They are not dashes of a line - they are **hachure ticks hanging off
a baseline**, the standard civil symbol for the top of a ditch. `_links`
refuses them correctly. There is no bug there.

So `nearest_gap_stats` on these layers is measuring the **tick pitch**, and
its whole premise - "a dashed linetype has a constant gap, so the 90th
percentile is the linetype's gap" - does not apply to a layer that is not a
linetype at all.

### The layers split cleanly on their own geometry

| layer | median fragment | longest | perpendicular to main axis | F hits |
| --- | ---: | ---: | ---: | --- |
| `E_Dittop` (7 sheets) | **11.64 pt** | 119-132 pt | 36-64% | 7 of 7 |
| `P_Ditch top` (7 sheets) | **11.64 pt** | 70-84 pt | 33-50% | 4 of 7 |
| `E_Ditbtm` (6 sheets) | 8.52 pt | 19-20 pt | 0-33% | none |
| `P_Ditch bottom` (6) | 8.52-16.68 pt | 19-143 pt | 0-49% | none |

The ditch **tops** are a baseline plus ticks; the ditch **bottoms** are
plain dashed lines with uniform short fragments and no perpendicular
component. That is the whole difference, and it is why the bottoms chain
correctly and the tops cannot.

Note the three `P_Ditch top` layers F does *not* hit (pages 4, 5, 11) are
the same kind of layer - their gap distribution simply happened to yield a
small tolerance. **All fourteen ditch-top layers are unchainable; eleven of
them happen to produce an inflated number and three happen to produce a
plausible one.** A plausible number from a meaningless computation is the
worse of the two.

### What this means for the fix

The prototype does not repair these layers either - it fails in the safer
direction, returning the raw ink instead of 2,103 m of welded baseline. The
correct behaviour is not a better percentile: it is to recognise a
composite symbol layer and **refuse to chain it**, the way
`layer_dictionary` already separates `outline_objects` from
`stroke_objects` for the shading layers. Any tolerance at all on a hachure
layer is a number with no meaning behind it.

Probe: `docs/audit/hachure_vs_line_probe.py`.

## Scope, measured over the whole drawing — F is not a ditch-top problem

Every layer on all 13 pages, 446 layer-pages in total.

The raw headline is misleading and worth stating so it is not quoted: 161
layer-pages weld large gaps, totalling **50,529 m**. But the top entries are
`Notes`, `P_Text`, `XREF`, `P_PROFILE GRID`, `P_Road_Txt` and title-block
frames - text and annotation, where chaining is meaningless by construction
and nobody would ask for a length. Counting those metres would be alarmism.

Excluding annotation (text, dimensions, grid, frames, xrefs, symbols,
labels) leaves **302 plausible-geometry layer-pages, 48 of which weld blank
paper, totalling 6,133 m**:

| layer | phantom | what it is |
| --- | ---: | --- |
| `E_Dittop` | 2,170.6 m | ditch top - hachure |
| `E_PL` | 1,088.7 m | property line, profile sheets 8-9 |
| `Abby_Cover Sheet Linework` | 513.3 m | cover sheet |
| `E_Feat_Pt`, `E_Hydro_Pt` | 827.6 m | **point/marker layers** - meaningless to chain, like text |
| `P_Ditch top` | 448.7 m | ditch top - hachure |
| `P_Sw` | 309.4 m | sidewalk - real linework |
| `P_Wall` | 134.9 m | wall - real linework, and quantity-bearing |

My earlier figure - 11 of 39 layers, 2,619 m - was scoped to the
ditch/pavement/curb subset and is still right for it. The drawing-wide
number is 48 of 302 and 6,133 m.

### `P_Wall` is a third failure mode, and neither patch nor prototype helps

`P_Wall` carries a quantity (items 3.03/3.05/3.07). Measured:

```
page_index 10:  drawn  68.14 m  ->  chained 125.46 m   (+84%)
    gap_stats = {median: 248.85, p90: 290.58, max: 290.58, count: 8}
page_index  7:  drawn  68.13 m  ->  chained 103.59 m   (+52%)
    gap_stats = {median: 237.12, p90: 237.12, max: 237.12, count: 2}
```

There is **no low mode at all** - every measured gap is hundreds of points.
So `MIN_GAP_SAMPLE` picks the median (237.12) and gets the same huge
tolerance; the linetype-cluster prototype finds no cluster to take. The
layer simply has no linetype: the walls are genuinely separate objects that
should never be joined to each other, and every statistic derived from
their gaps is meaningless.

`P_Sw` is the ordinary bimodal case by contrast - `median 4.24, p90 186.30`
- and goes from 65.17 m drawn to 140.35 m chained, +115%.

So there are three distinct shapes, and the automatic tolerance handles
none of them: a hachure layer (tick pitch mistaken for a linetype gap), a
bimodal line layer (real breaks pull the p90 into the wrong mode), and a
layer of separate objects with no linetype at all.

## The geometric classifier does not work - measured, not assumed

Yesterday I concluded the fix was to "recognise a composite symbol layer
and refuse to chain it". That does not reduce to a rule. Testing the
sharpest discriminator I could build - are the short fragments
perpendicular to the long ones - over 77 layers:

| | score |
| --- | ---: |
| ditch tops (the target) | 36-100% |
| `E_Fence` p10 | 96% |
| `P_Toe` p4 | 94% |
| `P_Culv` p3 | 71% |

No separating threshold exists. And `P_Toe` is the instructive
counterexample: it scores 94% yet is a perfectly sound dashed line -

```
page_index 3: drawn 74.02 m -> chained 103.27 m
    gap_stats = {median: 8.52, p90: 8.53, max: 298.46, count: 86}
    gap_tol 12.80; the 298 pt outlier is NOT bridged
```

39 joins at about 8.5 pt each account for the whole +29 m. That is dash
restoration working exactly as intended.

So the operative signal is the **shape of the gap distribution**, not
fragment geometry. The hachure finding explains *why* the ditch tops are
bimodal; it is not itself the detector.

### One more thing the P_Toe measurement establishes

`SCOPE_LEDGER_Sheet03_page3_2026-09-02.md` records `P_Toe` at **103.3 m**.
`chains_on_layer` returns **103.27 m**. The ledger takes figures verbatim
from this code path - that pathway is confirmed rather than assumed, which
is what makes the tolerance defect worth fixing even though every quantity
checked so far is sound.
