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
