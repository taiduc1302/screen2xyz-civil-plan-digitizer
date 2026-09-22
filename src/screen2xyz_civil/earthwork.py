"""Earthwork volumes from measured cross sections.

The takeoff domain can express metres, square metres and each. It cannot
express a cubic metre, so the two largest items on the Example Road schedule -
`31.04 Common Excavation, off-site disposal` (2 160 cu.m) and `31.06 Imported
Embankment Fill` (3 974 t) - had nowhere to be recorded at all. A plan view
cannot supply them either: they need the third dimension, which lives on the
cross-section sheets (DEMO-001-09 and -10, drawn 1:100 horizontal / 1:50
vertical).

This module computes those volumes by average end area, the method the
measurement clauses assume, and fails closed on the ways that method quietly
goes wrong:

- it never extrapolates past the first or last measured station, and says so;
- it refuses stations that are not strictly increasing;
- it flags intervals too long for average end area to be trustworthy;
- it keeps cut and fill separate, because netting one against the other hides
  that the contract pays to excavate *and* pays to import;
- it will not convert cubic metres to tonnes without an explicit density,
  because that conversion is an estimator's assumption, not a measurement.

Section areas are inputs to this module, not outputs of it. They come from
measuring each section on the drawing, where only the vertical axis carries the
1:50 factor and only the horizontal carries 1:100 - see
`plan_layers.Viewport`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence


class EarthworkError(ValueError):
    """A volume input violates a contract that must not be worked around."""


# Average end area assumes the surface varies linearly between sections. Past
# roughly 20 m that assumption starts to cost real money on curved or
# transitioning ground, which is why survey practice sections at 20 m or less.
DEFAULT_MAX_INTERVAL_M = 20.0


@dataclass(frozen=True)
class SectionArea:
    """One measured cross section.

    `cut_area_m2` is material to be excavated, `fill_area_m2` material to be
    placed. A section may legitimately carry both.
    """

    station_m: float
    cut_area_m2: float = 0.0
    fill_area_m2: float = 0.0
    source: str = ""

    def __post_init__(self) -> None:
        for name, value in (
            ("station_m", self.station_m),
            ("cut_area_m2", self.cut_area_m2),
            ("fill_area_m2", self.fill_area_m2),
        ):
            if value != value or value in (float("inf"), float("-inf")):
                raise EarthworkError(f"{name} must be a finite number")
        if self.cut_area_m2 < 0 or self.fill_area_m2 < 0:
            raise EarthworkError(
                "section areas are magnitudes and must be >= 0; cut and fill are "
                "recorded separately, never as one signed number"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "station_m": self.station_m,
            "cut_area_m2": self.cut_area_m2,
            "fill_area_m2": self.fill_area_m2,
            "source": self.source,
        }


@dataclass(frozen=True)
class Interval:
    """The volume between two adjacent sections."""

    from_station_m: float
    to_station_m: float
    length_m: float
    cut_m3: float
    fill_m3: float
    over_max_interval: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_station_m": self.from_station_m,
            "to_station_m": self.to_station_m,
            "length_m": self.length_m,
            "cut_m3": self.cut_m3,
            "fill_m3": self.fill_m3,
            "over_max_interval": self.over_max_interval,
        }


def _ordered(sections: Iterable[SectionArea]) -> list[SectionArea]:
    rows = list(sections)
    if len(rows) < 2:
        raise EarthworkError(
            "average end area needs at least two sections; a single section "
            "describes a plane, not a volume"
        )
    for earlier, later in zip(rows, rows[1:]):
        if later.station_m <= earlier.station_m:
            raise EarthworkError(
                "sections must be in strictly increasing station order "
                f"({earlier.station_m} then {later.station_m})"
            )
    return rows


def _monotonic_surface(points: Sequence[Sequence[float]], name: str) -> list[tuple[float, float]]:
    rows = [(float(p[0]), float(p[1])) for p in points]
    if len(rows) < 2:
        raise EarthworkError(f"{name} needs at least two points")
    for (x1, _), (x2, _) in zip(rows, rows[1:]):
        if x2 <= x1:
            raise EarthworkError(
                f"{name} must be single-valued and left-to-right in x "
                f"({x1} then {x2}). A surface that doubles back is not a "
                "cross-section line; check that the correct polyline was picked."
            )
    return rows


def _value_at(rows: Sequence[tuple[float, float]], x: float) -> float:
    if x <= rows[0][0]:
        return rows[0][1]
    if x >= rows[-1][0]:
        return rows[-1][1]
    for (x1, y1), (x2, y2) in zip(rows, rows[1:]):
        if x1 <= x <= x2:
            if x2 == x1:
                return y2
            return y1 + (y2 - y1) * (x - x1) / (x2 - x1)
    return rows[-1][1]


def section_areas_between_surfaces(
    *,
    existing: Sequence[Sequence[float]],
    proposed: Sequence[Sequence[float]],
    metres_per_point_x: float,
    metres_per_point_y: float,
    station_m: float,
    source: str = "",
) -> dict[str, Any]:
    """Cut and fill area of one cross section, from the two drawn surfaces.

    `existing` is the natural-ground line, `proposed` the design surface, both
    as points in PDF space on the cross-section sheet. Where the design sits
    below existing ground the material is excavated (cut); where it sits above,
    material is placed (fill). The two are returned separately and a section
    that does both returns both.

    The per-axis factors are separate arguments and are applied *before* any
    area is computed, because a cross section is drawn with vertical
    exaggeration - on this project 1:100 horizontal against 1:50 vertical.
    Computing an area in points and scaling it by one factor afterwards is the
    exact mistake that produced a quantity out by the ratio of the two axes.

    Only the x-range the two surfaces share is measured. Anything outside it is
    reported as uncovered rather than assumed to be zero.
    """

    if metres_per_point_x <= 0 or metres_per_point_y <= 0:
        raise EarthworkError("both axis factors must be positive")

    ex = _monotonic_surface(existing, "existing ground")
    pr = _monotonic_surface(proposed, "proposed surface")
    ex_m = [(x * metres_per_point_x, y * metres_per_point_y) for x, y in ex]
    pr_m = [(x * metres_per_point_x, y * metres_per_point_y) for x, y in pr]

    left = max(ex_m[0][0], pr_m[0][0])
    right = min(ex_m[-1][0], pr_m[-1][0])
    if right <= left:
        raise EarthworkError(
            "the two surfaces do not overlap in x; they are not the same section"
        )

    breaks = {left, right}
    for rows in (ex_m, pr_m):
        for x, _ in rows:
            if left < x < right:
                breaks.add(x)
    ordered = sorted(breaks)

    # Split any strip where the surfaces cross, so no strip mixes cut and fill.
    with_crossings: list[float] = []
    for x1, x2 in zip(ordered, ordered[1:]):
        with_crossings.append(x1)
        d1 = _value_at(pr_m, x1) - _value_at(ex_m, x1)
        d2 = _value_at(pr_m, x2) - _value_at(ex_m, x2)
        if (d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0):
            crossing = x1 + (x2 - x1) * abs(d1) / (abs(d1) + abs(d2))
            if x1 < crossing < x2:
                with_crossings.append(crossing)
    with_crossings.append(ordered[-1])

    cut = 0.0
    fill = 0.0
    for x1, x2 in zip(with_crossings, with_crossings[1:]):
        width = x2 - x1
        if width <= 0:
            continue
        d1 = _value_at(pr_m, x1) - _value_at(ex_m, x1)
        d2 = _value_at(pr_m, x2) - _value_at(ex_m, x2)
        mean = (d1 + d2) / 2.0
        if mean > 0:
            fill += mean * width
        else:
            cut += -mean * width

    uncovered = []
    if ex_m[0][0] < left or pr_m[0][0] < left:
        uncovered.append({"side": "left", "to_x_m": left})
    if ex_m[-1][0] > right or pr_m[-1][0] > right:
        uncovered.append({"side": "right", "from_x_m": right})

    findings: list[dict[str, Any]] = []
    if uncovered:
        findings.append(
            {
                "code": "SECTION_PARTIALLY_COVERED",
                "severity": "WARNING",
                "blocking": False,
                "detail": (
                    "One surface extends beyond the other; only their shared width "
                    f"({right - left:.3f} m) was measured. The rest is not included."
                ),
            }
        )
    if cut > 0 and fill > 0:
        findings.append(
            {
                "code": "SECTION_HAS_BOTH_CUT_AND_FILL",
                "severity": "INFO",
                "blocking": False,
                "detail": (
                    "The surfaces cross in this section. Cut and fill are reported "
                    "separately and must stay separate."
                ),
            }
        )

    return {
        "station_m": station_m,
        "cut_area_m2": cut,
        "fill_area_m2": fill,
        "measured_width_m": right - left,
        "uncovered": uncovered,
        "metres_per_point_x": metres_per_point_x,
        "metres_per_point_y": metres_per_point_y,
        "findings": findings,
        "section": SectionArea(
            station_m=station_m,
            cut_area_m2=cut,
            fill_area_m2=fill,
            source=source,
        ),
    }


def average_end_area_volume(
    sections: Iterable[SectionArea],
    *,
    max_interval_m: float = DEFAULT_MAX_INTERVAL_M,
) -> dict[str, Any]:
    """Volume between the measured sections, cut and fill kept apart.

    V = sum over intervals of (A1 + A2) / 2 * L.

    The result covers only the station range that was actually measured. Ground
    outside it is not estimated, guessed or extrapolated - it is reported as
    uncovered so that the gap is visible instead of silently reading as zero.
    """

    rows = _ordered(sections)
    if max_interval_m <= 0:
        raise EarthworkError("max_interval_m must be positive")

    intervals: list[Interval] = []
    cut_total = 0.0
    fill_total = 0.0
    for earlier, later in zip(rows, rows[1:]):
        length = later.station_m - earlier.station_m
        cut = (earlier.cut_area_m2 + later.cut_area_m2) / 2.0 * length
        fill = (earlier.fill_area_m2 + later.fill_area_m2) / 2.0 * length
        cut_total += cut
        fill_total += fill
        intervals.append(
            Interval(
                from_station_m=earlier.station_m,
                to_station_m=later.station_m,
                length_m=length,
                cut_m3=cut,
                fill_m3=fill,
                over_max_interval=length > max_interval_m,
            )
        )

    long_intervals = [item for item in intervals if item.over_max_interval]
    findings: list[dict[str, Any]] = []
    if long_intervals:
        findings.append(
            {
                "code": "SECTION_SPACING_TOO_WIDE",
                "severity": "WARNING",
                "blocking": False,
                "detail": (
                    f"{len(long_intervals)} interval(s) exceed {max_interval_m:g} m "
                    f"(longest {max(item.length_m for item in long_intervals):g} m). "
                    "Average end area assumes the surface varies linearly between "
                    "sections; over that distance the error is real on transitioning "
                    "ground. Measure an intermediate section or record the tolerance."
                ),
            }
        )
    findings.append(
        {
            "code": "RANGE_NOT_EXTRAPOLATED",
            "severity": "INFO",
            "blocking": False,
            "detail": (
                f"Volumes cover STA {rows[0].station_m:g} to {rows[-1].station_m:g} only "
                f"({rows[-1].station_m - rows[0].station_m:g} m). Ground outside this "
                "range is not included and has not been estimated."
            ),
        }
    )

    return {
        "method": "AVERAGE_END_AREA",
        "section_count": len(rows),
        "from_station_m": rows[0].station_m,
        "to_station_m": rows[-1].station_m,
        "covered_length_m": rows[-1].station_m - rows[0].station_m,
        "cut_m3": cut_total,
        "fill_m3": fill_total,
        "net_note": (
            "Cut and fill are reported separately and must not be netted: the "
            "contract pays to excavate and, separately, to import."
        ),
        "intervals": [item.to_dict() for item in intervals],
        "findings": findings,
        "sections": [item.to_dict() for item in rows],
    }


def tonnes_from_volume(
    volume_m3: float,
    *,
    density_t_per_m3: float,
    basis: str,
) -> dict[str, Any]:
    """Convert a measured volume to tonnes using an explicitly supplied density.

    `31.06 Imported Embankment Fill` is paid by the tonne while the drawing
    yields cubic metres. There is no default density here on purpose: the value
    depends on the material and its compacted state, it moves the paid quantity
    directly, and it is the estimator's call. `basis` records where the number
    came from so the assumption travels with the number.
    """

    if volume_m3 < 0:
        raise EarthworkError("volume must be >= 0")
    if density_t_per_m3 <= 0:
        raise EarthworkError("density must be positive and supplied explicitly")
    if not basis.strip():
        raise EarthworkError(
            "a density needs a stated basis (geotechnical report, supplier, or "
            "estimator assumption); an unsourced conversion factor is not usable"
        )
    return {
        "volume_m3": volume_m3,
        "density_t_per_m3": density_t_per_m3,
        "tonnes": volume_m3 * density_t_per_m3,
        "basis": basis.strip(),
        "classification": "ESTIMATOR_INPUT_NOT_A_MEASUREMENT",
    }


def compare_to_tender(
    measured: float,
    tendered: float,
    *,
    unit: str,
    tolerance_percent: float = 10.0,
) -> dict[str, Any]:
    """Compare a measured earthwork quantity against the tendered one.

    On a unit-price contract the owner's quantity governs payment, so a
    disagreement is not a defect to correct silently - it is a question to
    price. This reports the gap and leaves the decision alone.
    """

    if tendered <= 0:
        raise EarthworkError("tendered quantity must be positive")
    difference = measured - tendered
    percent = difference / tendered * 100.0
    agrees = abs(percent) <= tolerance_percent
    return {
        "measured": measured,
        "tendered": tendered,
        "unit": unit,
        "difference": difference,
        "difference_percent": percent,
        "within_tolerance": agrees,
        "action": (
            "Within tolerance; record both and price the tendered quantity."
            if agrees
            else (
                "Outside tolerance. On a unit-price contract the tendered quantity "
                "still governs payment - raise it as a question rather than "
                "substituting the measured figure."
            )
        ),
    }
