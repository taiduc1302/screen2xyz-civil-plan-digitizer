"""Live elevation-under-cursor support for estimator-assisted capture.

The extraction pool intentionally stays separate from ``CivilProject.points``.
Only an estimator click/Enter action promotes one candidate into the Point Cart.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
import re
import statistics
import time
from typing import Iterable

from . import contracts as C
from .detection import (
    SymbolCandidate,
    TextCandidate,
    classify_candidate,
    in_exclusion_zone,
)
from .models import Calibration, CivilProject, PixelPoint
from .transform import to_local


STRICT_REJECTION_TYPES = frozenset(
    {
        C.SLOPE_ANNOTATION,
        C.UTILITY_RIM,
        C.UTILITY_INVERT,
        C.SLAB_ELEVATION,
        C.DIMENSION,
        C.MATERIAL_THICKNESS,
        C.DRAWING_METADATA,
    }
)


@dataclass(frozen=True)
class CandidateEvidence:
    """One indexed extraction result, including explicit rejected evidence."""

    candidate_id: str
    page_index: int
    page_label: str
    pixel: PixelPoint
    elevation: float | None
    likely_type: str
    source_method: str
    detected_text: str
    normalized_text: str
    text_confidence: float | None
    symbol_type: str
    symbol_confidence: float | None
    association_confidence: float | None
    classification_confidence: float
    reasons: tuple[str, ...]
    text_bbox: dict[str, float]
    alternative_associations: tuple[dict[str, object], ...]
    rejected: bool
    rejection_category: str

    @property
    def capturable(self) -> bool:
        return self.elevation is not None and not self.rejected


@dataclass(frozen=True)
class HoverSuggestion:
    """Resolved cursor state suitable for both UI display and capture."""

    cursor: PixelPoint
    local_east: float | None
    local_north: float | None
    evidence: CandidateEvidence | None
    snap_pixel: PixelPoint | None
    snap_distance_px: float | None
    snap_status: str
    capture_mode: str
    lookup_ms: float

    @property
    def can_capture(self) -> bool:
        return (
            self.evidence is not None
            and self.evidence.capturable
            and self.snap_pixel is not None
        )


class SpatialCandidateIndex:
    """Small grid index with deterministic nearest-neighbour ordering."""

    def __init__(
        self,
        candidates: Iterable[CandidateEvidence] = (),
        *,
        cell_size_px: float = 96.0,
    ) -> None:
        if cell_size_px <= 0:
            raise ValueError("cell_size_px must be positive")
        self.cell_size_px = float(cell_size_px)
        self._candidates = tuple(candidates)
        buckets: dict[tuple[int, int], list[CandidateEvidence]] = {}
        for candidate in self._candidates:
            buckets.setdefault(self._cell(candidate.pixel), []).append(candidate)
        self._buckets = {
            key: tuple(sorted(value, key=lambda item: item.candidate_id))
            for key, value in buckets.items()
        }

    def __len__(self) -> int:
        return len(self._candidates)

    @property
    def candidates(self) -> tuple[CandidateEvidence, ...]:
        return self._candidates

    def nearest(
        self,
        point: PixelPoint,
        *,
        radius_px: float,
        limit: int = 12,
    ) -> tuple[tuple[CandidateEvidence, float], ...]:
        if radius_px < 0:
            raise ValueError("radius_px must be non-negative")
        if limit <= 0:
            return ()
        cell_radius = int(math.ceil(radius_px / self.cell_size_px))
        center_x, center_y = self._cell(point)
        matches: list[tuple[CandidateEvidence, float]] = []
        for grid_x in range(center_x - cell_radius, center_x + cell_radius + 1):
            for grid_y in range(center_y - cell_radius, center_y + cell_radius + 1):
                for candidate in self._buckets.get((grid_x, grid_y), ()):
                    distance = math.hypot(
                        candidate.pixel.x - point.x,
                        candidate.pixel.y - point.y,
                    )
                    if distance <= radius_px:
                        matches.append((candidate, distance))
        matches.sort(key=lambda item: (item[1], item[0].candidate_id))
        return tuple(matches[:limit])

    def _cell(self, point: PixelPoint) -> tuple[int, int]:
        return (
            int(math.floor(point.x / self.cell_size_px)),
            int(math.floor(point.y / self.cell_size_px)),
        )


class ElevationUnderCursorService:
    """Resolve the best safe elevation/snap candidate for a cursor location."""

    def __init__(
        self,
        index: SpatialCandidateIndex,
        *,
        calibration: Calibration | None = None,
        snap_radius_px: float = 72.0,
        rejection_guard_px: float = 30.0,
    ) -> None:
        self.index = index
        self.calibration = calibration
        self.snap_radius_px = float(snap_radius_px)
        self.rejection_guard_px = float(rejection_guard_px)

    def suggest(
        self,
        cursor: PixelPoint,
        *,
        capture_mode: str,
    ) -> HoverSuggestion:
        if capture_mode not in C.TERRAIN_POINT_TYPES:
            raise ValueError("capture_mode must be Existing, Design, or Contour")
        started = time.perf_counter()
        local_east = local_north = None
        if self.calibration is not None:
            local_east, local_north = to_local(cursor, self.calibration)
        nearby = self.index.nearest(cursor, radius_px=self.snap_radius_px)
        evidence: CandidateEvidence | None = None
        distance: float | None = None
        status = "NO CANDIDATE"
        if nearby:
            nearest, nearest_distance = nearby[0]
            if nearest.rejected and nearest_distance <= self.rejection_guard_px:
                evidence = nearest
                distance = nearest_distance
                status = f"REJECTED {nearest.rejection_category}"
            else:
                capturable = [item for item in nearby if item[0].capturable]
                matching = [
                    item
                    for item in capturable
                    if item[0].likely_type == capture_mode
                ]
                chosen = (matching or capturable)
                if chosen:
                    evidence, distance = chosen[0]
                    status = (
                        "SNAP MATCH"
                        if evidence.likely_type == capture_mode
                        else "SNAP MODE OVERRIDE"
                    )
                else:
                    evidence, distance = nearest, nearest_distance
                    status = (
                        f"REJECTED {nearest.rejection_category}"
                        if nearest.rejected
                        else "NO ELEVATION"
                    )
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return HoverSuggestion(
            cursor=cursor,
            local_east=local_east,
            local_north=local_north,
            evidence=evidence,
            snap_pixel=(
                evidence.pixel if evidence is not None and evidence.capturable else None
            ),
            snap_distance_px=distance,
            snap_status=status,
            capture_mode=capture_mode,
            lookup_ms=elapsed_ms,
        )


def build_candidate_evidence(
    project: CivilProject,
    candidates: Iterable[TextCandidate],
    symbols: Iterable[SymbolCandidate] = (),
) -> tuple[CandidateEvidence, ...]:
    """Classify every extraction result without adding anything to the cart."""

    available_candidates = tuple(candidates)
    available_symbols = tuple(symbols)
    local_elevation_center = _dominant_explicit_decimal_center(
        available_candidates,
        plausible_range=(
            project.plausible_elevation_min,
            project.plausible_elevation_max,
        ),
    )
    evidence_items: list[CandidateEvidence] = []
    symbol_by_id = {symbol.id: symbol for symbol in available_symbols}
    for candidate in available_candidates:
        outside_crop = (
            project.crop is not None and not project.crop.contains(candidate.bbox.center)
        )
        excluded = in_exclusion_zone(candidate.bbox, project.exclusion_polygons)
        effective = (
            replace(candidate, in_exclusion_zone=True)
            if excluded and not candidate.in_exclusion_zone
            else candidate
        )
        repaired_text = _repair_missing_decimal(
            candidate.text,
            local_elevation_center=local_elevation_center,
        )
        classified_candidate = (
            effective
            if repaired_text is None
            else replace(effective, text=repaired_text)
        )
        classification = classify_candidate(
            classified_candidate,
            available_symbols,
            plausible_range=(
                project.plausible_elevation_min,
                project.plausible_elevation_max,
            ),
        )
        if repaired_text is not None:
            classification = replace(
                classification,
                confidence=min(classification.confidence, 0.68),
                reasons=(
                    (
                        "missing decimal glyph repaired from the page-local "
                        "elevation pattern; reviewer confirmation required"
                    ),
                )
                + classification.reasons,
            )
        association = classification.association
        matched_symbol = (
            None if association is None else symbol_by_id.get(association.symbol_id)
        )
        point_pixel = (
            association.point if association is not None else candidate.bbox.center
        )
        normalized_value = (
            None
            if classification.normalized is None
            else classification.normalized.value
        )
        outside_plausible = (
            normalized_value is not None
            and not (
                project.plausible_elevation_min
                <= normalized_value
                <= project.plausible_elevation_max
            )
        )
        local_pattern_conflict = (
            repaired_text is None
            and local_elevation_center is not None
            and re.fullmatch(r"\d{4,}", candidate.text.strip()) is not None
        )
        strict_rejection = classification.point_type in STRICT_REJECTION_TYPES
        rejected = (
            outside_crop
            or excluded
            or strict_rejection
            or outside_plausible
            or local_pattern_conflict
        )
        rejection_category = ""
        reasons = list(classification.reasons)
        if outside_crop:
            rejection_category = "OUTSIDE_CROP"
            reasons.append("candidate lies outside the selected crop")
        elif excluded:
            rejection_category = "EXCLUSION_ZONE"
        elif strict_rejection:
            rejection_category = classification.point_type
        elif outside_plausible:
            rejection_category = "OUTSIDE_PLAUSIBLE_RANGE"
        elif local_pattern_conflict:
            rejection_category = "LOCAL_ELEVATION_PATTERN_CONFLICT"
        evidence_items.append(
            CandidateEvidence(
                candidate_id=candidate.id,
                page_index=candidate.page_index,
                page_label=str(candidate.page_index + 1),
                pixel=point_pixel,
                elevation=(
                    None
                    if classification.normalized is None
                    else classification.normalized.value
                ),
                likely_type=classification.point_type,
                source_method=candidate.source_method,
                detected_text=candidate.text,
                normalized_text=(
                    ""
                    if classification.normalized is None
                    else classification.normalized.normalized_text
                ),
                text_confidence=candidate.confidence,
                symbol_type=(
                    "NONE" if association is None else association.symbol_type
                ),
                symbol_confidence=(
                    None if matched_symbol is None else matched_symbol.confidence
                ),
                association_confidence=(
                    None if association is None else association.score
                ),
                classification_confidence=classification.confidence,
                reasons=tuple(reasons),
                text_bbox=candidate.bbox.to_dict(),
                alternative_associations=tuple(
                    item.to_dict() for item in classification.alternatives
                ),
                rejected=rejected,
                rejection_category=rejection_category,
            )
        )
    return tuple(
        sorted(
            evidence_items,
            key=lambda item: (item.page_index, item.pixel.y, item.pixel.x, item.candidate_id),
        )
    )


def _dominant_explicit_decimal_center(
    candidates: Iterable[TextCandidate],
    *,
    plausible_range: tuple[float, float],
) -> float | None:
    """Find a robust local elevation band from explicit decimal tokens."""

    values: list[float] = []
    for candidate in candidates:
        text = candidate.text.strip().replace(",", ".")
        if not re.fullmatch(r"[+-]?\d{1,5}\.\d{1,3}", text):
            continue
        try:
            value = float(text)
        except ValueError:
            continue
        if plausible_range[0] <= value <= plausible_range[1]:
            values.append(value)
    if len(values) < 3:
        return None
    ordered = sorted(values)
    best_window: list[float] = []
    right = 0
    for left, start in enumerate(ordered):
        right = max(right, left)
        while right < len(ordered) and ordered[right] - start <= 20.0:
            right += 1
        window = ordered[left:right]
        if len(window) > len(best_window):
            best_window = window
    if len(best_window) < 3:
        return None
    return float(statistics.median(best_window))


def _repair_missing_decimal(
    text: str,
    *,
    local_elevation_center: float | None,
) -> str | None:
    """Repair only high-signal four-digit tokens such as 5146 -> 51.46."""

    if local_elevation_center is None:
        return None
    stripped = text.strip()
    if not re.fullmatch(r"\d{4}", stripped):
        return None
    repaired_value = int(stripped) / 100.0
    if abs(repaired_value - local_elevation_center) > 10.0:
        return None
    return f"{repaired_value:.2f}"
