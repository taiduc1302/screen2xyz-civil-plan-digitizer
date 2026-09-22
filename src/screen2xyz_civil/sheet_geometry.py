"""Vector geometry helpers for combined plan-and-profile civil sheets.

Source-agnostic. Nothing here knows about a particular job, client, drawing set or
coordinate system; every dimension is a caller-supplied parameter.

The module exists because four separate extraction defects were observed on real
combined sheets, each of which returns a plausible, wrong answer rather than an error:

``flip_y``
    PDF drawing and text coordinates are top-down; several markup and takeoff tools use a
    bottom-up page space. A mirrored copy near mid-page lands close enough to the original
    to look correct, so the mistake does not announce itself.

``segments``
    Curve items must be flattened, and rectangle and quad items expanded. Skipping curves
    silently deletes every rounded nose, kerb return and cul-de-sac; skipping rectangles
    deletes every axis-aligned pad and box. Both are shapes likely to be a closed feature
    worth finding, and both vanish without raising anything.

``chains``
    Segments are joined only when they share an endpoint **and** a style. Loosening the
    snap tolerance to close a stubborn outline merges the two sides of a narrow feature and
    shrinks it; see ``SNAP_CEILING_NOTE``.

``plan_band``
    On a combined sheet the plan sits above the profile, so a page-level filter cannot
    work. The discriminator is the standalone view title, not the sheet title, which names
    both views on every page.

Optional dependencies: this module needs ``pymupdf`` and ``shapely``. They are not in
``requirements.txt`` because the rest of the application does not use them; import this
module only where they are available.

Treat outputs as preliminary. A sweep built on these helpers should carry a control case
whose answer is already known and report it alongside every run -- see ``README`` notes in
``docs/``.
"""

from __future__ import annotations

import collections
import math
from typing import Iterable, Sequence

__all__ = [
    "SNAP_CEILING_NOTE",
    "flip_y",
    "flatten_cubic",
    "segments",
    "chains",
    "closed_rings",
    "label_points",
    "plan_band",
    "group_offsets",
    "boundary_offset",
]

SNAP_CEILING_NOTE = (
    "Raising the chain snap tolerance to force an open outline closed will merge the two "
    "sides of any feature narrower than the tolerance. Validate a snap change against a "
    "control feature of known area before adopting it; if the control moves, the tolerance "
    "is too high whatever it does to the stubborn outline."
)


def flip_y(y: float, page_height: float) -> float:
    """Convert a top-down PDF y to a bottom-up page y, or back. The operation is its own
    inverse, which is why an unflipped copy is easy to mistake for a flipped one."""
    return page_height - y


def flatten_cubic(p0, p1, p2, p3, steps: int = 8):
    """Flatten one cubic Bezier to ``steps`` points, excluding the start point."""
    out = []
    for i in range(1, steps + 1):
        t = i / steps
        u = 1.0 - t
        out.append(
            (
                u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0],
                u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1],
            )
        )
    return out


def segments(page, page_height: float, colours: Iterable | None = None,
             min_len_pt: float = 0.5, curve_steps: int = 8):
    """Return ``[(a, b, colour, width)]`` in bottom-up page space.

    Handles line, cubic curve, rectangle and quad items. Curves are flattened to
    ``curve_steps`` chords; rectangles and quads are expanded to their closed edge loops.
    An item kind that is not handled is skipped silently by the producer, so extend this
    function rather than filtering downstream.

    ``colours`` optionally restricts to an iterable of RGB triples rounded to three places.
    """
    wanted = None if colours is None else {tuple(round(c, 3) for c in col) for col in colours}
    out = []
    for drawing in page.get_drawings():
        colour = tuple(round(c, 3) for c in (drawing.get("color") or ()))
        if wanted is not None and colour not in wanted:
            continue
        width = round(drawing.get("width") or 0.0, 2)
        for item in drawing["items"]:
            kind = item[0]
            if kind == "l":
                pts = [(item[1].x, flip_y(item[1].y, page_height)),
                       (item[2].x, flip_y(item[2].y, page_height))]
            elif kind == "c":
                ctrl = [(item[k].x, flip_y(item[k].y, page_height)) for k in (1, 2, 3, 4)]
                pts = [ctrl[0]] + flatten_cubic(*ctrl, steps=curve_steps)
            elif kind == "re":
                rect = item[1]
                corners = [(rect.x0, rect.y0), (rect.x1, rect.y0),
                           (rect.x1, rect.y1), (rect.x0, rect.y1)]
                pts = [(x, flip_y(y, page_height)) for x, y in corners]
                pts.append(pts[0])
            elif kind == "qu":
                quad = item[1]
                pts = [(p.x, flip_y(p.y, page_height))
                       for p in (quad.ul, quad.ur, quad.lr, quad.ll)]
                pts.append(pts[0])
            else:
                continue
            for a, b in zip(pts, pts[1:]):
                if math.hypot(b[0] - a[0], b[1] - a[1]) >= min_len_pt:
                    out.append((a, b, colour, width))
    return out


