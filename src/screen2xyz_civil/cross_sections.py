"""Cross-section sheets: both drawn surfaces of every section, from the vectors.

Sheets 09 and 10 of DEMO-001 carry the only evidence for the two largest tender
items - 31.04 Common Excavation and 31.06 Imported Embankment Fill - and until
now the plan was to trace each section by hand: eight panels a sheet, two
surfaces each, at 1:100 horizontal against 1:50 vertical. This module reads
the surfaces out of the page's own vector content instead.

What the sheet actually contains, measured on DEMO-001-09 panel 1+080:

* a grid of 0.12 pt lines, 28.35 pt apart vertically and 141.7 pt apart
  horizontally - exactly 0.5 m at 1:50 and 5 m at 1:100, so the grid verifies
  the declared scale before a single area is computed;
* the design surface as 0.84 pt strokes, each drawn two or three times about a
  point apart to make the line heavy - the pavement between the edge labels
  and the thinner ditch and daylight slopes are the same class;
* the existing ground as 0.84 pt dashes about 6 pt long, each dash its own
  object, chained end to end across the whole box;
* the pavement structure as boxes under the surface, in the same class;
* every label - station, elevation, offset, crossfall - as outlined glyph
  strokes at 0.36 and 1.14 pt, not text. Nothing on these sheets is readable
  as text except the consultant's address.

Design surface = the upper envelope of the long strokes. Everything in that
class sits at or below the finished surface (pavement layers, ditch), so the
envelope is the surface. The doubled strokes are averaged first: taking the
upper one would bias every area by about a point of elevation.

Existing ground = the longest chain of dashes that continue one another.

The station is not read. It is drawn as outlines, no OCR is available, and
inferring it from panel order is exactly the kind of assumption this project
refuses - DEMO-001-09 skips 1+200 and carries 1+220 and 1+240 instead. Every
panel gets a thumbnail, the operator names it, and nothing becomes a volume
before that.

Coordinates: `page.get_drawings()` returns the page's content-stream frame.
On this set's 180-rotated pages elevation increases with y in that frame and
display-right is decreasing x; a render clip wants both axes flipped. See the
addendum in `PLAN_SHEET_LAYER_METHOD.md`. Every surface here is returned in a
per-panel *section frame* - x = offset from centreline in points, positive to
the right as displayed; y = elevation in points above the panel's lowest grid
line - which is rotation-independent and what a reader of the sheet expects.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from .earthwork import (
    SectionArea,
    average_end_area_volume,
    section_areas_between_surfaces,
)


class CrossSectionError(RuntimeError):
    """A cross-section sheet could not be read safely."""


@dataclass(frozen=True)
class SectionSheetSpec:
    """How one consultant's sheets draw a section. Measured, not assumed.

    Defaults are DEMO-001's. Another set needs its own, the way another set
    needs its own title-block baseline.
    """

    grid_stroke_pt: float = 0.12
    surface_stroke_pt: float = 0.84
    grid_x_metres: float = 5.0  # read from the offset labels on the sheet
    grid_y_metres: float = 0.5  # read from the elevation labels on the sheet
    min_grid_line_pt: float = 100.0
    max_dash_pt: float = 12.0  # dashes measure 0.1-11.3 pt; design strokes 25+
    max_dash_gap_pt: float = 15.0  # measured gaps top out at 7.9 pt
    twin_tolerance_pt: float = 2.5  # heavy line copies sit about 1.1 pt apart
    coincidence_pt: float = 3.0  # 0.05 m at 1:50 - "on the design surface"
    stroke_tolerance_pt: float = 0.02


@dataclass(frozen=True)
class Segment:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def length(self) -> float:
        return math.hypot(self.x1 - self.x0, self.y1 - self.y0)

    @property
    def vertical(self) -> bool:
        return abs(self.x1 - self.x0) < 0.3

    @property
    def horizontal(self) -> bool:
        return abs(self.y1 - self.y0) < 0.3


@dataclass
class Panel:
    """One cross section as drawn, in its own section frame."""

    index: int  # 1-based, column-major as displayed: left column top to bottom
    bbox_gd: tuple[float, float, float, float]  # get_drawings frame
    bbox_display: tuple[float, float, float, float]  # render-clip frame
    centreline_x_gd: float
    base_y_gd: float
    grid_dx_pt: float
    grid_dy_pt: float
    metres_per_point_x: float
    metres_per_point_y: float
    existing: list[tuple[float, float]] = field(default_factory=list)
    design: list[tuple[float, float]] = field(default_factory=list)
    subgrade: list[tuple[float, float]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    cut_area_m2: float | None = None  # existing vs finished surface
    fill_area_m2: float | None = None
    cut_to_subgrade_m2: float | None = None  # existing vs bottom of structure
    fill_to_subgrade_m2: float | None = None
    max_structure_depth_m: float | None = None
    measured_width_m: float | None = None

    @property
    def blocking(self) -> bool:
        return any(f.get("blocking") for f in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "bbox_gd": list(self.bbox_gd),
            "bbox_display": list(self.bbox_display),
            "centreline_x_gd": self.centreline_x_gd,
            "grid_dx_pt": self.grid_dx_pt,
            "grid_dy_pt": self.grid_dy_pt,
            "metres_per_point_x": self.metres_per_point_x,
            "metres_per_point_y": self.metres_per_point_y,
            "existing_section_frame_pt": [list(p) for p in self.existing],
            "design_section_frame_pt": [list(p) for p in self.design],
            "subgrade_section_frame_pt": [list(p) for p in self.subgrade],
            "existing_offset_range_m": _range_m(self.existing, self.metres_per_point_x),
            "design_offset_range_m": _range_m(self.design, self.metres_per_point_x),
            "cut_area_m2": self.cut_area_m2,
            "fill_area_m2": self.fill_area_m2,
            "cut_to_subgrade_m2": self.cut_to_subgrade_m2,
            "fill_to_subgrade_m2": self.fill_to_subgrade_m2,
            "max_structure_depth_m": self.max_structure_depth_m,
            "measured_width_m": self.measured_width_m,
            "pay_item_note": (
                "cut/fill_area_m2 are to the finished surface; *_to_subgrade_m2 are to "
                "the bottom of the drawn pavement structure. Excavation and embankment "
                "items are usually measured to subgrade and the structure paid under "
                "its own items - which applies is the specification's call, not this "
                "module's. `measure_sections` requires the choice to be stated."
            ),
            "findings": list(self.findings),
            "blocking": self.blocking,
            "station_m": None,
            "station_note": (
                "Not read - drawn as outlines. Name this panel from its thumbnail "
                "before it is used in a volume."
            ),
        }


def _range_m(points: Sequence[tuple[float, float]], cx: float) -> list[float] | None:
    if not points:
        return None
    return [points[0][0] * cx, points[-1][0] * cx]


def _finding(code: str, detail: str, *, blocking: bool, severity: str | None = None) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity or ("BLOCKER" if blocking else "WARNING"),
        "blocking": blocking,
        "detail": detail,
    }


# --------------------------------------------------------------------------
# Reading the page


def _import_pymupdf() -> Any:
    try:
        import pymupdf  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - environment, not logic
        raise CrossSectionError("pymupdf is required to read cross-section sheets") from exc
    return pymupdf


def _segments_of(drawing: dict[str, Any]) -> list[Segment]:
    out: list[Segment] = []
    for item in drawing["items"]:
        kind = item[0]
        if kind == "l":
            out.append(Segment(item[1].x, item[1].y, item[2].x, item[2].y))
        elif kind == "re":
            r = item[1]
            corners = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)]
            out += [Segment(*a, *b) for a, b in zip(corners, corners[1:] + corners[:1])]
        elif kind == "qu":
            q = item[1]
            corners = [(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y)]
            out += [Segment(*a, *b) for a, b in zip(corners, corners[1:] + corners[:1])]
    return out


def _stroke_objects(page: Any, width_pt: float, tolerance: float) -> list[list[Segment]]:
    objects: list[list[Segment]] = []
    for drawing in page.get_drawings():
        if drawing.get("fill") is not None or drawing.get("color") is None:
            continue
        width = drawing.get("width") or 0.0
        if abs(width - width_pt) > tolerance:
            continue
        segments = _segments_of(drawing)
        if segments:
            objects.append(segments)
    return objects


# --------------------------------------------------------------------------
# Panels from the grid


def _merge_collinear(
    lines: list[Segment], *, axis: str, max_gap: float = 5.0
) -> list[tuple[float, float, float]]:
    """Join grid pieces broken at labels into spans: (position, lo, hi).

    Only pieces that touch are joined. Two panels in the same row share the
    same y for every grid line, and joining everything at one y welded each
    pair into a single box twice as wide.
    """

    by_key: dict[float, list[tuple[float, float, float]]] = {}
    for s in lines:
        pos = s.y0 if axis == "h" else s.x0
        lo, hi = ((min(s.x0, s.x1), max(s.x0, s.x1)) if axis == "h"
                  else (min(s.y0, s.y1), max(s.y0, s.y1)))
        by_key.setdefault(round(pos * 2) / 2, []).append((pos, lo, hi))
    spans: list[tuple[float, float, float]] = []
    for pieces in by_key.values():
        pieces.sort(key=lambda p: p[1])
        current = list(pieces[0])
        members = [pieces[0][0]]
        for pos, lo, hi in pieces[1:]:
            if lo <= current[2] + max_gap:
                current[2] = max(current[2], hi)
                members.append(pos)
            else:
                spans.append((sum(members) / len(members), current[1], current[2]))
                current = [pos, lo, hi]
                members = [pos]
        spans.append((sum(members) / len(members), current[1], current[2]))
    return spans


def _cluster(values: Sequence[float], gap: float) -> list[list[float]]:
    ordered = sorted(values)
    groups: list[list[float]] = [[ordered[0]]] if ordered else []
    for a, b in zip(ordered, ordered[1:]):
        if b - a > gap:
            groups.append([b])
        else:
            groups[-1].append(b)
    return groups


def _find_panels(
    grid_objects: list[list[Segment]],
    *,
    spec: SectionSheetSpec,
    page_width: float,
    page_height: float,
    rotation: int,
) -> list[Panel]:
    horizontals = [s for o in grid_objects for s in o if s.horizontal and s.length >= 20]
    verticals = [s for o in grid_objects for s in o if s.vertical and s.length >= 20]
    if not horizontals or not verticals:
        raise CrossSectionError(
            f"no grid found at {spec.grid_stroke_pt} pt - this is not a cross-section "
            "sheet drawn the way the spec describes, or the spec is for another set"
        )

    long_h = [
        (y, x0, x1) for y, x0, x1 in _merge_collinear(horizontals, axis="h")
        if x1 - x0 >= spec.min_grid_line_pt
    ]

    # Group grid lines into boxes: same x-extent, then split by a y gap that
    # is clearly more than one grid step.
    by_extent: dict[tuple[float, float], list[float]] = {}
    for y, x0, x1 in long_h:
        by_extent.setdefault((round(x0), round(x1)), []).append(y)

    boxes: list[tuple[float, float, float, float, list[float]]] = []
    for (x0, x1), ys in by_extent.items():
        if len(ys) < 3:
            continue
        steps = sorted(b - a for a, b in zip(sorted(ys), sorted(ys)[1:]))
        step = steps[len(steps) // 2]
        for group in _cluster(ys, gap=step * 2.5):
            if len(group) >= 3:
                boxes.append((x0, min(group), x1, max(group), sorted(group)))

    v_spans = _merge_collinear(verticals, axis="v")

    panels: list[Panel] = []
    for x0, y0, x1, y1, ys in boxes:
        cols = sorted(
            x for x, vy0, vy1 in v_spans
            if x0 - 2 <= x <= x1 + 2 and vy0 <= y0 + 2 and vy1 >= y1 - 2
        )
        findings: list[dict[str, Any]] = []
        dys = [b - a for a, b in zip(ys, ys[1:])]
        dy = statistics.median(dys)
        if cols and len(cols) >= 3:
            dxs = [b - a for a, b in zip(cols, cols[1:])]
            dx = statistics.median(dxs)
            if len(cols) % 2 == 1:
                centre = cols[len(cols) // 2]
            else:
                centre = (cols[len(cols) // 2 - 1] + cols[len(cols) // 2]) / 2.0
                findings.append(_finding(
                    "CENTRELINE_AMBIGUOUS",
                    f"{len(cols)} vertical grid lines - no middle one to take as the "
                    "centreline; offsets are relative to the midpoint of the middle pair.",
                    blocking=False,
                ))
        else:
            dx = float("nan")
            centre = (x0 + x1) / 2.0
            findings.append(_finding(
                "GRID_VERTICALS_MISSING",
                "fewer than three vertical grid lines - horizontal scale cannot be "
                "verified from the grid and the centreline is a guess",
                blocking=True,
            ))

        panels.append(Panel(
            index=0,
            bbox_gd=(x0, y0, x1, y1),
            bbox_display=_display_rect((x0, y0, x1, y1), page_width, page_height, rotation),
            centreline_x_gd=centre,
            base_y_gd=(y0 if rotation == 180 else y1),
            grid_dx_pt=dx,
            grid_dy_pt=dy,
            metres_per_point_x=spec.grid_x_metres / dx if dx == dx else float("nan"),
            metres_per_point_y=spec.grid_y_metres / dy,
            findings=findings,
        ))

    # Column-major as displayed. Display x for rotation 180 is decreasing gd x.
    def display_key(p: Panel) -> tuple[float, float]:
        dx0, dy0, _, _ = p.bbox_display
        return (round(dx0 / 200), dy0)

    panels.sort(key=display_key)
    for i, p in enumerate(panels, start=1):
        p.index = i
    return panels


def _display_rect(
    box: tuple[float, float, float, float], w: float, h: float, rotation: int
) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = box
    if rotation == 180:
        return (w - x1, h - y1, w - x0, h - y0)
    if rotation == 0:
        return (x0, y0, x1, y1)
    raise CrossSectionError(
        f"page rotation {rotation} is not handled; only 0 and 180 have been verified "
        "on this set"
    )


# --------------------------------------------------------------------------
# Surfaces


def _to_section_frame(x: float, y: float, panel: Panel, rotation: int) -> tuple[float, float]:
    if rotation == 180:
        return (panel.centreline_x_gd - x, y - panel.base_y_gd)
    return (x - panel.centreline_x_gd, panel.base_y_gd - y)


def _inside(s: Segment, box: tuple[float, float, float, float], pad: float = 3.0) -> bool:
    x0, y0, x1, y1 = box
    return all(
        x0 - pad <= x <= x1 + pad and y0 - pad <= y <= y1 + pad
        for x, y in ((s.x0, s.y0), (s.x1, s.y1))
    )


def _canonical(s: Segment) -> Segment:
    if (s.x0, s.y0) <= (s.x1, s.y1):
        return s
    return Segment(s.x1, s.y1, s.x0, s.y0)


def _collapse_twins(segments: list[Segment], tolerance: float) -> list[Segment]:
    """Average the copies a heavy line was drawn as."""

    pending = [_canonical(s) for s in segments]
    out: list[Segment] = []
    used = [False] * len(pending)
    for i, a in enumerate(pending):
        if used[i]:
            continue
        group = [a]
        used[i] = True
        for j in range(i + 1, len(pending)):
            if used[j]:
                continue
            b = pending[j]
            if (abs(a.x0 - b.x0) <= tolerance and abs(a.y0 - b.y0) <= tolerance
                    and abs(a.x1 - b.x1) <= tolerance and abs(a.y1 - b.y1) <= tolerance):
                group.append(b)
                used[j] = True
        n = len(group)
        out.append(Segment(
            sum(s.x0 for s in group) / n, sum(s.y0 for s in group) / n,
            sum(s.x1 for s in group) / n, sum(s.y1 for s in group) / n,
        ))
    return out


def _envelope(
    segments: list[tuple[float, float, float, float]], *, upper: bool
) -> list[tuple[float, float]]:
    """Extreme y over covering segments, sampled at every endpoint and midpoint.

    Upper is the finished surface: nothing in the design class is drawn above
    it. Lower is the subgrade: under the pavement the lowest line is the
    bottom of the structure boxes, and everywhere else the only line is the
    surface itself, so the two coincide there.
    """

    # Sample just either side of every endpoint as well as on it. The lower
    # envelope steps vertically where a structure box ends - its side is a
    # vertical stroke, which the surface classes exclude - and sampling only
    # on the endpoints turned that step into a diagonal to the next sample,
    # about 0.7 sq m of invented cut at each inner box edge.
    step = 1e-3
    xs: set[float] = set()
    for x0, _, x1, _ in segments:
        xs.update((x0 - step, x0, x0 + step, x1 - step, x1, x1 + step, (x0 + x1) / 2.0))
    pick = max if upper else min
    points: list[tuple[float, float]] = []
    for x in sorted(xs):
        best: float | None = None
        for x0, y0, x1, y1 in segments:
            if x0 - 1e-6 <= x <= x1 + 1e-6:
                y = y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
                best = y if best is None else pick(best, y)
        if best is not None:
            points.append((x, best))
    return _simplify(points, 0.05)


def _simplify(points: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    """Douglas-Peucker, recursive against each kept segment's own endpoints.

    The dense endpoint/midpoint sampling in `_envelope` puts several points
    within a thousandth of a point of a sharp corner - the crown of the
    finished surface among them, where this set's 2.00% crossfall each way
    meets at a peak. A single consecutive-triple pass compares each point
    only to its immediate neighbours, which are themselves that close to the
    corner; the deviation looks negligible even though the corner is real,
    and the peak point gets dropped. Recursing against the actual endpoints
    of the segment being simplified - the same method used throughout this
    project's plan-view work - keeps a real corner regardless of how densely
    its neighbours were sampled.
    """

    if len(points) < 3:
        return points
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        x0, y0 = xs[a], ys[a]
        x1, y1 = xs[b], ys[b]
        dx, dy = x1 - x0, y1 - y0
        norm = math.hypot(dx, dy) or 1.0
        far_i, far_d = a, 0.0
        for i in range(a + 1, b):
            d = abs(dy * (xs[i] - x0) - dx * (ys[i] - y0)) / norm
            if d > far_d:
                far_i, far_d = i, d
        if far_d > tolerance:
            keep[far_i] = True
            stack.append((a, far_i))
            stack.append((far_i, b))
    return [points[i] for i in range(len(points)) if keep[i]]


def _design_surfaces(
    objects: list[list[Segment]], panel: Panel, spec: SectionSheetSpec, rotation: int
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """The finished surface and the subgrade, from the same strokes."""

    long_segments = [
        s for o in objects for s in o
        if _inside(s, panel.bbox_gd) and s.length >= spec.max_dash_pt and not s.vertical
    ]
    if not long_segments:
        return [], []
    merged = _collapse_twins(long_segments, spec.twin_tolerance_pt)
    framed = []
    for s in merged:
        a = _to_section_frame(s.x0, s.y0, panel, rotation)
        b = _to_section_frame(s.x1, s.y1, panel, rotation)
        (ax, ay), (bx, by) = sorted([a, b])
        if bx - ax < 0.3:
            continue
        framed.append((ax, ay, bx, by))
    return _envelope(framed, upper=True), _envelope(framed, upper=False)


def _existing_ground(objects: list[list[Segment]], panel: Panel, spec: SectionSheetSpec, rotation: int) -> tuple[list[tuple[float, float]], int]:
    """Trace the dashed line. Returns the surface and how many dashes were left out.

    Every dash is its own segment, whatever object it came from: a dashed run
    is sometimes one path of ten dashes, sometimes ten paths. Tracing walks
    from each dash to the one that best continues it - nearest, and pointing
    the same way - so a stray short stroke of the design line nearby is passed
    over rather than spliced in. The longest trace is the ground.
    """

    dashes: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for o in objects:
        if not all(_inside(s, panel.bbox_gd) for s in o):
            continue
        if any(s.length >= spec.max_dash_pt for s in o):
            continue  # anything with a long stroke is design, box or border
        if len(o) > 1 and all(s.vertical or s.horizontal for s in o):
            continue  # tick marks and box corners
        for s in o:
            if s.vertical or s.length < 0.5:
                continue
            a = _to_section_frame(s.x0, s.y0, panel, rotation)
            b = _to_section_frame(s.x1, s.y1, panel, rotation)
            start, end = (a, b) if a[0] <= b[0] else (b, a)
            dashes.append((start, end))
    if not dashes:
        return [], 0
    dashes.sort()

    used = [False] * len(dashes)
    chains: list[list[int]] = []
    for seed in range(len(dashes)):
        if used[seed]:
            continue
        chain = [seed]
        used[seed] = True
        current = seed
        while True:
            (sx, sy), (ex, ey) = dashes[current]
            dx, dy = ex - sx, ey - sy
            norm = math.hypot(dx, dy) or 1.0
            best_j, best_score = -1, float("inf")
            for j in range(current + 1, len(dashes)):
                (nx, ny), (nx2, ny2) = dashes[j]
                if nx - ex > spec.max_dash_gap_pt:
                    break  # sorted by x: nothing further can be closer
                if used[j] or nx < ex - 1.0 or abs(ny - ey) > spec.max_dash_gap_pt:
                    continue
                gap = math.hypot(nx - ex, ny - ey)
                ndx, ndy = nx2 - nx, ny2 - ny
                nnorm = math.hypot(ndx, ndy) or 1.0
                # 0 when the next dash points the same way, 2 when opposite
                turn = 1.0 - (dx * ndx + dy * ndy) / (norm * nnorm)
                score = gap + turn * spec.max_dash_gap_pt
                if score < best_score:
                    best_j, best_score = j, score
            if best_j < 0:
                break
            chain.append(best_j)
            used[best_j] = True
            current = best_j
        chains.append(chain)

    # Each trace is one run of the ground line. The ground is the set of runs
    # that do not overlap in x and together cover the most width.
    runs: list[list[tuple[float, float]]] = []
    for chain in chains:
        pts: list[tuple[float, float]] = []
        for i in chain:
            for p in dashes[i]:
                if not pts or p[0] > pts[-1][0] + 0.05:
                    pts.append(p)
        if len(pts) >= 2:
            runs.append(pts)
    chosen = _widest_non_overlapping(runs)
    used_dashes = sum(len(r) for r in chosen)
    return chosen, len(dashes) - used_dashes


def _widest_non_overlapping(runs: list[list[tuple[float, float]]]) -> list[list[tuple[float, float]]]:
    """Weighted interval scheduling on x-span: the runs that cover the most."""

    if not runs:
        return []
    ordered = sorted(runs, key=lambda r: r[-1][0])
    n = len(ordered)
    starts = [r[0][0] for r in ordered]
    ends = [r[-1][0] for r in ordered]
    spans = [e - s for s, e in zip(starts, ends)]
    best = [0.0] * (n + 1)
    take = [False] * n
    prev = [-1] * n
    for i in range(n):
        j = i - 1
        while j >= 0 and ends[j] > starts[i] + 0.05:
            j -= 1
        prev[i] = j
        with_i = spans[i] + best[j + 1]
        if with_i > best[i]:
            best[i + 1] = with_i
            take[i] = True
        else:
            best[i + 1] = best[i]
    chosen: list[list[tuple[float, float]]] = []
    i = n - 1
    while i >= 0:
        if take[i]:
            chosen.append(ordered[i])
            i = prev[i]
        else:
            i -= 1
    chosen.reverse()
    return chosen


def _join_runs(
    runs: list[list[tuple[float, float]]],
    design: list[tuple[float, float]],
    *,
    coincidence_pt: float,
    short_gap_pt: float,
    metres_per_point_x: float,
) -> tuple[list[tuple[float, float]], list[dict[str, Any]]]:
    """Make one ground line out of the runs, saying how each gap was closed.

    A gap whose two ends both sit on the design surface is closed along the
    design: the consultant did not draw existing ground where it coincides
    with the new surface, and following the design there adds no area. A
    short gap is closed straight. A long gap that is not on the design is
    closed straight too, but flagged, because the ground there is unknown.
    """

    findings: list[dict[str, Any]] = []
    if not runs:
        return [], findings
    points = list(runs[0])
    for run in runs[1:]:
        ex, ey = points[-1]
        sx, sy = run[0]
        gap_pt = sx - ex
        d_end = _y_on(design, ex)
        d_start = _y_on(design, sx)
        on_design = (
            d_end is not None and d_start is not None
            and abs(ey - d_end) <= coincidence_pt and abs(sy - d_start) <= coincidence_pt
        )
        if on_design and gap_pt > short_gap_pt:
            points.extend((x, y) for x, y in design if ex + 0.05 < x < sx - 0.05)
            findings.append(_finding(
                "EXISTING_FOLLOWS_DESIGN",
                f"existing ground not drawn for {gap_pt * metres_per_point_x:.2f} m where it "
                "coincides with the design surface; taken as the design there (zero area)",
                blocking=False, severity="INFO",
            ))
        elif gap_pt > short_gap_pt:
            findings.append(_finding(
                "EXISTING_GROUND_GAP",
                f"no existing-ground dashes for {gap_pt * metres_per_point_x:.2f} m at "
                f"{ex * metres_per_point_x:+.1f} m offset and the line is not on the design "
                "there; closed straight. Check the thumbnail.",
                blocking=gap_pt * metres_per_point_x > 1.0,
            ))
        points.extend(p for p in run if p[0] > points[-1][0] + 0.05)
    return _simplify(points, 0.05), findings


def _y_on(polyline: list[tuple[float, float]], x: float) -> float | None:
    if len(polyline) < 2 or x < polyline[0][0] or x > polyline[-1][0]:
        return None
    for (x0, y0), (x1, y1) in zip(polyline, polyline[1:]):
        if x0 <= x <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return None


# --------------------------------------------------------------------------
# Public API


def extract_panels(
    pdf_path: Path,
    page_index: int,
    *,
    spec: SectionSheetSpec | None = None,
    declared_metres_per_point_x: float | None = None,
    declared_metres_per_point_y: float | None = None,
    scale_tolerance: float = 0.01,
) -> dict[str, Any]:
    """Read every cross-section panel on a sheet.

    Areas are computed per panel because they need no station. Volumes do,
    and `measure_sections` refuses to produce one until every panel it uses
    has been named.
    """

    spec = spec or SectionSheetSpec()
    pymupdf = _import_pymupdf()
    source = Path(pdf_path).expanduser().resolve()
    if not source.is_file():
        raise CrossSectionError(f"sheet PDF does not exist: {source}")
    document = pymupdf.open(str(source))
    try:
        if not 0 <= page_index < document.page_count:
            raise CrossSectionError(f"page index {page_index} is outside {source.name}")
        page = document[page_index]
        rotation = int(page.rotation)
        width, height = float(page.rect.width), float(page.rect.height)
        grid = _stroke_objects(page, spec.grid_stroke_pt, spec.stroke_tolerance_pt)
        surface = _stroke_objects(page, spec.surface_stroke_pt, spec.stroke_tolerance_pt)
    finally:
        document.close()

    panels = _find_panels(grid, spec=spec, page_width=width, page_height=height, rotation=rotation)
    sheet_findings: list[dict[str, Any]] = []

    for panel in panels:
        _verify_scale(panel, declared_metres_per_point_x, declared_metres_per_point_y, scale_tolerance, spec)
        panel.design, panel.subgrade = _design_surfaces(surface, panel, spec, rotation)
        runs, _left_out = _existing_ground(surface, panel, spec, rotation)
        panel.existing, join_findings = _join_runs(
            runs, panel.design,
            coincidence_pt=spec.coincidence_pt,
            short_gap_pt=spec.max_dash_gap_pt,
            metres_per_point_x=panel.metres_per_point_x,
        )
        panel.findings.extend(join_findings)
        if not panel.design:
            panel.findings.append(_finding("DESIGN_SURFACE_NOT_FOUND", "no long strokes of the surface class inside this panel", blocking=True))
        if len(panel.existing) < 2:
            panel.findings.append(_finding("EXISTING_GROUND_NOT_FOUND", "no dash chain of the surface class inside this panel", blocking=True))
        else:
            grid_width = panel.bbox_gd[2] - panel.bbox_gd[0]
            covered = panel.existing[-1][0] - panel.existing[0][0]
            if covered < 0.9 * grid_width:
                panel.findings.append(_finding(
                    "EXISTING_GROUND_TRUNCATED",
                    f"the traced ground covers {covered * panel.metres_per_point_x:.1f} m of a "
                    f"{grid_width * panel.metres_per_point_x:.1f} m panel; check the thumbnail "
                    "for where the dashed line was lost",
                    blocking=False,
                ))
        if panel.design and len(panel.existing) >= 2 and not panel.blocking:
            _crown_check(panel)
            try:
                result = section_areas_between_surfaces(
                    existing=panel.existing,
                    proposed=panel.design,
                    metres_per_point_x=panel.metres_per_point_x,
                    metres_per_point_y=panel.metres_per_point_y,
                    station_m=0.0,
                )
            except Exception as exc:  # EarthworkError or a geometry refusal
                panel.findings.append(_finding("SECTION_AREA_REFUSED", str(exc), blocking=True))
            else:
                panel.cut_area_m2 = result["cut_area_m2"]
                panel.fill_area_m2 = result["fill_area_m2"]
                panel.measured_width_m = result["measured_width_m"]
                _measure_to_subgrade(panel)
                design_inside_existing = (
                    panel.existing[0][0] <= panel.design[0][0] + 0.05
                    and panel.design[-1][0] <= panel.existing[-1][0] + 0.05
                )
                for finding in result["findings"]:
                    if finding["code"] == "SECTION_PARTIALLY_COVERED" and design_inside_existing:
                        # The design ties into drawn ground at both ends. That is
                        # the normal case, not a gap in evidence.
                        continue
                    if finding["code"] == "SECTION_PARTIALLY_COVERED":
                        finding = dict(finding, blocking=True, severity="BLOCKER", detail=(
                            "the design surface extends beyond the drawn existing ground; "
                            "the section cannot be closed there. " + finding["detail"]
                        ))
                    panel.findings.append(finding)

    if not panels:
        sheet_findings.append(_finding("NO_PANELS", "no cross-section grid boxes found on this page", blocking=True))

    return {
        "pdf": source.name,
        "page_index": page_index,
        "rotation": rotation,
        "spec": spec.__dict__,
        "panel_count": len(panels),
        "panels": [p.to_dict() for p in panels],
        "_panels": panels,
        "findings": sheet_findings,
        "stations_confirmed": False,
        "next_step": (
            "Render each panel with `render_panel`, read its station from the "
            "thumbnail, then call `measure_sections` with the station map."
        ),
    }


def _verify_scale(panel: Panel, cx: float | None, cy: float | None, tolerance: float, spec: SectionSheetSpec) -> None:
    if panel.metres_per_point_x != panel.metres_per_point_x:  # NaN
        return
    if cx is None or cy is None:
        panel.findings.append(_finding(
            "SCALE_FROM_GRID_ONLY",
            f"no declared scale to check against; using the grid ({spec.grid_x_metres} m "
            f"per {panel.grid_dx_pt:.2f} pt, {spec.grid_y_metres} m per {panel.grid_dy_pt:.2f} pt) "
            "on the operator's word that those are the label steps",
            blocking=False, severity="INFO",
        ))
        return
    ex = abs(panel.metres_per_point_x - cx) / cx
    ey = abs(panel.metres_per_point_y - cy) / cy
    if ex > tolerance or ey > tolerance:
        panel.findings.append(_finding(
            "SCALE_GRID_MISMATCH",
            f"grid implies {panel.metres_per_point_x:.6f} x {panel.metres_per_point_y:.6f} m/pt, "
            f"declared {cx:.6f} x {cy:.6f} (off by {ex*100:.1f}% / {ey*100:.1f}%). Either the "
            "declared scale or the grid-step reading is wrong; nothing is measurable until they agree.",
            blocking=True,
        ))
    else:
        panel.findings.append(_finding(
            "SCALE_VERIFIED_BY_GRID",
            f"grid spacing agrees with the declared scale within {max(ex, ey)*100:.2f}%",
            blocking=False, severity="INFO",
        ))


def _measure_to_subgrade(panel: Panel) -> None:
    """Cut and fill against the bottom of the drawn pavement structure.

    The subgrade is the lower envelope of the design strokes. Where no
    structure is drawn it is the finished surface, so the two agree there; a
    depth beyond anything a road structure could be means a stray stroke was
    read as structure, and those numbers are withheld rather than reported.
    """

    if len(panel.subgrade) < 2:
        return
    depths = []
    for x, y in panel.subgrade:
        top = _y_on(panel.design, x)
        if top is not None:
            depths.append((top - y) * panel.metres_per_point_y)
    if not depths:
        return
    max_depth = max(depths)
    panel.max_structure_depth_m = max_depth
    if max_depth > 1.5:
        panel.findings.append(_finding(
            "SUBGRADE_DEPTH_SUSPECT",
            f"lowest design stroke is {max_depth:.2f} m under the surface - deeper than "
            "a road structure. Something other than the structure was read as its "
            "bottom; subgrade quantities withheld for this panel.",
            blocking=False,
        ))
        return
    if max_depth < 0.05:
        panel.findings.append(_finding(
            "NO_STRUCTURE_DRAWN",
            "no pavement structure below the surface on this panel; subgrade equals "
            "the finished surface here",
            blocking=False, severity="INFO",
        ))
    try:
        result = section_areas_between_surfaces(
            existing=panel.existing,
            proposed=panel.subgrade,
            metres_per_point_x=panel.metres_per_point_x,
            metres_per_point_y=panel.metres_per_point_y,
            station_m=0.0,
        )
    except Exception as exc:
        panel.findings.append(_finding("SUBGRADE_AREA_REFUSED", str(exc), blocking=False))
        return
    panel.cut_to_subgrade_m2 = result["cut_area_m2"]
    panel.fill_to_subgrade_m2 = result["fill_area_m2"]


def _crown_check(panel: Panel) -> None:
    """A crowned road is higher at the centreline than 3 m either side.

    Not every section is crowned, so a failure only warns - but a frame that
    is upside down fails it on every panel, which is the point.
    """

    def at(x: float) -> float | None:
        pts = panel.design
        if not pts or x < pts[0][0] or x > pts[-1][0]:
            return None
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if x0 <= x <= x1:
                return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
        return None

    three_m = 3.0 / panel.metres_per_point_x
    centre, left, right = at(0.0), at(-three_m), at(three_m)
    if None in (centre, left, right):
        return
    if centre < left and centre < right:
        panel.findings.append(_finding(
            "SECTION_ORIENTATION_SUSPECT",
            "the design surface is lower at the centreline than 3 m either side. "
            "Either this section is not crowned, or the elevation axis is inverted - "
            "check the thumbnail before trusting cut against fill.",
            blocking=False,
        ))


def render_panel(
    pdf_path: Path,
    page_index: int,
    panel: Panel,
    out_png: Path,
    *,
    zoom: float = 2.0,
    overlay: bool = True,
) -> Path:
    """Thumbnail of one panel, with the extracted surfaces drawn over it.

    The overlay is the check: if red does not sit on the heavy line and blue
    on the dashes, the extraction is wrong for this panel and its numbers do
    not count.
    """

    pymupdf = _import_pymupdf()
    document = pymupdf.open(str(pdf_path))
    try:
        page = document[page_index]
        rotation = int(page.rotation)
        if overlay:
            shape = page.new_shape()
            layers = (
                (panel.existing, (0, 0, 1)),  # blue on the dashes
                (panel.subgrade, (0, 0.6, 0)),  # green on the structure bottom
                (panel.design, (1, 0, 0)),  # red on the heavy line
            )
            for pts, colour in layers:
                if len(pts) < 2:
                    continue
                gd = [_from_section_frame(x, y, panel, rotation) for x, y in pts]
                shape.draw_polyline([pymupdf.Point(*p) for p in gd])
                # finish() closes the path by default, which drew a chord from
                # the last point back to the first across every section.
                shape.finish(color=colour, width=1.2, closePath=False)
            shape.commit()
        x0, y0, x1, y1 = panel.bbox_display
        # The station title sits above the grid box; keep it in the picture.
        clip = pymupdf.Rect(x0 - 12.0, y0 - 40.0, x1 + 12.0, y1 + 30.0)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip)
        out = Path(out_png)
        out.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(out))
        return out
    finally:
        document.close()


def _from_section_frame(sx: float, sy: float, panel: Panel, rotation: int) -> tuple[float, float]:
    if rotation == 180:
        return (panel.centreline_x_gd - sx, panel.base_y_gd + sy)
    return (panel.centreline_x_gd + sx, panel.base_y_gd - sy)


SURFACES = ("finished", "subgrade")


def measure_sections(
    extractions: Sequence[dict[str, Any]],
    stations: dict[tuple[int, int], float],
    *,
    surface: str,
    source: str = "",
    max_interval_m: float = 20.0,
) -> dict[str, Any]:
    """Volumes from named panels, possibly across sheets.

    `stations` maps `(page_index, panel_index)` to a chainage in metres, as
    read by the operator from the thumbnails. `surface` must be stated:
    "finished" measures to the design surface, "subgrade" to the bottom of
    the drawn structure. Refuses anything unnamed, blocked, or ambiguous.
    """

    if surface not in SURFACES:
        raise CrossSectionError(f"surface must be one of {SURFACES}, not {surface!r}")
    by_key: dict[tuple[int, int], Panel] = {}
    for extraction in extractions:
        page = int(extraction["page_index"])
        for panel in extraction.get("_panels", []):
            by_key[(page, panel.index)] = panel

    sections: list[SectionArea] = []
    refused: list[dict[str, Any]] = []
    for key, station in sorted(stations.items(), key=lambda kv: kv[1]):
        panel = by_key.get(tuple(key))  # type: ignore[arg-type]
        if panel is None:
            refused.append({"panel": list(key), "reason": "no such panel in the extractions given"})
            continue
        if surface == "finished":
            cut, fill = panel.cut_area_m2, panel.fill_area_m2
        else:
            cut, fill = panel.cut_to_subgrade_m2, panel.fill_to_subgrade_m2
        if panel.blocking or cut is None or fill is None:
            refused.append({
                "panel": list(key),
                "reason": f"no usable {surface} areas - see findings",
                "findings": [f["code"] for f in panel.findings],
            })
            continue
        sections.append(SectionArea(
            station_m=float(station),
            cut_area_m2=cut,
            fill_area_m2=fill,
            source=f"{source} page {key[0]} panel {key[1]} ({surface})".strip(),
        ))
    unnamed = [k for k in by_key if k not in stations]
    if refused:
        raise CrossSectionError(f"cannot measure: {refused}")
    volume = average_end_area_volume(sections, max_interval_m=max_interval_m)
    volume["surface"] = surface
    volume["stations_used"] = [s.station_m for s in sections]
    volume["panels_unnamed"] = [list(k) for k in unnamed]
    volume["stations_confirmed"] = True
    return volume
