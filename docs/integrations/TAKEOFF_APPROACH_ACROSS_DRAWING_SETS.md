# One approach for every drawing set

**Status:** approach, 2026-09-03. Written after two pilot sets (DEMO-001, a
road-widening tender; a firehall site-servicing set) and a survey of the
company's own drawing archive. It says what stays fixed from one set to the
next, what changes, and what to read first.

## The question this answers

Two drawing sets look different. The same civil scope - curb, pavement,
storm, ditch, culverts, driveways - is drawn in different pens, different
hatches, different symbols, by different consultants. The day-long failures
on DEMO-001 (raster tracing chasing a hatch pitch, radius fits picking up a
gas line, thirteen numerically clean markups in the wrong place) were all
attempts to recover *identity* from *appearance*. Appearance is the part
that changes per set. So the approach has to rest on the parts that do not.

## What does not change

Four things are constant across every civil set, in this order of strength:

1. **The bid schedule is the list of what to find.** The estimator does not
   read a drawing to see what is there; they read it to find each schedule
   item and to notice what the schedule missed. `takeoff.py`'s rule
   catalogue and the scope ledger are this list, and "no silent miss" is its
   discipline. This is exactly the company's own written procedure for
   roadwork: *identify surface features that apply to the scope, take off
   per tender item on the roadwork drawing and typical section, then the
   removals, then base and subbase* - and its sewer procedure is a checklist
   of item types, each with the attributes to record (size, material,
   in-roadway or boulevard, existing pavement or new).
2. **The drawing names its own vocabulary.** A legend, a callout leader, a
   printed station/offset, a table row: these are the drawing telling you
   what a thing *is* and where it *runs*. `feature_identity` ranks them and
   refuses anything below them. The legend is per set; the rule that the
   legend is authoritative is not.
3. **The engineer's CAD layers, when the PDF still carries them.** A direct
   export from Civil 3D or AutoCAD keeps every drawing layer as a PDF
   optional content group, and PyMuPDF returns the layer name on every
   drawing object. On DEMO-001 that is 141 names: `P_Curb`, `P_Pavement edge`,
   `P_Ditch top`, `P_Ditch bottom`, `P_Culv`, `E_Culv`, `P_Wall`, `P_Sw`,
   `RD-DW-PRO`, `STM-MH-PRO`, `E_Gas`, `E_Fence`, `Shading 245 (50%)`,
   `XSE_HATCH`. Two conventions cover what has been seen: the house style
   `P_`/`E_` with `-PRO`/`-EXI` on utilities, and the National CAD Standard
   `C-ROAD-CURB-N`. Both are read by `cad_layers.classify_layer_name`.
4. **Geometry is geometry.** A boundary is a drawn line; an outline object
   is a multi-item path while hatch strokes are single-item; arcs are arcs;
   a pattern's extent oscillates at its pitch. None of that depends on the
   set. `polygon_health`, `pattern_edge`, and method step 5a are set-agnostic.

## What changes per set - the "pre-pattern"

Everything that has to be read fresh fits in one small record per set,
confirmed by a person once and then applied everywhere:

| Field | Where it comes from | DEMO-001 example |
|---|---|---|
| Drawing regime per sheet | `cad_layers.document_regime` | `LAYERED_VECTOR`, all 13 sheets |
| Text regime | same | `OUTLINE_TEXT` - 23-56 real words per plan sheet, the rest glyph outlines |
| Layer dictionary | `cad_layers.layer_dictionary` + `hints_present` | `CURB -> P_Curb`, `EDGE_OF_PAVEMENT -> E_Ep, P_Pavement edge`, `DITCH -> P_Ditch bottom, E_Ditbtm, E_Dittop` |
| Legend: pattern/colour/symbol -> meaning | cover-sheet legend + per-sheet key, read from a render | widening cross-hatch, full-depth asphalt R&R, ditch infill |
| Scale and viewports per sheet | method steps 2-3 | plan 1:500, profile 1:50 vertical |
| Sheet index and overlaps | method step 9 | sheets 04-06 overlap; sheet 11 is the rotation-0 sheet |
| Consultant furniture | `sheet_pass.derive_title_block_baseline` | frame layers `18-198 - XTB$0$…` |

The dictionary row `layer -> feature` is a *claim by the engineer*, so it
enters `feature_identity` as `CAD_LAYER_NAME`, which names a feature once the
set's dictionary has been confirmed against the legend or a callout. The
confirmation is one look per layer per set, not one per object. The layer
still does not fix a boundary; the object's own geometry does.

## The three regimes, and what each allows

`cad_layers.document_regime(pdf)` runs first and decides the method:

| Regime | How to tell | Identification | Geometry |
|---|---|---|---|
| `LAYERED_VECTOR` | objects carry `layer` | layer dictionary + legend confirmation | vector objects from the named layer |
| `FLAT_VECTOR` | vectors, no layers | legend swatch, callout, table; pen only narrows | vector objects filtered by pen, checked against a drawn outline |
| `RASTER` | pixels only | legend swatch by eye; symbol matching | raster trace, never as a boundary where a line can be read |

