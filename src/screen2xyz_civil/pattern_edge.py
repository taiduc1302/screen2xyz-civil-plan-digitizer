"""Boundaries that chase a fill pattern instead of following a drawn line.

A hatch is a *fill*, not an edge. It is drawn as separate strokes with gaps
between them, so "how far the hatch reaches" is not a line - it oscillates
between the strokes and the gaps, at the pattern's own pitch, for ever.
Tracing that extent can only ever produce a sawtooth. The real edge is the line
the drawing draws; the pattern merely stops at it.

Measured on DEMO-001-05, the mill-and-overlay boundary against the widening:

    y alternates 1242.2 / 1248.5 / 1242.2 / 1248.6 / 1242.2 / 1248.7 ...
    period 11.9 pt = 1.05 m      hatch stroke pitch 13.6 pt = 1.20 m
    peak to peak 6.5 pt = 0.57 m

The period IS the pattern pitch. That is the signature, and it is what makes
this detectable rather than a matter of taste.

**The repair here is second best, and the reason matters.** An earlier version
of this file claimed the constant side of the oscillation was "the drawn line
the strokes are clipped against". That was wrong, and the drawing disproved it
the same day: the hatch region carries its own **drawn outline**, in the same
pen as the hatch, and it lies beyond *both* sides of the oscillation. The two
constants are the strokes' far ends and their near ends - peaks and troughs of
the pattern, not lines. On sheet 05 the outline sits at y 1190.9 and 1248.0
while the oscillation ran between 1242.2 and 1248.7.

So the real repair is to go and find the outline object, which `vector_fill`
does: it is emitted as a **polyline**, one drawing object carrying several path
items, where every hatch stroke is its own single-item object. Colour and width
cannot tell them apart; the object structure can. `flatten_to_envelope` below
only removes the sawtooth. It does not put the boundary on the drawn line, and
it must not be described as if it did.

Why the checks already here did not catch it:

* `bluebeam_bridge.polygon_health` measures self-intersection and
  perimeter/sqrt(area). A sawtooth raises the perimeter, but on a band that is
  already long and thin the ratio stays under the threshold.
* `vector_fill.raster_trace_signature` catches the *other* raster defect, a
  dense pixel-edge trace of 60+ vertices at ~8 pt spacing. The sheet 05
  boundary has 21 vertices at 13.5 pt and sails past it.
* Area reconciles, mutual overlap is zero, sum equals union. Every number
  agrees and the boundary is still not on a drawn feature.

So this module tests for periodicity, which is the thing that is actually
wrong, and puts the repair next to the diagnosis.
"""

from __future__ import annotations

import math
import statistics
from typing import Any, Iterable, Sequence

Point = tuple[float, float]


class PatternEdgeError(ValueError):
    """A boundary could not be examined for pattern chasing."""


# Four reversals is two full cycles: enough to have a period at all, few enough
# to catch a short boundary like the 53 sq m sheet 05 sliver.
MIN_REVERSALS = 4
# A pattern has one pitch, so its period is regular. Real geometry that happens
# to zigzag - a curb return, a driveway throat - is not.
MAX_PERIOD_SPREAD = 0.35
# Within this fraction of a supplied pattern pitch, the match is named.
PITCH_TOLERANCE = 0.30


def _as_points(points: Iterable[Sequence[float]]) -> list[Point]:
    rows: list[Point] = []
    for item in points:
        x, y = float(item[0]), float(item[1])
        if not (math.isfinite(x) and math.isfinite(y)):
            raise PatternEdgeError("boundary contains a non-finite coordinate")
        rows.append((x, y))
    return rows


def oscillation_profile(values: Sequence[float], positions: Sequence[float]) -> dict[str, Any]:
    """Reversals, period and amplitude of a run of cross-axis offsets.

    `values` are offsets perpendicular to the boundary's general direction and
    `positions` the distance along it. A straight edge never reverses; a
    pattern-chasing edge reverses at every stroke, evenly.
    """

    if len(values) != len(positions):
        raise PatternEdgeError("values and positions must be the same length")
    if len(values) < 3:
        return {"reversals": 0, "period_pt": 0.0, "period_spread": 0.0,
                "amplitude_pt": 0.0, "regular": False}

    deltas = [b - a for a, b in zip(values, values[1:])]
    turn_positions: list[float] = []
    amplitudes: list[float] = []
    previous = 0.0
    for index, delta in enumerate(deltas):
        if abs(delta) < 1e-9:
            continue
        if previous != 0.0 and (delta > 0) != (previous > 0):
            turn_positions.append(positions[index])
            amplitudes.append(abs(delta))
        previous = delta

    gaps = [b - a for a, b in zip(turn_positions, turn_positions[1:]) if b > a]
    period = statistics.median(gaps) if gaps else 0.0
    spread = (statistics.pstdev(gaps) / period) if len(gaps) > 1 and period else 0.0
    return {
        "reversals": len(turn_positions),
        "period_pt": period,
        "period_spread": spread,
        "amplitude_pt": statistics.median(amplitudes) if amplitudes else 0.0,
        "regular": (len(turn_positions) >= MIN_REVERSALS and period > 0
                    and spread <= MAX_PERIOD_SPREAD),
    }


