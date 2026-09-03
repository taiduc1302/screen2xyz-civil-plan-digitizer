"""Fill and hatch layers on a plan sheet, traced into polygons.

The corridor method in `PLAN_SHEET_LAYER_METHOD.md` reads a layer as a band:
for each column of the render, the top and bottom of the colour, then the
band's outline. It is exact on a straight corridor and it is what measured
sheets 03, 04 and 05. It has no answer where two roads' fills meet in plan -
the Example Road junction intersection on sheets 04 and 06 - and it cannot give the
eight scattered ditch-infill patches on sheet 04 their own boundaries. Both
were left "not done, stated plainly" by the session that measured the rest.

This module reads a layer as a region instead. It renders the viewport with
anti-aliasing off, masks the exact colour, heals the cuts that linework and the
seams of the PDF's tiling pattern leave in the mask, labels the connected
regions, traces each region's boundary along pixel edges, simplifies it, and
returns it in the Bluebeam raw frame with its area computed two independent
ways - pixel count and polygon shoelace - which must agree.

What the Example Road sheets actually do (measured on DEMO-001-05):

* the grey "solid" fill (#E5E5E5, 40 mm mill and overlay per the legend) is not
  a vector path at all - `get_drawings` returns no such fill. It is a PDF
  tiling pattern, rendered as 65 x 36 px cells at 90 DPI with one-pixel seams
  between cells wherever the cell grid does not land on the pixel grid;
* the road-widening X-hatch (#7F7F7F strokes) is drawn *over* the same grey, so
  the grey region is mill-and-overlay plus widening, and the widening is the
  part of it under the hatch;
* linework crosses the fill everywhere: centreline, lane lines, station ticks,
  leaders, and white label boxes printed on top of it.

A closing of two pixels heals seams and linework; a hatch needs a closing of
about half its line spacing to become a region at all. Both radii are
parameters and both are reported with the result, because a region traced
after a closing is the region *plus up to that many pixels of rounding at
every concave corner* - small against a road, not nothing.

Nothing here decides what a region means. The grey region on sheet 05 is
1 500 sq m of pavement; whether a given part of it is paid as mill-and-overlay
or as full-depth widening is read from the hatch and from the legend, by the
operator, and recorded with its evidence.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from .bluebeam_bridge import polygon_health
from .plan_layers import Viewport

Colour = tuple[int, int, int]

# Exact rendered colours of the patterns on DEMO-001-04's own legend, censused
# from the legend swatches at 90 DPI with anti-aliasing off. The last two are
# on the sheet and in no legend; crops at their positions (2026-09-03) show
# grey-128 as the grey of utility symbols - culvert bodies, flow arrows - and
# grey-153 as the stipple on the pedestrian asphalt pads at the curb returns.
# Neither is pavement under this module's names; they are kept out of every
# paving total and reported on their own so the estimator sees them.
EXAMPLE_PLAN_PATTERNS: dict[str, Colour] = {
    "widening_x_hatch": (127, 127, 127),  # ROAD WIDENING (FULL ROAD STRUCTURE)
    "full_depth_asphalt_rr": (178, 178, 178),  # FULL DEPTH ASPHALT REMOVAL AND REPLACEMENT
    "ditch_infill_dots": (0, 127, 0),  # DITCH INFILL
    "utility_symbol_grey_128": (128, 128, 128),  # not a paving pattern
    "pad_stipple_grey_153": (153, 153, 153),  # pedestrian asphalt pads - not legended
}


class FillLayerError(RuntimeError):
    """A fill layer could not be traced safely."""


@dataclass(frozen=True)
class RenderFrame:
    """How pixels of a viewport render map back to the Bluebeam raw frame."""

    dpi: int
    rotation: int
    page_width_pt: float
    page_height_pt: float
    display_x0: float
    display_y0: float
    width_px: int
    height_px: int

    @property
    def points_per_pixel(self) -> float:
        return 72.0 / self.dpi

    def pixel_to_raw(self, col: float, row: float) -> tuple[float, float]:
        """Pixel-corner coordinate to the raw markup frame.

        For this set's 180-rotated pages the render clip is the displayed
        frame, which relates to the raw frame by `raw_x = W - disp_x`,
        `raw_y = disp_y` (see the addendum in PLAN_SHEET_LAYER_METHOD.md).
        """

        disp_x = self.display_x0 + col * self.points_per_pixel
        disp_y = self.display_y0 + row * self.points_per_pixel
        if self.rotation == 180:
            return (self.page_width_pt - disp_x, disp_y)
        if self.rotation == 0:
            return (disp_x, disp_y)
        raise FillLayerError(f"page rotation {self.rotation} is not handled")


@dataclass
class FillRegion:
    index: int
    pixel_count: int
    area_m2_pixels: float
    area_m2_polygon: float
    polygon_raw: list[tuple[float, float]]
    holes_raw: list[list[tuple[float, float]]]
    holes_filled_px: int
    bbox_raw: tuple[float, float, float, float]
    linework_inside_m2: float = 0.0  # lines, hatch, text drawn over the fill
    white_inside_m2: float = 0.0  # label boxes or openings closed over
    health_safe: bool = True  # bluebeam_bridge.polygon_health verdict
    health_codes: list[str] = field(default_factory=list)
    compactness_ratio: float = 0.0  # perimeter / sqrt(area); a square is 4
    pattern_fractions: dict[str, float] = field(default_factory=dict)
    dominant_pattern: str = ""
    findings: list[dict[str, Any]] = field(default_factory=list)

    @property
    def blocking(self) -> bool:
        return any(f.get("blocking") for f in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "pixel_count": self.pixel_count,
            "area_m2_pixels": self.area_m2_pixels,
            "area_m2_polygon": self.area_m2_polygon,
            "linework_inside_m2": self.linework_inside_m2,
            "white_inside_m2": self.white_inside_m2,
            "health_safe": self.health_safe,
            "health_codes": list(self.health_codes),
            "compactness_ratio": self.compactness_ratio,
            "pattern_fractions": dict(self.pattern_fractions),
            "dominant_pattern": self.dominant_pattern,
            "vertex_count": len(self.polygon_raw),
            "polygon_raw": [list(p) for p in self.polygon_raw],
            "holes_raw": [[list(p) for p in h] for h in self.holes_raw],
            "holes_filled_px": self.holes_filled_px,
            "bbox_raw": list(self.bbox_raw),
            "findings": list(self.findings),
            "blocking": self.blocking,
        }


def _finding(code: str, detail: str, *, blocking: bool, severity: str | None = None) -> dict[str, Any]:
    return {"code": code, "severity": severity or ("BLOCKER" if blocking else "WARNING"), "blocking": blocking, "detail": detail}


# --------------------------------------------------------------------------
# Rendering


def _import_pymupdf() -> Any:
    try:
        import pymupdf  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover
        raise FillLayerError("pymupdf is required to trace fill layers") from exc
    return pymupdf


def render_viewport(
    pdf_path: Path, page_index: int, viewport: Viewport, *, dpi: int = 90
) -> tuple[np.ndarray, RenderFrame]:
    """Exact-colour RGB render of one viewport, anti-aliasing off.

    `viewport` is in the raw markup frame, as every viewport in this project
    is declared. The render clip is built in the displayed frame from it.
    """

    pymupdf = _import_pymupdf()
    source = Path(pdf_path).expanduser().resolve()
    if not source.is_file():
        raise FillLayerError(f"sheet PDF does not exist: {source}")
    document = pymupdf.open(str(source))
    previous = dict(pymupdf.TOOLS.show_aa_level())
    pymupdf.TOOLS.set_aa_level(0)
    try:
        if not 0 <= page_index < document.page_count:
            raise FillLayerError(f"page index {page_index} is outside {source.name}")
        page = document[page_index]
        rotation = int(page.rotation)
        width, height = float(page.rect.width), float(page.rect.height)
        if rotation == 180:
            clip = (width - viewport.x1, viewport.y0, width - viewport.x0, viewport.y1)
        elif rotation == 0:
            clip = (viewport.x0, viewport.y0, viewport.x1, viewport.y1)
        else:
            raise FillLayerError(f"page rotation {rotation} is not handled")
        pix = page.get_pixmap(
            matrix=pymupdf.Matrix(dpi / 72.0, dpi / 72.0),
            clip=pymupdf.Rect(*clip),
            alpha=False,
        )
        rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3].copy()
        frame = RenderFrame(
            dpi=dpi, rotation=rotation, page_width_pt=width, page_height_pt=height,
            display_x0=clip[0], display_y0=clip[1], width_px=pix.w, height_px=pix.h,
        )
        return rgb, frame
    finally:
        document.close()
        pymupdf.TOOLS.set_aa_level(previous.get("graphics", 8))


def colour_mask(rgb: np.ndarray, colour: Colour) -> np.ndarray:
    target = np.array(colour, dtype=np.uint8)
    return np.all(rgb == target, axis=2)


# --------------------------------------------------------------------------
# Morphology and labelling, numpy only


def _box_sum(mask: np.ndarray, radius: int) -> np.ndarray:
    """Count of set pixels in the (2r+1)-square around each pixel."""

    r = radius
    padded = np.pad(mask.astype(np.int32), r + 1)
    integral = padded.cumsum(0).cumsum(1)
    h, w = mask.shape
    size = 2 * r + 1
    return (
        integral[size:size + h, size:size + w]
        - integral[0:h, size:size + w]
        - integral[size:size + h, 0:w]
        + integral[0:h, 0:w]
    )


def dilate(mask: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return mask.copy()
    return _box_sum(mask, radius) > 0


def erode(mask: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return mask.copy()
    size = 2 * radius + 1
    return _box_sum(mask, radius) == size * size


def close(mask: np.ndarray, radius: int) -> np.ndarray:
    """Dilate then erode: fills gaps up to 2r wide, keeps the outline."""

    return erode(dilate(mask, radius), radius)


def label_components(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """4-connected labelling. Returns labels (0 = background) and sizes[label]."""

    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    n = 0
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys.tolist(), xs.tolist()):
        if labels[y0, x0]:
            continue
        n += 1
        labels[y0, x0] = n
        stack = [(y0, x0)]
        while stack:
            y, x = stack.pop()
            if y > 0 and mask[y - 1, x] and not labels[y - 1, x]:
                labels[y - 1, x] = n
                stack.append((y - 1, x))
            if y + 1 < h and mask[y + 1, x] and not labels[y + 1, x]:
                labels[y + 1, x] = n
                stack.append((y + 1, x))
            if x > 0 and mask[y, x - 1] and not labels[y, x - 1]:
                labels[y, x - 1] = n
                stack.append((y, x - 1))
            if x + 1 < w and mask[y, x + 1] and not labels[y, x + 1]:
                labels[y, x + 1] = n
                stack.append((y, x + 1))
    sizes = np.bincount(labels.ravel(), minlength=n + 1)
    return labels, sizes


def fill_holes(mask: np.ndarray, max_hole_px: int) -> tuple[np.ndarray, int]:
    """Fill enclosed background pockets up to `max_hole_px`.

    A label box printed over a fill is a white island inside it. Filling it
    keeps the pavement whole; a larger pocket is a real opening and is kept.
    Returns the mask and how many pixels were filled.
    """

    background = ~mask
    labels, sizes = label_components(background)
    border = np.unique(np.concatenate([labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]]))
    filled = mask.copy()
    total = 0
    for label in range(1, len(sizes)):
        if label in border or sizes[label] > max_hole_px:
            continue
        filled[labels == label] = True
        total += int(sizes[label])
    return filled, total


# --------------------------------------------------------------------------
# Boundary tracing along pixel edges


def trace_loops(region: np.ndarray) -> list[list[tuple[int, int]]]:
    """Closed boundary loops of a binary region, as pixel-corner vertices.

    Every edge between a set pixel and an unset one is a boundary edge; they
    are linked into loops keeping the region on the same side throughout, so
    a vertex where two pixels touch only diagonally is passed without joining
    the two. The outer loop of a region and the loop of each hole come back
    separately; the caller tells them apart by area.
    """

    h, w = region.shape
    padded = np.pad(region, 1)
    # Directed edges with the region on the left, so outer loops run one way
    # and hole loops the other. Corner (x, y) is the top-left corner of pixel
    # (x, y) in the padded array.
    edges: dict[tuple[int, int], list[tuple[int, int]]] = {}

    def add(a: tuple[int, int], b: tuple[int, int]) -> None:
        edges.setdefault(a, []).append(b)

    top = padded[1:, :] & ~padded[:-1, :]  # set pixel below, unset above -> edge on top of pixel
    for y, x in zip(*np.nonzero(top)):
        add((x, y + 1), (x + 1, y + 1))  # left to right along the pixel's top edge... region below
    bottom = padded[:-1, :] & ~padded[1:, :]
    for y, x in zip(*np.nonzero(bottom)):
        add((x + 1, y + 1), (x, y + 1))
    left = padded[:, 1:] & ~padded[:, :-1]
    for y, x in zip(*np.nonzero(left)):
        add((x + 1, y + 1), (x + 1, y))
    right = padded[:, :-1] & ~padded[:, 1:]
    for y, x in zip(*np.nonzero(right)):
        add((x + 1, y), (x + 1, y + 1))

    loops: list[list[tuple[int, int]]] = []
    while edges:
        start = next(iter(edges))
        loop = [start]
        current = start
        previous_dir: tuple[int, int] | None = None
        while True:
            options = edges.get(current)
            if not options:
                break
            if len(options) == 1 or previous_dir is None:
                nxt = options.pop(0)
            else:
                # Two ways on: turn right relative to how we arrived, which
                # keeps a diagonal touch from merging two separate lobes.
                dx, dy = previous_dir
                right_turn = (-dy, dx)
                choice = None
                for candidate in options:
                    if (candidate[0] - current[0], candidate[1] - current[1]) == right_turn:
                        choice = candidate
                        break
                nxt = choice if choice is not None else options[0]
                options.remove(nxt)
            if not options:
                del edges[current]
            previous_dir = (nxt[0] - current[0], nxt[1] - current[1])
            if nxt == start:
                break
            loop.append(nxt)
            current = nxt
        if len(loop) >= 4:
            loops.append([(x - 1, y - 1) for x, y in loop])  # un-pad
    return loops


def signed_area(points: Sequence[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0  # a clipped-away polygon has no area, not an error
    total = 0.0
    for (x1, y1), (x2, y2) in zip(points, list(points[1:]) + [points[0]]):
        total += x1 * y2 - x2 * y1
    return total / 2.0


def simplify_closed(points: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    """Douglas-Peucker on a closed loop, split at its two farthest vertices."""

    if len(points) < 4:
        return list(points)
    # Anchor at the point farthest from the first, then simplify both halves.
    x0, y0 = points[0]
    far = max(range(len(points)), key=lambda i: (points[i][0] - x0) ** 2 + (points[i][1] - y0) ** 2)
    first = _dp(points[: far + 1], tolerance)
    second = _dp(points[far:] + [points[0]], tolerance)
    return first[:-1] + second[:-1]


def _dp(points: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    if len(points) < 3:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        (x0, y0), (x1, y1) = points[a], points[b]
        dx, dy = x1 - x0, y1 - y0
        norm = math.hypot(dx, dy) or 1.0
        far_i, far_d = a, 0.0
        for i in range(a + 1, b):
            d = abs(dy * (points[i][0] - x0) - dx * (points[i][1] - y0)) / norm
            if d > far_d:
                far_i, far_d = i, d
        if far_d > tolerance:
            keep[far_i] = True
            stack.append((a, far_i))
            stack.append((far_i, b))
    return [p for p, k in zip(points, keep) if k]


# --------------------------------------------------------------------------
# Public API


def extract_fill_regions(
    pdf_path: Path,
    page_index: int,
    viewport: Viewport,
    colour: Colour,
    *,
    dpi: int = 90,
    close_radius_px: int = 2,
    min_area_m2: float = 1.0,
    fill_holes_below_m2: float = 12.0,
    simplify_px: float = 1.5,
    rgb: np.ndarray | None = None,
    frame: RenderFrame | None = None,
) -> dict[str, Any]:
    """Every region of `colour` in the viewport, as raw-frame polygons.

    Pass `rgb`/`frame` from `render_viewport` to reuse one render for several
    colours. Areas come from the pixel count *before* closing (what is
    actually painted) and from the traced polygon *after* closing (what will
    be written); the two are reported side by side and their disagreement is
    a finding when it is more than the closing can explain.
    """

    if not viewport.isotropic:
        raise FillLayerError(
            f"viewport {viewport.name!r} is anisotropic; an area has no meaning in it"
        )
    if rgb is None or frame is None:
        rgb, frame = render_viewport(pdf_path, page_index, viewport, dpi=dpi)
    m_per_px = frame.points_per_pixel * viewport.metres_per_point_x
    px_area = m_per_px**2

    raw_mask = colour_mask(rgb, colour)
    healed = close(raw_mask, close_radius_px)
    healed, holes_px = fill_holes(healed, int(fill_holes_below_m2 / px_area))
    labels, regions = trace_regions(
        healed, raw_mask, rgb, frame, px_area=px_area, min_area_m2=min_area_m2,
        simplify_px=simplify_px, metres_per_point=viewport.metres_per_point_x,
        patterns=EXAMPLE_PLAN_PATTERNS,
    )

    return {
        "pdf": Path(pdf_path).name,
        "page_index": page_index,
        "viewport": viewport.name,
        "colour": list(colour),
        "dpi": dpi,
        "close_radius_px": close_radius_px,
        "close_radius_m": close_radius_px * m_per_px,
        "metres_per_pixel": m_per_px,
        "painted_pixels_total": int(raw_mask.sum()),
        "painted_area_m2_total": float(raw_mask.sum()) * px_area,
        "holes_filled_px": holes_px,
        "region_count": len(regions),
        "regions": [r.to_dict() for r in regions],
        "_regions": regions,
        "_labels": labels,
        "_frame": frame,
        "note": (
            "Regions are what is painted in this colour, healed of linework and "
            "pattern seams. What each region is paid as is read from the legend and "
            "the hatch, not from this module."
        ),
    }


def trace_regions(
    healed: np.ndarray,
    raw_mask: np.ndarray,
    rgb: np.ndarray,
    frame: RenderFrame,
    *,
    px_area: float,
    min_area_m2: float,
    simplify_px: float,
    metres_per_point: float | None = None,
    patterns: dict[str, Colour] | None = None,
) -> tuple[np.ndarray, list[FillRegion]]:
    """Every connected region of `healed` as a raw-frame polygon with checks.

    `raw_mask` is the paint before healing; the difference between the two
    inside a region is accounted for by colour so a polygon larger than its
    paint is explained (linework over the fill) or flagged (white inside).
    """

    labels, sizes = label_components(healed)
    regions: list[FillRegion] = []
    min_px = int(min_area_m2 / px_area)
    order = [i for i in np.argsort(-sizes) if i != 0 and sizes[i] >= min_px]
    n = 0
    for label in order:
        component = labels == label
        loops = trace_loops(component)
        if not loops:
            continue
        # A 4-connected region can touch itself at a corner; its boundary then
        # passes one vertex twice and any polygon checker calls that a
        # self-intersection. Split such loops at the repeated vertex: the lobes
        # are separate simple polygons of the same paint.
        simple: list[list[tuple[int, int]]] = []
        for lp in loops:
            simple.extend(split_pinches(lp))
        simple.sort(key=lambda lp: -abs(signed_area(lp)))
        outers = [lp for lp in simple if signed_area(lp) > 0]
        holes_all = [lp for lp in simple if signed_area(lp) < 0]
        for outer_loop in outers:
            if abs(signed_area(outer_loop)) < min_px:
                continue
            n += 1
            outer_pts = [(float(x), float(y)) for x, y in outer_loop]
            outer = simplify_closed(outer_pts, simplify_px)
            lobe = _loop_mask(outer_loop, component.shape) & component
            painted = int((lobe & raw_mask).sum())
            holes = [
                simplify_closed([(float(x), float(y)) for x, y in lp], simplify_px)
                for lp in holes_all
                if abs(signed_area(lp)) * px_area >= min_area_m2 and _inside_loop(lp[0], outer_loop)
            ]
            outer_raw = [frame.pixel_to_raw(x, y) for x, y in outer]
            holes_raw = [[frame.pixel_to_raw(x, y) for x, y in h] for h in holes]
            area_polygon = (abs(signed_area(outer)) - sum(abs(signed_area(h)) for h in holes)) * px_area
            area_pixels = painted * px_area
            xs = [p[0] for p in outer_raw]
            ys = [p[1] for p in outer_raw]
            findings, region = _finish_region(
                n, lobe, raw_mask, rgb, frame, px_area=px_area,
                painted=painted, area_pixels=area_pixels, area_polygon=area_polygon,
                outer=outer, outer_raw=outer_raw, holes_raw=holes_raw, xs=xs, ys=ys,
                metres_per_point=metres_per_point, patterns=patterns,
            )
            regions.append(region)
    return labels, regions


def _finish_region(
    n: int,
    component: np.ndarray,
    raw_mask: np.ndarray,
    rgb: np.ndarray,
    frame: RenderFrame,
    *,
    px_area: float,
    painted: int,
    area_pixels: float,
    area_polygon: float,
    outer: list[tuple[float, float]],
    outer_raw: list[tuple[float, float]],
    holes_raw: list[list[tuple[float, float]]],
    xs: list[float],
    ys: list[float],
    metres_per_point: float | None,
    patterns: dict[str, Colour] | None,
) -> tuple[list[dict[str, Any]], FillRegion]:
    """Checks and bookkeeping for one traced lobe."""

    findings: list[dict[str, Any]] = []
    # What sits inside the traced region that is not the colour itself.
    # Linework and hatch drawn over a fill are still that fill - the road
    # does not stop under a lane line - so they explain, rather than
    # contradict, a polygon larger than its paint. White inside is
    # different: a label box or a real opening, and it needs eyes.
    inside = component & ~raw_mask
    unpainted = int(inside.sum())
    white = int(np.all(rgb[inside] == 255, axis=1).sum()) if unpainted else 0
    linework = unpainted - white
    if area_polygon > 0 and white * px_area > 0.03 * area_polygon:
        findings.append(_finding(
            "WHITE_INSIDE_REGION",
            f"{white * px_area:.1f} sq m of white inside a {area_polygon:.1f} sq m region "
            "- label boxes or real openings that were closed over. Look at the overlay "
            "before writing.",
            blocking=True,
        ))
    if area_polygon > 0:
        unexplained = abs(area_polygon - (area_pixels + unpainted * px_area)) / area_polygon
        if unexplained > 0.03:
            findings.append(_finding(
                "TRACE_DISAGREES_WITH_PAINT",
                f"polygon {area_polygon:.1f} sq m against {area_pixels:.1f} sq m painted plus "
                f"{unpainted * px_area:.1f} sq m under linework ({unexplained * 100:.1f}% "
                "unexplained) - the trace does not follow the paint.",
                blocking=True,
            ))
    if len(outer) > 400:
        findings.append(_finding(
            "TRACE_VERY_DETAILED",
            f"{len(outer)} vertices after simplification - a ragged boundary, likely a "
            "hatch traced as a fill or a fill full of linework. Consider a larger closing.",
            blocking=False,
        ))

    # The repository's own pre-write gate, applied at extraction so an
    # outline that would be refused at the host is refused here, and left
    # out of every total until someone looks at it.
    health = polygon_health(outer_raw, metres_per_unit=metres_per_point)
    health_codes = [
        (f["code"] if isinstance(f, dict) else getattr(f, "code", str(f)))
        for f in health.get("findings", [])
    ]
    if not health.get("safe_to_write", False):
        findings.append(_finding(
            "POLYGON_UNHEALTHY",
            f"polygon_health refuses this outline ({', '.join(health_codes)}); excluded "
            "from totals until it is looked at",
            blocking=True,
        ))

    # Which other patterns are drawn inside this region. On sheet 04 the
    # widening hatch is (127,127,127), full-depth asphalt removal is
    # (178,178,178) and the landing pads carry (128,128,128): one grey level
    # apart, and the only thing that tells them from each other.
    fractions: dict[str, float] = {}
    if patterns and component.any():
        total = int(component.sum())
        pixels = rgb[component]
        for name, colour in patterns.items():
            count = int(np.all(pixels == np.array(colour, dtype=np.uint8), axis=1).sum())
            fractions[name] = count / total
    dominant = max(fractions, key=fractions.get) if fractions else ""

    region = FillRegion(
        index=n, pixel_count=painted, area_m2_pixels=area_pixels,
        area_m2_polygon=area_polygon, polygon_raw=outer_raw, holes_raw=holes_raw,
        holes_filled_px=0, bbox_raw=(min(xs), min(ys), max(xs), max(ys)),
        linework_inside_m2=linework * px_area, white_inside_m2=white * px_area,
        health_safe=bool(health.get("safe_to_write", False)), health_codes=health_codes,
        compactness_ratio=float(health.get("compactness_ratio") or 0.0),
        pattern_fractions=fractions, dominant_pattern=dominant,
        findings=findings,
    )
    return findings, region


def split_pinches(loop: list[tuple[int, int]]) -> list[list[tuple[int, int]]]:
    """Cut a boundary loop wherever it revisits a vertex.

    Each cut-out sub-loop is a lobe of the region that touched the rest only
    at that corner. Returned loops are simple; orientation is preserved, so
    outer lobes stay positive and holes negative under `signed_area`.
    """

    stack: list[list[tuple[int, int]]] = [list(loop)]
    out: list[list[tuple[int, int]]] = []
    while stack:
        current = stack.pop()
        seen: dict[tuple[int, int], int] = {}
        cut = None
        for i, v in enumerate(current):
            if v in seen:
                cut = (seen[v], i)
                break
            seen[v] = i
        if cut is None:
            if len(current) >= 4:
                out.append(current)
            continue
        a, b = cut
        inner = current[a:b]
        rest = current[:a] + current[b:]
        if len(inner) >= 4:
            stack.append(inner)
        if len(rest) >= 4:
            stack.append(rest)
    return out


def _loop_mask(loop: list[tuple[int, int]], shape: tuple[int, int]) -> np.ndarray:
    """Pixels enclosed by a pixel-corner loop, by even-odd scanline fill."""

    h, w = shape
    mask = np.zeros((h, w), dtype=bool)
    n = len(loop)
    ys = [p[1] for p in loop]
    for y in range(max(min(ys), 0), min(max(ys), h)):
        yc = y + 0.5
        xs: list[float] = []
        for i in range(n):
            (x0, y0), (x1, y1) = loop[i], loop[(i + 1) % n]
            if y0 == y1:
                continue
            if (y0 <= yc < y1) or (y1 <= yc < y0):
                xs.append(x0 + (yc - y0) * (x1 - x0) / (y1 - y0))
        xs.sort()
        for j in range(0, len(xs) - 1, 2):
            lo = int(math.ceil(xs[j] - 0.5))
            hi = int(math.floor(xs[j + 1] - 0.5))
            if hi >= lo:
                mask[y, max(lo, 0):min(hi, w - 1) + 1] = True
    return mask


def _inside_loop(point: tuple[float, float], loop: list[tuple[int, int]]) -> bool:
    x, y = point[0] + 0.5, point[1] + 0.5
    inside = False
    n = len(loop)
    for i in range(n):
        (x0, y0), (x1, y1) = loop[i], loop[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            cross = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if cross > x:
                inside = not inside
    return inside


def hatch_closing_radius(hatch_mask: np.ndarray, *, sample_every: int = 7) -> int:
    """Closing radius that turns a hatch into a region: half its line gap.

    Measured along rows, so a 45-degree hatch with lines s apart shows gaps
    of s*sqrt(2). On DEMO-001-05 the median row gap is 17 px at 90 DPI; radius 7
    leaves the widening in four pieces full of holes, 9 closes it into one
    ring within 0.85% of the hand-traced polygons, 11 over-rounds to +2.5%.
    """

    ys, xs = np.nonzero(hatch_mask)
    if len(ys) == 0:
        raise FillLayerError("no hatch pixels to measure")
    gaps: list[int] = []
    for y in range(int(ys.min()), int(ys.max()) + 1, sample_every):
        row = np.nonzero(hatch_mask[y])[0]
        if len(row) > 5:
            d = np.diff(row)
            gaps.extend(d[d > 1].tolist())
    if not gaps:
        raise FillLayerError("hatch pixels found but no gaps between them - a solid, not a hatch")
    return int(math.ceil(float(np.median(gaps)) / 2.0))


def split_pavement(
    pdf_path: Path,
    page_index: int,
    viewport: Viewport,
    *,
    fill_colour: Colour = (229, 229, 229),
    hatch_colour: Colour = (127, 127, 127),
    dpi: int = 90,
    fill_close_px: int = 2,
    hatch_close_px: int | None = None,
    min_area_m2: float = 1.0,
    fill_holes_below_m2: float = 12.0,
    simplify_px: float = 1.5,
    patterns: dict[str, Colour] | None = None,
) -> dict[str, Any]:
    """Pavement, and the part of it under the hatch, and the rest.

    On the Example Road set the grey fill is every paved surface in the works and
    the X-hatch drawn over part of it marks full-structure widening; what is
    grey and not hatched is mill and overlay. This returns all three as
    regions. Whether those names are right on a given sheet is the legend's
    say, and the estimator's - the module only separates the paint.

    Validated on DEMO-001-05 against polygons hand-traced and read back from
    Revu: pavement 1 566.8 vs 1 564.9 sq m, widening ring 997.3 vs 1 005.8,
    mill and overlay 570.4 vs 559.0, each clipped to the same station range.
    The widening/mill split boundary here is the hatch envelope; the hand
    trace used the drawn edge line, which is where the 2% on the split lives.
    """

    if not viewport.isotropic:
        raise FillLayerError(f"viewport {viewport.name!r} is anisotropic; an area has no meaning in it")
    patterns = EXAMPLE_PLAN_PATTERNS if patterns is None else patterns
    rgb, frame = render_viewport(pdf_path, page_index, viewport, dpi=dpi)
    m_per_px = frame.points_per_pixel * viewport.metres_per_point_x
    px_area = m_per_px**2

    fill_raw = colour_mask(rgb, fill_colour)
    hatch_raw = colour_mask(rgb, hatch_colour)
    pavement = close(fill_raw, fill_close_px)
    # A label box printed over the pavement is a white island up to a dozen
    # square metres at 1:250. Filling it keeps the pavement whole; anything
    # larger is kept as an opening and both are reported.
    pavement, filled_px = fill_holes(pavement, int(fill_holes_below_m2 / px_area))

    findings: list[dict[str, Any]] = []
    if filled_px:
        findings.append(_finding(
            "HOLES_FILLED",
            f"{filled_px * px_area:.1f} sq m of white islands under {fill_holes_below_m2:.0f} sq m "
            "each were closed over inside the fill (label boxes, most likely). Check the overlay "
            "if any opening in the pavement is real.",
            blocking=False, severity="INFO",
        ))
    radius = hatch_close_px
    if radius is None:
        try:
            radius = hatch_closing_radius(hatch_raw)
        except FillLayerError as exc:
            radius = 0
            findings.append(_finding("NO_HATCH", str(exc), blocking=False, severity="INFO"))
    hatched = close(hatch_raw, radius) if radius else np.zeros_like(hatch_raw)
    if radius:
        hatched, _ = fill_holes(hatched, int(fill_holes_below_m2 / px_area))
    # Other hatches on the same paint: on sheet 04's legend (178,178,178) is
    # FULL DEPTH ASPHALT REMOVAL AND REPLACEMENT, its own pay item, and the
    # landing pads carry an unlisted (128,128,128). Each is closed on its own
    # radius and taken out of both the widening and the mill-and-overlay, so
    # a region is counted once, under the pattern actually drawn on it. Where
    # two closed hatches overlap, the one with more of its own paint there wins.
    others: dict[str, np.ndarray] = {}
    for name, colour in (patterns or {}).items():
        if colour == hatch_colour or colour == fill_colour or name.startswith("ditch"):
            continue
        raw = colour_mask(rgb, colour)
        if raw.sum() * px_area < min_area_m2:
            continue
        try:
            r_other = hatch_closing_radius(raw)
        except FillLayerError:
            continue
        closed_other = close(raw, r_other)
        closed_other, _ = fill_holes(closed_other, int(fill_holes_below_m2 / px_area))
        # Priority by paint where the closed regions overlap.
        contested = closed_other & hatched
        if contested.any():
            own = dilate(raw, 2)
            hatch_own = dilate(hatch_raw, 2)
            closed_other = closed_other & ~(contested & hatch_own & ~own)
            hatched = hatched & ~(contested & own & ~hatch_own)
        others[name] = closed_other
    other_union = np.zeros_like(hatched)
    for m in others.values():
        other_union |= m

    # The hatch is drawn to the edge line; the pattern fill under it stops a
    # pixel or two short of that line. The hatched ring is therefore the
    # widening on its own terms, the pavement less every hatch is mill and
    # overlay, and their union is the paved works - not the grey alone.
    widening_mask = hatched & ~other_union
    mill_mask = pavement & ~hatched & ~other_union
    works = pavement | hatched | other_union
    hatch_outside = (hatched | other_union) & ~pavement
    if hatch_outside.sum() * px_area > 25.0:
        findings.append(_finding(
            "HATCH_OUTSIDE_FILL",
            f"{hatch_outside.sum() * px_area:.1f} sq m of hatch region lies outside the grey fill - "
            "more than the edge strip explains. A hatch that is not widening over pavement "
            "(a driveway, a different legend entry) or a fill the closing did not reach. "
            "Check the overlay.",
            blocking=False,
        ))

    mpp = viewport.metres_per_point_x
    common = dict(px_area=px_area, min_area_m2=min_area_m2, simplify_px=simplify_px, metres_per_point=mpp, patterns=patterns)
    _, total = trace_regions(works, fill_raw | hatch_raw, rgb, frame, **common)
    _, widening = trace_regions(widening_mask, hatch_raw, rgb, frame, **common)
    _, mill = trace_regions(mill_mask, fill_raw & ~hatched & ~other_union, rgb, frame, **common)
    other_regions: dict[str, list[FillRegion]] = {}
    for name, mask in others.items():
        _, regs = trace_regions(mask, colour_mask(rgb, patterns[name]), rgb, frame, **common)
        other_regions[name] = regs
    # A hatch is lines: its paint is a fraction of its region by construction,
    # so the paint check has no meaning for hatched regions.
    for regs in [widening, *other_regions.values()]:
        for region in regs:
            region.findings = [f for f in region.findings if f["code"] != "TRACE_DISAGREES_WITH_PAINT"]

    def total_of(regions: list[FillRegion]) -> float:
        return sum(r.area_m2_polygon for r in regions if r.health_safe)

    def excluded_of(regions: list[FillRegion]) -> float:
        return sum(r.area_m2_polygon for r in regions if not r.health_safe)

    excluded = excluded_of(total) + excluded_of(widening) + excluded_of(mill) + sum(excluded_of(r) for r in other_regions.values())
    if excluded > 0:
        findings.append(_finding(
            "REGIONS_EXCLUDED_UNHEALTHY",
            f"{excluded:.1f} sq m of traced regions fail polygon_health and are left out of "
            "every total; each carries POLYGON_UNHEALTHY with the reason",
            blocking=False,
        ))

    return {
        "pdf": Path(pdf_path).name,
        "page_index": page_index,
        "viewport": viewport.name,
        "dpi": dpi,
        "fill_colour": list(fill_colour),
        "hatch_colour": list(hatch_colour),
        "fill_close_px": fill_close_px,
        "hatch_close_px": radius,
        "metres_per_pixel": m_per_px,
        "patterns": {k: list(v) for k, v in (patterns or {}).items()},
        "paved_works_m2": total_of(total),
        "widening_m2": total_of(widening),
        "mill_overlay_m2": total_of(mill),
        "other_hatched_m2": {name: total_of(regs) for name, regs in other_regions.items()},
        "excluded_unhealthy_m2": excluded,
        "paved_works": [r.to_dict() for r in total],
        "widening": [r.to_dict() for r in widening],
        "mill_overlay": [r.to_dict() for r in mill],
        "other_hatched": {name: [r.to_dict() for r in regs] for name, regs in other_regions.items()},
        "_paved_works": total,
        "_widening": widening,
        "_mill_overlay": mill,
        "_other_hatched": other_regions,
        "_frame": frame,
        "findings": findings,
        "note": (
            "Names follow the Example Road legend (grey = paved works, X-hatch = full-structure "
            "widening, grey without hatch = mill and overlay). Confirm against this sheet's "
            "own legend. Regions are uncut: clip to the agreed stations before summing, and "
            "resolve the overlap with the neighbouring sheet."
        ),
    }


def clip_polygon_x(
    polygon: Sequence[tuple[float, float]], x_min: float, x_max: float
) -> list[list[tuple[float, float]]]:
    """Clip a simple polygon to a vertical band in x, as simple parts.

    Sheets overlap by 10-20 m and every quantity is cut at an agreed station;
    the station maps to a raw x through the sheet's `StationFrame`.

    Returns a list of rings. A concave region cut across its mouth becomes
    two or more pieces, and this returns them separately. The first version
    was Sutherland-Hodgman, which joins such pieces with edges running back
    along the cut line: the area came out right and the boundary was invalid
    (self-touching), caught by the session writing it to Revu on 2026-09-03.

    Method: the boundary is split into chains that lie inside the band, each
    ending on a cut line; on each cut line the chain ends are paired in y
    order (the interior of a simple polygon alternates along the line) and
    the chains are linked through those pairs into closed rings.
    """

    lo, hi = min(x_min, x_max), max(x_min, x_max)
    pts = [(float(p[0]), float(p[1])) for p in polygon]
    if len(pts) < 3 or lo >= hi:
        return []
    eps = 1e-9
    n = len(pts)

    def inside(p: tuple[float, float]) -> bool:
        return lo - eps <= p[0] <= hi + eps

    if all(inside(p) for p in pts):
        return [pts]
    if all(p[0] < lo - eps for p in pts) or all(p[0] > hi + eps for p in pts):
        return []

    def cross(a: tuple[float, float], b: tuple[float, float], x: float) -> tuple[float, float]:
        t = (x - a[0]) / (b[0] - a[0])
        return (x, a[1] + (b[1] - a[1]) * t)

    # Walk the boundary and collect the pieces inside the band. Each piece
    # is a list of points; the first and last lie on a cut line unless the
    # ring never leaves the band (handled above).
    start = next(i for i in range(n) if not inside(pts[i]))
    chains: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    for k in range(n):
        a = pts[(start + k) % n]
        b = pts[(start + k + 1) % n]
        # Points where edge a->b crosses lo or hi, in travel order.
        crossings: list[tuple[float, float]] = []
        for x in (lo, hi):
            if (a[0] - x) * (b[0] - x) < 0:
                crossings.append(cross(a, b, x))
        crossings.sort(key=lambda p: abs(p[0] - a[0]))
        position = a
        for c in crossings:
            if inside(position) and current:
                current.append(c)
                chains.append(current)
                current = []
            elif not inside(position):
                current = [c]
            position = c
        if inside(b):
            if not current:
                current = [b]  # entered exactly on a vertex that sits on the line
            else:
                current.append(b)
        elif current:
            chains.append(current)
            current = []
    if current:
        chains.append(current)
    chains = [c for c in chains if len(c) >= 2]
    if not chains:
        return []

    # Pair chain ends along each cut line in y order.
    ends: list[tuple[float, float, int, int]] = []  # (x, y, chain index, 0=start/1=end)
    for i, c in enumerate(chains):
        ends.append((c[0][0], c[0][1], i, 0))
        ends.append((c[-1][0], c[-1][1], i, 1))
    partner: dict[tuple[int, int], tuple[int, int]] = {}
    for x in (lo, hi):
        on_line = sorted((e for e in ends if abs(e[0] - x) <= 1e-6), key=lambda e: e[1])
        for j in range(0, len(on_line) - 1, 2):
            a_key = (on_line[j][2], on_line[j][3])
            b_key = (on_line[j + 1][2], on_line[j + 1][3])
            partner[a_key] = b_key
            partner[b_key] = a_key

    rings: list[list[tuple[float, float]]] = []
    used = [False] * len(chains)
    for seed in range(len(chains)):
        if used[seed]:
            continue
        ring: list[tuple[float, float]] = []
        index, forward = seed, True
        while True:
            used[index] = True
            chain = chains[index] if forward else list(reversed(chains[index]))
            ring.extend(chain)
            exit_key = (index, 1 if forward else 0)
            nxt = partner.get(exit_key)
            if nxt is None:
                break
            index, entry = nxt
            forward = entry == 0
            if index == seed and forward:
                break
            if used[index]:
                break
        cleaned = [p for i, p in enumerate(ring) if i == 0 or (abs(p[0] - ring[i - 1][0]) > eps or abs(p[1] - ring[i - 1][1]) > eps)]
        if len(cleaned) > 1 and abs(cleaned[0][0] - cleaned[-1][0]) <= eps and abs(cleaned[0][1] - cleaned[-1][1]) <= eps:
            cleaned.pop()
        if len(cleaned) >= 3:
            rings.append(cleaned)
    return rings


def clip_area_m2(
    polygon: Sequence[tuple[float, float]], x_min: float, x_max: float, viewport: Viewport
) -> float:
    """Area of a polygon within a band, summed over its clipped parts."""

    return sum(polygon_area_m2(part, viewport) for part in clip_polygon_x(polygon, x_min, x_max))


def polygon_area_m2(polygon: Sequence[tuple[float, float]], viewport: Viewport) -> float:
    return viewport.area_m2(abs(signed_area(list(polygon))))


def render_overlay(
    pdf_path: Path,
    page_index: int,
    viewport: Viewport,
    regions: Sequence[FillRegion],
    out_png: Path,
    *,
    zoom: float = 1.0,
    colour: tuple[float, float, float] = (1.0, 0.0, 0.0),
) -> Path:
    """The viewport with every traced polygon drawn over it. The check."""

    pymupdf = _import_pymupdf()
    document = pymupdf.open(str(pdf_path))
    try:
        page = document[page_index]
        rotation = int(page.rotation)
        width, height = float(page.rect.width), float(page.rect.height)
        shape = page.new_shape()
        for region in regions:
            for ring in [region.polygon_raw, *region.holes_raw]:
                if len(ring) < 3:
                    continue
                # raw -> get_drawings frame for drawing: raw_x = x_gd, raw_y = H - y_gd
                pts = [pymupdf.Point(x, height - y) if rotation == 180 else pymupdf.Point(x, y) for x, y in ring]
                shape.draw_polyline(pts + [pts[0]])
                shape.finish(color=colour, width=1.5, closePath=False)
        shape.commit()
        if rotation == 180:
            clip = pymupdf.Rect(width - viewport.x1, viewport.y0, width - viewport.x0, viewport.y1)
        else:
            clip = pymupdf.Rect(viewport.x0, viewport.y0, viewport.x1, viewport.y1)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip)
        out = Path(out_png)
        out.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(out))
        return out
    finally:
        document.close()
