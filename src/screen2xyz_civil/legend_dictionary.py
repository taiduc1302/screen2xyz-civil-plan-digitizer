"""Discover boxed drawing legends and propose label-to-layer associations.

No project colour dictionary is used. OCR supplies labels, visible vector
swatches supply appearance, and occurrences outside the legend supply layer
candidates. This is identification evidence, never a boundary or scope decision.
    Complex symbol-column legends remain explicitly unresolved by this pass.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import statistics


def _inside(a, b, pad=0):
    return a[0]>=b[0]-pad and a[1]>=b[1]-pad and a[2]<=b[2]+pad and a[3]<=b[3]+pad


def _area(r):
    return max(0,r[2]-r[0])*max(0,r[3]-r[1])


def _union(rects):
    return [min(r[0] for r in rects),min(r[1] for r in rects),
            max(r[2] for r in rects),max(r[3] for r in rects)]


def _rgb(colour):
    return tuple(round(x*255) for x in colour) if colour is not None else None


def boxed_legends(words, rectangle_candidates, page_area):
    """Smallest enclosing vector box around each OCR legend heading."""
    found=[]
    for word in words:
        label=word['text'].strip().upper()
        if label not in ('LEGEND','LEGEND:','SYMBOL LEGEND','SYMBOLS LEGEND','LINETYPE LEGEND','KEY'):
            continue
        w=word['rect_view']
        candidates=[r for r in rectangle_candidates if _inside(w,r,2)
                    and _area(r)>_area(w)*8 and _area(r)<page_area*.4
                    and r[3]-w[3]>25]
        if not candidates:
            # An unboxed paving key can still be located by a repeated column
            # of small swatch rectangles below its heading. The inferred box
            # is only an OCR search region, never a construction boundary.
            swatches=[r for r in rectangle_candidates if r[1]>w[3] and abs(r[0]-w[0])<30
                      and 10<r[2]-r[0]<80 and 5<r[3]-r[1]<40]
            columns=defaultdict(list)
            for r in swatches:columns[round(r[0]/5)*5].append(r)
            repeated=[rs for rs in columns.values() if len(rs)>=3]
            if repeated:
                rs=max(repeated,key=len);extent=_union(rs)
                nearby=[v['rect_view'] for v in words if v['rect_view'][0]>extent[2]
                        and v['rect_view'][0]<extent[2]+40 and w[3]<v['rect_view'][1]<extent[3]+30]
                if nearby:
                    rect=_union([w,extent]+nearby)
                    rect=[rect[0]-3,rect[1]-3,rect[2]+3,rect[3]+3]
                    found.append({'heading':word,'rect_view':rect,'status':'REPEATED_SWATCH_COLUMN_CANDIDATE'})
                    continue
            found.append({'heading':word,'rect_view':None,'status':'NO_ENCLOSING_VECTOR_BOX'})
            continue
        rect=min(candidates,key=_area)
        if any(x['rect_view']==rect for x in found):continue
        found.append({'heading':word,'rect_view':rect,'status':'BOX_CANDIDATE'})
    return found


def pair_labels(words, swatches):
    """Nearest left/right swatch by vertical interval, preserving ambiguity.

    Horizontal separation discriminates adjacent legend columns. Wrapped OCR
    lines can share a swatch; equally plausible associations stay unresolved.
    """
    pairs=[{'swatch':s,'words':[],'ambiguous_words':[]} for s in swatches]
    unpaired=[]
    for w in words:
        r=w['rect_view'];cy=(r[1]+r[3])/2; ranked=[]
        for i,s in enumerate(swatches):
            b=s['rect_view']
            dx=max(b[0]-r[2],r[0]-b[2],0)
            if dx<=0 or dx>max(150,(r[2]-r[0])*2):continue
            dy=max(b[1]-cy,cy-b[3],0)
            ranked.append((dy+dx*.12,i))
        ranked.sort()
        if not ranked or ranked[0][0]>max(30,(r[3]-r[1])*2):
            unpaired.append(w);continue
        if len(ranked)>1 and abs(ranked[1][0]-ranked[0][0])<1:
            for _,i in ranked[:2]:pairs[i]['ambiguous_words'].append(w)
        else:pairs[ranked[0][1]]['words'].append(w)
    for pair in pairs:
        lines=[]
        for w in sorted(pair['words'],key=lambda w:sum(w['rect_view'][1::2])/2):
            b=w['rect_view'];cy=(b[1]+b[3])/2;h=b[3]-b[1]
            if lines and abs(cy-lines[-1][0])<=.55*max(h,lines[-1][1]):lines[-1][2].append(w)
            else:lines.append([cy,h,[w]])
        pair['words']=[w for line in lines for w in sorted(line[2],key=lambda w:w['rect_view'][0])]
        pair['label']=' '.join(w['text'] for w in pair['words'])
        pair['status']='AMBIGUOUS_LABEL' if pair['ambiguous_words'] else ('PAIRED' if pair['words'] else 'UNLABELLED')
    return pairs,unpaired


def appearance_signature(objects):
    """Translation-independent colour/angle/spacing evidence; plotted duplicates removed."""
    groups=defaultdict(list);seen=set()
    for o in objects:
        key=(tuple(round(v,2) for v in o['rect_view']),o['stroke'],o['fill'],
             tuple(tuple(round(v,2) for v in line) for line in o['segments']),
             tuple(tuple(round(v,2) for v in curve) for curve in o.get('curves',[])))
        if key in seen:continue
        seen.add(key)
        col=o['fill'] if o['fill'] is not None else o['stroke']
        if col is not None:groups[tuple(col)].append(o)
    result=[]
    for colour,paths in sorted(groups.items()):
        angles=Counter();intercepts=defaultdict(set);lengths=[];widths=[];curves=set()
        for o in paths:
            widths.append(o['width'])
            r=o['rect_view'];size=max(r[2]-r[0],r[3]-r[1],.001)
            if o.get('curves'):
                curves.add(tuple(tuple(round((v-r[i%2])/size,2) for i,v in enumerate(c)) for c in o['curves']))
            # Filled polygon tessellation does not describe hatch directions.
            if o['fill'] is not None:continue
            for x0,y0,x1,y1 in o['segments']:
                length=math.hypot(x1-x0,y1-y0)
                if length<.2:continue
                angle=round(math.degrees(math.atan2(y1-y0,x1-x0))%180/2)*2%180
                angles[angle]+=length;lengths.append(length)
                rad=math.radians(angle)
                intercepts[angle].add(round(-x0*math.sin(rad)+y0*math.cos(rad),1))
        total=sum(angles.values())
        dominant=[a for a,n in angles.most_common() if n>=total*.12]
        pitch={}
        for a in dominant:
            values=sorted(intercepts[a]);gaps=[b-a for a,b in zip(values,values[1:]) if b-a>.3]
            if gaps:pitch[str(a)]=round(statistics.median(gaps),2)
        result.append({'rgb':list(colour),'objects':len(paths),'filled_objects':sum(o['fill'] is not None for o in paths),
                       'angles_deg':sorted(dominant),'pitch_pt':pitch,
                       'median_segment_pt':statistics.median(lengths) if lengths else None,
                       'median_width_pt':statistics.median(widths),
                       'curve_shapes':sorted(curves),
                       'bounds_view':_union([o['rect_view'] for o in paths])})
    return result


def match_signatures(swatch, layers):
    """Match colour plus geometry; ties preserved and colour-only is weak."""
    matches=[]
    meaningful=[s for s in swatch if min(s['rgb'])<=245]
    # A hatch's shared pale background cannot identify the hatch layer.
    chromatic=[s for s in meaningful if max(s['rgb'])>=20]
    preferred=chromatic or meaningful
    strokes=[s for s in preferred if s['angles_deg'] and not s['filled_objects']]
    primary=strokes or preferred
    for name,signature in layers.items():
        components=[]
        for a in primary:
            for b in signature:
                if max(abs(x-y) for x,y in zip(a['rgb'],b['rgb']))>2:continue
                aa=set(a['angles_deg']);bb=set(b['angles_deg'])
                angle_agrees=bool(aa) and all(any(min(abs(x-y),180-abs(x-y))<=3 for y in bb) for x in aa)
                fill_agrees=bool(a['filled_objects']) and bool(b['filled_objects'])
                curve_agrees=bool(a.get('curve_shapes')) and any(x==y for x in a['curve_shapes'] for y in b.get('curve_shapes',[]))
                components.append({'rgb':a['rgb'],'angle_subset':angle_agrees,'fill_agrees':fill_agrees,
                                   'curve_shape_agrees':curve_agrees,
                                   'score':.9 if curve_agrees else (.8 if angle_agrees or fill_agrees else .4)})
        if components:
            matches.append({'layer':name or None,'score':max(c['score'] for c in components),'components':components})
    return sorted(matches,key=lambda x:(-x['score'],x['layer'] or ''))


def _paths(page):
    """Represent vector paths in displayed coordinates (all rotations)."""
    out=[];rectangles=[];matrix=page.rotation_matrix
    for o in page.get_drawings():
        r=list(o['rect']*matrix);segments=[];curves=[]
        for item in o['items']:
            pairs=[]
            if item[0]=='l':pairs=[(item[1],item[2])]
            elif item[0]=='c':
                curves.append([v for point in item[1:] for v in tuple(point*matrix)])
            elif item[0] in ('re','qu'):
                q=item[1]
                points=([q.tl,q.tr,q.br,q.bl,q.tl] if item[0]=='re'
                        else [q.ul,q.ur,q.lr,q.ll,q.ul])
                pairs=list(zip(points,points[1:]))
                if len(o['items'])==1 and r[2]-r[0]>10 and r[3]-r[1]>8:rectangles.append(r)
            for a,b in pairs:
                a,b=a*matrix,b*matrix;segments.append([a.x,a.y,b.x,b.y])
        out.append({'rect_view':r,'segments':segments,'curves':curves,'stroke':_rgb(o['color']),
                    'fill':_rgb(o['fill']),'width':o['width'] or 0,
                    'layer':o.get('layer',''),'seqno':o.get('seqno')})
    return out,rectangles


def _visible(paths, image, scale):
    """Conservative rendered-colour witness; not an exact clipping substitute.

    A witness checks pixels near interior/segment samples. Same-colour
    overprinting remains indistinguishable and is declared in output.
    """
    import numpy as np
    rgb=np.asarray(image.convert('RGB'));kept=[]
    for o in paths:
        colour=o['fill'] if o['fill'] is not None else o['stroke']
        if colour is None:continue
        r=o['rect_view'];samples=[]
        if o['fill'] is not None:samples.append(((r[0]+r[2])/2,(r[1]+r[3])/2))
        else:
            samples.extend(((a+c)/2,(b+d)/2) for a,b,c,d in o['segments'][:12])
            if not samples:samples=[((r[0]+r[2])/2,r[1]),(r[0],(r[1]+r[3])/2)]
        for x,y in samples:
            px,py=round(x*scale),round(y*scale)
            if not (0<=px<rgb.shape[1] and 0<=py<rgb.shape[0]):continue
            patch=rgb[max(0,py-2):min(rgb.shape[0],py+3),max(0,px-2):min(rgb.shape[1],px+3)]
            if patch.size and (np.abs(patch.astype(int)-colour).max(axis=2)<=10).any():
                kept.append(o);break
    return kept


def legend_dictionary(pdf, *, out_dir, pages=None, adapter=None, word_evidence=None):
    """Discover boxed legends and retain an auditable per-set proposal record.

    Output directory must be new. Optional word_evidence maps page indices to
    earlier read_words results; source/page are checked before reuse.
    """
    import pymupdf as fitz
    from PIL import Image
    from .sheet_text import read_words,RapidOcrAdapter
    target=Path(out_dir);target.mkdir(parents=True,exist_ok=False)
    pdf=Path(pdf).resolve();engine=adapter or RapidOcrAdapter()
    report={'pdf':str(pdf),'status':'AI_PROPOSED','pages':[],'layer_inventory':[],
            'limitations':['Boxed legends and repeated rectangular swatch columns; complex symbol columns remain unresolved.',
                          'Rendered colour witnesses do not distinguish coincident same-colour overprints.',
                          'Associations are appearance candidates, not quantity or scope approval.']}
    with fitz.open(pdf) as doc:
        for index in (range(len(doc)) if pages is None else pages):
            page=doc[index]
            e=(word_evidence or {}).get(index)
            if e is not None:
                if Path(e['pdf']).resolve()!=pdf or e['page_index']!=index:raise ValueError('OCR source mismatch')
            else:e=read_words(pdf,index,None,out_png=target/f'page_{index+1:02d}_ocr.png',dpi=160,max_dimension=5200,adapter=engine)
            (target/f'page_{index+1:02d}_words.json').write_text(json.dumps(e,indent=2),encoding='utf-8')
            paths,rectangles=_paths(page)
            legends=boxed_legends(e['words'],rectangles,page.rect.get_area())
            record={'page_index':index,'rotation':page.rotation,'legends':[],
                    'heading_count':len(legends),'status':'NO_BOXED_LEGEND_FOUND' if not legends else 'CANDIDATES'}
            # Render at two pixels/point, no antialiasing, to witness exact pens.
            aa=fitz.TOOLS.show_aa_level()
            try:
                fitz.TOOLS.set_aa_level(0)
                pix=page.get_pixmap(matrix=fitz.Matrix(2,2),annots=False)
            finally:fitz.TOOLS.set_aa_level(aa['graphics'])
            im=Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
            visible=_visible(paths,im,2)
            outside=[o for o in visible if not any(l['rect_view'] and _inside(o['rect_view'],l['rect_view'],1) for l in legends)]
            layer_objects=defaultdict(list)
            for o in outside:layer_objects[o['layer']].append(o)
            layer_signatures={name:appearance_signature(objs) for name,objs in layer_objects.items()}
            report['layer_inventory'].append({'page_index':index,'signatures':layer_signatures})
            for number,legend in enumerate(legends):
                box=legend['rect_view']
                if box is None:record['legends'].append(legend);continue
                heading=legend['heading']['rect_view']
                words=[w for w in e['words'] if _inside(w['rect_view'],box,2) and w['rect_view'][1]>heading[3]-2]
                # Repeated label left margins locate a swatch column without
                # consulting layer names or a project's predefined colours.
                margins=Counter(round(w['rect_view'][0]/8)*8 for w in words)
                label_x=[x for x,n in margins.items() if n>=2 and x>box[0]+20]
                swatches=[]
                for x in sorted(label_x):
                    col=[o for o in visible if _inside(o['rect_view'],box,1)
                         and o['rect_view'][2]<x-2 and o['rect_view'][0]>max(box[0]+4,x-110)
                         and o['rect_view'][1]>heading[3]+2 and o['rect_view'][3]<box[3]-2]
                    # Merge vertical overlap of non-text swatch parts, including
                    # dot tessellation. Blank vertical gaps separate entries.
                    groups=[]
                    for o in sorted(col,key=lambda o:o['rect_view'][1]):
                        r=o['rect_view']
                        if groups and r[1]<=groups[-1]['rect_view'][3]+1.5:
                            groups[-1]['objects'].append(o);groups[-1]['rect_view']=_union([groups[-1]['rect_view'],r])
                        else:groups.append({'rect_view':r[:],'objects':[o]})
                    for g in groups:
                        if not any(_inside(g['rect_view'],s['rect_view'],2) for s in swatches):swatches.append(g)
                pairs,unpaired=pair_labels(words,swatches)
                entries=[]
                for pair in pairs:
                    swatch=pair.pop('swatch')
                    # A rectangular swatch frame is packaging, not its symbol.
                    content=[o for o in swatch['objects'] if not (o['stroke']==(0,0,0) and o['fill'] is None
                             and _area(o['rect_view'])>0 and all(abs(a-b)<.5 for a,b in zip(o['rect_view'],swatch['rect_view']))
                             and len(o['segments'])==4 and not o.get('curves'))]
                    sig=appearance_signature(content)
                    colours=Counter(im.crop(tuple(round(v*2) for v in swatch['rect_view'])).getdata()) if _area(swatch['rect_view']) else Counter()
                    pair.update({'swatch_rect_view':swatch['rect_view'],'signature':sig,
                                 'signature_status':'VECTOR_APPEARANCE' if sig else 'RASTER_OR_UNEXTRACTED_VECTOR_SWATCH',
                                 'rendered_colours':[{'rgb':list(c),'pixels':n} for c,n in colours.most_common(12)],
                                 'matching_layers':match_signatures(sig,layer_signatures)})
                    entries.append(pair)
                crop=im.crop(tuple(round(v*2) for v in box));image_path=target/f'page_{index+1:02d}_legend_{number+1}.png';crop.save(image_path)
                legend.update({'entries':entries,'unpaired_words':unpaired,'image':str(image_path.resolve()),'render_checked':False})
                record['legends'].append(legend)
            report['pages'].append(record)
            (target/'dictionary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    # Match against all pages, retaining page provenance and equal candidates.
    for page in report['pages']:
        for legend in page['legends']:
            for entry in legend.get('entries',[]):
                matches=[]
                for inventory in report['layer_inventory']:
                    for match in match_signatures(entry['signature'],inventory['signatures']):
                        match['page_index']=inventory['page_index'];matches.append(match)
                entry['matching_layers']=sorted(matches,key=lambda m:(-m['score'],m['page_index'],m['layer'] or ''))
    (target/'dictionary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report
