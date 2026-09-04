"""Fail-closed checks between a Screen2XYZ session and a live Bluebeam host.

Every check in this module exists because the failure it catches actually
happened during the 2026-09-02 owner-machine Example Road Sheet 03 run, was only
noticed by luck, and would otherwise have reached an estimator as a plausible
looking number. The module is deliberately pure: it never calls Bluebeam. The
operator reads the host through whatever MCP surface is available and passes
the values in, so these rules apply identically to a live connector, a GUI
transcript, or a replayed fixture.

Failures observed, and the function that now catches each one:

1. A polygon whose vertex order crossed itself was written to the host. The
   host returned a small, plausible area (14.84 sq m) and a nonsense perimeter
   (247 m) for it, and the geometry looked fine in the vertex list.
   -> `polygon_health`
2. Three polygons were written using coordinates taken from the sheet's
   PROFILE band while their quantities were interpreted with the PLAN band's
   scale. Nothing appeared on the plan drawing, and the areas came back
   "wrong by exactly 5.00x" - which an earlier pass wrote down as a Bluebeam
   defect. It was not: 5.00 is that sheet's plan/profile axis-scale ratio, and
   the host was correct. Corrected 2026-09-03.
   -> `plan_layers.single_viewport_check` (root cause, canonical),
      `cross_check_quantity` (symptom)
3. Long provenance text was written into Bluebeam's `label`, which the host
   renders on the sheet itself, covering the drawing with unreadable text.
   -> `markup_text_plan`
4. The session's page and the page actually worked in the host drifted apart
   (session page 5, work done on page 3) because a viewer page label and the
   consultant drawing number were treated as the same identifier.
   -> `page_identity_report`
5. The session and the host became two disagreeing records of the same work.
   -> `reconcile`
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from . import pattern_edge


Point = tuple[float, float]

# Bluebeam renders `label` onto the sheet. Anything longer than a short tag
# turns the drawing into unreadable overlapping text, so long provenance must
# stay in the session record instead.
MAX_LABEL_CHARS = 48
MAX_SUBJECT_CHARS = 96


class BridgeError(ValueError):
    """A bridge contract was violated in a way that must not be worked around."""


@dataclass(frozen=True)
class Finding:
    """One check result. `blocking` findings must reach a human, never a total."""

    code: str
    severity: str
    detail: str
    blocking: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "detail": self.detail,
            "blocking": self.blocking,
        }


def _as_points(points: Iterable[Sequence[float]]) -> list[Point]:
    rows: list[Point] = []
    for point in points:
        values = tuple(float(value) for value in point)
        if len(values) != 2:
            raise BridgeError("each point must contain exactly x and y")
        if not all(math.isfinite(value) for value in values):
            raise BridgeError("point coordinates must be finite")
        rows.append((values[0], values[1]))
    return rows


def shoelace_area(points: Iterable[Sequence[float]]) -> float:
    """Signed-area magnitude of a closed polygon, in input units squared."""

    rows = _as_points(points)
    if len(rows) < 3:
        raise BridgeError("polygon area requires at least three points")
    total = 0.0
    for (x1, y1), (x2, y2) in zip(rows, rows[1:] + rows[:1]):
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def perimeter(points: Iterable[Sequence[float]], *, closed: bool = True) -> float:
    """Path length; closed adds the segment back to the first point."""

    rows = _as_points(points)
    if len(rows) < 2:
        raise BridgeError("perimeter requires at least two points")
    pairs = zip(rows, rows[1:] + rows[:1]) if closed else zip(rows, rows[1:])
    return sum(math.hypot(x2 - x1, y2 - y1) for (x1, y1), (x2, y2) in pairs)


def _orientation(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Point, b: Point, c: Point) -> bool:
    return (
        min(a[0], b[0]) - 1e-9 <= c[0] <= max(a[0], b[0]) + 1e-9
        and min(a[1], b[1]) - 1e-9 <= c[1] <= max(a[1], b[1]) + 1e-9
    )


def _segments_cross(p1: Point, p2: Point, p3: Point, p4: Point) -> bool:
    d1 = _orientation(p3, p4, p1)
    d2 = _orientation(p3, p4, p2)
    d3 = _orientation(p1, p2, p3)
    d4 = _orientation(p1, p2, p4)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return True
    for base_a, base_b, other in (
        (p3, p4, p1),
        (p3, p4, p2),
        (p1, p2, p3),
        (p1, p2, p4),
    ):
        if abs(_orientation(base_a, base_b, other)) <= 1e-9 and _on_segment(
            base_a, base_b, other
        ):
            return True
    return False


def _normalise_ring(rows: list[Point]) -> list[Point]:
    """Drop the vertices that make an edge of zero length.

    A ring written the way shapely writes one repeats its first vertex at the
    end; a ring rounded to 0.1 pt by the host can carry two consecutive equal
    vertices. Either gives a zero-length edge, and an edge of zero length
    "touches" its neighbours at a shared point, which the touch test below
    reported as a self-intersection on polygons that shapely called valid
    (2026-09-03, all five sheet 05 polygons). The polygon is the same without
    those vertices; the checks are only right without them.
    """

    out: list[Point] = []
    for point in rows:
        if out and abs(point[0] - out[-1][0]) <= 1e-9 and abs(point[1] - out[-1][1]) <= 1e-9:
            continue
        out.append(point)
    while len(out) > 1 and abs(out[0][0] - out[-1][0]) <= 1e-9 and abs(out[0][1] - out[-1][1]) <= 1e-9:
        out.pop()
    return out


def self_intersections(points: Iterable[Sequence[float]]) -> list[tuple[int, int]]:
    """Return index pairs of crossing, non-adjacent edges of a closed polygon.

    Indices refer to the ring with zero-length edges removed (see
    `_normalise_ring`); the ring is closed implicitly, do not repeat the
    first vertex.
    """

    rows = _normalise_ring(_as_points(points))
    count = len(rows)
    if count < 4:
        return []
    edges = [(rows[i], rows[(i + 1) % count]) for i in range(count)]
    crossings: list[tuple[int, int]] = []
    for i in range(count):
        for j in range(i + 1, count):
            if j == i or (j + 1) % count == i or (i + 1) % count == j:
                continue
            if _segments_cross(*edges[i], *edges[j]):
                crossings.append((i, j))
    return crossings


def polygon_health(
    points: Iterable[Sequence[float]],
    *,
    metres_per_unit: float | None = None,
    sliver_ratio_threshold: float = 25.0,
    pattern_pitch_pt: float | None = None,
    check_pattern_chase: bool = True,
) -> dict[str, Any]:
    """Check a polygon before it is written to Bluebeam.

    `sliver_ratio_threshold` guards perimeter / sqrt(area). A square scores 4.0
    and a legitimately long road corridor scores roughly 7-8, so the default is
    deliberately loose: it is meant to catch the 60+ scores produced by a
    crossed or spiked outline, not to argue with a genuinely elongated strip.
    """

    rows = _normalise_ring(_as_points(points))
    findings: list[Finding] = []
    if len(rows) < 3:
        raise BridgeError("polygon health requires at least three points")

    crossings = self_intersections(rows)
    area = shoelace_area(rows)
    ring = perimeter(rows, closed=True)
    ratio = ring / math.sqrt(area) if area > 0 else math.inf

    if crossings:
        findings.append(
            Finding(
                code="POLYGON_SELF_INTERSECTS",
                severity="ERROR",
                detail=(
                    f"{len(crossings)} crossing edge pair(s), first at edges "
                    f"{crossings[0][0]}/{crossings[0][1]}. A host may still report a "
                    "plausible-looking area for this shape; it is not a valid outline."
                ),
                blocking=True,
            )
        )
    if area <= 0:
        findings.append(
            Finding(
                code="POLYGON_DEGENERATE_AREA",
                severity="ERROR",
                detail="Polygon encloses no area.",
                blocking=True,
            )
        )
    elif ratio > sliver_ratio_threshold:
        # Blocking on purpose. The 2026-09-02 outline that reached the host
        # scored 29.4 here, was NOT self-intersecting, and still produced a
        # meaningless host quantity. A warning would have been ignored exactly
        # as it was that day, so this stops the write and makes the operator
        # either fix the outline or override it deliberately.
        findings.append(
            Finding(
                code="POLYGON_SLIVER_SUSPECTED",
                severity="ERROR",
                detail=(
                    f"perimeter/sqrt(area) = {ratio:.1f}, above {sliver_ratio_threshold:.0f}. "
                    "Typical of a stray vertex dragged away from the real outline. A square scores "
                    "4.0 and a long road corridor about 7-8, so this shape is not simply elongated."
                ),
                blocking=True,
            )
        )

    # A boundary that oscillates evenly is following a fill pattern's extent,
    # not a drawn line, and no other check here can see it: a sawtooth raises
    # the perimeter but stays under the sliver ratio on a band that is already
    # long and thin, and the area reconciles perfectly with itself. Blocking,
    # because on DEMO-001-05 it reached the host and sat there being wrong by
    # 0.57 m along the whole edge while every number agreed.
    if check_pattern_chase and len(rows) >= 8:
        chase = pattern_edge.pattern_chase_report(
            rows, pitch_pt=pattern_pitch_pt, metres_per_unit=metres_per_unit
        )
        if chase["chasing_pattern"]:
            findings.append(
                Finding(
                    code="BOUNDARY_CHASES_A_PATTERN",
                    severity="ERROR",
                    detail=(
                        f"{chase['detail']}. A hatch is a fill, not an edge - its extent "
                        "oscillates at its own pitch for ever, so a boundary taken from it "
                        "can never be the drawn line. The hatch region carries its own "
                        "drawn outline in the same pen - a polyline object, where each stroke "
                        "is a single-item object - so take the edge from vector_fill. "
                        "pattern_edge.flatten_to_envelope only removes the sawtooth and leaves "
                        "the boundary on a pattern extreme; use it only where the drawing "
                        "draws no boundary at all."
                    ),
                    blocking=True,
                )
            )

    # A concave hull through the points of a stipple has no sawtooth, so the
    # check above passes it; its edges are integer multiples of the pitch.
    # Five ditch-infill polygons on DEMO-001-06 reached the host that way.
    if check_pattern_chase and pattern_pitch_pt and len(rows) >= 8:
        lattice = pattern_edge.lattice_report(rows, pitch_pt=pattern_pitch_pt)
        if lattice["on_lattice"]:
            findings.append(
                Finding(
                    code="BOUNDARY_ON_A_PATTERN_LATTICE",
                    severity="ERROR",
                    detail=(
                        f"{lattice['detail']}: the vertices sit on the pattern's own points, "
                        "so this is a hull of the fill, not a drawn line. Find the lines that "
                        "bound the region (toe of slope, pavement edge, curb return, the next "
                        "region's outline) and build the boundary from their chains; use the "
                        "hull only to say which side is inside."
                    ),
                    blocking=True,
                )
            )

    report: dict[str, Any] = {
        "vertex_count": len(rows),
        "self_intersections": crossings,
        "area_units2": area,
        "perimeter_units": ring,
        "compactness_ratio": ratio,
        "findings": [item.to_dict() for item in findings],
        "blocking": any(item.blocking for item in findings),
        "safe_to_write": not any(item.blocking for item in findings),
    }
    if metres_per_unit is not None:
        factor = float(metres_per_unit)
        if factor <= 0:
            raise BridgeError("metres_per_unit must be positive")
        report["area_m2"] = area * factor * factor
        report["perimeter_m"] = ring * factor
    return report


def cross_check_quantity(
    *,
    expected: float,
    reported: float,
    unit: str,
    tolerance_percent: float = 1.0,
) -> dict[str, Any]:
    """Compare an independently computed quantity with what the host reported.

    A clean ratio between the two is the signature of a **scale-context**
    disagreement, and on 2026-09-03 it was traced to its real cause: three
    polygons had been drawn into Sheet 03's PROFILE viewport instead of its
    PLAN viewport. Revu was right; it applied the profile's anisotropic scale
    (Cx=0.0881944, Cy=0.0176389 m/pt) because that is where the vertices were.
    Cx/Cy = 5.00 exactly, which is the "x5" that an earlier pass mistook for a
    host defect.

    So a ratio finding here means *the caller's assumed scale is not the scale
    the host applied to that geometry* - normally because the geometry is in a
    different viewport than intended. Run `plan_layers.single_viewport_check`
    first; do not report it as a host bug, and do not substitute the locally
    computed number, because in that situation both values are meaningless.
    """

    expected = float(expected)
    reported = float(reported)
    if not math.isfinite(expected) or not math.isfinite(reported):
        raise BridgeError("quantities must be finite")
    if expected <= 0:
        raise BridgeError("expected quantity must be positive")

    error_percent = abs(reported - expected) / expected * 100.0
    agrees = error_percent <= float(tolerance_percent)
    findings: list[Finding] = []
    integer_ratio: int | None = None

    if not agrees and reported > 0:
        ratio = expected / reported
        nearest = round(ratio)
        if nearest >= 2 and abs(ratio - nearest) / nearest <= 0.01:
            integer_ratio = int(nearest)
            findings.append(
                Finding(
                    code="SCALE_CONTEXT_MISMATCH",
                    severity="ERROR",
                    detail=(
                        f"Host reported {reported:g} {unit} where {expected:g} {unit} was computed "
                        f"from the same geometry - almost exactly 1/{integer_ratio}. A clean ratio "
                        "means the host applied a different scale than the one assumed here, which "
                        "in practice means the geometry sits in a different viewport (a profile or "
                        "section band applies an anisotropic scale; on Example Road Sheet 03 the plan/"
                        "profile axis ratio is exactly 5.00). Run plan_layers.single_viewport_check before "
                        "anything else. Neither number is usable for a bid until the geometry is "
                        "confirmed to be in the intended viewport - do not publish the host value "
                        "and do not substitute the computed one."
                    ),
                    blocking=True,
                )
            )
        else:
            findings.append(
                Finding(
                    code="HOST_QUANTITY_MISMATCH",
                    severity="ERROR",
                    detail=(
                        f"Host reported {reported:g} {unit}, computed {expected:g} {unit} "
                        f"({error_percent:.2f}% apart, tolerance {tolerance_percent:g}%)."
                    ),
                    blocking=True,
                )
            )

    return {
        "expected": expected,
        "reported": reported,
        "unit": unit,
        "error_percent": error_percent,
        "agrees": agrees,
        "integer_ratio": integer_ratio,
        "findings": [item.to_dict() for item in findings],
        "blocking": any(item.blocking for item in findings),
    }


def markup_text_plan(
    *,
    rule_id: str,
    instance: str,
    quantity_text: str = "",
    sheet_label: str = "",
    provenance: str = "",
) -> dict[str, Any]:
    """Build host-safe markup text and keep provenance out of the drawing.

    Bluebeam draws `label` on the sheet. Long provenance placed there covered
    the Example Road plan with overlapping red text, which is why this returns an
    empty label by default and hands the long text back under `session_notes`
    for the `.s2a.json` record instead.
    """

    rule = str(rule_id).strip()
    if not rule:
        raise BridgeError("rule_id is required")
    parts = [rule, str(instance).strip()]
    if sheet_label.strip():
        parts.append(f"Sheet {sheet_label.strip()}")
    if quantity_text.strip():
        parts.append(quantity_text.strip())
    subject = " | ".join(part for part in parts if part)

    findings: list[Finding] = []
    if len(subject) > MAX_SUBJECT_CHARS:
        subject = subject[: MAX_SUBJECT_CHARS - 1].rstrip() + "…"
        findings.append(
            Finding(
                code="SUBJECT_TRUNCATED",
                severity="INFO",
                detail=f"Subject trimmed to {MAX_SUBJECT_CHARS} characters for host display.",
            )
        )
    if len(provenance) > 0:
        findings.append(
            Finding(
                code="PROVENANCE_KEPT_OUT_OF_PDF",
                severity="INFO",
                detail=(
                    "Provenance text is returned for the session record only; writing it to the "
                    "host `label` would render it across the sheet."
                ),
            )
        )

    return {
        "subject": subject,
        "label": "",
        "comment": "",
        "session_notes": provenance,
        "findings": [item.to_dict() for item in findings],
    }


def audit_host_text(markups: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Flag host markups whose text will render as clutter on the sheet."""

    offenders: list[dict[str, Any]] = []
    for markup_id, properties in markups.items():
        label = str(properties.get("label") or "")
        subject = str(properties.get("subject") or "")
        reasons = []
        if len(label) > MAX_LABEL_CHARS:
            reasons.append(f"label {len(label)} chars (max {MAX_LABEL_CHARS}, renders on sheet)")
        if len(subject) > MAX_SUBJECT_CHARS:
            reasons.append(f"subject {len(subject)} chars (max {MAX_SUBJECT_CHARS})")
        if reasons:
            offenders.append({"markup_id": markup_id, "reasons": reasons})
    return {
        "checked": len(markups),
        "offenders": offenders,
        "clean": not offenders,
    }


