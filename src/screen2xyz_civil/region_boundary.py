"""Enclosing faces from independently identified drawn linework.

Pattern seeds identify which face to inspect. No pattern hull, analysis box,
or implicit closing segment is ever inserted into the arrangement.
"""
from __future__ import annotations

import math


def enclosing_face(seed_raw, linework, *, metres_per_unit=None, analysis_window=None):
    """Node supplied raw-frame lines and report the smallest face containing seed.

    Each input contains points_raw, layer, optional source_id and boundary_from.
    Supply drawn fragments for strict evidence; chain bridges must be declared
    as CHAIN_GAP_CANDIDATE separately. No endpoint snapping is performed.
    Unclosed paths remain unclosed, even if their implicit area looks plausible.
    """
    from shapely.geometry import LineString,Point,box
    from shapely.ops import polygonize_full,unary_union
    if len(seed_raw)!=2 or not all(math.isfinite(x) for x in seed_raw):
        raise ValueError('finite raw seed required')
    if metres_per_unit is not None and (not math.isfinite(metres_per_unit) or metres_per_unit<=0):
        raise ValueError('positive finite metres_per_unit required')
    sources=[]
    for i,row in enumerate(linework):
        points=row['points_raw']
        if not all(len(p)==2 and all(math.isfinite(x) for x in p) for p in points):
            raise ValueError('finite raw line coordinates required')
        if len(points)<2:continue
        line=LineString(points)
        if line.length==0:continue
        sources.append((line,row.get('source_id',i),row.get('layer'),row.get('boundary_from','DRAWN_LINE')))
    result={'seed_raw':list(seed_raw),'coordinate_frame':'PDF_RAW_BOTTOM_LEFT',
            'status':'NO_CLOSED_DRAWN_FACE','polygon_raw':None,'area_m2':None,
            'render_checked':False,'sides':[],
            'open_side_basis':'PATTERN_EXTENT_UNBOUNDED; no closing geometry invented'}
    if not sources:return result
    noded=unary_union([s[0] for s in sources])
    polygons,cuts,dangles,invalid=polygonize_full(noded)
    result['arrangement']={'faces':len(polygons.geoms),'cut_edges':len(cuts.geoms),
                           'dangles':len(dangles.geoms),'invalid_rings':len(invalid.geoms)}
    point=Point(seed_raw)
    candidates=[p for p in polygons.geoms if p.covers(point)]
    if not candidates:return result
    polygon=min(candidates,key=lambda p:p.area)
    if polygon.boundary.distance(point)<1e-8:
        result['status']='SEED_ON_BOUNDARY';return result
    rings=[polygon.exterior,*polygon.interiors]
    for ring_index,ring in enumerate(rings):
        coordinates=list(ring.coords)
        for a,b in zip(coordinates,coordinates[1:]):
            edge=LineString([a,b]);provenance=[]
            for line,source_id,layer,basis in sources:
                if edge.difference(line.buffer(1e-7)).length<1e-7:
                    provenance.append({'source_id':source_id,'layer':layer,'basis':basis})
            result['sides'].append({'ring_index':ring_index,'points_raw':[list(a),list(b)],'sources':provenance})
    unsupported=any(not side['sources'] or all(s['basis']!='DRAWN_LINE' for s in side['sources']) for side in result['sides'])
    touches=analysis_window is not None and polygon.boundary.intersects(box(*analysis_window).boundary)
    result.update({'status':'UNSUPPORTED_CLOSURE' if unsupported else ('REGION_TOUCHES_THE_ANALYSIS_EDGE' if touches else 'CLOSED_DRAWN_FACE_CANDIDATE'),
                   'polygon_raw':[list(p) for p in polygon.exterior.coords],
                   'holes_raw':[[list(p) for p in ring.coords] for ring in polygon.interiors],
                   'area_raw2':polygon.area,'area_m2':polygon.area*metres_per_unit**2 if metres_per_unit else None,
                   'open_side_basis':None if not unsupported else 'CHAIN_GAP_OR_UNSUPPORTED_EDGE'})
    return result
