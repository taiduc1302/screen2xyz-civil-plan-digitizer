"""Are the layers finding F hits actually hatch/tick symbols rather than lines?

A hatch is many short strokes at one pitch, mostly perpendicular to a
baseline. A line is fewer, longer polylines that continue each other.
chains_on_layer has no notion of the difference, and chaining a hatch is
meaningless whatever the tolerance.

NOTE (2026-09-22): the drawing this reads is no longer tracked - the
repository history was rewritten to remove `pilot/` for publication. The
figures in FINDING_F_REAL_SHEETS.md are historical measurements taken
when it was present; running this needs the owner's copy of that file.
"""
import sys, math, collections, json
sys.path.insert(0,'src')
import pymupdf
from screen2xyz_civil.cad_layers import objects_on_layer, printed_objects, layer_dictionary
from screen2xyz_civil.layer_chains import _as_points, _length, _heading
doc=pymupdf.open('pilot/DEMO-001/working/IssuedForTender_BASE.pdf')
WANT=("ditbtm","dittop","ditch","pavement edge","gravel","curb")
rows=[]
for r in layer_dictionary(doc):
    full=getattr(r.layer,"name",None) or r.layer.short
    if not any(w in str(full).lower() for w in WANT): continue
    for pi in r.pages:
        objs=objects_on_layer(doc,pi,full); printed_objects(doc,pi,full,objs)
        kept=[o for o in objs if o.get("printed",True)]
        frags=[f for f in (_as_points(o) for o in kept) if len(f)>=2]
        if len(frags)<5: continue
        lens=sorted(_length(f) for f in frags)
        med=lens[len(lens)//2]
        # direction of each fragment, folded to [0,180)
        dirs=[math.degrees(_heading(f[0],f[-1])) % 180 for f in frags]
        hist=collections.Counter(int(d//10)*10 for d in dirs)
        top=hist.most_common(2)
        # a hatch: most fragments share one direction and are short
        share=top[0][1]/len(frags)
        perp = sum(1 for d in dirs if abs(((d - top[0][0]) % 180) - 90) < 15)/len(frags)
        rows.append({"page":pi,"layer":str(full).split("|")[-1],"n":len(frags),
                     "med_len":med,"max_len":lens[-1],
                     "dom_dir":top[0][0],"dom_share":share,"perp_share":perp,
                     "outline":r.outline_objects,"stroke":r.stroke_objects})
print(json.dumps(rows,default=float))
