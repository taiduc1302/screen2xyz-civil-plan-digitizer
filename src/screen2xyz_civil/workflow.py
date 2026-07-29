"""UI-independent review workflow and state invariants."""

from __future__ import annotations

import math
import re
import secrets
from dataclasses import replace
from functools import wraps
from typing import Any, Callable

from . import contracts as C
from .assisted_capture import CandidateEvidence
from .detection import (
    SymbolCandidate,
    TextCandidate,
    candidate_to_point,
    classify_candidate,
    in_exclusion_zone,
)
from .models import (
    Calibration,
    CivilModelError,
    CivilElevationLine,
    CivilPoint,
    CivilProject,
    CropRegion,
    PixelPoint,
)
from .transform import build_calibration, to_local, verify_scale


class WorkflowError(RuntimeError):
    """A requested workflow transition is unsafe or incomplete."""


def _default_id() -> str:
    return f"CPD-{secrets.token_hex(6).upper()}"


def new_project(
    name: str,
    source_manifest: dict[str, Any],
    *,
    now: Callable[[], str],
    project_id: str | None = None,
) -> CivilProject:
    timestamp = now()
    project = CivilProject(
        project_id=project_id or _default_id(),
        name=name.strip(),
        created_at=timestamp,
        updated_at=timestamp,
        source_manifest=dict(source_manifest),
        pages=[
            {
                "page_index": 0,
                "page_label": "1",
                "width_px": source_manifest.get("width_px"),
                "height_px": source_manifest.get("height_px"),
            }
        ],
    )
    project.decision_log.append(
        {
            "at": timestamp,
            "action": "PROJECT_CREATED",
            "detail": "Local preliminary civil project created.",
        }
    )
    return project


def undoable(method):
    """Record one project snapshot for each outer estimator action."""

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        outer = self._mutation_depth == 0
        snapshot = None
        if outer:
            snapshot = self.project.to_dict()
            self._undo_stack.append(snapshot)
            self._redo_stack.clear()
        self._mutation_depth += 1
        try:
            return method(self, *args, **kwargs)
        except Exception:
            if outer and snapshot is not None:
                self._restore_snapshot(snapshot)
                self._undo_stack.pop()
            raise
        finally:
            self._mutation_depth -= 1

    return wrapper