A `FLAT_VECTOR` set whose producer is "Print To PDF" or a PDF printer is a
re-print: the consultant's export had the names and a re-print dropped them
(`REPRINT_LOST_LAYERS`). The firehall civil set arrived that way - 9,033
vectors on one sheet, zero layers. The first action on that finding is a
request for the direct export, not a day of tracing.

In the archive survey (120 drawing-sized PDFs), roughly 45 were layered, 11
flat vector, 64 raster. All three are real work; the method has to cover all
three, and the layered path is the one that removes most of the failure
modes seen on DEMO-001.

## Text: read it from the render

On both pilot sets the drawing text is glyph outlines. `get_text` and the
host's search only see the title block. What the layers give is *which*
text sits *where*: `P_Road_Txt`, `P_Stm_Txt`, `STM-TXT-PRO`, `Notes`,
`P_label.1`. A callout on `STM-TXT-PRO` near a `STM-MH-PRO` object is that
manhole's label; crop it from a render and read it (OCR when tesseract is
installed, eyes otherwise - `symbols.crop_symbol` already does the crop).

## A layer gives identity and candidates, not a finished line

On sheet 04 `P_Pavement edge` is 404 objects with a longest of 39 pt: the
linetype's dashes, its dots (260 zero-length objects), the flattened chords
of the curb-return arcs, and every one of them plotted two or three times
over (one copy per xref that carries the line). `P_Curb` is 83 tick
symbols. `layer_chains.chain_fragments` turns that into continuous lines:
it drops the coincident copies, reads the linetype's gap from the data,
and links fragment ends that face each other **and lie on each other's
axis**. The last condition is the one that matters on this sheet: the
pavement edge runs beside a second dashed line 3.4 pt away - the printed
0.30 m gravel shoulder - whose dashes are as close and as well aligned as
the edge's own, and only the lateral offset tells them apart. Result on
sheet 04: 16 chains, the longest 45 m, one branch reported; on sheet 05
`E_Ep` is 4 chains from 159 fragments. The arcs stay the chords the
engineer plotted, and nothing from another layer can wander in.

That is the geometry step for this regime: **chain fragments within one
layer**, then `polygon_health` / `identification_report` as before. It
replaces the raster trace where layers exist; it does not replace the
thumbnail check - the chains above were rendered over the sheet and looked
at before this paragraph was written. Two things the layer still does not
say: which of two parallel lines on it is the feature (the printed 0.30 m
separation says), and where a line that the linetype breaks at a real gap
ends (the chain ends there, and the sheet decides whether that is the
feature's end or a break to bridge).

## The skeleton, in the order a person works

0. `document_regime` - regime, text regime, dictionary, hints. Stop and
   ask for the direct export on `REPRINT_LOST_LAYERS`.
1. Bid schedule -> rule catalogue -> scope ledger. Every item ends as
   proposed, withheld with a question, or evidence-backed not present.
2. Legend and per-sheet keys, read from a render; record the set's
   pattern/colour/symbol meanings and confirm the layer dictionary rows
   against them. One person, once per set.
3. Viewports, scale, stations (method steps 2-3).
4. For each ledger item: identify (layer + legend, or legend/callout/table
   alone), take geometry from the drawing's own objects on that layer
   (chained), fix the boundary from a drawn line, run the gates.
5. Write, read back by a different path, **look at the thumbnail**, then the
   render overlay for point markers and long bands.
6. Cross-check by an independent printed value where the set gives one
   (curb-return table, drainage table, typical section).

Steps 1, 4-6 are unchanged by the set. Steps 0 and 2 are the per-set
record. Step 3 is per sheet.

## Sources consulted

- Company takeoff procedures (roadwork, storm and sanitary) in the
  estimating archive - the item checklist and the "printed value first"
  rule.
- The firehall pilot's own findings: 86 missed-scope items and 21 RFIs came
  from reading the schedule against the drawings, not from geometry; the
  three quantity corrections there were printed-beats-measured, an
  under-traced lead, and a dashed line that the vector data drew longer than
  the eye had followed.
- PDF optional content: PyMuPDF `get_ocgs` / `get_drawings()["layer"]`
  (https://pymupdf.readthedocs.io/en/latest/recipes-optional-content.html);
  the E-/P- and NCS layer conventions (Autodesk community and the AIA/NCS
  layer guideline as adopted by public owners).
- Legend-informed symbol recognition (Fraunhofer, ECML PKDD 2025): the legend
  as the per-diagram exemplar set - the same idea as the pre-pattern, no
  public code.
- Commercial AI takeoff in 2026: floor-plan-first, self-reported 95-99 %,
  civil and site sheets largely out of scope; the estimator still owns the
  number. Nothing found that reads CAD layers out of the PDF for takeoff.
