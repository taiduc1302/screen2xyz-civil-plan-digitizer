"""Review-first civil quantity takeoff domain.

This module is intentionally UI- and engine-independent.  Manual geometry,
OpenTakeoff proposals, and future segmentation proposals must all normalize
into these records before an estimator can approve a quantity.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable


class TakeoffError(ValueError):
    """A takeoff record or transition violates a closed domain contract."""


LINE = "LINE"
POLYGON = "POLYGON"
COUNT = "COUNT"
GEOMETRY_KINDS = frozenset({LINE, POLYGON, COUNT})

REVIEW_REQUIRED = "REVIEW_REQUIRED"
APPROVED = "APPROVED"
EDITED_AND_APPROVED = "EDITED_AND_APPROVED"
REJECTED = "REJECTED"
TAKEOFF_REVIEW_STATUSES = frozenset(
    {REVIEW_REQUIRED, APPROVED, EDITED_AND_APPROVED, REJECTED}
)
APPROVED_TAKEOFF_STATUSES = frozenset({APPROVED, EDITED_AND_APPROVED})

UNIT_M = "m"
UNIT_M2 = "m2"
UNIT_EA = "ea"
TAKEOFF_UNITS = frozenset({UNIT_M, UNIT_M2, UNIT_EA})

# These flags mean that the estimator/agent has explicitly stated that the
# current record is not a final bid quantity.  They always fail closed.
FINALIZATION_BLOCKERS = frozenset(
    {
        "PARTIAL",
        "MIXED",
        "UNRESOLVED",
        "TENTATIVE",
        "SCALE_UNVERIFIED",
        "SCOPE_UNMAPPED",
        "GEOMETRY_UNVERIFIED",
    }
)


@dataclass(frozen=True)
class TakeoffVertex:
    """One point in the review-canvas pixel coordinate frame."""

    x: float
    y: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.x) or not math.isfinite(self.y):
            raise TakeoffError("takeoff vertex coordinates must be finite")
        if self.x < 0 or self.y < 0:
            raise TakeoffError("takeoff vertex coordinates must be non-negative")

    def to_dict(self) -> dict[str, float]:
        return {"x": float(self.x), "y": float(self.y)}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TakeoffVertex":
        return cls(float(value["x"]), float(value["y"]))


@dataclass(frozen=True)
class TakeoffGeometry:
    """Normalized geometry before conversion from pixels to real units."""

    kind: str
    vertices: tuple[TakeoffVertex, ...] = ()
    count: int | None = None

    def __post_init__(self) -> None:
        if self.kind not in GEOMETRY_KINDS:
            raise TakeoffError(f"unsupported takeoff geometry: {self.kind}")
        if self.kind == LINE:
            if len(self.vertices) < 2:
                raise TakeoffError("line takeoff requires at least two vertices")
            if self.count is not None:
                raise TakeoffError("line takeoff cannot carry a count")
        elif self.kind == POLYGON:
            if len(self.vertices) < 3:
                raise TakeoffError("polygon takeoff requires at least three vertices")
            if self.count is not None:
                raise TakeoffError("polygon takeoff cannot carry a count")
            if self.area_px2 <= 0:
                raise TakeoffError("polygon takeoff must have positive area")
        else:
            if self.vertices:
                raise TakeoffError("count takeoff cannot carry vertices")
            if self.count is None or self.count <= 0:
                raise TakeoffError("count takeoff requires a positive integer count")

    @property
    def length_px(self) -> float:
        if self.kind != LINE:
            raise TakeoffError("pixel length is only defined for line geometry")
        return sum(
            math.hypot(right.x - left.x, right.y - left.y)
            for left, right in zip(self.vertices, self.vertices[1:])
        )

    @property
    def area_px2(self) -> float:
        if self.kind != POLYGON:
            raise TakeoffError("pixel area is only defined for polygon geometry")
        total = 0.0
        for left, right in zip(self.vertices, self.vertices[1:] + self.vertices[:1]):
            total += left.x * right.y - right.x * left.y
        return abs(total) / 2.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "vertices": [vertex.to_dict() for vertex in self.vertices],
            "count": self.count,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TakeoffGeometry":
        return cls(
            kind=str(value["kind"]),
            vertices=tuple(
                TakeoffVertex.from_dict(item) for item in value.get("vertices", [])
            ),
            count=None if value.get("count") is None else int(value["count"]),
        )


def clone_geometry(value: TakeoffGeometry) -> TakeoffGeometry:
    """Make an explicit immutable evidence snapshot."""

    return TakeoffGeometry.from_dict(value.to_dict())


@dataclass(frozen=True)
class CivilTakeoffRule:
    rule_id: str
    display_name: str
    geometry_kind: str
    default_unit: str
    summable: bool = True
    stated_width_m: float | None = None
    guidance: str = ""

    def __post_init__(self) -> None:
        if not self.rule_id:
            raise TakeoffError("takeoff rule id is required")
        if self.geometry_kind not in GEOMETRY_KINDS:
            raise TakeoffError("takeoff rule has an invalid geometry kind")
        if self.default_unit not in TAKEOFF_UNITS:
            raise TakeoffError("takeoff rule has an invalid unit")
        expected = {LINE: UNIT_M, POLYGON: UNIT_M2, COUNT: UNIT_EA}[self.geometry_kind]
        if self.default_unit != expected:
            raise TakeoffError(
                f"{self.geometry_kind} rule must use {expected}, not {self.default_unit}"
            )
        if self.stated_width_m is not None and self.stated_width_m <= 0:
            raise TakeoffError("stated takeoff width must be positive")


RULES: dict[str, CivilTakeoffRule] = {
    "ANCHOR_ROADWORKS_EXTENT": CivilTakeoffRule(
        "ANCHOR_ROADWORKS_EXTENT",
        "Road works extent anchor - do not sum",
        POLYGON,
        UNIT_M2,
        summable=False,
        guidance=(
            "QA/reference geometry only. It may describe the overall roadworks "
            "extent but must never be added to bid quantities."
        ),
    ),
    "ROAD_WIDENING_FULL_STRUCTURE": CivilTakeoffRule(
        "ROAD_WIDENING_FULL_STRUCTURE",
        "Road widening - full road structure",
        POLYGON,
        UNIT_M2,
        guidance="Trace the actual full-road-structure hatch boundary.",
    ),
    "MILL_OVERLAY_40MM": CivilTakeoffRule(
        "MILL_OVERLAY_40MM",
        "40 mm mill and overlay",
        POLYGON,
        UNIT_M2,
        guidance="Trace only the drawing area assigned to the 40 mm mill/overlay hatch.",
    ),
    "FULL_DEPTH_ASPHALT_RR": CivilTakeoffRule(
        "FULL_DEPTH_ASPHALT_RR",
        "Full-depth asphalt removal and replacement",
        POLYGON,
        UNIT_M2,
        guidance="Do not infer this item merely because it appears in the legend.",
    ),
    "DITCH_INFILL": CivilTakeoffRule(
        "DITCH_INFILL",
        "Ditch infill",
        POLYGON,
        UNIT_M2,
        guidance="Keep ditch infill separate from ditch regrade and ditch relocation.",
    ),
    "DITCH_REGRADE": CivilTakeoffRule(
        "DITCH_REGRADE",
        "Existing ditch to be regraded",
        LINE,
        UNIT_M,
        guidance="Trace only the reach explicitly identified for regrading.",
    ),
    "DITCH_RELOCATION": CivilTakeoffRule(
        "DITCH_RELOCATION",
        "Existing ditch to be relocated",
        LINE,
        UNIT_M,
        guidance="Trace relocation separately; a mixed regrade/relocation trace is unresolved.",
    ),
    "GRAVEL_SHOULDER_030": CivilTakeoffRule(
        "GRAVEL_SHOULDER_030",
        "0.30 m gravel shoulder",
        LINE,
        UNIT_M,
        stated_width_m=0.30,
        guidance=(
            "Measure each continuous shoulder reach as length and preserve the "
            "drawing-stated 0.30 m width for derived area/material logic."
        ),
    ),
    "DRIVEWAY_CULVERT_300": CivilTakeoffRule(
        "DRIVEWAY_CULVERT_300",
        "300 mm driveway culvert",
        LINE,
        UNIT_M,
        guidance=(
            "Trace the pipe centerline from culvert end to culvert end. Do not use "
            "the printed driveway width as the pipe length."
        ),
    ),
    "GRAVEL_DRIVEWAY_REINSTATEMENT": CivilTakeoffRule(
        "GRAVEL_DRIVEWAY_REINSTATEMENT",
        "Existing gravel driveway access to be reinstated",
        POLYGON,
        UNIT_M2,
        guidance=(
            "Follow the actual reinstatement boundary. Do not replace an irregular "
            "drawing boundary with a generic rectangle."
        ),
    ),
    # --- added 2026-09-03 -------------------------------------------------
    # The Sheet 03 pass produced a list of features that are plainly drawn,
    # plainly paid for, and had no rule to be recorded under: curb, sawcut,
    # fence, hydroseed, topsoil, storm structures, clearing and slope limits.
    # A rule-level scope ledger cannot report a silent miss for scope it has no
    # rule for, so the omission was invisible by construction. Units follow the
    # tender Schedule of Quantities (Addendum #3).
    "CONCRETE_CURB": CivilTakeoffRule(
        "CONCRETE_CURB",
        "Concrete curb - MMCD C6 (item 3.01)",
        LINE,
        UNIT_M,
        guidance=(
            "Measure along the curb face. On a rural ditched section confirm the "
            "curb is genuinely built before proposing: profile labels such as "
            "PROP. NORTH CURB may be grade references rather than a curb run."
        ),
    ),
    "HANDRAIL": CivilTakeoffRule(
        "HANDRAIL",
        "Handrail c/w excavation, grout, footing (item 3.07)",
        LINE,
        UNIT_M,
        guidance=(
            "Added by Addendum #3. Normally runs with the Allan Block wall cap; "
            "check its length against item 3.05 rather than assuming they match."
        ),
    ),
    "SAWCUT": CivilTakeoffRule(
        "SAWCUT",
        "Sawcut asphaltic or concrete pavement (item 32.24, incidental)",
        LINE,
        UNIT_M,
        guidance=(
            "Incidental to the contract, so it earns no separate payment, but it "
            "is real cost and must still be measured - typically across each "
            "tie-in to existing pavement."
        ),
    ),
    "WIRE_FENCE_RELOCATION": CivilTakeoffRule(
        "WIRE_FENCE_RELOCATION",
        "Remove and relocate existing wire fence (item 32.27)",
        LINE,
        UNIT_M,
        guidance="Measure the existing fence run to be removed and relocated.",
    ),
    "CLEARING_LIMIT": CivilTakeoffRule(
        "CLEARING_LIMIT",
        "Vegetation / tree line extent (supports item 31.01)",
        LINE,
        UNIT_M,
        summable=False,
        guidance=(
            "Extent of the vegetation or tree line, recorded so clearing scope is "
            "visible. Not itself a paid line: 31.01 Shrub and Tree Preservation is "
            "incidental, and removal may fall under the SCS 11 clause. Record the "
            "extent, leave the pay treatment to the estimator."
        ),
    ),
    "EARTHWORK_SLOPE_LIMIT": CivilTakeoffRule(
        "EARTHWORK_SLOPE_LIMIT",
        "New top / bottom of slope (earthwork limit)",
        LINE,
        UNIT_M,
        summable=False,
        guidance=(
            "The drawn limit of earthworks. Not a paid quantity by itself - it "
            "bounds the excavation and embankment that are measured from the "
            "cross sections, and it is the reference that says whether a section "
            "is in cut or fill."
        ),
    ),
    "HYDROSEEDING": CivilTakeoffRule(
        "HYDROSEEDING",
        "Hydro seeding (item 32.28)",
        POLYGON,
        UNIT_M2,
        guidance=(
            "Restoration area. Check against imported topsoil (32.29): the two "
            "often cover the same ground but are separate pay items, and the "
            "topsoil depth called up in the ditch item may differ from the "
            "typical section."
        ),
    ),
    "IMPORTED_TOPSOIL": CivilTakeoffRule(
        "IMPORTED_TOPSOIL",
        "Imported topsoil 150 mm for restoration (item 32.29)",
        POLYGON,
        UNIT_M2,
        guidance=(
            "Paid by area, so record the depth called up on the drawing in the "
            "notes: the typical section and the ditch item have been seen to "
            "state different thicknesses on this project."
        ),
    ),
    "STORM_CULVERT": CivilTakeoffRule(
        "STORM_CULVERT",
        "Storm culvert - measure by diameter (items 33.01-33.03)",
        LINE,
        UNIT_M,
        guidance=(
            "Trace the pipe centreline end to end and record the diameter in the "
            "bid item, because 300/450/600 mm are three separate pay items. "
            "DRIVEWAY_CULVERT_300 stays separate: it is the driveway crossing "
            "specifically. A printed driveway width is not a pipe length."
        ),
    ),
    "STORM_MANHOLE_RISER": CivilTakeoffRule(
        "STORM_MANHOLE_RISER",
        "1200 mm manhole riser section (item 33.06)",
        LINE,
        UNIT_M,
        guidance="Paid by length of riser, not per structure.",
    ),
    "STORM_STRUCTURE_COUNT": CivilTakeoffRule(
        "STORM_STRUCTURE_COUNT",
        "Storm structure count - manholes and headwalls (items 33.04, 33.05, 33.07, 33.08)",
        COUNT,
        UNIT_EA,
        guidance=(
            "One record per structure type, with the bid item naming which: "
            "1200 mm manhole, overbuild manhole, Langley headwall Type II, or "
            "Langley mini headwall are four separate pay items. Native Bluebeam "
            "Count markups cannot be created through the current MCP surface, so "
            "record the count here and place static markers or use the Revu GUI "
            "if a visual count is also needed."
        ),
    ),
    "UTILITY_PROTECTION_COUNT": CivilTakeoffRule(
        "UTILITY_PROTECTION_COUNT",
        "Existing utility to remain / be protected - count",
        COUNT,
        UNIT_EA,
        summable=False,
        guidance=(
            "Hydro poles and similar marked TO REMAIN. Not a pay item on this "
            "schedule; counted because protection is real cost and because a pole "
            "marked for relocation by others is a coordination risk."
        ),
    ),
    # Added 2026-09-03 after the whole set was measured: three kinds of scope
    # that were found on the drawings and had nowhere to be recorded. A
    # quantity with no rule is a quantity that gets left out of the summary.
    "PEDESTRIAN_ASPHALT_PAD": CivilTakeoffRule(
        "PEDESTRIAN_ASPHALT_PAD",
        "Pedestrian asphalt pad / asphalt letdown at a curb return",
        POLYGON,
        UNIT_M2,
        guidance=(
            "The stippled pads at the curb returns ('PROP. PEDESTRIAN ASPHALT PAD "
            "AND ASPHALT LETDOWNS' on sheet 04; details on sheet 04). No legend "
            "entry - the pattern is identified from crops, so every proposal keeps "
            "its crop. Which schedule item pays for it is the estimator's call."
        ),
    ),
    "EXISTING_CULVERT_REMOVAL": CivilTakeoffRule(
        "EXISTING_CULVERT_REMOVAL",
        "Existing storm culvert marked TO BE REMOVED - length",
        LINE,
        UNIT_M,
        guidance=(
            "Demolition, not new work: the existing 450 dia runs and driveway "
            "culverts drawn with a removal note on sheets 03-06 and 11-12. Use the "
            "printed length where one exists. Removal is real cost whether or not "
            "the schedule carries a separate item for it."
        ),
    ),
    "EXISTING_HEADWALL_REMOVAL": CivilTakeoffRule(
        "EXISTING_HEADWALL_REMOVAL",
        "Existing headwall marked TO BE REMOVED - count",
        COUNT,
        UNIT_EA,
        guidance=(
            "EX.HW1-4 on sheets 11-12 carry a removal note. One count per headwall, "
            "each with its position, so a headwall removed and a headwall built "
            "(STORM_STRUCTURE_COUNT) are never the same record."
        ),
    ),
}


def takeoff_rule(rule_id: str) -> CivilTakeoffRule:
    try:
        return RULES[rule_id]
    except KeyError as exc:
        raise TakeoffError(f"unknown civil takeoff rule: {rule_id}") from exc


@dataclass
class TakeoffProvenance:
    """Machine proposal evidence plus estimator correction history."""

    source_engine: str
    source_method: str
    generated_by: str
    confidence: float | None = None
    external_id: str = ""
    original_geometry: TakeoffGeometry | None = None
    correction_history: list[dict[str, Any]] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_engine.strip():
            raise TakeoffError("takeoff source engine is required")
        if not self.source_method.strip():
            raise TakeoffError("takeoff source method is required")
        if not self.generated_by.strip():
            raise TakeoffError("takeoff generated_by is required")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise TakeoffError("takeoff confidence must be between 0 and 1")

    @property
    def human_corrected(self) -> bool:
        return bool(self.correction_history)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_engine": self.source_engine,
            "source_method": self.source_method,
            "generated_by": self.generated_by,
            "confidence": self.confidence,
            "external_id": self.external_id,
            "original_geometry": (
                None if self.original_geometry is None else self.original_geometry.to_dict()
            ),
            "correction_history": list(self.correction_history),
            "extra": dict(self.extra),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TakeoffProvenance":
        original = value.get("original_geometry")
        return cls(
            source_engine=str(value.get("source_engine", "manual")),
            source_method=str(value.get("source_method", "manual")),
            generated_by=str(value.get("generated_by", "human")),
            confidence=(
                None if value.get("confidence") is None else float(value["confidence"])
            ),
            external_id=str(value.get("external_id", "")),
            original_geometry=(
                None if original is None else TakeoffGeometry.from_dict(original)
            ),
            correction_history=list(value.get("correction_history", [])),
            extra=dict(value.get("extra", {})),
        )


@dataclass
class TakeoffMeasurement:
    id: str
    rule_id: str
    page_index: int
    page_label: str
    geometry: TakeoffGeometry
    review_status: str
    unit: str
    created_at: str
    updated_at: str
    provenance: TakeoffProvenance
    label: str = ""
    bid_item: str = ""
    quantity: float | None = None
    stated_width_m: float | None = None
    flags: set[str] = field(default_factory=set)
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.id.startswith("TK-"):
            raise TakeoffError("takeoff id must start with TK-")
        if self.page_index < 0:
            raise TakeoffError("takeoff page index must be non-negative")
        if self.review_status not in TAKEOFF_REVIEW_STATUSES:
            raise TakeoffError("invalid takeoff review status")
        if self.unit not in TAKEOFF_UNITS:
            raise TakeoffError("invalid takeoff unit")
        rule = takeoff_rule(self.rule_id)
        if self.geometry.kind != rule.geometry_kind:
            raise TakeoffError(
                f"{self.rule_id} requires {rule.geometry_kind} geometry"
            )
        if self.unit != rule.default_unit:
            raise TakeoffError(f"{self.rule_id} requires unit {rule.default_unit}")
        if self.quantity is not None and (
            not math.isfinite(self.quantity) or self.quantity <= 0
        ):
            raise TakeoffError("takeoff quantity must be positive when present")
        if self.stated_width_m is not None and self.stated_width_m <= 0:
            raise TakeoffError("takeoff stated width must be positive")
        self.flags = {str(flag).strip().upper() for flag in self.flags if str(flag).strip()}

    @property
    def rule(self) -> CivilTakeoffRule:
        return takeoff_rule(self.rule_id)

    @property
    def approved(self) -> bool:
        return self.review_status in APPROVED_TAKEOFF_STATUSES

    @property
    def summable(self) -> bool:
        return self.rule.summable

    @property
    def blocker_flags(self) -> set[str]:
        return self.flags.intersection(FINALIZATION_BLOCKERS)

    @property
    def requires_review(self) -> bool:
        return self.review_status == REVIEW_REQUIRED or bool(self.blocker_flags)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "page_index": self.page_index,
            "page_label": self.page_label,
            "geometry": self.geometry.to_dict(),
            "review_status": self.review_status,
            "unit": self.unit,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "provenance": self.provenance.to_dict(),
            "label": self.label,
            "bid_item": self.bid_item,
            "quantity": self.quantity,
            "stated_width_m": self.stated_width_m,
            "flags": sorted(self.flags),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TakeoffMeasurement":
        return cls(
            id=str(value["id"]),
            rule_id=str(value["rule_id"]),
            page_index=int(value.get("page_index", 0)),
            page_label=str(value.get("page_label", "1")),
            geometry=TakeoffGeometry.from_dict(value["geometry"]),
            review_status=str(value.get("review_status", REVIEW_REQUIRED)),
            unit=str(value["unit"]),
            created_at=str(value.get("created_at", "")),
            updated_at=str(value.get("updated_at", "")),
            provenance=TakeoffProvenance.from_dict(value.get("provenance", {})),
            label=str(value.get("label", "")),
            bid_item=str(value.get("bid_item", "")),
            quantity=(
                None if value.get("quantity") is None else float(value["quantity"])
            ),
            stated_width_m=(
                None
                if value.get("stated_width_m") is None
                else float(value["stated_width_m"])
            ),
            flags=set(value.get("flags", [])),
            notes=str(value.get("notes", "")),
        )


def new_takeoff_proposal(
    *,
    takeoff_id: str,
    rule_id: str,
    page_index: int,
    page_label: str,
    geometry: TakeoffGeometry,
    now: str,
    source_engine: str,
    source_method: str,
    generated_by: str,
    confidence: float | None = None,
    external_id: str = "",
    label: str = "",
    bid_item: str = "",
    flags: Iterable[str] = (),
    notes: str = "",
) -> TakeoffMeasurement:
    """Create a proposal that always requires explicit estimator review."""

    rule = takeoff_rule(rule_id)
    provenance = TakeoffProvenance(
        source_engine=source_engine,
        source_method=source_method,
        generated_by=generated_by,
        confidence=confidence,
        external_id=external_id,
        original_geometry=(
            None
            if generated_by.strip().lower() in {"human", "estimator", "manual"}
            else clone_geometry(geometry)
        ),
    )
    return TakeoffMeasurement(
        id=takeoff_id,
        rule_id=rule_id,
        page_index=page_index,
        page_label=page_label,
        geometry=geometry,
        review_status=REVIEW_REQUIRED,
        unit=rule.default_unit,
        created_at=now,
        updated_at=now,
        provenance=provenance,
        label=label,
        bid_item=bid_item,
        stated_width_m=rule.stated_width_m,
        flags=set(flags),
        notes=notes,
    )


def quantity_for(
    measurement: TakeoffMeasurement,
    *,
    metres_per_pixel: float | None,
) -> float:
    """Compute net measured quantity from the explicit reviewed scale."""

    if measurement.geometry.kind == COUNT:
        assert measurement.geometry.count is not None
        return float(measurement.geometry.count)
    if metres_per_pixel is None or not math.isfinite(metres_per_pixel):
        raise TakeoffError("a reviewed metres_per_pixel calibration is required")
    if metres_per_pixel <= 0:
        raise TakeoffError("metres_per_pixel must be positive")
    if measurement.geometry.kind == LINE:
        return measurement.geometry.length_px * metres_per_pixel
    return measurement.geometry.area_px2 * metres_per_pixel * metres_per_pixel


def derived_area_m2(
    measurement: TakeoffMeasurement,
    *,
    metres_per_pixel: float,
) -> float | None:
    """Return optional length x stated-width area without changing bid unit."""

    width = measurement.stated_width_m
    if measurement.geometry.kind != LINE or width is None:
        return None
    return quantity_for(measurement, metres_per_pixel=metres_per_pixel) * width


def correct_takeoff_geometry(
    measurement: TakeoffMeasurement,
    corrected_geometry: TakeoffGeometry,
    *,
    now: str,
    actor: str = "estimator",
    reason: str = "geometry corrected during review",
) -> TakeoffMeasurement:
    """Apply a human correction while retaining the machine's first geometry."""

    if measurement.review_status == REJECTED:
        raise TakeoffError("rejected takeoff cannot be edited without a new proposal")
    if corrected_geometry.kind != measurement.rule.geometry_kind:
        raise TakeoffError("corrected geometry does not match the takeoff rule")
    before = clone_geometry(measurement.geometry)
    if measurement.provenance.original_geometry is None:
        measurement.provenance.original_geometry = clone_geometry(before)
    measurement.geometry = corrected_geometry
    measurement.quantity = None
    measurement.review_status = REVIEW_REQUIRED
    measurement.updated_at = now
    measurement.provenance.correction_history.append(
        {
            "at": now,
            "actor": actor,
            "reason": reason,
            "before": before.to_dict(),
            "after": corrected_geometry.to_dict(),
        }
    )
    return measurement