def page_identity_report(
    *,
    expected_drawing_number: str,
    page_text: str,
    viewer_page_label: str = "",
) -> dict[str, Any]:
    """Confirm the worked page really is the intended consultant drawing.

    A viewer page label and the consultant drawing number are different
    identifiers: on Example Road, page 3 carried viewer label "01 STA 1+000 TO
    1+140" and drawing number DEMO-001-03. Treating them as one put a session on
    the wrong sheet.
    """

    expected = str(expected_drawing_number).strip()
    if not expected:
        raise BridgeError("expected_drawing_number is required")
    haystack = re.sub(r"\s+", "", str(page_text)).upper()
    needle = re.sub(r"\s+", "", expected).upper()
    confirmed = needle in haystack

    findings: list[Finding] = []
    if not confirmed:
        findings.append(
            Finding(
                code="PAGE_IDENTITY_UNCONFIRMED",
                severity="ERROR",
                detail=(
                    f"Drawing number {expected} was not found in the page's own text. Do not "
                    "assume the page from a viewer label; confirm against the title block."
                ),
                blocking=True,
            )
        )
    if viewer_page_label.strip() and needle not in re.sub(
        r"\s+", "", viewer_page_label
    ).upper():
        findings.append(
            Finding(
                code="VIEWER_LABEL_DIFFERS_FROM_DRAWING_NUMBER",
                severity="WARNING",
                detail=(
                    f"Viewer label {viewer_page_label!r} does not contain {expected}. These are "
                    "separate numbering systems; record both."
                ),
            )
        )
    return {
        "expected_drawing_number": expected,
        "viewer_page_label": viewer_page_label,
        "confirmed": confirmed,
        "findings": [item.to_dict() for item in findings],
        "blocking": any(item.blocking for item in findings),
    }


