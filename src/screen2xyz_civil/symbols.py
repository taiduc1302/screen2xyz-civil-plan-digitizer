"""Point symbols on a plan sheet, found in the vector content and counted.

The catalogue has COUNT rules - storm structures, utility protection - and
until now nothing that could find a symbol. A count made by eye is the count
most likely to be one short: on DEMO-001-11/12 the profile shows three 1200 mm
structures, D1-D3, and two were marked because only two label positions were
found with confidence.

A manhole on these sheets is a filled black circle of radius 4.2 pt (a 0.75 m
symbol at 1:250) drawn as four Bezier arcs; a hydro pole is an open grey circle
of radius 5.6 pt. Both are ordinary paths in `page.get_drawings()`, so they can
be found by shape, size and colour, and every candidate comes back with its
centre in the raw markup frame and a crop to look at. The label next to a
symbol is outlined text on this set and is not read; the operator names each
candidate from its crop, the way cross-section panels are named.

Counting is proposal work: a candidate is a place to look, not a structure.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from .plan_layers import Viewport

Colour = tuple[int, int, int]


class SymbolError(RuntimeError):
    """A sheet could not be searched for symbols."""


@dataclass(frozen=True)
class CircleSymbol:
    centre_raw: tuple[float, float]
    radius_pt: float
    stroke: Colour | None
    fill: Colour | None
    filled: bool
    width_pt: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "centre_raw": list(self.centre_raw),
            "radius_pt": self.radius_pt,
            "stroke": None if self.stroke is None else list(self.stroke),
            "fill": None if self.fill is None else list(self.fill),
            "filled": self.filled,
            "width_pt": self.width_pt,
        }


def _rgb(value: Sequence[float] | None) -> Colour | None:
    if value is None:
        return None
    return tuple(int(round(float(c) * 255)) for c in value)  # type: ignore[return-value]


def _rect_of(drawing: dict[str, Any]) -> tuple[float, float, float, float]:
    rect = drawing["rect"]
    if hasattr(rect, "x0"):
        return (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))
    x0, y0, x1, y1 = rect
    return (float(x0), float(y0), float(x1), float(y1))


def circles_from_drawings(
    drawings: Sequence[dict[str, Any]],
    *,
    radius_pt: tuple[float, float],
    roundness: float = 0.15,
) -> list[dict[str, Any]]:
    """Paths that are circles: all curve segments, square bounding box.

    Works on the plain dictionaries `page.get_drawings()` returns, so it can
    be tested without a PDF. Coordinates are left in the drawing frame; the
    caller converts.
    """

    lo, hi = radius_pt
    out: list[dict[str, Any]] = []
    for drawing in drawings:
        items = drawing.get("items") or []
        if not items or len(items) > 8:
            continue
        curves = sum(1 for item in items if item[0] == "c")
        if curves < 3 or curves < len(items) - 1:
            continue
        x0, y0, x1, y1 = _rect_of(drawing)
        w, h = x1 - x0, y1 - y0
        if w <= 0 or h <= 0 or abs(w - h) > roundness * max(w, h):
            continue
        r = (w + h) / 4.0
        if not lo <= r <= hi:
            continue
        stroke = _rgb(drawing.get("color"))
        fill = _rgb(drawing.get("fill"))
        width = float(drawing.get("width") or 0.0)
        # A symbol that looks solid is not always a filled path: the D1-D3
        # manholes on DEMO-001-12 are open circles stroked so heavily that the
        # stroke covers the interior. Report the stroke width and let the
        # caller decide what "solid" means.
        out.append({
            "centre_gd": ((x0 + x1) / 2.0, (y0 + y1) / 2.0),
            "radius_pt": r,
            "stroke": stroke,
            "fill": fill,
            "width_pt": width,
            "filled": fill is not None or width >= r,
        })
    return out


def _to_raw(x_gd: float, y_gd: float, *, rotation: int, width: float, height: float) -> tuple[float, float]:
    """`get_drawings` coordinates to the Bluebeam raw markup frame.

    `get_drawings` measures y from the top of the page; the raw markup frame is
    PDF-native and measures it from the bottom. That flip is between two
    coordinate conventions and **does not depend on page rotation** - an
    earlier version returned y unchanged on an unrotated page, which put every
    symbol on DEMO-001-11 (the only rotation-0 sheet in the set) 1684 - y away
    from the truth. Two markers were written from those coordinates before a
    host thumbnail showed them on blank paper.

    Rotation does not move x either: `get_drawings` works in unrotated content
    space, and it is the render clip, not the raw frame, that flips x on a
    180-rotated page.
    """

    if rotation in (0, 180):
        return (x_gd, height - y_gd)
    raise SymbolError(f"page rotation {rotation} is not handled")


def find_circles(
    pdf_path: Path,
    page_index: int,
    viewport: Viewport | None = None,
    *,
    radius_pt: tuple[float, float] = (3.5, 9.0),
    filled: bool | None = None,
    stroke: Colour | None = None,
) -> dict[str, Any]:
    """Circle symbols on a page, optionally inside one viewport.

    Returns candidates in the raw markup frame grouped by (radius, filled,
    stroke colour) so that "three filled black circles of 4.2 pt" reads as
    one line, and the operator checks three crops rather than a page.
    """

    try:
        import pymupdf  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover
        raise SymbolError("pymupdf is required to search a sheet for symbols") from exc
    source = Path(pdf_path).expanduser().resolve()
    if not source.is_file():
        raise SymbolError(f"sheet PDF does not exist: {source}")
    document = pymupdf.open(str(source))
    try:
        if not 0 <= page_index < document.page_count:
            raise SymbolError(f"page index {page_index} is outside {source.name}")
        page = document[page_index]
        rotation = int(page.rotation)
        width, height = float(page.rect.width), float(page.rect.height)
        found = circles_from_drawings(page.get_drawings(), radius_pt=radius_pt)
    finally:
        document.close()

    symbols: list[CircleSymbol] = []
    for c in found:
        if filled is not None and c["filled"] != filled:
            continue
        if stroke is not None and c["stroke"] != stroke:
            continue
        raw = _to_raw(*c["centre_gd"], rotation=rotation, width=width, height=height)
        if viewport is not None and not viewport.contains(raw):
            continue
        symbols.append(CircleSymbol(
            centre_raw=raw, radius_pt=round(c["radius_pt"], 2),
            stroke=c["stroke"], fill=c["fill"], filled=c["filled"],
            width_pt=round(c["width_pt"], 2),
        ))

    groups: dict[str, list[CircleSymbol]] = {}
    for s in symbols:
        key = f"r={s.radius_pt:.1f}pt {'solid' if s.filled else 'open'} stroke={s.stroke} width={s.width_pt:.1f}"
        groups.setdefault(key, []).append(s)

    return {
        "pdf": source.name,
        "page_index": page_index,
        "rotation": rotation,
        "viewport": None if viewport is None else viewport.name,
        "radius_pt": list(radius_pt),
        "candidate_count": len(symbols),
        "groups": {k: [s.to_dict() for s in v] for k, v in groups.items()},
        "_symbols": symbols,
        "note": (
            "Candidates, not structures. Name each from its crop (`crop_symbol`) "
            "before it is counted under a rule; the label beside it is outlined "
            "text and is not read."
        ),
    }


def crop_symbol(
    pdf_path: Path,
    page_index: int,
    symbol: CircleSymbol,
    out_png: Path,
    *,
    half_pt: float = 120.0,
    zoom: float = 2.5,
) -> Path:
    """A crop around one candidate, wide enough to include its label."""

    import pymupdf  # noqa: PLC0415

    document = pymupdf.open(str(pdf_path))
    try:
        page = document[page_index]
        rotation = int(page.rotation)
        width, height = float(page.rect.width), float(page.rect.height)
        x, y = symbol.centre_raw
        # raw -> displayed: both axes flip on rotation 180 (render clip frame).
        dx, dy = (width - x, y) if rotation == 180 else (x, y)
        clip = pymupdf.Rect(dx - half_pt, dy - half_pt, dx + half_pt, dy + half_pt)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip)
        out = Path(out_png)
        out.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(out))
        return out
    finally:
        document.close()