def set_takeoff_flag(
    measurement: TakeoffMeasurement,
    flag: str,
    *,
    now: str,
) -> TakeoffMeasurement:
    cleaned = flag.strip().upper()
    if not cleaned:
        raise TakeoffError("takeoff flag cannot be empty")
    measurement.flags.add(cleaned)
    measurement.quantity = None
    measurement.review_status = REVIEW_REQUIRED
    measurement.updated_at = now
    return measurement


def clear_takeoff_flag(
    measurement: TakeoffMeasurement,
    flag: str,
    *,
    now: str,
) -> TakeoffMeasurement:
    measurement.flags.discard(flag.strip().upper())
    measurement.quantity = None
    measurement.review_status = REVIEW_REQUIRED
    measurement.updated_at = now
    return measurement


def reject_takeoff(
    measurement: TakeoffMeasurement,
    *,
    now: str,
    reason: str,
) -> TakeoffMeasurement:
    if not reason.strip():
        raise TakeoffError("takeoff rejection reason is required")
    measurement.review_status = REJECTED
    measurement.quantity = None
    measurement.updated_at = now
    measurement.notes = (
        f"{measurement.notes}\nREJECTED: {reason.strip()}".strip()
    )
    return measurement


def approve_takeoff(
    measurement: TakeoffMeasurement,
    *,
    metres_per_pixel: float | None,
    scale_verified: bool,
    now: str,
) -> TakeoffMeasurement:
    """Estimator-only finalization gate for one bid quantity."""

    if measurement.review_status == REJECTED:
        raise TakeoffError("rejected takeoff cannot be approved")
    if not measurement.summable:
        raise TakeoffError("reference/anchor geometry is not a bid quantity")
    if measurement.blocker_flags:
        blockers = ", ".join(sorted(measurement.blocker_flags))
        raise TakeoffError(f"takeoff has unresolved blocker flags: {blockers}")
    if measurement.geometry.kind in {LINE, POLYGON} and not scale_verified:
        raise TakeoffError("scale verification is required before quantity approval")
    quantity = quantity_for(measurement, metres_per_pixel=metres_per_pixel)
    if not math.isfinite(quantity) or quantity <= 0:
        raise TakeoffError("approved takeoff quantity must be positive")
    measurement.quantity = quantity
    measurement.review_status = (
        EDITED_AND_APPROVED
        if measurement.provenance.human_corrected
        else APPROVED
    )
    measurement.updated_at = now
    return measurement