def render_shows_host_state(
    *,
    host_markup_count: int,
    rendered_annotation_count: int,
) -> dict[str, Any]:
    """Say whether a render of the file can be trusted to show host markups.

    Revu keeps MCP-created markups in memory until the file is saved. Renders
    of the file on disk then show a stale sheet, which is not a safe basis for
    claiming a markup was visually checked.
    """

    trustworthy = host_markup_count == rendered_annotation_count
    findings: list[Finding] = []
    if not trustworthy:
        findings.append(
            Finding(
                code="RENDER_STALE_VS_HOST",
                severity="WARNING",
                detail=(
                    f"Host reports {host_markup_count} markup(s); the rendered file contains "
                    f"{rendered_annotation_count}. The file is probably unsaved. Do not claim visual "
                    "verification from this render."
                ),
            )
        )
    return {
        "host_markup_count": host_markup_count,
        "rendered_annotation_count": rendered_annotation_count,
        "visual_verification_supported": trustworthy,
        "findings": [item.to_dict() for item in findings],
    }


@dataclass
class ReconcileRow:
    takeoff_id: str
    rule_id: str
    markup_id: str
    status: str
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "takeoff_id": self.takeoff_id,
            "rule_id": self.rule_id,
            "markup_id": self.markup_id,
            "status": self.status,
            "detail": self.detail,
        }


