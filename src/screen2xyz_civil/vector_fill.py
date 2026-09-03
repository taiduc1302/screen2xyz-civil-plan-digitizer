"""Boundaries taken from the drawing's own filled vector paths.

Why this exists
---------------

`fill_layers.py` rasterises the sheet at 90 DPI, masks a colour and traces the
boundary along pixel edges. That is the right way to *find* where a pattern is.
It is the wrong way to *place* a boundary, for a reason that cost this project a
day: wherever another element is drawn on top of the fill - the black dashed
edge-of-pavement line, survey dots, a white label box - the colour mask has a
hole there, and the traced boundary detours around the hole instead of running
through it. Measured on DEMO-001-04: the traced edge sat 3-5 pt outside the drawn
edge on average and dropped up to 20 pt (about 1.8 m at 1:250) into the pavement
at each dash. On a length item the same defect is worse still - the two gravel
shoulders on that sheet read 95.72 m and 111.73 m over a segment that is 43.00 m
long.

The pavement fill on this drawing set *is* vector: `page.get_drawings()` returns
278 paths filled #E5E5E5 on DEMO-001-04, and their edges run smoothly - one
measured 1131.84 pt unbroken. Reading those paths gives a boundary that lands on
the drawn line, with no DPI, no mask and no morphology.

What this module does not do
----------------------------

It does not find the widening / mill-and-overlay interface. The X-hatch that
marks widening is **not** in the vector content - there is not one 45-degree
stroke inside a hatched band; the hatch is a PDF pattern. Colour-classifying
vector strokes as "the hatch" is what produced ten wrong markups on the sheet 04
intersection: RGB-127 strokes turn out to be symbol strokes (mean length 10.3 pt,
angles scattered) and RGB-178 a stipple dot pattern (mean length 3.2 pt). Those
greys are what a thin black hatch line *renders as* at 90 DPI, nothing more.

So: use this module for the outside of a paved area, and find the interface some
other way - the drawn edge-of-pavement line, or a printed offset - and say which.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

Point = tuple[float, float]


class VectorFillError(ValueError):
    """A request that cannot be answered from the vector content."""


def raw_frame(points: Iterable[Sequence[float]], page_height: float) -> list[Point]:
    """Content-stream points to the Bluebeam raw frame used for markup paths.

    On this set's 180-degree-rotated pages `raw_x = x`, `raw_y = height - y`.
    Note this is *not* the frame `get_pixmap(clip=...)` wants; that one flips x
    as well, and confusing the two renders the mirror-image region of the page.
    """
    return [(float(p[0]), page_height - float(p[1])) for p in points]


def path_points(drawing: dict[str, Any], page_height: float) -> list[Point]:
    """Every point of one `get_drawings()` path, in the raw frame, de-duplicated."""
    pts: list[Point] = []

    def add(x: float, y: float) -> None:
        q = (round(float(x), 3), round(page_height - float(y), 3))
        if not pts or q != pts[-1]:
            pts.append(q)

    for item in drawing.get("items", ()):
        kind = item[0]
        if kind == "l":
            add(item[1].x, item[1].y)
            add(item[2].x, item[2].y)
        elif kind == "re":
            r = item[1]
            add(r.x0, r.y0)
            add(r.x1, r.y0)
            add(r.x1, r.y1)
            add(r.x0, r.y1)
        elif kind == "qu":
            for p in item[1]:
                add(p.x, p.y)
        elif kind == "c":
            add(item[1].x, item[1].y)
            add(item[4].x, item[4].y)
    return pts


def colour_matches(colour: Sequence[float] | None, target: Sequence[float], tol: float = 0.02) -> bool:
    if colour is None:
        return False
    return all(abs(float(c) - float(t)) <= tol for c, t in zip(colour, target))


def filled_paths(
    drawings: Iterable[dict[str, Any]],
    fill_rgb: Sequence[float],
    page_height: float,
    *,
    tol: float = 0.02,
    min_points: int = 3,
) -> list[list[Point]]:
    """Rings of every path filled with `fill_rgb`, in the raw frame."""
    out: list[list[Point]] = []
    for d in drawings:
        if not colour_matches(d.get("fill"), fill_rgb, tol):
            continue
        pts = path_points(d, page_height)
        if len(pts) >= min_points:
            out.append(pts)
    return out


def crossings(ring: Sequence[Point], x: float) -> list[float]:
    """y values where the closed ring crosses the vertical line at `x`."""
    ys: list[float] = []
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        if x1 == x2:
            continue
        lo, hi = (x1, x2) if x1 < x2 else (x2, x1)
        if not (lo <= x < hi):
            continue
        ys.append(y1 + (y2 - y1) * (x - x1) / (x2 - x1))
    return ys


@dataclass(frozen=True)
class EdgeProfile:
    """Outer top and bottom of a set of fills, sampled across x."""

    xs: list[float]
    top: list[float]
    bottom: list[float]

    def __post_init__(self) -> None:
        if not (len(self.xs) == len(self.top) == len(self.bottom)):
            raise VectorFillError("edge profile columns must be the same length")


def edge_profile(
    rings: Sequence[Sequence[Point]],
    x_from: float,
    x_to: float,
    *,
    step: float = 2.0,
    y_from: float | None = None,
    y_to: float | None = None,
) -> EdgeProfile:
    """Outermost top and bottom of the fill at each x sample.

    Taking the extremes over every ring means interior gaps - where a lane line
    or a station tick interrupts the fill - do not appear as boundary. The road
    does not stop under a lane line, and this is the cheapest correct way to say
    so: no morphological closing, so no closing radius to tune. (On the sheet 04
    intersection that radius moved the answer from 966 to 1261 sq m.)
    """
    if step <= 0:
        raise VectorFillError("step must be positive")
    if x_to <= x_from:
        raise VectorFillError("x_to must be greater than x_from")

    xs: list[float] = []
    top: list[float] = []
    bottom: list[float] = []
    x = x_from
    while x <= x_to + 1e-9:
        ys: list[float] = []
        for ring in rings:
            for y in crossings(ring, x):
                if y_from is not None and y < y_from:
                    continue
                if y_to is not None and y > y_to:
                    continue
                ys.append(y)
        if ys:
            xs.append(round(x, 4))
            top.append(min(ys))
            bottom.append(max(ys))
        x += step
    if not xs:
        raise VectorFillError("no fill found in that x range")
    return EdgeProfile(xs, top, bottom)


def simplify(points: Sequence[Point], tolerance: float = 0.3) -> list[Point]:
    """Douglas-Peucker against the chord of each range, not the neighbours.

    Comparing a point to its immediate neighbours drops real corners when the
    sampling is dense, which is how a road crown once vanished from a
    cross-section in this project.
    """
    pts = list(points)
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        ax, ay = pts[i]
        bx, by = pts[j]
        dx, dy = bx - ax, by - ay
        den = (dx * dx + dy * dy) ** 0.5 or 1.0
        worst, at = -1.0, None
        for k in range(i + 1, j):
            px, py = pts[k]
            d = abs(dy * px - dx * py + bx * ay - by * ax) / den
            if d > worst:
                worst, at = d, k
        if worst > tolerance and at is not None:
            keep[at] = True
            stack.append((i, at))
            stack.append((at, j))
    return [p for p, k in zip(pts, keep) if k]


def band(upper: Sequence[Point], lower: Sequence[Point]) -> list[Point]:
    """Closed ring between an upper and a lower chain, both left to right."""
    up = list(upper)
    lo = list(lower)
    if len(up) < 2 or len(lo) < 2:
        raise VectorFillError("a band needs at least two points per chain")
    ring = up + list(reversed(lo))
    out: list[Point] = []
    for p in ring:
        if not out or p != out[-1]:
            out.append(p)
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out


def shoelace_area(ring: Sequence[Point]) -> float:
    total = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def polyline_length(points: Sequence[Point]) -> float:
    return sum(
        ((points[i + 1][0] - points[i][0]) ** 2 + (points[i + 1][1] - points[i][1]) ** 2) ** 0.5
        for i in range(len(points) - 1)
    )


def markup_path(ring: Sequence[Point], *, closed: bool = True, precision: int = 1) -> str:
    """Bluebeam markup path. One ring only - the host silently bridges two."""
    pts = [(round(x, precision), round(y, precision)) for x, y in ring]
    out: list[Point] = []
    for p in pts:
        if not out or p != out[-1]:
            out.append(p)
    if closed and len(out) > 1 and out[0] == out[-1]:
        out.pop()
    if len(out) < 2:
        raise VectorFillError("a markup path needs at least two distinct points")
    body = f"M {out[0][0]:.1f} {out[0][1]:.1f} " + " ".join(
        f"L {x:.1f} {y:.1f}" for x, y in out[1:]
    )
    return body + " H" if closed else body


def raster_trace_signature(ring: Sequence[Point]) -> dict[str, float]:
    """Numbers that separate a raster trace from a boundary read off the drawing.

    A 90-DPI pixel-edge trace of a simple corridor band comes back with a hundred
    or more vertices at roughly 8 pt spacing; a boundary taken from the drawing's
    own geometry has a handful at ten times that. `looks_raster_traced` is a
    warning, not a verdict - check the markup against the sheet before acting.
    """
    pts = list(ring)
    if len(pts) < 3:
        raise VectorFillError("need at least three points")
    segments = list(zip(pts, pts[1:] + pts[:1]))
    lengths = [((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 for a, b in segments]
    total = sum(lengths) or 1.0
    axis = sum(
        length
        for (a, b), length in zip(segments, lengths)
        if abs(a[0] - b[0]) < 0.05 or abs(a[1] - b[1]) < 0.05
    )
    mean_segment = total / len(lengths)
    return {
        "points": float(len(pts)),
        "mean_segment_pt": mean_segment,
        "axis_aligned_fraction": axis / total,
        "looks_raster_traced": float(len(pts) >= 60 and mean_segment <= 15.0),
    }
