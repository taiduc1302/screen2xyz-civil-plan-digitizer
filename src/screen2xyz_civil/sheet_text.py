"""Local OCR of printed sheet content, with native PDF (raw-frame) evidence.

Windows OCR is optional and injectable. No PDF is saved or modified. Layer
selection uses the renderer so viewport clips remain authoritative. OCR is
proposal evidence: an unrecognized cell remains empty, never inferred.
"""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Iterable

from .ocr import OcrAdapter, OcrAdapterError, WindowsOcrAdapter, OcrResult, OcrLine, OcrWord
from .cad_layers import short_name


class RapidOcrAdapter:
    """Optional local RapidOCR text-span backend, initialized once per run.

    Model weights may be downloaded on first initialization by RapidOCR.
    Recognition runs locally; the source image is never sent to a service.
    Returned boxes are detected text spans, which may contain multiple words.
    """
    def __init__(self):
        from rapidocr import RapidOCR
        self.engine = RapidOCR()

    def extract(self, image: Path, *, language: str = 'en-US') -> OcrResult:
        from .detection import Rect
        result = self.engine(str(image))
        lines = []
        if result.txts is not None:
            for text, box, score in zip(result.txts, result.boxes, result.scores):
                xs, ys = box[:,0], box[:,1]
                word = OcrWord(text, Rect(float(min(xs)),float(min(ys)),float(max(xs)),float(max(ys))),float(score))
                lines.append(OcrLine(text,(word,)))
        return OcrResult('SUCCESS','\n'.join(x.text for x in lines),'RapidOCR (local text spans)',language,0,tuple(lines))


def _box(points):
    return [min(p.x for p in points), min(p.y for p in points),
            max(p.x for p in points), max(p.y for p in points)]


def _corners(rect):
    import pymupdf as fitz
    x0, y0, x1, y1 = rect
    return [fitz.Point(x0, y0), fitz.Point(x1, y0),
            fitz.Point(x1, y1), fitz.Point(x0, y1)]


def read_words(pdf: str | Path, page_index: int, window_raw: Iterable[float] | None,
               *, out_png: str | Path, dpi: float = 216,
               layers: Iterable[str] | None = None, adapter: OcrAdapter | None = None,
               max_dimension: int = 2500) -> dict[str, Any]:
    """Render a window and return words, raw quadrilaterals and display boxes.

    Pixel origin is the actual pixmap origin, including rounding at fractional
    crop coordinates. All four page rotations and nonzero MediaBox origins use
    PDF matrices. Explicit layer names must exist; absent layers never silently
    fall back to the full sheet. Unlayered content remains visible as in Revu.
    """
    import pymupdf as fitz
    if not math.isfinite(dpi) or dpi <= 0 or max_dimension < 64:
        raise ValueError("positive finite DPI and max_dimension >=64 required")
    target = Path(out_png).resolve()
    if target.suffix.lower() != ".png":
        raise ValueError("render output must be PNG")
    if target.exists():
        raise FileExistsError(f"retained render already exists: {target}")
    with fitz.open(str(pdf)) as doc:
        if not 0 <= page_index < len(doc):
            raise ValueError("page_index outside document")
        page = doc[page_index]
        rotation = page.rotation
        # MuPDF's rotated transformation matrix can omit nonzero box offsets.
        # Capture the native transform unrotated, then restore for rendering.
        page.set_rotation(0)
        native_to_page = page.transformation_matrix
        page.set_rotation(rotation)
        raw_to_view = native_to_page * page.rotation_matrix
        view_to_raw = ~raw_to_view
        if window_raw is None:
            clip = page.rect
        else:
            window = list(window_raw)
            if (len(window) != 4 or not all(math.isfinite(v) for v in window)
                    or window[0] >= window[2] or window[1] >= window[3]):
                raise ValueError("window_raw must be a finite ordered rectangle")
            clip = fitz.Rect(_box([p * raw_to_view for p in _corners(window)])) & page.rect
        if clip.is_empty:
            raise ValueError("window outside page")
        scale = min(dpi / 72, max_dimension / max(clip.width, clip.height))
        ocgs = doc.get_ocgs() or {}
        requested = None if layers is None else list(layers)
        wanted = []
        if requested is not None:
            for name in requested:
                hits = [x for x, v in ocgs.items()
                        if v['name'] == name or short_name(v['name']) == name]
                if not hits:
                    raise ValueError(f"layer not found: {name}")
                wanted.extend(hits)
        original = [x for x, v in ocgs.items() if v.get('on', True)]
        try:
            if requested is not None:
                doc.set_layer(-1, on=wanted, off=[x for x in ocgs if x not in wanted])
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip,
                                  alpha=False, annots=False)
        finally:
            if requested is not None:
                doc.set_layer(-1, on=original, off=[x for x in ocgs if x not in original])
        target.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(target))
        engine = adapter or WindowsOcrAdapter(Path(__file__).resolve().parents[2])
        result = engine.extract(target)
        if result.status != 'SUCCESS':
            raise OcrAdapterError(f"OCR failed: {result.status}")
        words = []
        for line_index, line in enumerate(result.lines):
            for word in line.words:
                b = word.bbox
                displayed = [(b.x0 + pix.x) / scale, (b.y0 + pix.y) / scale,
                             (b.x1 + pix.x) / scale, (b.y1 + pix.y) / scale]
                raw = [p * view_to_raw for p in _corners(displayed)]
                words.append({'text': word.text, 'rect_raw': _box(raw),
                              'quad_raw': [[p.x, p.y] for p in raw],
                              'rect_view': displayed, 'confidence': word.confidence,
                              'ocr_line': line_index})
        return {'pdf': str(Path(pdf).resolve()), 'page_index': page_index,
                'coordinate_frame': 'PDF_RAW_BOTTOM_LEFT', 'rotation': page.rotation,
                'window_view': list(clip), 'dpi_actual': scale * 72,
                'pixmap_origin': [pix.x, pix.y], 'image': str(target),
                'layers': requested, 'engine': result.engine,
                'status': 'AI_PROPOSED', 'words': words,
                'raw_text': result.raw_text}