def approved_totals(
    measurements: Iterable[TakeoffMeasurement],
) -> dict[str, float]:
    totals = {UNIT_M: 0.0, UNIT_M2: 0.0, UNIT_EA: 0.0}
    for measurement in measurements:
        if (
            measurement.approved
            and measurement.summable
            and measurement.quantity is not None
        ):
            totals[measurement.unit] += measurement.quantity
    return totals


def takeoff_qa_summary(
    measurements: Iterable[TakeoffMeasurement],
) -> dict[str, Any]:
    records = list(measurements)
    issues: list[dict[str, Any]] = []
    for measurement in records:
        if not measurement.summable:
            issues.append(
                {
                    "severity": "INFO",
                    "code": "REFERENCE_DO_NOT_SUM",
                    "takeoff_id": measurement.id,
                    "detail": "Reference/anchor geometry is excluded from bid totals.",
                }
            )
        if measurement.blocker_flags:
            issues.append(
                {
                    "severity": "ERROR",
                    "code": "TAKEOFF_BLOCKED",
                    "takeoff_id": measurement.id,
                    "flags": sorted(measurement.blocker_flags),
                    "detail": "Takeoff contains an explicit unresolved scope/geometry flag.",
                }
            )
        if measurement.approved and measurement.quantity is None:
            issues.append(
                {
                    "severity": "CRITICAL",
                    "code": "APPROVED_TAKEOFF_MISSING_QUANTITY",
                    "takeoff_id": measurement.id,
                    "detail": "Approved summable takeoff has no final quantity.",
                }
            )
        if measurement.approved and not measurement.summable:
            issues.append(
                {
                    "severity": "CRITICAL",
                    "code": "REFERENCE_TAKEOFF_APPROVED",
                    "takeoff_id": measurement.id,
                    "detail": "Reference geometry must never be an approved bid quantity.",
                }
            )
        if measurement.review_status == REVIEW_REQUIRED:
            issues.append(
                {
                    "severity": "INFO",
                    "code": "TAKEOFF_REVIEW_REQUIRED",
                    "takeoff_id": measurement.id,
                    "detail": "Takeoff is excluded from final totals until estimator review.",
                }
            )
    return {
        "count": len(records),
        "approved": sum(record.approved for record in records),
        "review_required": sum(
            record.review_status == REVIEW_REQUIRED for record in records
        ),
        "rejected": sum(record.review_status == REJECTED for record in records),
        "references": sum(not record.summable for record in records),
        "human_corrected": sum(
            record.provenance.human_corrected for record in records
        ),
        "blocked": sum(bool(record.blocker_flags) for record in records),
        "totals": approved_totals(records),
        "issue_counts": {
            severity: sum(issue["severity"] == severity for issue in issues)
            for severity in ("CRITICAL", "ERROR", "WARNING", "INFO")
        },
        "issues": issues,
    }


def correction_training_record(measurement: TakeoffMeasurement) -> dict[str, Any] | None:
    """Return a compact supervised geometry correction example when available."""

    if (
        measurement.provenance.original_geometry is None
        or not measurement.provenance.human_corrected
    ):
        return None
    return {
        "takeoff_id": measurement.id,
        "rule_id": measurement.rule_id,
        "page_label": measurement.page_label,
        "source_engine": measurement.provenance.source_engine,
        "source_method": measurement.provenance.source_method,
        "confidence": measurement.provenance.confidence,
        "proposal_geometry": measurement.provenance.original_geometry.to_dict(),
        "reviewed_geometry": measurement.geometry.to_dict(),
        "review_status": measurement.review_status,
        "flags": sorted(measurement.flags),
    }
