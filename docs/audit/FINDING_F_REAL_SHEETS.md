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