def cells_from_grid(words: list[dict], x_edges: list[float], y_edges: list[float]) -> list[list[dict]]:
    """Assemble cells from *display-frame* grid boundaries, retaining evidence.

    Words crossing a grid border are explicitly flagged. Grid locations can be
    recovered from printed vector lines or supplied as a documented table schema.
    No numeric repair or reference-answer substitution is performed.
    """
    for edges in (x_edges, y_edges):
        if len(edges) < 2 or any(not math.isfinite(x) for x in edges) or any(a >= b for a, b in zip(edges, edges[1:])):
            raise ValueError('grid edges must be finite and strictly increasing')
    rows = []
    for y0, y1 in zip(y_edges, y_edges[1:]):
        row = []
        for x0, x1 in zip(x_edges, x_edges[1:]):
            selected = [w for w in words if x0 <= (w['rect_view'][0] + w['rect_view'][2]) / 2 < x1
                        and y0 <= (w['rect_view'][1] + w['rect_view'][3]) / 2 < y1]
            # Group overlapping baselines before sorting left-to-right. This
            # keeps superscripts in order and preserves stacked Q10/Q100 rows.
            lines = []
            for word in sorted(selected, key=lambda w: (w['rect_view'][1]+w['rect_view'][3])/2):
                b = word['rect_view']
                cy, height = (b[1]+b[3])/2, b[3]-b[1]
                if lines and abs(cy-lines[-1][0]) <= .55*max(height,lines[-1][1]):
                    lines[-1][2].append(word)
                else:
                    lines.append([cy,height,[word]])
            ordered = [sorted(line[2],key=lambda w:w['rect_view'][0]) for line in lines]
            selected = [w for line in ordered for w in line]
            text = '\n'.join(' '.join(w['text'] for w in line) for line in ordered)
            flags = [] if selected else ['EMPTY_CELL']
            if any(w['rect_view'][0] < x0 - 1 or w['rect_view'][2] > x1 + 1
                   or w['rect_view'][1] < y0 - 1 or w['rect_view'][3] > y1 + 1 for w in selected):
                flags.append('WORD_CROSSES_GRID')
            compact = re.sub(r'\s+', '', text)
            value = float(compact) if len(ordered) == 1 and re.fullmatch(r'[+-]?\d+(?:\.\d+)?', compact) else None
            row.append({'text': text, 'numeric_value': value, 'words': selected,
                        'rect_view': [x0, y0, x1, y1], 'flags': flags})
        rows.append(row)
    return rows


