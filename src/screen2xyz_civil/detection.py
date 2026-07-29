"""Explainable numeric, symbol, association, and civil-classification rules."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from . import contracts as C
from .models import CivilPoint, PixelPoint


@dataclass(frozen=True)
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self) -> None:
        if self.x1 < self.x0 or self.y1 < self.y0:
            raise ValueError("rectangle coordinates must be normalized")

    @property
    def center(self) -> PixelPoint:
        return PixelPoint((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    def contains(self, point: PixelPoint) -> bool:
        return self.x0 <= point.x <= self.x1 and self.y0 <= point.y <= self.y1

    def intersects(self, other: "Rect") -> bool:
        return not (
            self.x1 < other.x0
            or self.x0 > other.x1
            or self.y1 < other.y0
            or self.y0 > other.y1
        )

    def expanded(self, padding: float) -> "Rect":
        return Rect(
            self.x0 - padding,
            self.y0 - padding,
            self.x1 + padding,
            self.y1 + padding,
        )

    def to_dict(self) -> dict[str, float]:
        return {"x0": self.x0, "y0": self.y0, "x1": self.x1, "y1": self.y1}


@dataclass(frozen=True)
class TextCandidate:
    id: str
    text: str
    bbox: Rect
    page_index: int
    source_method: str
    confidence: float
    context: str = ""
    pdf_bbox: Rect | None = None
    in_exclusion_zone: bool = False


@dataclass(frozen=True)
class VectorShape:
    id: str
    bbox: Rect
    kind: str
    closed: bool = False
    line_segments: int = 0
    has_leader: bool = False
    stroke_color: str = ""
    layer: str = ""
    confidence: float = 0.5


@dataclass(frozen=True)
class SymbolCandidate:
    id: str
    symbol_type: str
    bbox: Rect
    confidence: float
    source_method: str
    has_leader: bool = False
    stroke_color: str = ""
    layer: str = ""


@dataclass(frozen=True)
class AssociationCandidate:
    symbol_id: str
    symbol_type: str
    score: float
    distance_px: float
    reasons: tuple[str, ...]
    point: PixelPoint

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol_id": self.symbol_id,
            "symbol_type": self.symbol_type,
            "score": self.score,
            "distance_px": self.distance_px,
            "reasons": list(self.reasons),
            "pixel_x": self.point.x,
            "pixel_y": self.point.y,
        }


@dataclass(frozen=True)
class NormalizedNumber:
    value: float
    normalized_text: str
    ambiguous: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Classification:
    point_type: str
    confidence: float
    reasons: tuple[str, ...]
    normalized: NormalizedNumber | None = None
    association: AssociationCandidate | None = None
    alternatives: tuple[AssociationCandidate, ...] = field(default_factory=tuple)


_NUMBER_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
_PERCENT_RE = re.compile(r"^[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)\s*%$")
_DATE_RE = re.compile(r"^(?:\d{1,2}[-/]){2}\d{2,4}$")
_SCALE_RE = re.compile(r"^(?:1\s*:\s*\d+|\d+\s*=\s*\d+)$")
_STATION_RE = re.compile(r"^\d+\+\d+(?:\.\d+)?$")


def normalize_numeric(text: str, *, allow_decimal_comma: bool = True) -> NormalizedNumber:
    raw = text.strip().replace("\u2212", "-").replace("\u2013", "-")
    if not raw:
        raise ValueError("empty numeric candidate")
    if _PERCENT_RE.match(raw):
        raise ValueError("percentage is not an elevation")
    if _DATE_RE.match(raw) or _SCALE_RE.match(raw) or _STATION_RE.match(raw):
        raise ValueError("metadata-like numeric candidate")
    reasons: list[str] = []
    ambiguous = False
    normalized = raw
    if allow_decimal_comma and "," in normalized and "." not in normalized:
        normalized = normalized.replace(",", ".")
        reasons.append("decimal comma normalized")
    elif "," in normalized:
        raise ValueError("mixed comma and decimal point is ambiguous")
    compact = re.sub(r"\s+", "", normalized)
    if compact != normalized:
        if not re.fullmatch(r"[+\-\d.Oo\s]+", normalized):
            raise ValueError("unsafe spaced numeric normalization")
        normalized = compact
        ambiguous = True
        reasons.append("spaces removed; reviewer confirmation required")
    corrected = re.sub(r"(?<=[\d.])[Oo](?=\d)", "0", normalized)
    if corrected != normalized:
        normalized = corrected
        ambiguous = True
        reasons.append("OCR letter O between digits normalized to zero")
    if not _NUMBER_RE.fullmatch(normalized):
        raise ValueError("not a standalone decimal number")
    value = float(normalized)
    if not math.isfinite(value):
        raise ValueError("numeric candidate is not finite")
    reasons.append("standalone decimal parsed")
    return NormalizedNumber(value, normalized, ambiguous, tuple(reasons))


def detect_symbols(shapes: Iterable[VectorShape]) -> list[SymbolCandidate]:
    shape_list = list(shapes)
    symbols: list[SymbolCandidate] = []
    for shape in shape_list:
        kind = shape.kind.strip().lower()
        aspect = (
            shape.bbox.width / shape.bbox.height
            if shape.bbox.height > 0
            else float("inf")
        )
        symbol_type = "UNKNOWN_SYMBOL"
        confidence = shape.confidence
        if kind in {"ellipse", "oval"} or (
            shape.closed
            and 1.15 <= aspect <= 3.5
            and shape.bbox.width >= 4
            and shape.bbox.height >= 3
        ):
            symbol_type = "DESIGN_OVAL"
            confidence = max(confidence, 0.78)
        elif kind in {"cross", "plus"} or (
            not shape.closed
            and shape.line_segments >= 2
            and 0.6 <= aspect <= 1.7
            and max(shape.bbox.width, shape.bbox.height) <= 40
        ):
            symbol_type = "EXISTING_CROSS"
            confidence = max(confidence, 0.72)
        elif kind in {"dot", "circle"} and shape.closed and max(
            shape.bbox.width, shape.bbox.height
        ) <= 12:
            symbol_type = "POINT_DOT"
            confidence = max(confidence, 0.65)
        elif kind in {"leader_endpoint", "leader"}:
            symbol_type = "LEADER_ENDPOINT"
            confidence = max(confidence, 0.6)
        symbols.append(
            SymbolCandidate(
                id=shape.id,
                symbol_type=symbol_type,
                bbox=shape.bbox,
                confidence=min(1.0, confidence),
                source_method=C.PDF_VECTOR,
                has_leader=shape.has_leader,
                stroke_color=shape.stroke_color,
                layer=shape.layer,
            )
        )
    line_shapes = [
        shape
        for shape in shape_list
        if shape.kind.strip().lower() == "line" and shape.line_segments == 1
    ]
    for index, first in enumerate(line_shapes):
        for second in line_shapes[index + 1 :]:
            first_horizontal = first.bbox.width >= first.bbox.height * 3
            first_vertical = first.bbox.height >= first.bbox.width * 3
            second_horizontal = second.bbox.width >= second.bbox.height * 3
            second_vertical = second.bbox.height >= second.bbox.width * 3
            if not (
                (first_horizontal and second_vertical)
                or (first_vertical and second_horizontal)
            ):
                continue
            if not first.bbox.expanded(2).intersects(second.bbox.expanded(2)):
                continue
            bbox = Rect(
                min(first.bbox.x0, second.bbox.x0),
                min(first.bbox.y0, second.bbox.y0),
                max(first.bbox.x1, second.bbox.x1),
                max(first.bbox.y1, second.bbox.y1),
            )
            symbols.append(
                SymbolCandidate(
                    id=f"cross:{first.id}:{second.id}",
                    symbol_type="EXISTING_CROSS",
                    bbox=bbox,
                    confidence=max(0.72, min(first.confidence, second.confidence)),
                    source_method=C.PDF_VECTOR,
                )
            )
    return symbols


def associate_candidate(
    text: TextCandidate,
    symbols: Iterable[SymbolCandidate],
    *,
    max_distance_px: float = 80.0,
    expected_label_right: bool = True,
    local_pattern_symbol_type: str | None = None,
) -> tuple[AssociationCandidate, ...]:
    associations: list[AssociationCandidate] = []
    text_center = text.bbox.center
    for symbol in symbols:
        symbol_center = symbol.bbox.center
        distance = math.hypot(
            symbol_center.x - text_center.x, symbol_center.y - text_center.y
        )
        contained = symbol.bbox.expanded(2.0).contains(text_center) or text.bbox.contains(
            symbol_center
        )
        if not contained and distance > max_distance_px:
            continue
        score = 0.0
        reasons: list[str] = []
        if contained:
            score += 0.43
            reasons.append("label and symbol geometries contain or overlap")
        proximity = max(0.0, 1.0 - distance / max_distance_px)
        score += 0.24 * proximity
        reasons.append(f"proximity contribution {0.24 * proximity:.3f}")
        if expected_label_right and text_center.x >= symbol_center.x:
            score += 0.08
            reasons.append("label lies in expected right-side position")
        if symbol.has_leader:
            score += 0.13
            reasons.append("vector leader signal present")
        if symbol.symbol_type in {"DESIGN_OVAL", "EXISTING_CROSS"}:
            score += 0.05
            reasons.append("recognized civil symbol geometry")
        if local_pattern_symbol_type == symbol.symbol_type:
            score += 0.05
            reasons.append("matches local symbol pattern")
        score += 0.02 * symbol.confidence
        associations.append(
            AssociationCandidate(
                symbol_id=symbol.id,
                symbol_type=symbol.symbol_type,
                score=min(1.0, score),
                distance_px=distance,
                reasons=tuple(reasons),
                point=symbol_center,
            )
        )
    return tuple(sorted(associations, key=lambda item: (-item.score, item.distance_px))[:3])


def classify_candidate(
    candidate: TextCandidate,
    symbols: Iterable[SymbolCandidate] = (),
    *,
    plausible_range: tuple[float, float] = C.DEFAULT_PLAUSIBLE_ELEVATION_RANGE,
) -> Classification:
    text = candidate.text.strip()
    context = f"{candidate.context} {text}".upper()
    if candidate.in_exclusion_zone:
        return Classification(
            C.DRAWING_METADATA,
            0.98,
            ("candidate lies in a reviewed exclusion zone",),
        )
    if _PERCENT_RE.match(text):
        return Classification(
            C.SLOPE_ANNOTATION,
            0.99,
            ("percent sign identifies a slope annotation",),
        )
    if re.search(r"\b(?:INV|INVERT)\b", context):
        point_type = C.UTILITY_INVERT
        context_reason = "near INV or INVERT notation"
    elif re.search(r"\bRIM\b", context):
        point_type = C.UTILITY_RIM
        context_reason = "near RIM notation"
    elif re.search(r"\b(?:SLAB|FFE|FFL)\b", context):
        point_type = C.SLAB_ELEVATION
        context_reason = "near slab or finished-floor notation"
    elif re.search(r"\b(?:SCALE|DATE|SHEET|REV|DRAWING)\b", context):
        point_type = C.DRAWING_METADATA
        context_reason = "near drawing metadata notation"
    else:
        point_type = ""
        context_reason = ""
    try:
        normalized = normalize_numeric(text)
    except ValueError as exc:
        return Classification(
            point_type or C.UNKNOWN_NUMERIC,
            0.92 if point_type else 0.2,
            ((context_reason,) if context_reason else ()) + (str(exc),),
        )
    if point_type:
        return Classification(
            point_type,
            0.94,
            (context_reason,) + normalized.reasons,
            normalized=normalized,
        )
    if not plausible_range[0] <= normalized.value <= plausible_range[1]:
        return Classification(
            C.UNKNOWN_NUMERIC,
            0.35,
            normalized.reasons
            + ("value is outside the configured plausible elevation range",),
            normalized=normalized,
        )
    associations = associate_candidate(candidate, symbols)
    association = associations[0] if associations else None
    if association and association.symbol_type == "DESIGN_OVAL":
        point_type = C.DESIGN_GRADE
        confidence = 0.55 + 0.4 * association.score
        reason = "best association is a design oval"
    elif association and association.symbol_type in {
        "EXISTING_CROSS",
        "PLUS_SIGN",
        "SURVEY_MARKER",
        "POINT_DOT",
    }:
        point_type = C.EXISTING_GROUND
        confidence = 0.52 + 0.4 * association.score
        reason = "best association is an existing/survey point marker"
    else:
        point_type = C.REVIEW_REQUIRED_TYPE
        confidence = 0.4
        reason = "standalone plausible decimal has no reliable terrain symbol"
    if normalized.ambiguous:
        confidence = min(confidence, 0.59)
    return Classification(
        point_type,
        min(0.99, confidence),
        normalized.reasons + (reason,),
        normalized=normalized,
        association=association,
        alternatives=associations[1:],
    )


def candidate_to_point(
    candidate: TextCandidate,
    classification: Classification,
    *,
    point_id: str,
    source_file: str,
    source_sha256: str,
    now: str,
) -> CivilPoint:
    if classification.normalized is None:
        raise ValueError("candidate has no normalized elevation")
    point_pixel = (
        classification.association.point
        if classification.association is not None
        else candidate.bbox.center
    )
    status = (
        C.AUTO_HIGH_CONFIDENCE
        if classification.point_type in C.TERRAIN_POINT_TYPES
        and classification.confidence >= 0.85
        else C.REVIEW_REQUIRED
    )
    association_confidence = (
        None
        if classification.association is None
        else classification.association.score
    )
    symbol_type = (
        "NONE"
        if classification.association is None
        else classification.association.symbol_type
    )
    return CivilPoint(
        id=point_id,
        page_index=candidate.page_index,
        page_label=str(candidate.page_index + 1),
        source_file=source_file,
        source_sha256=source_sha256,
        pixel_x=point_pixel.x,
        pixel_y=point_pixel.y,
        pdf_x=None if candidate.pdf_bbox is None else candidate.pdf_bbox.center.x,
        pdf_y=None if candidate.pdf_bbox is None else candidate.pdf_bbox.center.y,
        elevation=classification.normalized.value,
        point_type=classification.point_type,
        symbol_type=symbol_type,
        source_method=candidate.source_method,
        detected_text=candidate.text,
        normalized_text=classification.normalized.normalized_text,
        text_confidence=candidate.confidence,
        symbol_confidence=None,
        association_confidence=association_confidence,
        classification_confidence=classification.confidence,
        review_status=status,
        classification_reason=list(classification.reasons),
        description=C.DESCRIPTION_BY_TYPE.get(classification.point_type, ""),
        text_bbox=candidate.bbox.to_dict(),
        alternative_associations=[
            association.to_dict() for association in classification.alternatives
        ],
        created_at=now,
        updated_at=now,
    )


def in_exclusion_zone(bbox: Rect, zones: Iterable[Iterable[PixelPoint]]) -> bool:
    center = bbox.center
    return any(_point_in_polygon(center, list(zone)) for zone in zones)


def _point_in_polygon(point: PixelPoint, polygon: list[PixelPoint]) -> bool:
    if len(polygon) < 3:
        return False
    inside = False
    previous = polygon[-1]
    for current in polygon:
        if (current.y > point.y) != (previous.y > point.y):
            crossing_x = (
                (previous.x - current.x)
                * (point.y - current.y)
                / (previous.y - current.y)
                + current.x
            )
            if point.x < crossing_x:
                inside = not inside
        previous = current
    return inside
