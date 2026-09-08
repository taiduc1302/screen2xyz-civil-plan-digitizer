"""Prototype for finding F: read the linetype gap as a cluster, not a percentile.

NOT a patch. It is the instrument the numbers in FINDING_F_REAL_SHEETS.md
"a measured direction" section were taken with, and it removes every welded
gap of blank paper without establishing that the resulting length is right -
see the open question in that section before treating it as a fix.

    PYTHONPATH=src python docs/audit/linetype_mode_prototype.py \
        src pilot/24-047/working/IssuedForTender_BASE.pdf

Reads the drawing in place and prints JSON; embeds no drawing data.
"""
import sys, json, math
src, pdf = sys.argv[1], sys.argv[2]
sys.path.insert(0, src)
import pymupdf
from screen2xyz_civil.cad_layers import objects_on_layer, printed_objects, layer_dictionary
from screen2xyz_civil.layer_chains import (_as_points, _length, chain_fragments,
                                           nearest_gap_stats, _endpoints,
                                           MIN_GAP_TOL, GAP_TOL_FACTOR, LATERAL_TOL)

def raw_gaps(fragments):
    ends = _endpoints(fragments); gaps=[]
    for i, ea, pa, ha in ends:
        ux, uy = math.cos(ha), math.sin(ha); best=None
        for j, eb, pb, hb in ends:
            if j==i: continue
            dx, dy = pb[0]-pa[0], pb[1]-pa[1]
            if abs(dx*uy-dy*ux) > LATERAL_TOL or dx*ux+dy*uy < 0: continue
            d=math.dist(pa,pb)
            if best is None or d<best: best=d
        if best is not None: gaps.append(best)
    gaps.sort(); return gaps

#: A break is this many times the linetype's own gap, at least.
MODE_SPLIT_RATIO = 3.0
#: The linetype must account for at least this share of the measured gaps.
MODE_MIN_SHARE = 0.30

def linetype_gap(gaps):
    """(p90 of the linetype cluster, share, split_ratio).

    The linetype gap is the population the MEDIAN gap belongs to: on a layer
    that is mostly dashes, most gaps are the linetype's own. So the split is
    the first big step ABOVE the median, never inside the low mode - that is
    what stops the cluster collapsing onto a floor tolerance.
    """
    if not gaps: return None, 0.0, 0.0
    n=len(gaps)
    mid=n//2
    best_i, best_r = None, 1.0
    for i in range(mid, n-1):
        lo, hi = gaps[i], gaps[i+1]
        if lo <= 0: continue
        r = hi/lo
        if r > best_r: best_r, best_i = r, i
    if best_i is None or best_r < MODE_SPLIT_RATIO:
        return gaps[max(0, math.ceil(0.9*n)-1)], 1.0, best_r      # unimodal: as now
    cluster = gaps[:best_i+1]
    share = len(cluster)/n
    m=len(cluster)
    return cluster[max(0, math.ceil(0.9*m)-1)], share, best_r

MPU=20/226.8
doc=pymupdf.open(pdf)
WANT=("ditbtm","dittop","ditch","pavement edge","gravel","curb")
out=[]
for r in layer_dictionary(doc):
    full=getattr(r.layer,"name",None) or r.layer.short
    if not any(w in str(full).lower() for w in WANT): continue
    for pi in r.pages:
        objs=objects_on_layer(doc,pi,full); printed_objects(doc,pi,full,objs)
        frags=[f for f in (_as_points(o) for o in objs if o.get("printed",True)) if len(f)>=2]
        if len(frags)<2: continue
        gaps=raw_gaps(frags)
        if not gaps: continue
        st=nearest_gap_stats(frags)
        cur=max(MIN_GAP_TOL, GAP_TOL_FACTOR*st["p90"])
        lt, share, ratio = linetype_gap(gaps)
        new = None if lt is None else max(MIN_GAP_TOL, GAP_TOL_FACTOR*lt)
        def phantom(tol):
            if tol is None: return 0.0
            rep=chain_fragments(frags, gap_tol=tol); welds=[]
            for ch in rep["chains"]:
                prev=None
                for mi in ch["members"]:
                    f=frags[mi]
                    if prev is not None:
                        welds.append(min(math.dist(prev[0],f[0]),math.dist(prev[0],f[-1]),
                                         math.dist(prev[1],f[0]),math.dist(prev[1],f[-1])))
                    prev=(f[0],f[-1])
            th=max(4*st["median"],20.0)
            return sum(w for w in welds if w>th)*MPU
        def cl(tol):
            if tol is None: return (0,0.0)
            rep=chain_fragments(frags, gap_tol=tol)
            return (len(rep["chains"]), rep["total_length"]*MPU)
        c_cur, l_cur = cl(cur); c_new, l_new = cl(new)
        out.append({"chains_cur":c_cur,"chains_new":c_new,"len_cur":l_cur,"len_new":l_new,
                    "page":pi,"layer":str(full).split("|")[-1],"n":len(gaps),
                    "median":st["median"],"p90":st["p90"],"cur_tol":cur,
                    "new_tol":new,"share":share,"ratio":ratio,
                    "phantom_cur":phantom(cur),"phantom_new":phantom(new)})
print(json.dumps(out,default=float))