def vector_grid(pdf: str | Path, page_index: int, window_view: Iterable[float],
                *, min_span_fraction: float = .65, tolerance: float = 1) -> dict:
    """Recover candidate straight table rules from vector paths in a window.

    This identifies table cells only, never construction feature boundaries.
    Raster tables require an explicit grid or a raster rule detector. As with
    get_drawings(), candidates can include clipped objects. The caller must
    inspect the rendered table before accepting these grid coordinates.
    """
    import pymupdf as fitz
    r = fitz.Rect(window_view)
    xs, ys = [], []
    with fitz.open(str(pdf)) as doc:
        page = doc[page_index]
        for drawing in page.get_drawings():
            for item in drawing['items']:
                pairs = []
                if item[0] == 'l':
                    pairs = [(item[1], item[2])]
                elif item[0] == 're':
                    q = item[1]
                    p = [q.tl, q.tr, q.br, q.bl, q.tl]
                    pairs = list(zip(p, p[1:]))
                for a, b in pairs:
                    a, b = a * page.rotation_matrix, b * page.rotation_matrix
                    if not (r.contains(a) and r.contains(b)):
                        continue
                    if abs(a.x - b.x) <= tolerance and abs(a.y - b.y) >= 15:
                        xs.append(((a.x + b.x) / 2, min(a.y,b.y), max(a.y,b.y)))
                    if abs(a.y - b.y) <= tolerance and abs(a.x - b.x) >= 15:
                        ys.append(((a.y + b.y) / 2, min(a.x,b.x), max(a.x,b.x)))
    def merge(values, span):
        groups = []
        for v in sorted(values):
            if groups and v[0] - groups[-1][-1][0] <= tolerance:
                groups[-1].append(v)
            else:
                groups.append([v])
        kept = []
        for g in groups:
            intervals = []
            for _, lo, hi in sorted(g, key=lambda v:v[1]):
                if intervals and lo <= intervals[-1][1] + tolerance:
                    intervals[-1][1] = max(intervals[-1][1], hi)
                else:
                    intervals.append([lo,hi])
            if sum(b-a for a,b in intervals) >= span * min_span_fraction:
                kept.append(sum(v[0] for v in g) / len(g))
        return kept
    return {'x_edges': merge(xs,r.height), 'y_edges': merge(ys,r.width),
            'source': 'VECTOR_TABLE_RULE_CANDIDATES', 'render_checked': False}


def raster_grid(evidence: dict, *, body_top_view: float | None = None) -> dict:
    """Detect table rules in the retained rendered image, including image tables.

    Optional body_top_view limits the vertical-rule test below merged headers.
    Only cell layout is detected; these rules are not takeoff boundaries.
    """
    import cv2
    import numpy as np
    im = cv2.imread(evidence['image'],cv2.IMREAD_GRAYSCALE)
    if im is None:
        raise ValueError('table image cannot be read')
    scale = evidence['dpi_actual']/72
    ox,oy = evidence['pixmap_origin']
    ink = (im < 120).astype(np.uint8)*255
    horizontal = cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((1,max(20,im.shape[1]//3)),np.uint8))
    start = 0 if body_top_view is None else max(0,int(body_top_view*scale-oy))
    body=ink[start:]
    if body.shape[0]<10:
        raise ValueError('table body outside image')
    vertical = cv2.morphologyEx(body,cv2.MORPH_OPEN,np.ones((max(10,body.shape[0]//5),1),np.uint8))
    def centres(indices):
        groups=[]
        for value in indices:
            if groups and value-groups[-1][-1]<=3:
                groups[-1].append(value)
            else: groups.append([value])
        return [sum(g)/len(g) for g in groups]
    xs=centres(np.flatnonzero((vertical>0).sum(axis=0)>body.shape[0]*.50))
    ys=centres(np.flatnonzero((horizontal>0).sum(axis=1)>im.shape[1]*.65))
    return {'x_edges':[(float(x)+ox)/scale for x in xs],
            'y_edges':[(float(y)+oy)/scale for y in ys],
            'source':'RENDERED_TABLE_RULES', 'render_checked':False}


def structured_table(evidence: dict, grid: dict, kind: str) -> dict:
    """Interpret curb-return or drainage table rows, preserving every cell.

    Column schemas describe the printed table, not expected answers. Drainage
    'Proposed' is a hydraulic scenario, never a construction-status decision.
    """
    rows=cells_from_grid(evidence['words'],grid['x_edges'],grid['y_edges'])
    records=[]
    scenario=None
    for row in rows:
        if kind=='curb':
            if not row or not re.fullmatch(r'C\d+',row[0]['text'].strip()): continue
            names=['segment','bc_station','bc_offset','ec_station','ec_offset',
                   'length_m','radius_m','delta','tangent_m','chord_m',
                   'bc_elev','quarter_elev','half_elev','three_quarter_elev','ec_elev']
            if len(row)!=len(names): raise ValueError('curb grid does not have 15 columns')
            record=dict(zip(names,row))
            record['row_id']=row[0]['text']
        elif kind=='drainage':
            if row[0]['text'] in ('Existing','Proposed'):
                scenario=row[0]['text'];continue
            if len(row)<18 or row[13]['numeric_value'] is None or row[14]['numeric_value'] is None: continue
            names=['location','from_mh','to_mh','area','coefficient','calculated',
                   'sum_axr','time_1','time_2','time_3','rainfall','q10_q100',
                   'slope_percent','diameter_mm','length_m','velocity','qcap','remarks']
            record=dict(zip(names,row[:18]));record['flow_scenario']=scenario
            record['construction_status']='NOT_DETERMINED_BY_HYDRAULIC_TABLE'
        else: raise ValueError('kind must be curb or drainage')
        records.append(record)
    return {'kind':kind,'pdf':evidence['pdf'],'page_index':evidence['page_index'],
            'engine':evidence['engine'],'status':'AI_PROPOSED','grid':grid,
            'rows':records,'row_count':len(records)}