class CivilWorkflow:
    def __init__(self, project: CivilProject, *, now: Callable[[], str]) -> None:
        self.project = project
        self._now = now
        self._undo_stack: list[dict[str, Any]] = []
        self._redo_stack: list[dict[str, Any]] = []
        self._mutation_depth = 0

    def _touch(self) -> str:
        timestamp = self._now()
        self.project.updated_at = timestamp
        return timestamp

    def _audit(self, action: str, detail: str, **extra: Any) -> None:
        event = {"at": self._touch(), "action": action, "detail": detail}
        event.update(extra)
        self.project.decision_log.append(event)

    @undoable
    def set_crop(self, crop: CropRegion) -> None:
        width = float(self.project.source_manifest.get("width_px", 0))
        height = float(self.project.source_manifest.get("height_px", 0))
        if width and crop.x + crop.width > width:
            raise WorkflowError("crop extends beyond source width")
        if height and crop.y + crop.height > height:
            raise WorkflowError("crop extends beyond source height")
        self.project.crop = crop
        self.project.exports_stale = True
        self._audit("CROP_SET", "Working crop selected.", crop=crop.to_dict())

    @undoable
    def set_plausible_elevation_range(
        self,
        minimum: float,
        maximum: float,
    ) -> None:
        minimum = float(minimum)
        maximum = float(maximum)
        if not math.isfinite(minimum) or not math.isfinite(maximum):
            raise WorkflowError("plausible elevation limits must be finite")
        if minimum >= maximum:
            raise WorkflowError("minimum elevation must be less than maximum elevation")
        self.project.plausible_elevation_min = minimum
        self.project.plausible_elevation_max = maximum
        self.project.exports_stale = True
        self._audit(
            "PLAUSIBLE_ELEVATION_RANGE_SET",
            (
                f"Project elevation screening range set to "
                f"{minimum:g} through {maximum:g} metres."
            ),
            minimum=minimum,
            maximum=maximum,
        )

    @undoable
    def apply_calibration(
        self,
        *,
        scale_point_1: PixelPoint,
        scale_point_2: PixelPoint,
        known_distance_m: float,
        origin_pixel: PixelPoint,
        east_reference: PixelPoint,
        origin_east_m: float = 0.0,
        origin_north_m: float = 0.0,
        check_point_1: PixelPoint | None = None,
        check_point_2: PixelPoint | None = None,
        check_known_distance_m: float | None = None,
    ) -> Calibration:
        timestamp = self._now()
        revision = (
            1 if self.project.calibration is None else self.project.calibration.revision + 1
        )
        calibration = build_calibration(
            revision=revision,
            created_at=timestamp,
            scale_point_1=scale_point_1,
            scale_point_2=scale_point_2,
            known_distance_m=known_distance_m,
            origin_pixel=origin_pixel,
            east_reference=east_reference,
            origin_east_m=origin_east_m,
            origin_north_m=origin_north_m,
            check_point_1=check_point_1,
            check_point_2=check_point_2,
            check_known_distance_m=check_known_distance_m,
        )
        if self.project.calibration is not None:
            self.project.calibration_history.append(self.project.calibration)
        self.project.calibration = calibration
        for point in self.project.points:
            point.local_east, point.local_north = to_local(
                PixelPoint(point.pixel_x, point.pixel_y), calibration
            )
            point.calibration_revision = calibration.revision
            point.updated_at = timestamp
        self.project.exports_stale = True
        detail = f"Calibration revision {revision} applied; derived coordinates recomputed."
        if calibration.scale_check is not None and not calibration.scale_check.passed:
            detail += (
                f" Second-distance check warning: "
                f"{calibration.scale_check.error_percent:.3f}% error."
            )
        self._audit(
            "CALIBRATION_APPLIED",
            detail,
            revision=revision,
            exports_stale=True,
        )
        return calibration

    @undoable
    def verify_current_scale(
        self,
        point_1: PixelPoint,
        point_2: PixelPoint,
        known_distance_m: float,
    ):
        if self.project.calibration is None:
            raise WorkflowError("calibrate scale before running a second check")
        check = verify_scale(
            point_1,
            point_2,
            known_distance_m,
            self.project.calibration.metres_per_pixel,
        )
        self.project.calibration = replace(
            self.project.calibration, scale_check=check
        )
        self.project.exports_stale = True
        self._audit(
            "SCALE_CHECK_RECORDED",
            (
                f"Second-distance verification "
                f"{'passed' if check.passed else 'requires review'} at "
                f"{check.error_percent:.3f}% error."
            ),
            error_percent=check.error_percent,
            passed=check.passed,
        )
        return check

    @undoable
    def add_manual_point(
        self,
        *,
        pixel: PixelPoint,
        elevation: float,
        point_type: str,
        page_index: int = 0,
        page_label: str = "1",
    ) -> CivilPoint:
        if point_type not in C.TERRAIN_POINT_TYPES:
            raise WorkflowError("manual terrain point must be Existing, Design, or Contour")
        self._validate_elevation(elevation)
        if self.project.crop is not None and not self.project.crop.contains(pixel):
            raise WorkflowError("manual point is outside the selected crop")
        point_id = self._next_point_id()
        timestamp = self._now()
        local_east = local_north = None
        revision = None
        if self.project.calibration is not None:
            local_east, local_north = to_local(pixel, self.project.calibration)
            revision = self.project.calibration.revision
        description = (
            "MANUAL_EX"
            if point_type == C.EXISTING_GROUND
            else "MANUAL_DES"
            if point_type == C.DESIGN_GRADE
            else C.DESCRIPTION_BY_TYPE[point_type]
        )
        point = CivilPoint(
            id=point_id,
            point_number=point_id,
            page_index=page_index,
            page_label=page_label,
            source_file=str(self.project.source_manifest.get("display_name", "")),
            source_sha256=str(self.project.source_manifest.get("sha256", "")),
            pixel_x=pixel.x,
            pixel_y=pixel.y,
            local_east=local_east,
            local_north=local_north,
            elevation=float(elevation),
            point_type=point_type,
            symbol_type="MANUAL_POINT",
            source_method=C.MANUAL,
            review_status=C.UNREVIEWED,
            classification_reason=["manually entered by reviewer"],
            description=description,
            created_at=timestamp,
            updated_at=timestamp,
            calibration_revision=revision,
        )
        self.project.points.append(point)
        self.project.exports_stale = True
        self._audit(
            "POINT_ADDED",
            "Manual point added; explicit review is still required.",
            point_id=point.id,
        )
        return point

    @undoable
    def capture_assisted_point(
        self,
        evidence: CandidateEvidence,
        *,
        capture_mode: str,
        click_pixel: PixelPoint,
        snap_distance_px: float,
        capture_method: str = "CLICK",
    ) -> CivilPoint:
        """Promote exactly one indexed suggestion into the estimator Point Cart."""

        if capture_mode not in C.TERRAIN_POINT_TYPES:
            raise WorkflowError("capture mode must be Existing, Design, or Contour")
        if not evidence.capturable or evidence.elevation is None:
            category = evidence.rejection_category or "NOT_CAPTURABLE"
            raise WorkflowError(f"candidate is rejected evidence: {category}")
        if any(
            point.capture_candidate_id == evidence.candidate_id
            and point.capture_mode == capture_mode
            for point in self.project.points
        ):
            raise WorkflowError(
                "this candidate is already present in the Point Cart for this mode"
            )
        self._validate_elevation(evidence.elevation)
        if self.project.crop is not None and not self.project.crop.contains(
            evidence.pixel
        ):
            raise WorkflowError("snapped point is outside the selected crop")
        point_id = self._next_point_id()
        timestamp = self._now()
        local_east = local_north = None
        revision = None
        if self.project.calibration is not None:
            local_east, local_north = to_local(
                evidence.pixel, self.project.calibration
            )
            revision = self.project.calibration.revision
        confidence_values = [
            value
            for value in (
                evidence.text_confidence,
                evidence.association_confidence,
                evidence.classification_confidence,
            )
            if value is not None
        ]
        capture_confidence = (
            sum(confidence_values) / len(confidence_values)
            if confidence_values
            else None
        )
        reasons = list(evidence.reasons)
        reasons.insert(
            0,
            (
                f"estimator accepted assisted {capture_mode} capture "
                f"using {capture_method}"
            ),
        )
        if evidence.likely_type != capture_mode:
            reasons.append(
                f"capture mode overrode likely class {evidence.likely_type}"
            )
        description = (
            "ASSISTED_EX"
            if capture_mode == C.EXISTING_GROUND
            else "ASSISTED_DES"
            if capture_mode == C.DESIGN_GRADE
            else "CONTOUR"
        )
        sheet = str(
            self.project.source_manifest.get("sheet_id")
            or evidence.page_label
        )
        revision_label = str(
            self.project.source_manifest.get("revision") or ""
        )
        point = CivilPoint(
            id=point_id,
            point_number=point_id,
            page_index=evidence.page_index,
            page_label=evidence.page_label,
            sheet=sheet,
            revision_label=revision_label,
            source_file=str(self.project.source_manifest.get("display_name", "")),
            source_sha256=str(self.project.source_manifest.get("sha256", "")),
            pixel_x=evidence.pixel.x,
            pixel_y=evidence.pixel.y,
            local_east=local_east,
            local_north=local_north,
            elevation=float(evidence.elevation),
            point_type=capture_mode,
            symbol_type=evidence.symbol_type,
            source_method=evidence.source_method,
            review_status=C.UNREVIEWED,
            detected_text=evidence.detected_text,
            normalized_text=evidence.normalized_text,
            text_confidence=evidence.text_confidence,
            symbol_confidence=evidence.symbol_confidence,
            association_confidence=evidence.association_confidence,
            classification_confidence=evidence.classification_confidence,
            capture_confidence=capture_confidence,
            classification_reason=reasons,
            description=description,
            text_bbox=dict(evidence.text_bbox),
            alternative_associations=[
                dict(item) for item in evidence.alternative_associations
            ],
            created_at=timestamp,
            updated_at=timestamp,
            calibration_revision=revision,
            capture_candidate_id=evidence.candidate_id,
            capture_mode=capture_mode,
            capture_audit={
                "method": capture_method,
                "candidate_id": evidence.candidate_id,
                "likely_type": evidence.likely_type,
                "click_pixel": click_pixel.to_dict(),
                "snap_pixel": evidence.pixel.to_dict(),
                "snap_distance_px": float(snap_distance_px),
                "classification_confidence": evidence.classification_confidence,
                "captured_at": timestamp,
            },
        )
        self.project.points.append(point)
        self.project.exports_stale = True
        self._audit(
            "ASSISTED_POINT_CAPTURED",
            "Indexed suggestion promoted into the Point Cart for explicit review.",
            point_id=point.id,
            candidate_id=evidence.candidate_id,
            capture_mode=capture_mode,
            capture_method=capture_method,
            snap_distance_px=float(snap_distance_px),
        )
        return point

    @undoable
    def add_elevation_line(
        self,
        vertices: list[PixelPoint],
        *,
        elevation: float,
        source_method: str = C.MANUAL,
        description: str = "CONTOUR",
    ) -> CivilElevationLine:
        self._validate_elevation(elevation)
        if len(vertices) < 2:
            raise WorkflowError("contour line requires at least two vertices")
        if source_method not in C.SOURCE_METHODS:
            raise WorkflowError("invalid contour-line source method")
        for vertex in vertices:
            if self.project.crop is not None and not self.project.crop.contains(vertex):
                raise WorkflowError("contour-line vertex is outside the selected crop")
        timestamp = self._now()
        next_number = max(
            (
                int(line.id.split("-")[-1])
                for line in self.project.elevation_lines
                if line.id.split("-")[-1].isdigit()
            ),
            default=0,
        ) + 1
        line = CivilElevationLine(
            id=f"CL-{next_number:06d}",
            elevation=float(elevation),
            vertices=list(vertices),
            source_method=source_method,
            review_status=C.UNREVIEWED,
            created_at=timestamp,
            updated_at=timestamp,
            description=description.strip() or "CONTOUR",
            sheet=str(self.project.source_manifest.get("sheet_id") or ""),
            revision_label=str(self.project.source_manifest.get("revision") or ""),
        )
        self.project.elevation_lines.append(line)
        self.project.exports_stale = True
        self._audit(
            "ELEVATION_LINE_ADDED",
            "Reviewer supplied explicit contour-line geometry and elevation.",
            line_id=line.id,
            vertex_count=len(vertices),
            elevation=float(elevation),
        )
        return line

    @undoable
    def approve_elevation_line(self, line_id: str) -> CivilElevationLine:
        if self.project.calibration is None:
            raise WorkflowError("calibration is required before line approval")
        line = next(
            (item for item in self.project.elevation_lines if item.id == line_id),
            None,
        )
        if line is None:
            raise WorkflowError(f"unknown elevation line: {line_id}")
        line.review_status = C.APPROVED
        line.updated_at = self._touch()
        self.project.exports_stale = True
        self._audit(
            "ELEVATION_LINE_APPROVED",
            "Reviewer explicitly approved contour-line geometry.",
            line_id=line.id,
        )
        return line

    @undoable
    def add_candidate(self, point: CivilPoint) -> CivilPoint:
        if any(existing.id == point.id for existing in self.project.points):
            raise WorkflowError(f"duplicate point id: {point.id}")
        if point.approved:
            raise WorkflowError("automatic candidate cannot enter the project approved")
        if self.project.crop is not None and not self.project.crop.contains(
            PixelPoint(point.pixel_x, point.pixel_y)
        ):
            raise WorkflowError("candidate is outside the selected crop")
        if self.project.calibration is not None:
            point.local_east, point.local_north = to_local(
                PixelPoint(point.pixel_x, point.pixel_y), self.project.calibration
            )
            point.calibration_revision = self.project.calibration.revision
        if not point.point_number:
            point.point_number = point.id
        self.project.points.append(point)
        self.project.exports_stale = True
        self._audit(
            "CANDIDATE_ADDED",
            "Extracted candidate added for review.",
            point_id=point.id,
        )
        return point

    @undoable
    def ingest_text_candidates(
        self,
        candidates: list[TextCandidate],
        symbols: list[SymbolCandidate] | None = None,
    ) -> dict[str, Any]:
        added: list[CivilPoint] = []
        filtered: list[dict[str, str]] = []
        available_symbols = symbols or []
        for candidate in candidates:
            if self.project.crop is not None and not self.project.crop.contains(
                candidate.bbox.center
            ):
                filtered.append(
                    {"candidate_id": candidate.id, "reason": "outside selected crop"}
                )
                continue
            excluded = in_exclusion_zone(
                candidate.bbox, self.project.exclusion_polygons
            )
            effective = (
                replace(candidate, in_exclusion_zone=True)
                if excluded and not candidate.in_exclusion_zone
                else candidate
            )
            classification = classify_candidate(
                effective,
                available_symbols,
                plausible_range=(
                    self.project.plausible_elevation_min,
                    self.project.plausible_elevation_max,
                ),
            )
            if (
                classification.normalized is None
                or classification.point_type
                in {
                    C.SLOPE_ANNOTATION,
                    C.DRAWING_METADATA,
                    C.UTILITY_INVERT,
                    C.UTILITY_RIM,
                    C.SLAB_ELEVATION,
                    C.DIMENSION,
                    C.MATERIAL_THICKNESS,
                }
            ):
                filtered.append(
                    {
                        "candidate_id": candidate.id,
                        "reason": "; ".join(classification.reasons),
                    }
                )
                continue
            point = candidate_to_point(
                effective,
                classification,
                point_id=self._next_point_id(),
                source_file=str(
                    self.project.source_manifest.get("display_name", "")
                ),
                source_sha256=str(
                    self.project.source_manifest.get("sha256", "")
                ),
                now=self._now(),
            )
            if classification.association is not None:
                match = next(
                    (
                        symbol
                        for symbol in available_symbols
                        if symbol.id == classification.association.symbol_id
                    ),
                    None,
                )
                point.symbol_confidence = (
                    None if match is None else match.confidence
                )
            self.add_candidate(point)
            added.append(point)
        self._audit(
            "CANDIDATE_BATCH_INGESTED",
            (
                f"Added {len(added)} review candidates; "
                f"filtered {len(filtered)} non-terrain/out-of-crop values."
            ),
            added_count=len(added),
            filtered_count=len(filtered),
        )
        return {"added": added, "filtered": filtered}

    @undoable
    def use_alternative_association(
        self, point_id: str, alternative_index: int = 0
    ) -> CivilPoint:
        point = self.project.point(point_id)
        if not 0 <= alternative_index < len(point.alternative_associations):
            raise WorkflowError("requested alternative association is unavailable")
        alternative = point.alternative_associations.pop(alternative_index)
        updated = self.edit_point(
            point_id,
            pixel=PixelPoint(
                float(alternative["pixel_x"]), float(alternative["pixel_y"])
            ),
        )
        updated.symbol_type = str(alternative["symbol_type"])
        updated.association_confidence = float(alternative["score"])
        updated.classification_reason.append(
            f"reviewer selected alternative symbol {alternative['symbol_id']}"
        )
        return updated

    @undoable
    def edit_point(
        self,
        point_id: str,
        *,
        elevation: float | None = None,
        point_type: str | None = None,
        pixel: PixelPoint | None = None,
        point_number: str | None = None,
        description: str | None = None,
        sheet: str | None = None,
        revision_label: str | None = None,
        notes: str | None = None,
    ) -> CivilPoint:
        point = self.project.point(point_id)
        before = {
            "elevation": point.elevation,
            "point_type": point.point_type,
            "pixel_x": point.pixel_x,
            "pixel_y": point.pixel_y,
            "review_status": point.review_status,
            "point_number": point.point_number,
            "description": point.description,
            "sheet": point.sheet,
            "revision_label": point.revision_label,
            "notes": point.notes,
        }
        if elevation is not None:
            self._validate_elevation(elevation)
            point.elevation = float(elevation)
        if point_type is not None:
            if point_type not in C.POINT_TYPES:
                raise WorkflowError("invalid point classification")
            point.point_type = point_type
            point.description = C.DESCRIPTION_BY_TYPE.get(point_type, point.description)
        if pixel is not None:
            if self.project.crop is not None and not self.project.crop.contains(pixel):
                raise WorkflowError("point move would leave the selected crop")
            point.pixel_x = pixel.x
            point.pixel_y = pixel.y
            if self.project.calibration is not None:
                point.local_east, point.local_north = to_local(
                    pixel, self.project.calibration
                )
                point.calibration_revision = self.project.calibration.revision
        if point_number is not None:
            cleaned = point_number.strip()
            if not cleaned:
                raise WorkflowError("point number cannot be empty")
            if any(
                other.id != point.id and other.point_number == cleaned
                for other in self.project.points
            ):
                raise WorkflowError("point number must be unique")
            point.point_number = cleaned
        if description is not None:
            point.description = description.strip()
        if sheet is not None:
            point.sheet = sheet.strip()
        if revision_label is not None:
            point.revision_label = revision_label.strip()
        if notes is not None:
            point.notes = notes.strip()
        point.review_status = C.REVIEW_REQUIRED
        timestamp = self._touch()
        point.updated_at = timestamp
        point.user_edits.append(
            {
                "at": timestamp,
                "before": before,
                "after": {
                    "elevation": point.elevation,
                    "point_type": point.point_type,
                    "pixel_x": point.pixel_x,
                    "pixel_y": point.pixel_y,
                    "point_number": point.point_number,
                    "description": point.description,
                    "sheet": point.sheet,
                    "revision_label": point.revision_label,
                    "notes": point.notes,
                },
            }
        )
        self.project.exports_stale = True
        self.project.decision_log.append(
            {
                "at": timestamp,
                "action": "POINT_EDITED",
                "detail": "Point edited and returned to review.",
                "point_id": point.id,
            }
        )
        return point

    @undoable
    def approve_point(self, point_id: str) -> CivilPoint:
        point = self.project.point(point_id)
        if self.project.calibration is None:
            raise WorkflowError("calibration is required before point approval")
        if not point.terrain_relevant:
            raise WorkflowError("only terrain-relevant classes can be approved for export")
        self._validate_elevation(point.elevation)
        if point.local_east is None or point.local_north is None:
            raise WorkflowError("point has no derived local coordinates")
        point.review_status = (
            C.EDITED_AND_APPROVED if point.user_edits else C.APPROVED
        )
        point.updated_at = self._touch()
        point.calibration_revision = self.project.calibration.revision
        self.project.exports_stale = True
        self.project.decision_log.append(
            {
                "at": point.updated_at,
                "action": "POINT_APPROVED",
                "detail": "Reviewer explicitly approved point.",
                "point_id": point.id,
            }
        )
        return point

    @undoable
    def reject_point(self, point_id: str, reason: str = "Reviewer rejected point.") -> CivilPoint:
        point = self.project.point(point_id)
        point.review_status = C.REJECTED
        point.updated_at = self._touch()
        point.classification_reason.append(reason)
        self.project.exports_stale = True
        self.project.decision_log.append(
            {
                "at": point.updated_at,
                "action": "POINT_REJECTED",
                "detail": reason,
                "point_id": point.id,
            }
        )
        return point

    @undoable
    def mark_review_required(self, point_id: str, reason: str) -> CivilPoint:
        point = self.project.point(point_id)
        point.review_status = C.REVIEW_REQUIRED
        point.updated_at = self._touch()
        point.classification_reason.append(reason)
        self.project.exports_stale = True
        return point

    @undoable
    def merge_duplicate(self, keep_id: str, reject_id: str) -> CivilPoint:
        if keep_id == reject_id:
            raise WorkflowError("cannot merge a point with itself")
        kept = self.project.point(keep_id)
        rejected = self.project.point(reject_id)
        if None in (kept.local_east, kept.local_north, rejected.local_east, rejected.local_north):
            raise WorkflowError("both duplicate candidates need local coordinates")
        distance = math.hypot(
            float(kept.local_east) - float(rejected.local_east),
            float(kept.local_north) - float(rejected.local_north),
        )
        if distance > C.DEFAULT_DUPLICATE_DISTANCE_M:
            raise WorkflowError("points are not within the duplicate tolerance")
        return self.reject_point(
            reject_id, f"Merged as duplicate of {keep_id}; separation {distance:.6f} m."
        )

    @undoable
    def delete_manual_point(self, point_id: str) -> None:
        point = self.project.point(point_id)
        if point.source_method != C.MANUAL:
            raise WorkflowError("only manually added points can be deleted")
        self.project.points.remove(point)
        self.project.exports_stale = True
        self._audit(
            "MANUAL_POINT_DELETED",
            "Reviewer deleted a manual point after confirmation.",
            point_id=point.id,
        )

    @undoable
    def delete_cart_point(self, point_id: str) -> None:
        point = self.project.point(point_id)
        self.project.points.remove(point)
        self.project.exports_stale = True
        self._audit(
            "CART_POINT_DELETED",
            "Reviewer deleted a Point Cart row after confirmation.",
            point_id=point.id,
            point_number=point.point_number or point.id,
            prior_status=point.review_status,
        )

    @undoable
    def bulk_approve(self, point_ids: list[str]) -> list[CivilPoint]:
        if not point_ids:
            raise WorkflowError("select at least one point to bulk approve")
        approved = [self.approve_point(point_id) for point_id in point_ids]
        self._audit(
            "POINTS_BULK_APPROVED",
            f"Reviewer explicitly approved {len(approved)} selected cart rows.",
            point_ids=list(point_ids),
        )
        return approved

    @undoable
    def bulk_change_description(
        self,
        point_ids: list[str],
        description: str,
    ) -> list[CivilPoint]:
        if not point_ids:
            raise WorkflowError("select at least one point")
        changed = [
            self.edit_point(point_id, description=description)
            for point_id in point_ids
        ]
        self._audit(
            "POINTS_BULK_DESCRIPTION_CHANGED",
            f"Changed description on {len(changed)} selected cart rows.",
            point_ids=list(point_ids),
        )
        return changed

    @undoable
    def renumber_points(
        self,
        *,
        point_ids: list[str] | None = None,
        prefix: str = "P",
        start: int = 1,
        padding: int = 4,
    ) -> list[CivilPoint]:
        if start < 0 or not 1 <= padding <= 12:
            raise WorkflowError("renumber settings are invalid")
        selected = (
            list(self.project.points)
            if point_ids is None
            else [self.project.point(point_id) for point_id in point_ids]
        )
        if not selected:
            raise WorkflowError("there are no points to renumber")
        untouched = {
            point.point_number
            for point in self.project.points
            if point not in selected and point.point_number
        }
        new_numbers = [
            f"{prefix}{number:0{padding}d}"
            for number in range(start, start + len(selected))
        ]
        if len(set(new_numbers)) != len(new_numbers) or untouched.intersection(
            new_numbers
        ):
            raise WorkflowError("renumbering would create duplicate point numbers")
        timestamp = self._now()
        for point, number in zip(selected, new_numbers):
            point.point_number = number
            point.updated_at = timestamp
        self.project.exports_stale = True
        self._audit(
            "POINTS_RENUMBERED",
            f"Renumbered {len(selected)} Point Cart rows.",
            point_ids=[point.id for point in selected],
            prefix=prefix,
            start=start,
            padding=padding,
        )
        return selected

    @undoable
    def sort_points(self, key: str, *, reverse: bool = False) -> None:
        keys = {
            "point_number": lambda point: point.point_number or point.id,
            "page": lambda point: (point.page_index, point.id),
            "elevation": lambda point: (point.elevation, point.id),
            "class": lambda point: (point.point_type, point.id),
            "status": lambda point: (point.review_status, point.id),
            "created": lambda point: (point.created_at, point.id),
        }
        if key not in keys:
            raise WorkflowError("unsupported Point Cart sort")
        self.project.points.sort(key=keys[key], reverse=reverse)
        self._audit(
            "POINT_CART_SORTED",
            f"Point Cart sorted by {key}.",
            key=key,
            reverse=reverse,
        )

    def undo(self) -> str:
        if not self._undo_stack:
            raise WorkflowError("nothing to undo")
        current = self.project.to_dict()
        snapshot = self._undo_stack.pop()
        self._redo_stack.append(current)
        self._restore_snapshot(snapshot)
        self._audit("UNDO", "Reverted the previous estimator action.")
        return "Previous estimator action undone."

    def redo(self) -> str:
        if not self._redo_stack:
            raise WorkflowError("nothing to redo")
        current = self.project.to_dict()
        snapshot = self._redo_stack.pop()
        self._undo_stack.append(current)
        self._restore_snapshot(snapshot)
        self._audit("REDO", "Reapplied the previously undone estimator action.")
        return "Estimator action redone."

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def _restore_snapshot(self, snapshot: dict[str, Any]) -> None:
        restored = CivilProject.from_dict(snapshot)
        self.project.__dict__.clear()
        self.project.__dict__.update(restored.__dict__)

    @undoable
    def set_boundary(self, points: list[PixelPoint]) -> None:
        self._validate_geometry(points, minimum=3, label="boundary")
        self.project.boundaries = [list(points)]
        self.project.exports_stale = True
        self._audit(
            "BOUNDARY_SET",
            f"Reviewed boundary set with {len(points)} vertices.",
        )

    @undoable
    def add_exclusion_polygon(self, points: list[PixelPoint]) -> None:
        self._validate_geometry(points, minimum=3, label="exclusion polygon")
        self.project.exclusion_polygons.append(list(points))
        self.project.exports_stale = True
        self._audit(
            "EXCLUSION_ADDED",
            f"Reviewed exclusion polygon added with {len(points)} vertices.",
        )

    @undoable
    def add_breakline(self, points: list[PixelPoint]) -> None:
        self._validate_geometry(points, minimum=2, label="breakline")
        self.project.breaklines.append(list(points))
        self.project.exports_stale = True
        self._audit(
            "BREAKLINE_ADDED",
            f"User-reviewed preliminary breakline added with {len(points)} vertices.",
        )

    @undoable
    def add_no_cross_line(self, points: list[PixelPoint]) -> None:
        self._validate_geometry(points, minimum=2, label="no-cross line")
        self.project.no_cross_lines.append(list(points))
        self.project.exports_stale = True
        self._audit(
            "NO_CROSS_ADDED",
            f"User-reviewed no-cross line added with {len(points)} vertices.",
        )

    @undoable
    def disable_triangle(self, triangle_id: str) -> None:
        if not re.fullmatch(r"T-\d{4,}", triangle_id):
            raise WorkflowError("invalid triangle id")
        if triangle_id not in self.project.disabled_triangles:
            self.project.disabled_triangles.append(triangle_id)
        self.project.exports_stale = True
        self._audit(
            "TRIANGLE_DISABLED",
            "Reviewer disabled a preliminary surface triangle.",
            triangle_id=triangle_id,
        )

    def _validate_geometry(
        self, points: list[PixelPoint], *, minimum: int, label: str
    ) -> None:
        if len(points) < minimum:
            raise WorkflowError(f"{label} requires at least {minimum} vertices")
        if len({(point.x, point.y) for point in points}) < minimum:
            raise WorkflowError(f"{label} vertices must be distinct")
        if self.project.crop is not None and any(
            not self.project.crop.contains(point) for point in points
        ):
            raise WorkflowError(f"{label} must stay inside the selected crop")

    def _validate_elevation(self, elevation: float) -> None:
        if not math.isfinite(float(elevation)):
            raise WorkflowError("elevation must be finite")
        if not (
            self.project.plausible_elevation_min
            <= float(elevation)
            <= self.project.plausible_elevation_max
        ):
            raise WorkflowError("elevation is outside the configured plausible range")

    def _next_point_id(self) -> str:
        largest = 0
        for point in self.project.points:
            match = re.fullmatch(r"PT-(\d+)", point.id)
            if match:
                largest = max(largest, int(match.group(1)))
        return f"PT-{largest + 1:04d}"
