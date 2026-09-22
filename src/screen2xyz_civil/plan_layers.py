"""Layer extraction for civil plan sheets.

Distilled from the Example Road Sheet 03 pass of 2026-09-03, where three separate
attempts at the same quantities failed before a method worked. Every check here
exists because its absence produced a wrong number that looked plausible.

The failures this module is meant to make impossible:

* Geometry written into the wrong measurement viewport. A polygon drawn with
  profile-viewport coordinates measured "wrong" by exactly 5.00x - not a host
  defect, but the profile's anisotropic scale correctly applied to geometry that
  did not belong there. See :func:`viewport_of` and :func:`single_viewport_check`.
* A boundary inferred from a hatch envelope rather than the line the drawing
  actually draws. Sparse hatch tips zigzag; the drawn edge does not.
* A reach measured straight through a gap that was really a driveway crossing.
  See :func:`split_runs`.
* Two different symbols treated as one because both are small curved glyphs.
  See :func:`classify_glyph`.
* A quantity accepted without checking it against a dimension printed on the
  sheet. See :func:`check_against_printed`.
* Adjacent sheets each measured to their own matchline, double counting the
  ground between them. See :func:`sheet_overlap_report`.

Nothing here talks to Bluebeam. The operator reads the host, passes values in,
and these functions answer. That keeps them testable and keeps the host out of
the trust path.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

__all__ = [
    "Viewport",
    "StationFrame",
    "fit_station_frame",
    "viewport_of",
    "single_viewport_check",
    "colour_census",
    "band_extents",
    "classify_glyph",
    "split_runs",
    "shoelace_area_m2",
    "polyline_length_m",
    "offsets_from_centreline",
    "check_against_printed",
    "sheet_overlap_report",
]

Point = Sequence[float]


@dataclass(frozen=True)
class Viewport:
    """One measurement context on a sheet.

    ``metres_per_point_x`` and ``metres_per_point_y`` differ for profile and
    cross-section views. Quantities are only meaningful when the whole geometry
    sits inside one viewport and that viewport's own scale is used.
    """

    name: str
    x0: float
    y0: float
    x1: float
    y1: float
    metres_per_point_x: float
    metres_per_point_y: float

    def __post_init__(self) -> None:
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError("viewport bounds must be normalised (x0<x1, y0<y1)")
        for value in (self.metres_per_point_x, self.metres_per_point_y):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("metres-per-point must be positive and finite")

    @property
    def isotropic(self) -> bool:
        return math.isclose(
            self.metres_per_point_x, self.metres_per_point_y, rel_tol=1e-9
        )

    def contains(self, point: Point) -> bool:
        x, y = float(point[0]), float(point[1])
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1

    def area_m2(self, area_points2: float) -> float:
        """Convert a point-space area, respecting an anisotropic viewport.

        Shoelace area scales linearly in each axis, so the conversion is the
        product of the two factors for any polygon, not only rectangles.
        """

        return float(area_points2) * self.metres_per_point_x * self.metres_per_point_y


@dataclass(frozen=True)
class StationFrame:
    """Chainage calibration for one sheet."""

    points_per_metre: float
    ref_raw_x: float
    ref_station_m: float
    residual_m: float = 0.0

    def station(self, raw_x: float) -> float:
        return self.ref_station_m + (self.ref_raw_x - float(raw_x)) / self.points_per_metre

    def raw_x(self, station_m: float) -> float:
        return self.ref_raw_x - (float(station_m) - self.ref_station_m) * self.points_per_metre


def fit_station_frame(
    samples: Iterable[tuple[float, float]], *, max_residual_m: float = 0.5
) -> StationFrame:
    """Fit a station frame to ``(raw_x, station_m)`` samples.

    Requires at least three chainage labels so that a single mis-read label
    cannot silently define the frame, and refuses a fit whose worst sample sits
    further than ``max_residual_m`` from the line.
    """

    points = [(float(x), float(s)) for x, s in samples]
    if len(points) < 3:
        raise ValueError("station calibration needs at least three chainage samples")
    count = len(points)
    mean_x = sum(p[0] for p in points) / count
    mean_s = sum(p[1] for p in points) / count
    numerator = sum((p[0] - mean_x) * (p[1] - mean_s) for p in points)
    denominator = sum((p[0] - mean_x) ** 2 for p in points)
    if denominator == 0:
        raise ValueError("chainage samples share one x position")
    slope = numerator / denominator
    if slope == 0:
        raise ValueError("degenerate chainage fit")
    frame = StationFrame(
        points_per_metre=abs(1.0 / slope), ref_raw_x=mean_x, ref_station_m=mean_s
    )
    residual = max(abs(frame.station(x) - s) for x, s in points)
    if residual > max_residual_m:
        raise ValueError(
            f"chainage samples disagree by {residual:.2f} m "
            f"(limit {max_residual_m} m); check for a mis-read label"
        )
    return StationFrame(
        points_per_metre=frame.points_per_metre,
        ref_raw_x=mean_x,
        ref_station_m=mean_s,
        residual_m=residual,
    )


def viewport_of(point: Point, viewports: Sequence[Viewport]) -> Viewport | None:
    for viewport in viewports:
        if viewport.contains(point):
            return viewport
    return None


def single_viewport_check(
    points: Iterable[Point], viewports: Sequence[Viewport]
) -> dict[str, Any]:
    """Refuse geometry that is not wholly inside one isotropic viewport.

    This is the check that would have caught the 2026-09-02 Sheet 03 polygon
    before it was written, and with it the phantom "x5 area artifact".
    """

    pts = [(float(p[0]), float(p[1])) for p in points]
    if not pts:
        return {"safe_to_write": False, "findings": ["no vertices"], "viewport": None}
    hits = [viewport_of(p, viewports) for p in pts]
    findings: list[str] = []
    outside = [p for p, hit in zip(pts, hits) if hit is None]
    if outside:
        findings.append(
            f"{len(outside)} vertex/vertices lie in no declared viewport "
            f"(first at {outside[0][0]:.1f},{outside[0][1]:.1f})"
        )
    named = {hit.name for hit in hits if hit is not None}
    if len(named) > 1:
        findings.append(
            f"geometry spans viewports {sorted(named)} - their scales differ"
        )
    resolved = None
    if not outside and len(named) == 1:
        resolved = hits[0]
        if resolved is not None and not resolved.isotropic:
            findings.append(
                f"viewport {resolved.name!r} is anisotropic "
                f"({resolved.metres_per_point_x:.6f} x "
                f"{resolved.metres_per_point_y:.6f} m/pt); "
                "areas and diagonals are not measurable in it"
            )
    return {
        "safe_to_write": not findings,
        "findings": findings,
        "viewport": None if resolved is None else resolved.name,
    }


def colour_census(
    pixels: Iterable[Sequence[int]],
) -> list[tuple[tuple[int, int, int], int]]:
    """Exact-colour histogram, most frequent first.

    Render with anti-aliasing disabled before calling this: with anti-aliasing
    on, every edge invents intermediate colours and the census stops meaning
    anything.
    """

    counts: dict[tuple[int, int, int], int] = {}
    for pixel in pixels:
        key = (int(pixel[0]), int(pixel[1]), int(pixel[2]))
        counts[key] = counts.get(key, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def band_extents(
    columns: Iterable[tuple[float, Sequence[float]]], *, min_samples: int = 3
) -> list[tuple[float, float, float]]:
    """Reduce per-column sample sets to ``(x, y_min, y_max)`` envelopes.

    Columns with fewer than ``min_samples`` hits are dropped rather than
    interpolated: a gap in a sparse pattern is information, not noise.
    """

    out: list[tuple[float, float, float]] = []
    for x, ys in columns:
        values = [float(v) for v in ys]
        if len(values) < min_samples:
            continue
        out.append((float(x), min(values), max(values)))
    out.sort()
    return out


def classify_glyph(width: float, height: float, *, arrow_min_ratio: float = 2.7) -> str:
    """Tell a ditch flow arrow from a vegetation scallop by aspect ratio.

    Both are small curved glyphs and both cluster along the verge. On the King
    Road set the flow arrow runs about 4.0 wide-to-high and the vegetation
    scallop about 1.9. Reading them together produced a ditch 5.5x too long.
    """

    w, h = float(width), float(height)
    if h <= 0 or w <= 0:
        return "unknown"
    ratio = w / h
    if ratio >= arrow_min_ratio:
        return "flow_arrow"
    if ratio >= 1.4:
        return "vegetation_scallop"
    return "unknown"


def split_runs(
    xs: Iterable[float], *, metres_per_point: float, max_gap_m: float = 6.0
) -> list[list[float]]:
    """Split ordered positions into runs, breaking at gaps.

    A gap in a symbol chain usually means the feature is interrupted - a
    driveway crossing, a structure, a culvert. Fitting one line straight through
    such a gap overstated a ditch by 2.6x.
    """

    values = sorted(float(x) for x in xs)
    if not values:
        return []
    runs: list[list[float]] = [[values[0]]]
    for previous, current in zip(values, values[1:]):
        if (current - previous) * metres_per_point > max_gap_m:
            runs.append([current])
        else:
            runs[-1].append(current)
    return runs


def shoelace_area_m2(points: Sequence[Point], viewport: Viewport) -> float:
    pts = [(float(p[0]), float(p[1])) for p in points]
    if len(pts) < 3:
        return 0.0
    total = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        total += x1 * y2 - x2 * y1
    return viewport.area_m2(abs(total) / 2.0)


def polyline_length_m(points: Sequence[Point], viewport: Viewport) -> float:
    if not viewport.isotropic:
        raise ValueError(
            f"length in anisotropic viewport {viewport.name!r} is only defined "
            "along a pure axis; measure the components separately"
        )
    pts = [(float(p[0]), float(p[1])) for p in points]
    total = 0.0
    for a, b in zip(pts, pts[1:]):
        total += math.hypot(b[0] - a[0], b[1] - a[1])
    return total * viewport.metres_per_point_x


def offsets_from_centreline(
    line_ys: Iterable[float], centreline_y: float, *, metres_per_point: float
) -> list[tuple[float, float, str]]:
    """Return ``(y, offset_m, side)`` for each line, ordered north to south."""

    out: list[tuple[float, float, str]] = []
    for y in line_ys:
        y = float(y)
        offset = (float(centreline_y) - y) * float(metres_per_point)
        out.append((y, abs(offset), "L" if offset > 0 else "R"))
    out.sort()
    return out


def check_against_printed(
    measured_m: float, printed_m: float, *, tolerance_m: float = 0.15
) -> dict[str, Any]:
    """Compare a measurement with a dimension printed on the drawing.

    The printed dimension is the authority. A measurement that cannot be tied to
    one is not finished, it is a hypothesis.
    """

    difference = float(measured_m) - float(printed_m)
    agrees = abs(difference) <= tolerance_m
    return {
        "measured_m": round(float(measured_m), 3),
        "printed_m": round(float(printed_m), 3),
        "difference_m": round(difference, 3),
        "tolerance_m": tolerance_m,
        "agrees": agrees,
        "findings": []
        if agrees
        else [
            f"measured value differs from the printed dimension by {difference:+.2f} m"
        ],
        "blocking": not agrees,
    }


def sheet_overlap_report(
    this_matchline_station: float,
    neighbour_matchline_station: float,
    *,
    agreed_cut_station: float | None = None,
) -> dict[str, Any]:
    """Quantify how far two adjacent sheets draw the same ground.

    Adjacent sheets do not necessarily share a matchline station. Measuring each
    sheet to its own matchline then double counts the difference.
    """

    low = min(float(this_matchline_station), float(neighbour_matchline_station))
    high = max(float(this_matchline_station), float(neighbour_matchline_station))
    overlap = high - low
    findings: list[str] = []
    if overlap > 0.5:
        findings.append(
            f"sheets both draw STA {low:.1f}-{high:.1f} ({overlap:.1f} m); "
            "cut both takeoffs at one agreed station"
        )
    cut_inside = None
    if agreed_cut_station is not None:
        cut_inside = low - 0.5 <= float(agreed_cut_station) <= high + 0.5
        if not cut_inside:
            findings.append(
                f"agreed cut STA {float(agreed_cut_station):.1f} is outside the "
                "overlap; ground between the cut and a matchline belongs to "
                "neither takeoff"
            )
    return {
        "overlap_m": round(overlap, 2),
        "overlap_from_station": round(low, 2),
        "overlap_to_station": round(high, 2),
        "agreed_cut_station": agreed_cut_station,
        "cut_inside_overlap": cut_inside,
        "findings": findings,
        "blocking": bool(findings),
    }