def _dominant_axis(points: Sequence[Point]) -> int:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return 0 if (max(xs) - min(xs)) >= (max(ys) - min(ys)) else 1


def edge_runs(points: Sequence[Point], *, min_points: int = 5) -> list[list[int]]:
    """Index runs that travel steadily along one axis: the candidate edges.

    The ring is split where it turns a corner, so each long side is examined on
    its own rather than the whole outline at once.
    """

    rows = _as_points(points)
    if len(rows) < min_points:
        return []
    axis = _dominant_axis(rows)
    runs: list[list[int]] = []
    current: list[int] = [0]
    for index in range(1, len(rows)):
        step = rows[index][axis] - rows[index - 1][axis]
        if len(current) < 2:
            current.append(index)
            continue
        previous_step = rows[current[-1]][axis] - rows[current[-2]][axis]
        if step == 0.0 or previous_step == 0.0 or (step > 0) == (previous_step > 0):
            current.append(index)
        else:
            if len(current) >= min_points:
                runs.append(current)
            current = [index - 1, index]
    if len(current) >= min_points:
        runs.append(current)
    return runs


def oscillating_window(
    rows: Sequence[Point], indices: Sequence[int], axis: int, *, tolerance_pt: float = 0.6
) -> tuple[list[int], dict[str, Any]]:
    """The part of a run that is actually oscillating, and its profile.

    A run can carry a corner or a taper at its end - the outline leaving the
    edge. Those points are not part of the oscillation, and left in they do two
    kinds of harm: they drag a snapped line across the corner, and their single
    huge gap inflates the period spread until a real sawtooth stops reading as
    regular. So the periodicity is measured on the window, not on the run.

    The window is one full swing either side of the run's centre, sized from a
    provisional pass over the whole run.
    """

    cross = 1 - axis
    segment = [rows[i] for i in indices]
    provisional = oscillation_profile([p[cross] for p in segment], [p[axis] for p in segment])
    # Centre the window between the quartiles, not on the median. A square wave
    # rarely has equal counts on its two sides, and any corner points drag a
    # median toward the fuller side until the band clips the opposite peak -
    # which broke the alternation and made a clean sawtooth read as irregular.
    values = sorted(p[cross] for p in segment)
    if len(values) >= 4:
        quarters = statistics.quantiles(values, n=4)
        centre = (quarters[0] + quarters[2]) / 2.0
    else:
        centre = statistics.median(values)
    band = max(provisional["amplitude_pt"], tolerance_pt)
    inside = [i for i, p in zip(indices, segment) if abs(p[cross] - centre) <= band]
    if len(inside) < 3:
        return inside, provisional
    window = [rows[i] for i in inside]
    profile = oscillation_profile([p[cross] for p in window], [p[axis] for p in window])
    profile["points_in_window"] = len(inside)
    profile["points_outside_window"] = len(indices) - len(inside)
    return inside, profile


def pattern_chase_report(
    points: Iterable[Sequence[float]],
    *,
    pitch_pt: float | None = None,
    metres_per_unit: float | None = None,
) -> dict[str, Any]:
    """Does this boundary follow a drawn line, or the extent of a pattern?

    Pass `pitch_pt`, the pattern's stroke spacing, when it is known and a match
    is named in the detail. Without it the regular oscillation alone is still
    reported: a boundary that saws evenly is not one the drawing draws either
    way.
    """

    rows = _as_points(points)
    if len(rows) < 3:
        raise PatternEdgeError("a boundary needs at least three points")
    axis = _dominant_axis(rows)
    cross = 1 - axis
    worst: dict[str, Any] | None = None
    runs: list[dict[str, Any]] = []
    for indices in edge_runs(rows):
        inside, profile = oscillating_window(rows, indices, axis)
        if not inside:
            continue
        profile["from_index"] = inside[0]
        profile["to_index"] = inside[-1]
        if metres_per_unit:
            profile["period_m"] = profile["period_pt"] * metres_per_unit
            profile["amplitude_m"] = profile["amplitude_pt"] * metres_per_unit
        if pitch_pt and profile["period_pt"] > 0:
            ratio = profile["period_pt"] / float(pitch_pt)
            profile["pitch_ratio"] = ratio
            profile["matches_pitch"] = abs(ratio - 1.0) <= PITCH_TOLERANCE
        runs.append(profile)
        if profile["regular"] and (worst is None or profile["reversals"] > worst["reversals"]):
            worst = profile

    detail = ""
    if worst is not None:
        detail = (f"boundary reverses {worst['reversals']} times at a regular "
                  f"{worst['period_pt']:.1f} pt period")
        if metres_per_unit:
            detail += f" ({worst['period_pt'] * metres_per_unit:.2f} m)"
        detail += f", amplitude {worst['amplitude_pt']:.1f} pt"
        if worst.get("matches_pitch"):
            detail += (" - matching the pattern pitch, so this edge is tracing "
                       "the pattern rather than a drawn line")
        else:
            detail += " - a drawn edge does not oscillate evenly; check what this follows"
    return {
        "axis": "x" if axis == 0 else "y",
        "runs": runs,
        "chasing_pattern": worst is not None,
        "worst": worst,
        "detail": detail,
        "repair": "pattern_edge.flatten_to_envelope" if worst is not None else "",
    }


