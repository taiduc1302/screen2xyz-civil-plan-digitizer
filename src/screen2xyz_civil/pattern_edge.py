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
this detectable rather than a matter of taste. Note also that one side of the
oscillation repeats *exactly* - 1242.2, to 0.1 pt, every time. A constant like
that is the drawn line the strokes are clipped against, so snapping the
boundary to it is more accurate, not merely tidier: the excursions are the
pattern leaking into its own gaps.

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

    * `constant` - the side of the oscillation whose value repeats, which is
      the drawn line the strokes are clipped against. The accurate choice when
      one side really is constant, and what the Example Road boundaries want:
      their troughs repeat to 0.1 pt.
    * `outer` / `inner` - the extreme in the cross axis. Use these when the
      oscillation runs between two drawn lines and the drawing says which one
      bounds this item.

    Under `constant` a run whose two sides are *both* constant is left alone
    and listed in `ambiguous_runs`: that is not noise, it is an edge
    square-waving between two real lines, and which one applies is a scope
    question. `needs_a_scope_decision` says so.

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
                    "reason": ("both sides of the oscillation are constant, so this edge runs "
                               "between two drawn lines; choose keep='outer' or keep='inner' "
                               "against the drawing rather than letting a tolerance decide"),
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
        "note": ("A proposal. Snapping to the constant side removes the pattern's "
                 "excursions into its own gaps; render it against the drawing before "
                 "writing, and record the area change."),
    }
