"""Chain the fragments of one CAD layer into continuous lines.

A plotted line arrives in pieces. A dashed linetype is exported one dash per
object; an arc is flattened to chords, one object each; a polyline is often
split where the engineer's segments were. On DEMO-001 sheet 04 the proposed
pavement edge is 404 objects with a longest of 39 pt, and by eye it is a
dozen continuous lines with smooth curb returns.

Chaining joins fragments whose endpoints nearly meet **and whose directions
agree**. Both conditions matter: the gap tolerance alone would join a dash to
the driveway line that touches it, and direction alone would jump a gap the
engineer left on purpose. A join where two candidates both qualify is a
branch - a T with a driveway or a sidewalk - and is reported, not guessed.

The input is *one layer's* fragments (``cad_layers.objects_on_layer``), so
nothing from a gas line or a fence can enter a chain. That is the whole
reason to chain vectors instead of tracing a raster: the candidate set is
the engineer's, not a colour filter's. The chain is still geometry that has
to pass ``polygon_health`` / ``feature_identity`` and be looked at on the
sheet.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Sequence

Point = tuple[float, float]

#: Directions must agree within this many degrees at a join.
DEFAULT_ANGLE_TOL_DEG = 25.0
#: Auto gap tolerance = this multiple of the 90th-percentile nearest gap.
GAP_TOL_FACTOR = 1.5
#: Never let an automatic tolerance collapse below this many points.
MIN_GAP_TOL = 0.5
#: A continuation on our own line sits within this many points of the
#: line's axis. The proposed pavement edge on DEMO-001 sheet 04 is drawn
#: beside a parallel line 3.4 pt away (the printed 0.30 m gravel shoulder);
#: its dashes are as close and as well aligned as our own, and only the
#: lateral offset tells them apart. Two candidates inside this band are a
#: branch; one outside it is another line.
LATERAL_TOL = 1.5


def _as_points(fragment: Any) -> list[Point]:
    pts = fragment["points_raw"] if isinstance(fragment, dict) else fragment
    out: list[Point] = []
    for p in pts:
        q = (float(p[0]), float(p[1]))
        if not out or math.dist(out[-1], q) > 1e-9:
            out.append(q)
    return out


def _length(pts: Sequence[Point]) -> float:
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def _heading(a: Point, b: Point) -> float:
    return math.atan2(b[1] - a[1], b[0] - a[0])


def _angle_between(h1: float, h2: float) -> float:
    return abs((h1 - h2 + math.pi) % (2 * math.pi) - math.pi)


def nearest_gap_stats(fragments: Sequence[Sequence[Point]]) -> dict[str, float]:
    """Nearest-neighbour endpoint gap: median, 90th percentile, max.

    A dashed linetype has a constant gap, so the 90th percentile is the
    linetype's gap and everything beyond it is a real break.
    """

    ends = [(f[0], f[-1]) for f in fragments]
    gaps: list[float] = []
    for i, (a0, a1) in enumerate(ends):
        best = None
        for j, (b0, b1) in enumerate(ends):
            if j == i:
                continue
            d = min(math.dist(a1, b0), math.dist(a1, b1), math.dist(a0, b0), math.dist(a0, b1))
            if best is None or d < best:
                best = d
        if best is not None:
            gaps.append(best)
    if not gaps:
        return {"median": 0.0, "p90": 0.0, "max": 0.0, "count": 0}
    gaps.sort()
    return {
        "median": gaps[len(gaps) // 2],
        "p90": gaps[min(len(gaps) - 1, int(len(gaps) * 0.9))],
        "max": gaps[-1],
        "count": float(len(gaps)),
    }


#: Two fragments whose ends coincide within this many points are one
#: fragment plotted twice. A CAD export plots the same line once per xref
#: that carries it - DEMO-001 sheet 04's pavement edge arrives in two or
#: three coincident copies, and a duplicate defeats mutual-best linking
#: because each copy is the other's closest partner.
DUPLICATE_TOL = 0.5


def dedupe_fragments(frags: Sequence[Sequence[Point]], *, tol: float = DUPLICATE_TOL) -> tuple[list[int], int]:
    """Indexes of the fragments to keep, and how many duplicates were dropped.

    A duplicate has both ends within ``tol`` of another fragment's ends, in
    either orientation. The first occurrence is kept.
    """

    keep: list[int] = []
    kept_ends: list[tuple[Point, Point]] = []
    dropped = 0
    for i, f in enumerate(frags):
        a, b = f[0], f[-1]
        dup = False
        for (ka, kb) in kept_ends:
            if (math.dist(a, ka) <= tol and math.dist(b, kb) <= tol) or (
                math.dist(a, kb) <= tol and math.dist(b, ka) <= tol
            ):
                dup = True
                break
        if dup:
            dropped += 1
            continue
        keep.append(i)
        kept_ends.append((a, b))
    return keep, dropped


def _endpoints(frags: Sequence[Sequence[Point]]) -> list[tuple[int, int, Point, float]]:
    """(fragment, end 0|1, point, outward heading) for every fragment end."""

    out: list[tuple[int, int, Point, float]] = []
    for i, f in enumerate(frags):
        out.append((i, 0, f[0], _heading(f[1], f[0])))
        out.append((i, 1, f[-1], _heading(f[-2], f[-1])))
    return out


def _links(
    frags: Sequence[Sequence[Point]], *, gap_tol: float, angle_tol: float
) -> tuple[dict[tuple[int, int], tuple[int, int]], list[dict[str, Any]]]:
    """Mutual-best links between fragment ends, and the branches.

    Two ends may link when they lie within ``gap_tol`` and face each other
    within ``angle_tol``. Each end's best partner is the closest such end;
    a link is made only when the choice is mutual, so the order in which
    fragments are visited cannot change the result - a greedy walk that
    consumed fragments as it went left chains unable to meet each other.
    An end with more than one qualifying partner is a branch.
    """

    ends = _endpoints(frags)
    best: dict[tuple[int, int], tuple[int, int]] = {}
    branches: list[dict[str, Any]] = []
    for a in ends:
        i, ea, pa, ha = a
        ux, uy = math.cos(ha), math.sin(ha)
        cands: list[tuple[float, float, float, int, int]] = []
        for b in ends:
            j, eb, pb, hb = b
            if j == i:
                continue
            d = math.dist(pa, pb)
            if d > gap_tol:
                continue
            ang = _angle_between(ha, hb + math.pi)
            if ang > angle_tol:
                continue
            # where does the candidate sit relative to this end's own line?
            dx, dy = pb[0] - pa[0], pb[1] - pa[1]
            lon = dx * ux + dy * uy
            lat = abs(dx * uy - dy * ux)
            if lon < -LATERAL_TOL:
                continue  # behind us
            cands.append((round(lat, 1), d, ang, j, eb))
        if not cands:
            continue
        # the dash on our own line has no lateral offset; a parallel line's
        # dash is as close and as well aligned, but sits off the axis
        cands.sort()
        best[(i, ea)] = (cands[0][3], cands[0][4])
        others = sorted({c[3] for c in cands[1:] if c[0] <= cands[0][0] + LATERAL_TOL})
        if others:
            branches.append({
                "code": "CHAIN_BRANCH",
                "severity": "WARNING",
                "blocking": False,
                "at": pa,
                "fragment": i,
                "taken": cands[0][3],
                "alternatives": others,
                "detail": (
                    f"{len(others) + 1} fragments meet at ({pa[0]:.1f}, {pa[1]:.1f}) within "
                    f"{gap_tol:.2f} pt and {math.degrees(angle_tol):.0f} deg. A T with a "
                    "driveway or a sidewalk return - check the join on the sheet."
                ),
            })
    links: dict[tuple[int, int], tuple[int, int]] = {}
    for a, b in best.items():
        if best.get(b) == a:
            links[a] = b
    return links, branches


def chain_fragments(
    fragments: Iterable[Any],
    *,
    gap_tol: float | None = None,
    angle_tol_deg: float = DEFAULT_ANGLE_TOL_DEG,
    metres_per_unit: float | None = None,
) -> dict[str, Any]:
    """Join a layer's fragments into continuous polylines.

    ``fragments`` are point lists or ``objects_on_layer`` dicts. Coincident
    copies of a fragment are dropped first (``duplicates_removed``). ``gap_tol``
    defaults to 1.5 x the 90th-percentile nearest endpoint gap - the
    linetype's own gap. Returns chains sorted longest first, each with
    ``points``, ``length`` (and ``length_m`` when ``metres_per_unit`` is
    given), ``members`` (input indexes, in chain order), ``closed``; plus
    ``branches`` (joins where more than one fragment qualified),
    ``gap_stats`` and the ``gap_tol`` used.
    """

    frags = [_as_points(f) for f in fragments]
    usable = [i for i, f in enumerate(frags) if len(f) >= 2]
    keep, duplicates = dedupe_fragments([frags[i] for i in usable])
    index = [usable[k] for k in keep]
    live = [frags[i] for i in index]
    stats = nearest_gap_stats(live)
    if gap_tol is None:
        gap_tol = max(MIN_GAP_TOL, GAP_TOL_FACTOR * stats["p90"])
    angle_tol = math.radians(angle_tol_deg)

    links, branches = _links(live, gap_tol=gap_tol, angle_tol=angle_tol)
    used = [False] * len(live)
    chains: list[dict[str, Any]] = []

    def walk(start: int, enter_end: int) -> tuple[list[Point], list[int], bool]:
        # enter fragment `start` at `enter_end`, leave by the other end, follow links
        pts: list[Point] = []
        members: list[int] = []
        k, e = start, enter_end
        closed = False
        while True:
            used[k] = True
            f = live[k] if e == 0 else live[k][::-1]
            pts.extend(f if not pts else f[1:] if math.dist(pts[-1], f[0]) < 1e-9 else f)
            members.append(k)
            leave = 1 - e
            nxt = links.get((k, leave))
            if nxt is None:
                break
            if nxt[0] == start:
                closed = True
                break
            if used[nxt[0]]:
                break
            k, e = nxt
        return pts, members, closed

    # open runs first: start at ends that have no link
    free = [(k, e) for k in range(len(live)) for e in (0, 1) if (k, e) not in links]
    free.sort(key=lambda ke: (-_length(live[ke[0]]), ke))
    for k, e in free:
        if used[k]:
            continue
        pts, members, closed = walk(k, e)
        chains.append((pts, members, closed))
    # anything left is a closed loop
    for k in sorted(range(len(live)), key=lambda k: (-_length(live[k]), k)):
        if used[k]:
            continue
        pts, members, closed = walk(k, 0)
        chains.append((pts, members, closed))

    rows: list[dict[str, Any]] = []
    for pts, members, closed in chains:
        row: dict[str, Any] = {
            "points": pts,
            "length": _length(pts),
            "members": [index[m] for m in members],
            "closed": closed,
        }
        if metres_per_unit is not None:
            row["length_m"] = row["length"] * metres_per_unit
        rows.append(row)
    chains = rows
    chains.sort(key=lambda c: -c["length"])
    return {
        "chains": chains,
        "branches": branches,
        "gap_tol": gap_tol,
        "angle_tol_deg": angle_tol_deg,
        "gap_stats": stats,
        "fragments_in": len(frags),
        "fragments_used": len(live),
        "duplicates_removed": duplicates,
        "total_length": sum(c["length"] for c in chains),
    }


def chains_on_layer(
    doc: Any,
    page_index: int,
    layer: str,
    *,
    only: str | None = None,
    gap_tol: float | None = None,
    angle_tol_deg: float = DEFAULT_ANGLE_TOL_DEG,
    metres_per_unit: float | None = None,
) -> dict[str, Any]:
    """`chain_fragments` over `cad_layers.objects_on_layer` for one layer."""

    from .cad_layers import objects_on_layer

    objs = objects_on_layer(doc, page_index, layer, only=only)
    report = chain_fragments(
        objs, gap_tol=gap_tol, angle_tol_deg=angle_tol_deg, metres_per_unit=metres_per_unit
    )
    report["layer"] = layer
    report["page_index"] = page_index
    return report
