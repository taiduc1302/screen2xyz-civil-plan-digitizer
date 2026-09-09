"""Small one-shot raster ranking baseline; never a detector or certified count.

Inputs are isolated binary ink masks from a legend and candidate crops. Identity
comes from the supplied legend label. Similarity only ranks review candidates;
connecting lines, occlusion, scans and symbol variants require a learned method
and a separately annotated evaluation. No model or corpus is silently fetched.
"""
import math


def _normalise(mask, size=32):
    rows=[list(r) for r in mask]
    if not rows or not rows[0] or any(len(r)!=len(rows[0]) for r in rows):
        raise ValueError('mask must be a nonempty rectangular binary array')
    if any(v not in (0,1,False,True) for r in rows for v in r):
        raise ValueError('mask values must be binary ink, not grayscale')
    ink=[(x,y) for y,row in enumerate(rows) for x,v in enumerate(row) if v]
    if not ink: return set()
    x0,y0=min(x for x,y in ink),min(y for x,y in ink)
    w=max(x for x,y in ink)-x0+1; h=max(y for x,y in ink)-y0+1
    scale=min(size/w,size/h); nw=max(1,round(w*scale)); nh=max(1,round(h*scale))
    ox,oy=(size-nw)//2,(size-nh)//2
    return {(ox+x,oy+y) for y in range(nh) for x in range(nw)
            if rows[y0+min(h-1,int(y*h/nh))][x0+min(w-1,int(x*w/nw))]}


def rank_legend(candidate_mask, legend_masks, *, min_score=0.75, min_margin=0.10):
    """Aspect-preserving ink IoU, abstaining on unknowns and near ties.

    Scores are similarities, not probabilities. Rotation is deliberately not
    discarded: arrow direction may change meaning. Legend boxes/labels and
    candidate boxes must be supplied by separately checked extraction.
    """
    if any(not math.isfinite(v) or not 0<=v<=1 for v in (min_score,min_margin)):
        raise ValueError('thresholds must be finite in [0,1]')
    candidate=_normalise(candidate_mask)
    ranked=[]
    for label,mask in legend_masks.items():
        template=_normalise(mask)
        if not template: continue
        union=candidate|template
        score=len(candidate&template)/len(union) if candidate else 0.0
        ranked.append({'label':label,'score':score})
    ranked.sort(key=lambda r:(-r['score'],str(r['label'])))
    top=ranked[0]['score'] if ranked else 0.0
    margin=top-(ranked[1]['score'] if len(ranked)>1 else 0.0)
    status=('UNKNOWN' if not candidate or not ranked or top<min_score else
            'AMBIGUOUS' if margin<min_margin or (len(ranked)>1 and margin==0) else 'REVIEW_CANDIDATE')
    return {'status':status,'label':ranked[0]['label'] if status=='REVIEW_CANDIDATE' else None,
            'ranked':ranked,'margin':margin,'method':'NORMALISED_INK_IOU_BASELINE',
            'quantity_approved':False}
