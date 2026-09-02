"""Auditable takeoff workspace linked to a Civil Plan Digitizer project.

The first integration slice uses a sidecar (`.s2t.json`) instead of changing
the proven terrain-project schema in-place.  This keeps the new quantity domain
isolated while it is validated.  The sidecar records the Civil project id,
source identity, reviewed calibration snapshot, takeoff records, evidence,
withheld questions, and decision log.  A later owner-approved migration may
fold it into `CivilProject` once the workflow is stable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .io_utils import atomic_write_json, sha256_file
from .models import CivilProject
from .takeoff import (
    APPROVED_TAKEOFF_STATUSES,
    LINE,
    POLYGON,
    REVIEW_REQUIRED,
    TakeoffError,
    TakeoffGeometry,
    TakeoffMeasurement,
    approve_takeoff,
    clear_takeoff_flag,
    correct_takeoff_geometry,
    reject_takeoff,
    set_takeoff_flag,
    takeoff_qa_summary,
)
from .takeoff_context import (
    TakeoffContext,
    TakeoffContextError,
    TakeoffEvidenceRef,
    TakeoffQuestion,
    TakeoffRelation,
)


TAKEOFF_WORKSPACE_SCHEMA = "1.0"
TAKEOFF_WORKSPACE_SUFFIX = ".s2t.json"


class TakeoffWorkspaceError(RuntimeError):
    """Takeoff workspace state cannot be changed or persisted safely."""


@dataclass
class TakeoffWorkspace:
    civil_project_id: str
    created_at: str
    updated_at: str
    source_identity: dict[str, Any]
    schema_version: str = TAKEOFF_WORKSPACE_SCHEMA
    calibration_revision: int | None = None
    metres_per_pixel: float | None = None
    scale_verified: bool = False
    measurements: list[TakeoffMeasurement] = field(default_factory=list)
    context: TakeoffContext = field(default_factory=TakeoffContext)
    decision_log: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.civil_project_id.startswith("CPD-"):
            raise TakeoffWorkspaceError("civil project id must start with CPD-")
        ids = [item.id for item in self.measurements]
        if len(ids) != len(set(ids)):
            raise TakeoffWorkspaceError("duplicate takeoff ids")
        try:
            self.context.validate_links(ids)
        except TakeoffContextError as exc:
            raise TakeoffWorkspaceError(str(exc)) from exc

    def measurement(self, takeoff_id: str) -> TakeoffMeasurement:
        for item in self.measurements:
            if item.id == takeoff_id:
                return item
        raise TakeoffWorkspaceError(f"unknown takeoff: {takeoff_id}")

    @property
    def takeoff_ids(self) -> list[str]:
        return [item.id for item in self.measurements]

    def open_questions_for_takeoff(self, takeoff_id: str) -> list[TakeoffQuestion]:
        return [
            item
            for item in self.context.questions
            if item.status == "OPEN" and takeoff_id in item.related_takeoff_ids
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "civil_project_id": self.civil_project_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source_identity": dict(self.source_identity),
            "calibration": {
                "revision": self.calibration_revision,
                "metres_per_pixel": self.metres_per_pixel,
                "scale_verified": self.scale_verified,
            },
            "measurements": [item.to_dict() for item in self.measurements],
            "context": self.context.to_dict(),
            "decision_log": list(self.decision_log),
            "qa": {
                "takeoffs": takeoff_qa_summary(self.measurements),
                "unresolved": self.context.unresolved_summary(),
            },
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TakeoffWorkspace":
        version = str(value.get("schema_version", ""))
        if version != TAKEOFF_WORKSPACE_SCHEMA:
            raise TakeoffWorkspaceError(
                f"unsupported takeoff workspace schema: {version or '<missing>'}"
            )
        calibration = dict(value.get("calibration", {}))
        try:
            context = TakeoffContext.from_dict(dict(value.get("context", {})))
        except (TakeoffContextError, TypeError, ValueError) as exc:
            raise TakeoffWorkspaceError("invalid takeoff context") from exc
        return cls(
            schema_version=version,
            civil_project_id=str(value["civil_project_id"]),
            created_at=str(value.get("created_at", "")),
            updated_at=str(value.get("updated_at", "")),
            source_identity=dict(value.get("source_identity", {})),
            calibration_revision=(
                None
                if calibration.get("revision") is None
                else int(calibration["revision"])
            ),
            metres_per_pixel=(
                None
                if calibration.get("metres_per_pixel") is None
                else float(calibration["metres_per_pixel"])
            ),
            scale_verified=bool(calibration.get("scale_verified", False)),
            measurements=[
                TakeoffMeasurement.from_dict(item)
                for item in value.get("measurements", [])
            ],
            context=context,
            decision_log=list(value.get("decision_log", [])),
        )


def _source_identity(project: CivilProject) -> dict[str, Any]:
    source = project.source_manifest
    return {
        "display_name": str(source.get("display_name", "")),
        "sha256": str(source.get("sha256", "")),
        "source_type": str(source.get("source_type", "")),
        "page_count": source.get("page_count"),
        "sheet_id": str(source.get("sheet_id", "")),
        "revision": str(source.get("revision", "")),
    }


def new_takeoff_workspace(
    project: CivilProject,
    *,
    now: str,
) -> TakeoffWorkspace:
    workspace = TakeoffWorkspace(
        civil_project_id=project.project_id,
        created_at=now,
        updated_at=now,
        source_identity=_source_identity(project),
    )
    sync_workspace_calibration(workspace, project, now=now, initial=True)
    workspace.decision_log.append(
        {
            "at": now,
            "action": "TAKEOFF_WORKSPACE_CREATED",
            "detail": "Review-first quantity workspace linked to Civil project.",
        }
    )
    return workspace


def sync_workspace_calibration(
    workspace: TakeoffWorkspace,
    project: CivilProject,
    *,
    now: str,
    initial: bool = False,
) -> None:
    if workspace.civil_project_id != project.project_id:
        raise TakeoffWorkspaceError("workspace belongs to a different Civil project")
    calibration = project.calibration
    revision = None if calibration is None else calibration.revision
    mpp = None if calibration is None else calibration.metres_per_pixel
    # The existing project treats a second-distance check as optional. In the
    # takeoff sidecar it is explicit: a present passing check is verified;
    # otherwise an estimator must later call `confirm_workspace_scale`.
    checked = bool(
        calibration is not None
        and calibration.scale_check is not None
        and calibration.scale_check.passed
    )
    changed = (
        workspace.calibration_revision != revision
        or workspace.metres_per_pixel != mpp
    )
    workspace.calibration_revision = revision
    workspace.metres_per_pixel = mpp
    workspace.scale_verified = checked
    workspace.updated_at = now
    if changed and not initial:
        invalidated = 0
        for item in workspace.measurements:
            if item.geometry.kind in {LINE, POLYGON}:
                if item.review_status in APPROVED_TAKEOFF_STATUSES or item.quantity is not None:
                    invalidated += 1
                item.quantity = None
                item.review_status = REVIEW_REQUIRED
                item.flags.add("SCALE_UNVERIFIED")
                item.updated_at = now
        workspace.decision_log.append(
            {
                "at": now,
                "action": "TAKEOFF_SCALE_CHANGED",
                "detail": "Calibration changed; scaled takeoffs returned to review.",
                "calibration_revision": revision,
                "invalidated_count": invalidated,
            }
        )


def confirm_workspace_scale(
    workspace: TakeoffWorkspace,
    *,
    now: str,
    reason: str,
) -> None:
    if workspace.metres_per_pixel is None or workspace.calibration_revision is None:
        raise TakeoffWorkspaceError("Civil project calibration is required")
    if not reason.strip():
        raise TakeoffWorkspaceError("scale confirmation reason is required")
    workspace.scale_verified = True
    for item in workspace.measurements:
        item.flags.discard("SCALE_UNVERIFIED")
        if item.geometry.kind in {LINE, POLYGON} and item.approved:
            item.review_status = REVIEW_REQUIRED
            item.quantity = None
        item.updated_at = now
    workspace.updated_at = now
    workspace.decision_log.append(
        {
            "at": now,
            "action": "TAKEOFF_SCALE_CONFIRMED",
            "detail": reason.strip(),
            "calibration_revision": workspace.calibration_revision,
        }
    )


def add_workspace_takeoff(
    workspace: TakeoffWorkspace,
    measurement: TakeoffMeasurement,
    *,
    now: str,
) -> TakeoffMeasurement:
    if any(item.id == measurement.id for item in workspace.measurements):
        raise TakeoffWorkspaceError(f"duplicate takeoff id: {measurement.id}")
    if measurement.approved:
        raise TakeoffWorkspaceError("takeoff proposal cannot enter workspace approved")
    workspace.measurements.append(measurement)
    try:
        workspace.context.validate_links(workspace.takeoff_ids)
    except TakeoffContextError as exc:
        workspace.measurements.pop()
        raise TakeoffWorkspaceError(str(exc)) from exc
    workspace.updated_at = now
    workspace.decision_log.append(
        {
            "at": now,
            "action": "TAKEOFF_ADDED",
            "takeoff_id": measurement.id,
            "rule_id": measurement.rule_id,
            "detail": "Takeoff proposal added for estimator review.",
        }
    )
    return measurement


def add_workspace_evidence(
    workspace: TakeoffWorkspace,
    evidence: TakeoffEvidenceRef,
    *,
    now: str,
) -> TakeoffEvidenceRef:
    try:
        workspace.context.add_evidence(evidence)
    except TakeoffContextError as exc:
        raise TakeoffWorkspaceError(str(exc)) from exc
    workspace.updated_at = now
    workspace.decision_log.append(
        {
            "at": now,
            "action": "TAKEOFF_EVIDENCE_ADDED",
            "evidence_id": evidence.id,
            "kind": evidence.kind,
            "detail": evidence.summary,
        }
    )
    return evidence


def link_workspace_evidence(
    workspace: TakeoffWorkspace,
    relation: TakeoffRelation,
    *,
    now: str,
) -> TakeoffRelation:
    try:
        workspace.context.add_relation(relation, takeoff_ids=workspace.takeoff_ids)
    except TakeoffContextError as exc:
        raise TakeoffWorkspaceError(str(exc)) from exc
    workspace.updated_at = now
    workspace.decision_log.append(
        {
            "at": now,
            "action": "TAKEOFF_EVIDENCE_LINKED",
            "source_id": relation.source_id,
            "target_id": relation.target_id,
            "relation_type": relation.relation_type,
            "detail": relation.detail,
        }
    )
    return relation


def add_workspace_question(
    workspace: TakeoffWorkspace,
    question: TakeoffQuestion,
    *,
    now: str,
) -> TakeoffQuestion:
    try:
        workspace.context.add_question(question, takeoff_ids=workspace.takeoff_ids)
    except TakeoffContextError as exc:
        raise TakeoffWorkspaceError(str(exc)) from exc
    workspace.updated_at = now
    workspace.decision_log.append(
        {
            "at": now,
            "action": "TAKEOFF_QUESTION_ADDED",
            "question_id": question.id,
            "reason_code": question.reason_code,
            "detail": question.detail,
            "next_action": question.next_action,
        }
    )
    return question


def resolve_workspace_question(
    workspace: TakeoffWorkspace,
    question_id: str,
    *,
    now: str,
    resolution: str,
) -> TakeoffQuestion:
    try:
        question = workspace.context.question(question_id)
        question.resolve(now=now, resolution=resolution)
    except TakeoffContextError as exc:
        raise TakeoffWorkspaceError(str(exc)) from exc
    workspace.updated_at = now
    workspace.decision_log.append(
        {
            "at": now,
            "action": "TAKEOFF_QUESTION_RESOLVED",
            "question_id": question.id,
            "detail": question.resolution,
        }
    )
    return question


def correct_workspace_takeoff(
    workspace: TakeoffWorkspace,
    takeoff_id: str,
    geometry: TakeoffGeometry,
    *,
    now: str,
    actor: str = "estimator",
    reason: str = "geometry corrected during review",
) -> TakeoffMeasurement:
    item = workspace.measurement(takeoff_id)
    correct_takeoff_geometry(item, geometry, now=now, actor=actor, reason=reason)
    workspace.updated_at = now
    workspace.decision_log.append(
        {
            "at": now,
            "action": "TAKEOFF_GEOMETRY_CORRECTED",
            "takeoff_id": item.id,
            "detail": reason,
        }
    )
    return item


def flag_workspace_takeoff(
    workspace: TakeoffWorkspace,
    takeoff_id: str,
    flag: str,
    *,
    now: str,
) -> TakeoffMeasurement:
    item = set_takeoff_flag(workspace.measurement(takeoff_id), flag, now=now)
    workspace.updated_at = now
    workspace.decision_log.append(
        {
            "at": now,
            "action": "TAKEOFF_FLAG_SET",
            "takeoff_id": item.id,
            "flag": flag.strip().upper(),
            "detail": "Takeoff returned to review with an explicit blocker/status flag.",
        }
    )
    return item


def clear_workspace_takeoff_flag(
    workspace: TakeoffWorkspace,
    takeoff_id: str,
    flag: str,
    *,
    now: str,
) -> TakeoffMeasurement:
    item = clear_takeoff_flag(workspace.measurement(takeoff_id), flag, now=now)
    workspace.updated_at = now
    workspace.decision_log.append(
        {
            "at": now,
            "action": "TAKEOFF_FLAG_CLEARED",
            "takeoff_id": item.id,
            "flag": flag.strip().upper(),
            "detail": "Estimator cleared takeoff flag; explicit approval is still required.",
        }
    )
    return item


def approve_workspace_takeoff(
    workspace: TakeoffWorkspace,
    takeoff_id: str,
    *,
    now: str,
) -> TakeoffMeasurement:
    item = workspace.measurement(takeoff_id)
    blocking_questions = [
        question
        for question in workspace.open_questions_for_takeoff(takeoff_id)
        if question.severity == "ERROR"
    ]
    if blocking_questions:
        ids = ", ".join(question.id for question in blocking_questions)
        raise TakeoffWorkspaceError(
            f"takeoff has unresolved blocking question(s): {ids}"
        )
    try:
        approve_takeoff(
            item,
            metres_per_pixel=workspace.metres_per_pixel,
            scale_verified=workspace.scale_verified,
            now=now,
        )
    except TakeoffError as exc:
        raise TakeoffWorkspaceError(str(exc)) from exc
    workspace.updated_at = now
    workspace.decision_log.append(
        {
            "at": now,
            "action": "TAKEOFF_APPROVED",
            "takeoff_id": item.id,
            "rule_id": item.rule_id,
            "quantity": item.quantity,
            "unit": item.unit,
            "calibration_revision": workspace.calibration_revision,
            "detail": "Estimator explicitly approved bid quantity.",
        }
    )
    return item


def reject_workspace_takeoff(
    workspace: TakeoffWorkspace,
    takeoff_id: str,
    *,
    now: str,
    reason: str,
) -> TakeoffMeasurement:
    try:
        item = reject_takeoff(workspace.measurement(takeoff_id), now=now, reason=reason)
    except TakeoffError as exc:
        raise TakeoffWorkspaceError(str(exc)) from exc
    workspace.updated_at = now
    workspace.decision_log.append(
        {
            "at": now,
            "action": "TAKEOFF_REJECTED",
            "takeoff_id": item.id,
            "detail": reason.strip(),
        }
    )
    return item


def save_takeoff_workspace(
    workspace: TakeoffWorkspace,
    path: Path,
    *,
    replace: bool = True,
) -> dict[str, str]:
    target = path.expanduser().resolve()
    if target.suffixes[-2:] != [".s2t", ".json"]:
        raise TakeoffWorkspaceError(
            f"takeoff workspace file must end with {TAKEOFF_WORKSPACE_SUFFIX}"
        )
    try:
        workspace.context.validate_links(workspace.takeoff_ids)
        atomic_write_json(target, workspace.to_dict(), replace=replace)
        return {"path": str(target), "sha256": sha256_file(target)}
    except (OSError, ValueError, TakeoffError, TakeoffContextError) as exc:
        raise TakeoffWorkspaceError("takeoff workspace save failed") from exc


def load_takeoff_workspace(path: Path) -> TakeoffWorkspace:
    target = path.expanduser().resolve()
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise TakeoffWorkspaceError("takeoff workspace root must be a JSON object")
        return TakeoffWorkspace.from_dict(value)
    except TakeoffWorkspaceError:
        raise
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
        TakeoffContextError,
    ) as exc:
        raise TakeoffWorkspaceError("takeoff workspace load failed") from exc