def flatten_to_envelope(
    points: Iterable[Sequence[float]],
    *,
    keep: str = "constant",
    tolerance_pt: float = 0.6,
    constant_tolerance_pt: float = 0.5,
) -> dict[str, Any]:
    """Replace each pattern-chasing run with the line the pattern stops at.

    `keep`:

    **A fallback.** This removes the sawtooth; it does not find the drawn line.
    Both sides of the oscillation are pattern extremes - the strokes' far ends
    and their near ends - and the drawing's own outline lies beyond both. Use
    `vector_fill` to take the outline object first, and only come here when the
    drawing genuinely draws no boundary for that interface.

    * `constant` - the side whose value repeats. The tidier of the two pattern
      extremes, nothing more.
    * `outer` / `inner` - the extreme in the cross axis.

    Under `constant` a run whose two sides are *both* constant is left alone
    and listed in `ambiguous_runs` with `needs_a_scope_decision`. Read that as
    "this module cannot choose", not as "the drawing offers two options": an
    earlier version said the latter and it was false.

    Returns a new ring and what it changed; never edits in place. It is a
    proposal, so render it against the drawing before writing and record the
    area change, like anything else here.
    """

    if keep not in ("constant", "outer", "inner"):
        raise PatternEdgeError(f"keep must be constant, outer or inner, not {keep!r}")
    rows = _as_points(points)
    if len(rows) < 3:
        raise PatternEdgeError("a boundary needs at least three points")
    axis = _dominant_axis(rows)
    cross = 1 - axis
    out: list[Point] = list(rows)
    changes: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []

    for indices in edge_runs(rows):
        inside, profile = oscillating_window(rows, indices, axis, tolerance_pt=tolerance_pt)
        if not profile["regular"] or len(inside) < MIN_REVERSALS:
            continue
        values = [rows[i][cross] for i in inside]
        # Split by which extreme each value is nearer, not by the median. A
        # square wave has most of its samples at the two ends and a few in
        # transition; a median split drops those transitional values into the
        # wrong cluster and inflates its spread, which on DEMO-001-05 hid the
        # fact that one side repeats to 0.04 pt.
        lo_end, hi_end = min(values), max(values)
        low = [v for v in values if abs(v - lo_end) <= abs(v - hi_end)]
        high = [v for v in values if abs(v - lo_end) > abs(v - hi_end)]
        if not low or not high:
            continue
        low_spread = statistics.pstdev(low) if len(low) > 1 else 0.0
        high_spread = statistics.pstdev(high) if len(high) > 1 else 0.0
        if keep == "constant":
            # When BOTH sides are constant the boundary is not noisy - it is
            # square-waving between two real drawn lines, and which one bounds
            # this item is a scope question the drawing answers, not a spread
            # comparison. On DEMO-001-05 the two sit 6.4 pt (0.57 m) apart and
            # both repeat to better than 0.1 pt. Refuse rather than pick.
            if low_spread <= constant_tolerance_pt and high_spread <= constant_tolerance_pt:
                ambiguous.append({
                    "from_index": inside[0], "to_index": inside[-1],
                    "low_value": statistics.median(low), "high_value": statistics.median(high),
                    "separation_pt": abs(statistics.median(high) - statistics.median(low)),
                    "low_spread": low_spread, "high_spread": high_spread,
                    "reason": ("both sides of the oscillation are constant, and both are "
                               "pattern extremes rather than drawn lines. Look for the hatch "
                               "region's own outline object with vector_fill; only if the "
                               "drawing draws no boundary here, choose keep='outer' or "
                               "keep='inner' deliberately"),
                })
                continue
            take_low = low_spread <= high_spread
            chosen = statistics.median(low if take_low else high)
            side = "low" if take_low else "high"
        elif keep == "outer":
            chosen, side = max(values), "high"
        else:
            chosen, side = min(values), "low"
        for i in inside:
            point = list(out[i])
            point[cross] = chosen
            out[i] = (point[0], point[1])
        changes.append({
            "from_index": inside[0], "to_index": inside[-1], "side": side,
            "snapped_to": chosen, "reversals": profile["reversals"],
            "amplitude_pt": profile["amplitude_pt"],
            "points_snapped": len(inside),
            "points_left_alone": len(indices) - len(inside),
            "moved_pt": max(abs(v - chosen) for v in values) if values else 0.0,
        })

    cleaned: list[Point] = []
    for point in out:
        if (not cleaned or abs(point[0] - cleaned[-1][0]) > tolerance_pt
                or abs(point[1] - cleaned[-1][1]) > tolerance_pt):
            cleaned.append(point)
    if (len(cleaned) >= 4 and abs(cleaned[0][0] - cleaned[-1][0]) <= tolerance_pt
            and abs(cleaned[0][1] - cleaned[-1][1]) <= tolerance_pt):
        cleaned.pop()
    ring = cleaned if len(cleaned) >= 3 else out

    return {
        "ring": ring,
        "runs_flattened": len(changes),
        "changes": changes,
        "ambiguous_runs": ambiguous,
        "needs_a_scope_decision": bool(ambiguous),
        "vertices_before": len(rows),
        "vertices_after": len(ring),
        "note": ("A fallback, not the drawn line. It removes the sawtooth and leaves "
                 "the boundary on a pattern extreme. Look for the hatch region's own "
                 "outline object first (vector_fill); render whatever you keep against "
                 "the drawing before writing, and record the area change."),
    }


