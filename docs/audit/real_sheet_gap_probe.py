"""Finding F on the real 24-047 sheets: which gaps chaining actually welds.

Run against the tracked pilot drawing:

    PYTHONPATH=src python docs/audit/real_sheet_gap_probe.py \
        src pilot/24-047/working/IssuedForTender_BASE.pdf

Bridging a dashed linetype's own gap (~2.9 pt = 0.26 m at 1:250) is correct:
the line is continuous and the dashes are only how it is drawn. Bridging a
gap of hundreds of points is blank paper counted as line. So the diagnostic
is the size of each welded gap, not the total excess over drawn ink - that
distinction is what separates finding F from a false alarm.

Reads the drawing in place and prints JSON; embeds no drawing data.
"""
import sys, json, math
src, pdf = sys.argv[1], sys.argv[2]
sys.path.insert(0, src)
import pymupdf
from screen2xyz_civil.cad_layers import objects_on_layer, printed_objects, layer_dictionary
from screen2xyz_civil.layer_chains import (_as_points, _length, chain_fragments,
                                           nearest_gap_stats, MIN_GAP_TOL, GAP_TOL_FACTOR)
MPU = 20/226.8
doc = pymupdf.open(pdf)
WANT = ("ditbtm","dittop","ditch","pavement edge","gravel","curb")

def welded_gaps(frags, tol):
    """Gap lengths the chain walk actually jumped, in points."""
    rep = chain_fragments(frags, gap_tol=tol)
    gaps = []
    for ch in rep["chains"]:
        mem = ch["members"]
        if len(mem) < 2:
            continue
        # rebuild the walk: consecutive members are joined end-to-end
        pts = ch["points"]
        # a welded gap shows up as a jump between the end of one fragment and
        # the start of the next; recover it from the member fragments directly
        prev = None
        for mi in mem:
            f = frags[mi]
            if prev is not None:
                gaps.append(min(math.dist(prev[0], f[0]), math.dist(prev[0], f[-1]),
                                math.dist(prev[1], f[0]), math.dist(prev[1], f[-1])))
            prev = (f[0], f[-1])
    return rep, gaps

out=[]
for r in layer_dictionary(doc):
    full = getattr(r.layer, "name", None) or r.layer.short
    if not any(w in str(full).lower() for w in WANT): continue
    for pi in r.pages:
        objs = objects_on_layer(doc, pi, full)
        printed_objects(doc, pi, full, objs)
        kept = [o for o in objs if o.get("printed", True)]
        frags = [f for f in (_as_points(o) for o in kept) if len(f) >= 2]
        if len(frags) < 2: continue
        st = nearest_gap_stats(frags)
        med = st.get("median", 0.0)
        tol = max(MIN_GAP_TOL, GAP_TOL_FACTOR * st.get("p90", 0.0))
        rep, gaps = welded_gaps(frags, tol)
        if not gaps: continue
        # a welded gap far bigger than the linetype's own gap is blank paper
        thresh = max(4 * med, 20.0)   # 20 pt = 1.76 m at 1:250
        big = [g for g in gaps if g > thresh]
        out.append({"page": pi, "layer": str(full).split("|")[-1],
                    "n_gaps": st.get("count"), "median_gap": med, "p90": st.get("p90"),
                    "gap_tol": tol, "welded": len(gaps),
                    "max_welded_pt": max(gaps), "max_welded_m": max(gaps)*MPU,
                    "big_welds": len(big), "big_total_m": sum(big)*MPU,
                    "total_m": rep["total_length"]*MPU})
print(json.dumps(out, default=float))