def reconcile(session: Any, host_markup_ids: Iterable[str]) -> dict[str, Any]:
    """Compare the session's proposals against the host's markups.

    Two records of the same work drift apart silently. Every session proposal
    should name the host markup it corresponds to under
    `provenance.extra["bluebeam_markup_id"]`.
    """

    host_ids = {str(value) for value in host_markup_ids}
    rows: list[ReconcileRow] = []
    linked: set[str] = set()

    for item in getattr(session, "measurements", []):
        markup_id = str(item.provenance.extra.get("bluebeam_markup_id", "") or "")
        if not markup_id:
            rows.append(
                ReconcileRow(item.id, item.rule_id, "", "NO_HOST_LINK",
                             "Proposal does not name a host markup.")
            )
            continue
        if markup_id in host_ids:
            linked.add(markup_id)
            rows.append(ReconcileRow(item.id, item.rule_id, markup_id, "LINKED"))
        else:
            rows.append(
                ReconcileRow(item.id, item.rule_id, markup_id, "HOST_MARKUP_MISSING",
                             "Named host markup is not present; it may have been deleted or re-issued an id.")
            )

    orphans = sorted(host_ids - linked)
    return {
        "rows": [row.to_dict() for row in rows],
        "host_markups_without_proposal": orphans,
        "linked_count": len(linked),
        "in_sync": not orphans and all(row.status == "LINKED" for row in rows),
    }