#: Share of edges that must land on the pitch lattice before a boundary is
#: called a hull of the pattern's points.
LATTICE_SHARE = 0.6
#: An edge is "on the lattice" when its length is within this fraction of
#: the pitch from an integer multiple of it.
LATTICE_TOL = 0.12


def lattice_report(
    points: Iterable[Sequence[float]], *, pitch_pt: float, min_edges: int = 8
) -> dict[str, Any]:
    """Is this boundary a hull drawn through the points of a stipple?

    A concave hull of a dotted fill's points has no sawtooth - each vertex
    sits on a dot - so `pattern_chase_report` does not see it. What gives
    it away is that every edge joins two dots on the same lattice: edge
    lengths are integer multiples of the pitch (5.2, 10.4, 20.6 ... at a
    5.1 pt stipple). A drawn outline has no such preference. On DEMO-001-06
    five ditch-infill polygons reached the host this way and passed every
    other check.
    """

    if pitch_pt is None or pitch_pt <= 0:
        raise PatternEdgeError("pitch_pt must be a positive length")
    rows = _as_points(points)
    if len(rows) >= 2 and rows[0] == rows[-1]:
        rows = rows[:-1]
    # Merge collinear runs first: a straight edge that happens to carry
    # vertices at the pitch (a flattened envelope keeps them) is one edge,
    # not a run of lattice edges. Only real corners count.
    corners: list[Point] = []
    n = len(rows)
    for i in range(n):
        a, b, c = rows[i - 1], rows[i], rows[(i + 1) % n]
        h1 = math.atan2(b[1] - a[1], b[0] - a[0])
        h2 = math.atan2(c[1] - b[1], c[0] - b[0])
        turn = abs((h2 - h1 + math.pi) % (2 * math.pi) - math.pi)
        if turn > math.radians(5.0):
            corners.append(b)
    rows = corners if len(corners) >= 3 else rows
    # A stipple is a grid, so an edge between two of its points has BOTH
    # components on the pitch: (dx, dy) = (i, j) x pitch. Its length is a
    # multiple only when i or j is zero, which is why a length test misses
    # the diagonals. Axis-aligned grids only; a rotated stipple would need
    # its axes found first.
    vectors = []
    for i in range(len(rows)):
        a, b = rows[i], rows[(i + 1) % len(rows)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        if abs(dx) > 1e-9 or abs(dy) > 1e-9:
            vectors.append((dx, dy))
    on = 0
    tol = LATTICE_TOL * pitch_pt
    for dx, dy in vectors:
        kx, ky = round(dx / pitch_pt), round(dy / pitch_pt)
        if (kx, ky) != (0, 0) and abs(dx - kx * pitch_pt) <= tol and abs(dy - ky * pitch_pt) <= tol:
            on += 1
    share = on / len(vectors) if vectors else 0.0
    on_lattice = len(vectors) >= min_edges and share >= LATTICE_SHARE
    return {
        "edges": len(vectors),
        "on_lattice_edges": on,
        "share": share,
        "pitch_pt": pitch_pt,
        "on_lattice": on_lattice,
        "detail": (
            f"{on} of {len(vectors)} edges (after merging collinear runs) have both components "
            f"on the {pitch_pt:.1f} pt grid (within {LATTICE_TOL * 100:.0f}%)"
        ),
    }