def chains(segs: Sequence, snap: float = 0.1):
    """Join segments sharing an endpoint and a style into ``[(points, colour, width)]``.

    See ``SNAP_CEILING_NOTE`` before raising ``snap``.
    """
    def key(p):
        return (round(p[0] / snap) * snap, round(p[1] / snap) * snap)

    adjacency = collections.defaultdict(list)
    for index, (a, b, colour, width) in enumerate(segs):
        adjacency[(key(a), colour, width)].append(index)
        adjacency[(key(b), colour, width)].append(index)

    seen: set[int] = set()
    out = []
    for index in range(len(segs)):
        if index in seen:
            continue
        a, b, colour, width = segs[index]
        seen.add(index)
        run = [a, b]
        for from_start in (True, False):
            while True:
                tip = run[0] if from_start else run[-1]
                candidates = [j for j in adjacency[(key(tip), colour, width)] if j not in seen]
                if not candidates:
                    break
                j = candidates[0]
                seen.add(j)
                ja, jb, _, _ = segs[j]
                other = jb if key(ja) == key(tip) else ja
                if from_start:
                    run.insert(0, other)
                else:
                    run.append(other)
        out.append((run, colour, width))
    return out


def closed_rings(chain_list: Sequence, units_per_pt: float = 1.0,
                 min_area: float = 2.0, max_area: float = 400.0, gap: float = 1.5):
    """Chains that close on themselves, as ``[(polygon, ring, colour, width)]``.

    Areas and the closing ``gap`` are expressed in the caller's units; ``units_per_pt``
    converts from page points. Requires ``shapely``.
    """
    from shapely.geometry import LineString, Polygon

    out = []
    for run, colour, width in chain_list:
        if len(run) < 4:
            continue
        closing = math.hypot(run[0][0] - run[-1][0], run[0][1] - run[-1][1]) * units_per_pt
        if closing > gap:
            continue
        try:
            poly = Polygon(run).buffer(0)
        except Exception:
            continue
        if poly.is_empty:
            continue
        area = poly.area * units_per_pt * units_per_pt
        if not (min_area <= area <= max_area):
            continue
        out.append((poly, LineString(list(run) + [run[0]]), colour, width))
    return out


def label_points(page, page_height: float, words: Iterable[str]):
    """``[(text, x, y)]`` in bottom-up page space for the given upper-case words."""
    wanted = {w.upper() for w in words}
    out = []
    for word in page.get_text("words"):
        text = word[4].upper().strip()
        if text in wanted:
            out.append((text, (word[0] + word[2]) / 2.0,
                        flip_y((word[1] + word[3]) / 2.0, page_height)))
    return out


