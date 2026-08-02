"""Explainable civil-project QA and duplicate/conflict detection."""

from __future__ import annotations

import math
from typing import Any

from . import contracts as C
from .models import CivilPoint, CivilProject


def duplicate_pairs(
    project: CivilProject,
    *,
    distance_tolerance_m: float = C.DEFAULT_DUPLICATE_DISTANCE_M,
    conflict_elevation_m: float = C.DEFAULT_CONFLICT_ELEVATION_M,
) -> list[dict[str, Any]]:
    candidates = [
        point
        for point in project.points
        if point.local_east is not None
        and point.local_north is not None
        and point.review_status != C.REJECTED
    ]
    pairs: list[dict[str, Any]] = []
    for index, left in enumerate(candidates):
        for right in candidates[index + 1 :]:
            distance = math.hypot(
                float(left.local_east) - float(right.local_east),
                float(left.local_north) - float(right.local_north),
            )
            if distance <= distance_tolerance_m:
                elevation_delta = abs(left.elevation - right.elevation)
                pairs.append(
                    {
                        "point_ids": [left.id, right.id],
                        "distance_m": distance,
                        "elevation_delta_m": elevation_delta,
                        "conflicting": elevation_delta > conflict_elevation_m
                        or left.point_type != right.point_type,
                    }
                )
    return pairs


def qa_summary(project: CivilProject) -> dict[str, Any]:
    pairs = duplicate_pairs(project)
    issues: list[dict[str, Any]] = []
    if project.calibration is None and not project.feature_flags.get(
        "external_coordinate_channels", False
    ):
        issues.append(
            {
                "severity": "CRITICAL",
                "code": "CALIBRATION_MISSING",
                "detail": "Scale, origin, and orientation are required.",
            }
        )
    elif project.calibration is None:
        issues.append(
            {
                "severity": "INFO",
                "code": "EXTERNAL_COORDINATE_CHANNELS",
                "detail": "Coordinates came from mapped capture channels; no plan transform was applied.",
            }
        )
    elif (
        project.calibration.scale_check is not None
        and not project.calibration.scale_check.passed
    ):
        issues.append(
            {
                "severity": "WARNING",
                "code": "SCALE_CHECK_MISMATCH",
                "detail": (
                    f"Second-distance error is "
                    f"{project.calibration.scale_check.error_percent:.3f}%."
                ),
            }
        )
    for point in project.points:
        _append_point_issues(project, point, issues)
    for pair in pairs:
        issues.append(
            {
                "severity": "ERROR" if pair["conflicting"] else "WARNING",
                "code": (
                    "CONFLICTING_DUPLICATE"
                    if pair["conflicting"]
                    else "DUPLICATE_CANDIDATE"
                ),
                "detail": (
                    f"{pair['point_ids'][0]} and {pair['point_ids'][1]} are "
                    f"{pair['distance_m']:.4f} m apart."
                ),
                "point_ids": pair["point_ids"],
            }
        )
    located = [
        point
        for point in project.points
        if point.local_east is not None and point.local_north is not None
    ]
    extents = None
    if located:
        extents = {
            "min_east": min(float(point.local_east) for point in located),
            "max_east": max(float(point.local_east) for point in located),
            "min_north": min(float(point.local_north) for point in located),
            "max_north": max(float(point.local_north) for point in located),
            "min_elevation": min(point.elevation for point in located),
            "max_elevation": max(point.elevation for point in located),
        }
    summary = {
        "existing_candidates": _count(project, C.EXISTING_GROUND),
        "existing_approved": _count(
            project, C.EXISTING_GROUND, C.APPROVED_STATUSES
        ),
        "design_candidates": _count(project, C.DESIGN_GRADE),
        "design_approved": _count(project, C.DESIGN_GRADE, C.APPROVED_STATUSES),
        "contour_candidates": _count(project, C.CONTOUR_ELEVATION),
        "contour_approved": _count(
            project, C.CONTOUR_ELEVATION, C.APPROVED_STATUSES
        ),
        "review_required": sum(
            point.review_status in {C.UNREVIEWED, C.REVIEW_REQUIRED, C.AUTO_HIGH_CONFIDENCE}
            for point in project.points
        ),
        "rejected": sum(
            point.review_status == C.REJECTED for point in project.points
        ),
        "duplicate_candidates": len(pairs),
        "conflicting_elevations": sum(pair["conflicting"] for pair in pairs),
        "out_of_range_values": sum(
            not (
                project.plausible_elevation_min
                <= point.elevation
                <= project.plausible_elevation_max
            )
            for point in project.points
        ),
        "low_confidence_ocr": sum(
            point.source_method == C.LOCAL_OCR
            and (point.text_confidence is None or point.text_confidence < 0.75)
            for point in project.points
        ),
        "unassociated_labels": sum(
            point.source_method != C.MANUAL
            and point.symbol_type in {"NONE", "UNKNOWN_SYMBOL"}
            for point in project.points
        ),
        "unused_symbols": 0,
        "coordinate_extents": extents,
        "issue_counts": {
            severity: sum(issue["severity"] == severity for issue in issues)
            for severity in ("CRITICAL", "ERROR", "WARNING", "INFO")
        },
        "issues": issues,
    }
    project.qa_results = summary
    return summary


def has_critical_export_errors(summary: dict[str, Any]) -> bool:
    counts = summary.get("issue_counts", {})
    return bool(counts.get("CRITICAL", 0))


def _count(
    project: CivilProject,
    point_type: str,
    statuses: frozenset[str] | None = None,
) -> int:
    return sum(
        point.point_type == point_type
        and (statuses is None or point.review_status in statuses)
        for point in project.points
    )


def _append_point_issues(
    project: CivilProject, point: CivilPoint, issues: list[dict[str, Any]]
) -> None:
    if not (
        project.plausible_elevation_min
        <= point.elevation
        <= project.plausible_elevation_max
    ):
        issues.append(
            {
                "severity": "ERROR",
                "code": "ELEVATION_OUT_OF_RANGE",
                "detail": f"{point.id} elevation is outside the configured range.",
                "point_ids": [point.id],
            }
        )
    if point.approved and (
        point.local_east is None
        or point.local_north is None
        or point.point_type not in C.TERRAIN_POINT_TYPES
    ):
        issues.append(
            {
                "severity": "CRITICAL",
                "code": "APPROVED_POINT_INVALID",
                "detail": f"{point.id} is approved but not exportable.",
                "point_ids": [point.id],
            }
        )
    if point.review_status in {
        C.UNREVIEWED,
        C.REVIEW_REQUIRED,
        C.AUTO_HIGH_CONFIDENCE,
    }:
        issues.append(
            {
                "severity": "INFO",
                "code": "POINT_NOT_REVIEWED",
                "detail": f"{point.id} is excluded from default export.",
                "point_ids": [point.id],
            }
        )
    if (
        point.association_confidence is not None
        and point.association_confidence < 0.6
    ):
        issues.append(
            {
                "severity": "WARNING",
                "code": "LOW_ASSOCIATION_CONFIDENCE",
                "detail": f"{point.id} has a low-confidence label association.",
                "point_ids": [point.id],
            }
        )
