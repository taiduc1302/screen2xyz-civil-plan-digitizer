"""Step 0 of any sheet: which kind of drawing is this, and what does it name?

A drawing set arrives in one of three regimes, and the whole method after
this point depends on which:

* ``LAYERED_VECTOR`` - the PDF was exported straight from CAD and carries
  the engineer's layer names as Optional Content Groups. Every drawing
  object then says what the engineer called it: ``P_Curb``,
  ``P_Pavement edge``, ``P_Ditch bottom``, ``STM-MH-PRO``,
  ``Shading 245 (50%)``. The DEMO-001 tender set is this regime: 141 layers,
  and the curb that a day of raster tracing, radius fitting and deleting was
  about sits on its own named layer with 416 objects.
* ``FLAT_VECTOR`` - vector content with no layers. Usually a re-print: the
  consultant's layered export went through "Microsoft: Print To PDF" or a
  PDF printer on the way, and the names were lost. The Brookswood civil IFC
  is this regime (9,033 vectors, zero layers, producer "Print To PDF"). The
  fix is procedural - ask for the direct CAD export - and until then the
  raster/vector methods in ``fill_layers`` and ``symbols`` are the fallback.
* ``RASTER`` - a scan. Nothing but pixels and, sometimes, an OCR text layer.

Independently of that, **text has its own regime**. On the DEMO-001 plan
sheets ``get_text`` returns 23-56 words per sheet - the title block - while
the callouts, stations, notes and legend labels are thousands of glyph
outlines on ``P_Text`` / ``P_Road_Txt`` / ``Notes``. A layer name then says
*which discipline's* text sits *where*; reading it needs OCR of a render.

This module only reports. It does not identify a feature: a layer name is
the engineer's label and goes into ``feature_identity`` as
``CAD_LAYER_NAME``, which names the feature once the set's layer dictionary
has been confirmed against the legend or a callout - engineers do put
objects on the wrong layer. Position still comes from the object's own
geometry (``DRAWN_OUTLINE``), never from the name.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

# --- regimes ---------------------------------------------------------------

LAYERED_VECTOR = "LAYERED_VECTOR"
FLAT_VECTOR = "FLAT_VECTOR"
RASTER = "RASTER"
EMPTY = "EMPTY"

REAL_TEXT = "REAL_TEXT"
OUTLINE_TEXT = "OUTLINE_TEXT"
NO_TEXT = "NO_TEXT"

#: Fewer drawing objects than this and the page is not a vector drawing.
MIN_VECTOR_OBJECTS = 50
#: A plan sheet whose real words fit in a title block has its drawing text
#: drawn as outlines. DEMO-001 plan sheets: 23-56 words, 2,000-20,000 outline
#: objects on text layers.
MAX_TITLE_BLOCK_WORDS = 120

#: Producers that flatten layers on the way through.
_REPRINT_PRODUCERS = ("print to pdf", "pdf printer", "pdfcreator", "cutepdf", "printer")

# --- layer-name convention -------------------------------------------------

PROPOSED = "PROPOSED"
EXISTING = "EXISTING"
DEMOLISH = "DEMOLISH"
UNKNOWN = "UNKNOWN"

KIND_TEXT = "TEXT"
KIND_HATCH = "HATCH"
KIND_FRAME = "FRAME"
KIND_GEOMETRY = "GEOMETRY"

_TEXT_RE = re.compile(r"(text|txt|label|labl|notes|anno|dims|mhno|roadname)", re.I)
_HATCH_RE = re.compile(r"(shading|hatch|patt)", re.I)
_FRAME_RE = re.compile(r"(frame|tbk|logo|xref|cover|title|border|\$)", re.I)

#: Feature hints by keyword. A hint narrows what to look for; it is not an
#: identification until the set's dictionary has been confirmed.
FEATURE_HINTS: tuple[tuple[str, str], ...] = (
    (r"curb", "CURB"),
    (r"pavement edge|\bep\b|_ep$", "EDGE_OF_PAVEMENT"),
    (r"ditch|ditbtm|dittop", "DITCH"),
    (r"culv", "CULVERT"),
    (r"^stm|storm", "STORM"),
    (r"^san|sanit", "SANITARY"),
    (r"^wat|_wat|water", "WATER"),
    (r"^hyd|hydrant", "HYDRANT"),
    (r"gas", "GAS"),
    (r"fence", "FENCE"),
    (r"\bsw\b|_sw$|sidewalk|swk", "SIDEWALK"),
    (r"dwy|-dw-|driveway", "DRIVEWAY"),
    (r"wall", "WALL"),
    (r"veg|tree", "VEGETATION"),
    (r"gravel", "GRAVEL"),
    (r"\btop\b|_top$|\btoe\b|_toe$|slope", "SLOPE_LINE"),
    (r"\bpl\b|_pl$|prop.?line", "PROPERTY_LINE"),
    (r"profile|^prf", "PROFILE_VIEW"),
    (r"^xse|section", "CROSS_SECTION"),
    (r"sign", "SIGN"),
    (r"hydro|power|elec", "HYDRO"),
)


@dataclass(frozen=True)
class LayerName:
    """One layer name, read against the naming convention."""

    name: str
    short: str
    status: str
    kind: str
    hint: str | None

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "short": self.short, "status": self.status,
                "kind": self.kind, "hint": self.hint}


def short_name(name: str) -> str:
    """Strip the xref prefix Civil 3D adds: ``'DEMO-001 - DESIGN|P_Curb'`` -> ``'P_Curb'``."""
    return name.split("|")[-1].strip() if name else ""


def classify_layer_name(name: str) -> LayerName:
    """Read a layer name against the two conventions seen so far.

    Civil 3D house style: ``P_``/``E_`` prefix for proposed/existing,
    ``-PRO``/``-EXI`` suffix on utility layers, ``Shading NNN (pct%)`` for
    fills. National CAD Standard: ``C-ROAD-CURB-N``, one-letter status
    suffix ``N`` new, ``E`` existing, ``D`` demolish.
    """

    s = short_name(name)
    status = UNKNOWN
    if re.match(r"^P[_-]", s) or re.search(r"-PRO(?:-|$)", s):
        status = PROPOSED
    elif re.match(r"^E[_-]", s) or re.search(r"-EXI(?:-|$)", s):
        status = EXISTING
    elif re.match(r"^[A-Z]-[A-Z]{4}(?:-[A-Z]{4}){0,2}-([NED])$", s):
        status = {"N": PROPOSED, "E": EXISTING, "D": DEMOLISH}[s[-1]]

    # Frame before text: a title-block xref's "Frame-Text" is furniture.
    if _HATCH_RE.search(s):
        kind = KIND_HATCH
    elif _FRAME_RE.search(s):
        kind = KIND_FRAME
    elif _TEXT_RE.search(s):
        kind = KIND_TEXT
    else:
        kind = KIND_GEOMETRY

    hint = None
    if kind in (KIND_GEOMETRY, KIND_HATCH):
        for pattern, label in FEATURE_HINTS:
            if re.search(pattern, s, re.I):
                hint = label
                break
    return LayerName(name=name, short=s, status=status, kind=kind, hint=hint)


# --- regime detection ------------------------------------------------------

def _import_pymupdf() -> Any:
    try:
        import pymupdf  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment
        raise RuntimeError("cad_layers needs PyMuPDF (pip install pymupdf)") from exc
    return pymupdf


@dataclass
class PageRegime:
    page_index: int
    rotation: int
    drawing_regime: str
    text_regime: str
    vector_objects: int
    layered_objects: int
    images: int
    real_text_words: int
    layer_names: list[str] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "page_index": self.page_index, "rotation": self.rotation,
            "drawing_regime": self.drawing_regime, "text_regime": self.text_regime,
            "vector_objects": self.vector_objects, "layered_objects": self.layered_objects,
            "images": self.images, "real_text_words": self.real_text_words,
            "layer_names": list(self.layer_names), "findings": list(self.findings),
        }


def _finding(code: str, detail: str, *, blocking: bool = False) -> dict[str, Any]:
    return {"code": code, "severity": "ERROR" if blocking else "WARNING",
            "detail": detail, "blocking": blocking}


def page_regime(doc: Any, page_index: int) -> PageRegime:
    """Say what kind of page this is before any method step runs."""

    page = doc[page_index]
    drawings = page.get_drawings()
    layered = [d for d in drawings if d.get("layer")]
    names = sorted({d["layer"] for d in layered})
    images = len(page.get_images(full=False))
    words = len(page.get_text("words"))

    if layered:
        regime = LAYERED_VECTOR
    elif len(drawings) >= MIN_VECTOR_OBJECTS:
        regime = FLAT_VECTOR
    elif images:
        regime = RASTER
    else:
        regime = EMPTY

    if regime in (LAYERED_VECTOR, FLAT_VECTOR):
        text = OUTLINE_TEXT if words <= MAX_TITLE_BLOCK_WORDS else REAL_TEXT
    else:
        text = REAL_TEXT if words else NO_TEXT

    findings: list[dict[str, Any]] = []
    producer = ((doc.metadata or {}).get("producer") or "").lower()
    if regime == FLAT_VECTOR and any(p in producer for p in _REPRINT_PRODUCERS):
        findings.append(_finding(
            "REPRINT_LOST_LAYERS",
            f"vector content with no layer names, producer {producer!r}. The consultant's "
            "CAD export carried layer names; a re-print dropped them. Ask for the direct "
            "export before spending a day on raster tracing.",
        ))
    if text == OUTLINE_TEXT:
        findings.append(_finding(
            "TEXT_IS_DRAWN_AS_OUTLINES",
            f"{words} real words on a sheet with {len(drawings)} vector objects. Callouts, "
            "stations and legend labels are glyph outlines; get_text and the host's search "
            "will not find them. Read them from a render (OCR or by eye), and use the text "
            "layers to say which discipline's text sits where.",
        ))
    if page.rotation in (90, 270):
        findings.append(_finding(
            "ROTATION_90_270",
            f"page rotation {page.rotation}; host_frame refuses it and the legend on a "
            "rotated cover sheet must be read from the render.",
        ))
    return PageRegime(
        page_index=page_index, rotation=page.rotation, drawing_regime=regime,
        text_regime=text, vector_objects=len(drawings), layered_objects=len(layered),
        images=images, real_text_words=words, layer_names=names, findings=findings,
    )


def document_regime(pdf: str, *, pages: Iterable[int] | None = None) -> dict[str, Any]:
    """Regime per page plus the set-level verdict and the layer dictionary."""

    pymupdf = _import_pymupdf()
    doc = pymupdf.open(str(pdf))
    try:
        indexes = list(pages) if pages is not None else list(range(doc.page_count))
        per_page = [page_regime(doc, i) for i in indexes]
        ocgs = doc.get_ocgs() or {}
        regimes = {p.drawing_regime for p in per_page}
        if LAYERED_VECTOR in regimes:
            verdict = LAYERED_VECTOR
        elif FLAT_VECTOR in regimes:
            verdict = FLAT_VECTOR
        elif RASTER in regimes:
            verdict = RASTER
        else:
            verdict = EMPTY
        return {
            "pdf": str(pdf),
            "creator": (doc.metadata or {}).get("creator") or "",
            "producer": (doc.metadata or {}).get("producer") or "",
            "optional_content_groups": len(ocgs),
            "verdict": verdict,
            "pages": [p.as_dict() for p in per_page],
            "dictionary": [row.as_dict() for row in layer_dictionary(doc, pages=indexes)],
        }
    finally:
        doc.close()


# --- the layer dictionary --------------------------------------------------

@dataclass
class DictionaryRow:
    layer: LayerName
    objects: int
    pages: list[int]
    outline_objects: int
    stroke_objects: int

    def as_dict(self) -> dict[str, Any]:
        d = self.layer.as_dict()
        d.update({"objects": self.objects, "pages": list(self.pages),
                  "outline_objects": self.outline_objects,
                  "stroke_objects": self.stroke_objects})
        return d


def _is_outline(items: Any) -> bool:
    # Several path items, or one closed shape. PyMuPDF collapses an
    # axis-aligned closed rectangle to a single ``re``/``qu`` item, and that
    # is a region outline, not a hatch stroke.
    if len(items) > 1:
        return True
    return bool(items) and items[0][0] in ("re", "qu")


def layer_dictionary(doc: Any, *, pages: Iterable[int] | None = None) -> list[DictionaryRow]:
    """Every layer name in the set, read against the convention, with counts.

    ``outline_objects`` are drawing objects carrying several path items - the
    region outlines and symbols; ``stroke_objects`` carry one item each - the
    hatch strokes. The DEMO-001 sheet 04 widening layer ``Shading 245 (50%)``
    has 1,387 stroke objects and exactly one outline object, and the outline
    is the boundary (``PLAN_SHEET_LAYER_METHOD`` step 5a).
    """

    indexes = list(pages) if pages is not None else list(range(doc.page_count))
    counts: dict[str, int] = {}
    outline: dict[str, int] = {}
    stroke: dict[str, int] = {}
    where: dict[str, set[int]] = {}
    for i in indexes:
        for d in doc[i].get_drawings():
            name = d.get("layer")
            if not name:
                continue
            counts[name] = counts.get(name, 0) + 1
            where.setdefault(name, set()).add(i)
            if _is_outline(d.get("items", ())):
                outline[name] = outline.get(name, 0) + 1
            else:
                stroke[name] = stroke.get(name, 0) + 1
    rows = [
        DictionaryRow(layer=classify_layer_name(name), objects=n, pages=sorted(where[name]),
                      outline_objects=outline.get(name, 0), stroke_objects=stroke.get(name, 0))
        for name, n in counts.items()
    ]
    rows.sort(key=lambda r: (-r.objects, r.layer.short))
    return rows


def hints_present(rows: Iterable[DictionaryRow]) -> dict[str, list[str]]:
    """Feature hint -> the layer short names that carry it. The first thing
    to read against the bid schedule: a schedule item with no hinted layer
    and no legend swatch is scope that the drawing may not draw at all."""

    out: dict[str, list[str]] = {}
    for r in rows:
        if r.layer.hint:
            out.setdefault(r.layer.hint, []).append(r.layer.short)
    return {k: sorted(set(v)) for k, v in sorted(out.items())}


# --- geometry from a named layer --------------------------------------------

def _raw_point(x: float, y: float, height: float) -> tuple[float, float]:
    # ``get_drawings`` reports unrotated page space with a top-left origin;
    # the raw frame is the same space with a bottom-left origin. Same rule as
    # ``symbols._to_raw`` and ``markup_view.to_page``: (x, H - y).
    return (float(x), float(height - y))


def objects_on_layer(
    doc: Any, page_index: int, layer: str, *, only: str | None = None
) -> list[dict[str, Any]]:
    """Drawing objects on one layer, as raw-frame point lists.

    ``layer`` matches the short name or the full xref-qualified name.
    ``only`` may be ``"outline"`` (multi-item objects) or ``"stroke"``
    (single-item). Curves are returned by their control points; the caller
    who needs an arc keeps it an arc (``CLAUDE.md``: arcs are arcs).
    """

    if only not in (None, "outline", "stroke"):
        raise ValueError("only must be None, 'outline' or 'stroke'")
    page = doc[page_index]
    height = float(page.rect.height)
    out: list[dict[str, Any]] = []
    for d in page.get_drawings():
        name = d.get("layer") or ""
        if name != layer and short_name(name) != layer:
            continue
        items = d.get("items", ())
        is_outline = _is_outline(items)
        if only == "outline" and not is_outline:
            continue
        if only == "stroke" and is_outline:
            continue
        pts: list[tuple[float, float]] = []
        has_curve = False
        closed = bool(d.get("closePath"))
        for it in items:
            op = it[0]
            if op == "l":
                for p in it[1:3]:
                    pts.append(_raw_point(p.x, p.y, height))
            elif op == "c":
                has_curve = True
                for p in it[1:5]:
                    pts.append(_raw_point(p.x, p.y, height))
            elif op == "re":
                r = it[1]
                closed = True
                for x, y in ((r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1), (r.x0, r.y0)):
                    pts.append(_raw_point(x, y, height))
            elif op == "qu":
                q = it[1]
                closed = True
                for p in (q.ul, q.ur, q.lr, q.ll, q.ul):
                    pts.append(_raw_point(p.x, p.y, height))
        # drop consecutive duplicates left by segment end == next start
        dedup: list[tuple[float, float]] = []
        for p in pts:
            if not dedup or abs(dedup[-1][0] - p[0]) > 1e-6 or abs(dedup[-1][1] - p[1]) > 1e-6:
                dedup.append(p)
        rect = d["rect"]
        out.append({
            "layer": name, "short": short_name(name), "kind": "outline" if is_outline else "stroke",
            "items": len(items), "closed": closed, "has_curve": has_curve,
            "stroke": d.get("color"), "fill": d.get("fill"), "width": d.get("width"),
            "points_raw": dedup,
            "rect_raw": (float(rect.x0), float(height - rect.y1), float(rect.x1), float(height - rect.y0)),
        })
    return out


def objects_on_layer_in(
    pdf: str, page_index: int, layer: str, *, only: str | None = None
) -> list[dict[str, Any]]:
    """`objects_on_layer` for a path."""

    pymupdf = _import_pymupdf()
    doc = pymupdf.open(str(pdf))
    try:
        return objects_on_layer(doc, page_index, layer, only=only)
    finally:
        doc.close()
