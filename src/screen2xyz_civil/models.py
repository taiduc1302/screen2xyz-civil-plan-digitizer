"""Stable, schema-versioned civil project domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import contracts as C


class CivilModelError(ValueError):
    """A civil project or point violates a closed domain contract."""


@dataclass(frozen=True)
class PixelPoint:
    x: float
    y: float

    def to_dict(self) -> dict[str, float]:
        return {"x": float(self.x), "y": float(self.y)}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PixelPoint":
        return cls(float(value["x"]), float(value["y"]))


@dataclass(frozen=True)
class CropRegion:
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        if self.x < 0 or self.y < 0:
            raise CivilModelError("crop origin must be non-negative")
        if self.width <= 0 or self.height <= 0:
            raise CivilModelError("crop dimensions must be positive")

    def contains(self, point: PixelPoint) -> bool:
        return (
            self.x <= point.x <= self.x + self.width
            and self.y <= point.y <= self.y + self.height
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "x": float(self.x),
            "y": float(self.y),
            "width": float(self.width),
            "height": float(self.height),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CropRegion":
        return cls(
            float(value["x"]),
            float(value["y"]),
            float(value["width"]),
            float(value["height"]),
        )


@dataclass(frozen=True)
class ScaleCheck:
    point_1: PixelPoint
    point_2: PixelPoint
    known_distance_m: float
    measured_distance_m: float
    error_percent: float
    warning_threshold_percent: float = C.DEFAULT_SCALE_CHECK_WARNING_PERCENT

    @property
    def passed(self) -> bool:
        return self.error_percent <= self.warning_threshold_percent

    def to_dict(self) -> dict[str, Any]:
        return {
            "point_1": self.point_1.to_dict(),
            "point_2": self.point_2.to_dict(),
            "known_distance_m": self.known_distance_m,
            "measured_distance_m": self.measured_distance_m,
            "error_percent": self.error_percent,
            "warning_threshold_percent": self.warning_threshold_percent,
            "passed": self.passed,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ScaleCheck":
        return cls(
            point_1=PixelPoint.from_dict(value["point_1"]),
            point_2=PixelPoint.from_dict(value["point_2"]),
            known_distance_m=float(value["known_distance_m"]),
            measured_distance_m=float(value["measured_distance_m"]),
            error_percent=float(value["error_percent"]),
            warning_threshold_percent=float(
                value.get(
                    "warning_threshold_percent",
                    C.DEFAULT_SCALE_CHECK_WARNING_PERCENT,
                )
            ),
        )


@dataclass(frozen=True)
class Calibration:
    revision: int
    created_at: str
    scale_point_1: PixelPoint
    scale_point_2: PixelPoint
    known_distance_m: float
    metres_per_pixel: float
    origin_pixel: PixelPoint
    east_unit_x: float
    east_unit_y: float
    origin_east_m: float = 0.0
    origin_north_m: float = 0.0
    source_units: str = "metres"
    scale_check: ScaleCheck | None = None

    def __post_init__(self) -> None:
        if self.revision < 1:
            raise CivilModelError("calibration revision must be >= 1")
        if self.metres_per_pixel <= 0:
            raise CivilModelError("metres_per_pixel must be positive")
        norm = (self.east_unit_x**2 + self.east_unit_y**2) ** 0.5
        if abs(norm - 1.0) > 1e-9:
            raise CivilModelError("east basis must be normalized")
        if self.source_units != "metres":
            raise CivilModelError("only metre output is currently supported")

    @property
    def north_unit_x(self) -> float:
        return -self.east_unit_y

    @property
    def north_unit_y(self) -> float:
        return self.east_unit_x

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "created_at": self.created_at,
            "scale_point_1": self.scale_point_1.to_dict(),
            "scale_point_2": self.scale_point_2.to_dict(),
            "known_distance_m": self.known_distance_m,
            "metres_per_pixel": self.metres_per_pixel,
            "origin_pixel": self.origin_pixel.to_dict(),
            "east_unit": {"x": self.east_unit_x, "y": self.east_unit_y},
            "north_unit": {"x": self.north_unit_x, "y": self.north_unit_y},
            "origin_east_m": self.origin_east_m,
            "origin_north_m": self.origin_north_m,
            "source_units": self.source_units,
            "scale_check": None if self.scale_check is None else self.scale_check.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Calibration":
        east_unit = value["east_unit"]
        check = value.get("scale_check")
        return cls(
            revision=int(value["revision"]),
            created_at=str(value["created_at"]),
            scale_point_1=PixelPoint.from_dict(value["scale_point_1"]),
            scale_point_2=PixelPoint.from_dict(value["scale_point_2"]),
            known_distance_m=float(value["known_distance_m"]),
            metres_per_pixel=float(value["metres_per_pixel"]),
            origin_pixel=PixelPoint.from_dict(value["origin_pixel"]),
            east_unit_x=float(east_unit["x"]),
            east_unit_y=float(east_unit["y"]),
            origin_east_m=float(value.get("origin_east_m", 0.0)),
            origin_north_m=float(value.get("origin_north_m", 0.0)),
            source_units=str(value.get("source_units", "metres")),
            scale_check=None if check is None else ScaleCheck.from_dict(check),
        )


@dataclass
class CivilPoint:
    id: str
    page_index: int
    page_label: str
    source_file: str
    source_sha256: str
    pixel_x: float
    pixel_y: float
    elevation: float
    point_type: str
    symbol_type: str
    source_method: str
    review_status: str
    created_at: str
    updated_at: str
    local_east: float | None = None
    local_north: float | None = None
    pdf_x: float | None = None
    pdf_y: float | None = None
    detected_text: str = ""
    normalized_text: str = ""
    text_confidence: float | None = None
    symbol_confidence: float | None = None
    association_confidence: float | None = None
    classification_confidence: float | None = None
    classification_reason: list[str] = field(default_factory=list)
    description: str = ""
    crop_reference: str = ""
    text_bbox: dict[str, float] | None = None
    alternative_associations: list[dict[str, Any]] = field(default_factory=list)
    user_edits: list[dict[str, Any]] = field(default_factory=list)
    calibration_revision: int | None = None
    point_number: str = ""
    sheet: str = ""
    revision_label: str = ""
    notes: str = ""
    capture_candidate_id: str = ""
    capture_mode: str = ""
    capture_confidence: float | None = None
    capture_audit: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.id.startswith("PT-"):
            raise CivilModelError("point id must start with PT-")
        if self.page_index < 0:
            raise CivilModelError("page_index must be non-negative")
        if self.pixel_x < 0 or self.pixel_y < 0:
            raise CivilModelError("pixel coordinates must be non-negative")
        if self.point_type not in C.POINT_TYPES:
            raise CivilModelError(f"invalid point type: {self.point_type}")
        if self.review_status not in C.REVIEW_STATUSES:
            raise CivilModelError(f"invalid review status: {self.review_status}")
        if self.source_method not in C.SOURCE_METHODS:
            raise CivilModelError(f"invalid source method: {self.source_method}")
        if self.symbol_type not in C.SYMBOL_TYPES:
            raise CivilModelError(f"invalid symbol type: {self.symbol_type}")
        for confidence in (
            self.text_confidence,
            self.symbol_confidence,
            self.association_confidence,
            self.classification_confidence,
            self.capture_confidence,
        ):
            if confidence is not None and not 0.0 <= confidence <= 1.0:
                raise CivilModelError("confidence must be between 0 and 1")

    @property
    def approved(self) -> bool:
        return self.review_status in C.APPROVED_STATUSES

    @property
    def terrain_relevant(self) -> bool:
        return self.point_type in C.TERRAIN_POINT_TYPES

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "page_index": self.page_index,
            "page_label": self.page_label,
            "source_file": self.source_file,
            "source_sha256": self.source_sha256,
            "pixel_x": self.pixel_x,
            "pixel_y": self.pixel_y,
            "pdf_x": self.pdf_x,
            "pdf_y": self.pdf_y,
            "local_east": self.local_east,
            "local_north": self.local_north,
            "elevation": self.elevation,
            "point_type": self.point_type,
            "symbol_type": self.symbol_type,
            "source_method": self.source_method,
            "detected_text": self.detected_text,
            "normalized_text": self.normalized_text,
            "text_confidence": self.text_confidence,
            "symbol_confidence": self.symbol_confidence,
            "association_confidence": self.association_confidence,
            "classification_confidence": self.classification_confidence,
            "review_status": self.review_status,
            "classification_reason": list(self.classification_reason),
            "description": self.description,
            "crop_reference": self.crop_reference,
            "text_bbox": self.text_bbox,
            "alternative_associations": list(self.alternative_associations),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "user_edits": list(self.user_edits),
            "calibration_revision": self.calibration_revision,
            "point_number": self.point_number,
            "sheet": self.sheet,
            "revision_label": self.revision_label,
            "notes": self.notes,
            "capture_candidate_id": self.capture_candidate_id,
            "capture_mode": self.capture_mode,
            "capture_confidence": self.capture_confidence,
            "capture_audit": dict(self.capture_audit),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CivilPoint":
        return cls(
            id=str(value["id"]),
            page_index=int(value.get("page_index", 0)),
            page_label=str(value.get("page_label", "1")),
            source_file=str(value.get("source_file", "")),
            source_sha256=str(value.get("source_sha256", "")),
            pixel_x=float(value["pixel_x"]),
            pixel_y=float(value["pixel_y"]),
            pdf_x=None if value.get("pdf_x") is None else float(value["pdf_x"]),
            pdf_y=None if value.get("pdf_y") is None else float(value["pdf_y"]),
            local_east=(
                None if value.get("local_east") is None else float(value["local_east"])
            ),
            local_north=(
                None if value.get("local_north") is None else float(value["local_north"])
            ),
            elevation=float(value["elevation"]),
            point_type=str(value["point_type"]),
            symbol_type=str(value.get("symbol_type", "NONE")),
            source_method=str(value.get("source_method", C.MANUAL)),
            detected_text=str(value.get("detected_text", "")),
            normalized_text=str(value.get("normalized_text", "")),
            text_confidence=_optional_float(value.get("text_confidence")),
            symbol_confidence=_optional_float(value.get("symbol_confidence")),
            association_confidence=_optional_float(
                value.get("association_confidence")
            ),
            classification_confidence=_optional_float(
                value.get("classification_confidence")
            ),
            review_status=str(value.get("review_status", C.UNREVIEWED)),
            classification_reason=list(value.get("classification_reason", [])),
            description=str(value.get("description", "")),
            crop_reference=str(value.get("crop_reference", "")),
            text_bbox=value.get("text_bbox"),
            alternative_associations=list(
                value.get("alternative_associations", [])
            ),
            created_at=str(value.get("created_at", "")),
            updated_at=str(value.get("updated_at", "")),
            user_edits=list(value.get("user_edits", [])),
            calibration_revision=(
                None
                if value.get("calibration_revision") is None
                else int(value["calibration_revision"])
            ),
            point_number=str(value.get("point_number", "")),
            sheet=str(value.get("sheet", "")),
            revision_label=str(value.get("revision_label", "")),
            notes=str(value.get("notes", "")),
            capture_candidate_id=str(value.get("capture_candidate_id", "")),
            capture_mode=str(value.get("capture_mode", "")),
            capture_confidence=_optional_float(value.get("capture_confidence")),
            capture_audit=dict(value.get("capture_audit", {})),
        )


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


@dataclass
class CivilProject:
    project_id: str
    name: str
    created_at: str
    updated_at: str
    source_manifest: dict[str, Any]
    schema_version: str = C.SCHEMA_VERSION
    pages: list[dict[str, Any]] = field(default_factory=list)
    crop: CropRegion | None = None
    calibration: Calibration | None = None
    calibration_history: list[Calibration] = field(default_factory=list)
    plausible_elevation_min: float = C.DEFAULT_PLAUSIBLE_ELEVATION_RANGE[0]
    plausible_elevation_max: float = C.DEFAULT_PLAUSIBLE_ELEVATION_RANGE[1]
    points: list[CivilPoint] = field(default_factory=list)
    boundaries: list[list[PixelPoint]] = field(default_factory=list)
    exclusion_polygons: list[list[PixelPoint]] = field(default_factory=list)
    breaklines: list[list[PixelPoint]] = field(default_factory=list)
    no_cross_lines: list[list[PixelPoint]] = field(default_factory=list)
    disabled_triangles: list[str] = field(default_factory=list)
    qa_results: dict[str, Any] = field(default_factory=dict)
    export_history: list[dict[str, Any]] = field(default_factory=list)
    decision_log: list[dict[str, Any]] = field(default_factory=list)
    exports_stale: bool = True
    feature_flags: dict[str, bool] = field(
        default_factory=lambda: {"preliminary_surface": False, "landxml": False}
    )

    def __post_init__(self) -> None:
        if not self.project_id or not self.project_id.startswith("CPD-"):
            raise CivilModelError("project id must start with CPD-")
        if not self.name.strip():
            raise CivilModelError("project name is required")
        if self.plausible_elevation_min >= self.plausible_elevation_max:
            raise CivilModelError("plausible elevation range is invalid")
        ids = [point.id for point in self.points]
        if len(ids) != len(set(ids)):
            raise CivilModelError("duplicate point ids")

    def point(self, point_id: str) -> CivilPoint:
        for point in self.points:
            if point.id == point_id:
                return point
        raise CivilModelError(f"unknown point: {point_id}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source_manifest": dict(self.source_manifest),
            "pages": list(self.pages),
            "crop": None if self.crop is None else self.crop.to_dict(),
            "calibration": (
                None if self.calibration is None else self.calibration.to_dict()
            ),
            "calibration_history": [
                item.to_dict() for item in self.calibration_history
            ],
            "plausible_elevation_range": {
                "min": self.plausible_elevation_min,
                "max": self.plausible_elevation_max,
            },
            "point_candidates": [point.to_dict() for point in self.points],
            "approved_points": [
                point.id for point in self.points if point.approved
            ],
            "rejected_points": [
                point.id for point in self.points if point.review_status == C.REJECTED
            ],
            "manual_points": [
                point.id for point in self.points if point.source_method == C.MANUAL
            ],
            "boundaries": [_polygon_to_dict(item) for item in self.boundaries],
            "exclusion_polygons": [
                _polygon_to_dict(item) for item in self.exclusion_polygons
            ],
            "breaklines": [_polygon_to_dict(item) for item in self.breaklines],
            "no_cross_lines": [
                _polygon_to_dict(item) for item in self.no_cross_lines
            ],
            "disabled_triangles": list(self.disabled_triangles),
            "qa_results": dict(self.qa_results),
            "export_history": list(self.export_history),
            "decision_log": list(self.decision_log),
            "exports_stale": self.exports_stale,
            "feature_flags": dict(self.feature_flags),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CivilProject":
        elevation_range = value.get("plausible_elevation_range") or {}
        crop = value.get("crop")
        calibration = value.get("calibration")
        return cls(
            schema_version=str(value.get("schema_version", C.SCHEMA_VERSION)),
            project_id=str(value["project_id"]),
            name=str(value["name"]),
            created_at=str(value["created_at"]),
            updated_at=str(value["updated_at"]),
            source_manifest=dict(value.get("source_manifest", {})),
            pages=list(value.get("pages", [])),
            crop=None if crop is None else CropRegion.from_dict(crop),
            calibration=(
                None if calibration is None else Calibration.from_dict(calibration)
            ),
            calibration_history=[
                Calibration.from_dict(item)
                for item in value.get("calibration_history", [])
            ],
            plausible_elevation_min=float(
                elevation_range.get(
                    "min", C.DEFAULT_PLAUSIBLE_ELEVATION_RANGE[0]
                )
            ),
            plausible_elevation_max=float(
                elevation_range.get(
                    "max", C.DEFAULT_PLAUSIBLE_ELEVATION_RANGE[1]
                )
            ),
            points=[
                CivilPoint.from_dict(item)
                for item in value.get("point_candidates", value.get("points", []))
            ],
            boundaries=[
                _polygon_from_dict(item) for item in value.get("boundaries", [])
            ],
            exclusion_polygons=[
                _polygon_from_dict(item)
                for item in value.get("exclusion_polygons", [])
            ],
            breaklines=[
                _polygon_from_dict(item) for item in value.get("breaklines", [])
            ],
            no_cross_lines=[
                _polygon_from_dict(item)
                for item in value.get("no_cross_lines", [])
            ],
            disabled_triangles=list(value.get("disabled_triangles", [])),
            qa_results=dict(value.get("qa_results", {})),
            export_history=list(value.get("export_history", [])),
            decision_log=list(value.get("decision_log", [])),
            exports_stale=bool(value.get("exports_stale", True)),
            feature_flags=dict(
                value.get(
                    "feature_flags",
                    {"preliminary_surface": False, "landxml": False},
                )
            ),
        )


def _polygon_to_dict(points: list[PixelPoint]) -> list[dict[str, float]]:
    return [point.to_dict() for point in points]


def _polygon_from_dict(values: list[dict[str, Any]]) -> list[PixelPoint]:
    return [PixelPoint.from_dict(value) for value in values]