def plan_band(page, page_height: float, notes_x: float,
              title_word: str = "PLAN", paired_word: str = "PROFILE",
              pair_dy: float = 6.0, pair_dx: float = 140.0,
              upper_fraction: float = 0.5):
    """Locate the plan view's y band on a combined plan-and-profile sheet.

    Returns ``(y_low, y_high, titles)`` in bottom-up space, or ``None`` when the sheet
    carries no standalone view title and therefore no plan view.

    The discriminator is a standalone ``title_word`` that is **not** part of a combined
    caption -- a sheet whose caption reads "PLAN & PROFILE" names both views on every page,
    so the sheet title cannot classify it. ``notes_x`` excludes a right-hand boilerplate
    column, which on real sheets repeats both words on every page and will otherwise
    dominate the match.

    Derive the band per page rather than hardcoding it; a value measured on one sheet set
    is not portable.
    """
    words = [
        (w[4].strip().upper(), (w[0] + w[2]) / 2.0, flip_y((w[1] + w[3]) / 2.0, page_height))
        for w in page.get_text("words")
    ]
    titles_all = [(x, y) for t, x, y in words if t == title_word.upper() and x < notes_x]
    paired = [(x, y) for t, x, y in words if t == paired_word.upper() and x < notes_x]

    titles = []
    for x, y in titles_all:
        if any(abs(py - y) < pair_dy and abs(px - x) < pair_dx for px, py in paired):
            continue  # part of a combined caption
        if y < page_height * (1.0 - upper_fraction):
            continue  # below the halfway line: a detail caption, not the plan title
        titles.append((x, y))

    if not titles:
        return None

    # The view title sits below the view it names; the lowest such title bounds the plan.
    y_low = min(y for _, y in titles)
    return (y_low, page_height, titles)


def group_offsets(offsets: Sequence[float], max_gap: float):
    """Collapse offsets into groups, as ``[(near_end, far_end)]`` sorted ascending.

    Two parallel lines closer than ``max_gap`` are one feature, not two. Choose ``max_gap``
    from the measured separation distribution of the sheet set rather than from a nominal
    figure, and check that the two populations actually separate; if they do not, the
    parameter is not describing what you think it is.
    """
    ordered = sorted(offsets)
    groups: list[list[float]] = []
    for value in ordered:
        if groups and value - groups[-1][1] <= max_gap:
            groups[-1][1] = value
        else:
            groups.append([value, value])
    return [tuple(g) for g in groups]


def boundary_offset(groups: Sequence[tuple], edges: Sequence[float],
                    cut_half_width: float, sign: int, escalate_on_entry: bool = False):
    """Where a restoration boundary lands on one side of a centred cut.

    ``sign`` is ``-1`` for the negative side, ``+1`` for the positive. ``groups`` come from
    :func:`group_offsets`; ``edges`` are hard boundaries such as a kerb face.

    Three outcomes, and the distinction between the last two is the whole point:

    * the cut does not reach the group -> the boundary is the group's **near** face;
    * the cut enters the group but does not pass its **far** line -> the boundary is the far
      face, absorbing the group and stopping;
    * the cut passes the far line -> escalate to the next feature beyond.

    A single line has one face, so reaching it is crossing it, and only a genuine pair can
    produce the middle outcome. Set ``escalate_on_entry`` to reproduce the cruder rule that
    escalates as soon as the cut touches a group; comparing the two is a useful check, since
    a downstream table that disagrees with the entry rule but agrees with this one is
    implementing the subtler rule rather than being wrong.

    Returns ``(offset, tag)``.
    """
    cut_edge = sign * cut_half_width
    side = [g for g in groups if (g[0] < 0 if sign < 0 else g[1] > 0)]
    side.sort(key=lambda g: abs(g[0] if sign < 0 else g[1]))
    side_edges = [e for e in edges if (e < 0 if sign < 0 else e > 0)]

    last_far = None
    for group in side:
        near = group[1] if sign < 0 else group[0]
        far = group[0] if sign < 0 else group[1]
        last_far = far
        reaches = cut_edge <= near if sign < 0 else cut_edge >= near
        if not reaches:
            return near, "NEAR"
        crosses = cut_edge < far if sign < 0 else cut_edge > far
        if not escalate_on_entry and not crosses:
            return far, "FAR"
        continue  # escalate past this group

    if side_edges:
        return (max(side_edges) if sign < 0 else min(side_edges)), "EDGE"
    return (last_far if last_far is not None else cut_edge), "EDGE"
