"""Single-sheet, review-first takeoff session for AI-assisted Bluebeam work.

This is intentionally a pilot surface for the current estimator workflow.  It
stores geometry in a resolution-independent *rendered PDF point* frame:
72 units per rendered inch, origin top-left, y down.  Re-rendering at another
DPI therefore does not change retained geometry.

The session is not a Bluebeam file and does not silently approve bid quantity.
It is an auditable proposal/QA sidecar that an MCP agent can populate, after
which an estimator or a Bluebeam operator can create/read back native Revu
measurements.
"""

from __future__ import annotations

import json
import math
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .io_utils import atomic_write_json, sha256_file
from .pdf import inspect_pdf
from .takeoff import (
    COUNT,
    LINE,
    POLYGON,
    REVIEW_REQUIRED,
    RULES,
    TakeoffError,
    TakeoffGeometry,
    TakeoffMeasurement,
    TakeoffVertex,
    correct_takeoff_geometry,
    new_takeoff_proposal,
    quantity_for,
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


AGENT_SESSION_SCHEMA = "1.0"
AGENT_SESSION_SUFFIX = ".s2a.json"
CANONICAL_FRAME = "PDF_VIEW_POINTS_TOP_LEFT"
POINTS_PER_INCH = 72.0
METRES_PER_INCH = 0.0254


class AgentSessionError(RuntimeError):
    """The agent takeoff session cannot be changed safely."""


@dataclass
class AgentScale:
    metres_per_point: float | None = None
    resolved: bool = False
    verified: bool = False
    basis: str = ""
    method: str = ""

    def __post_init__(self) -> None:
        if self.metres_per_point is not None:
            if not math.isfinite(self.metres_per_point) or self.metres_per_point <= 0:
                raise AgentSessionError("scale metres_per_point must be positive")
            self.resolved = True
        if self.verified and not self.resolved:
            raise AgentSessionError("a verified scale must first be resolved")
        if self.verified and not self.basis.strip():
            raise AgentSessionError("verified scale requires a human-readable basis")

    def to_dict(self) -> dict[str, Any]:
        return {
            "metres_per_point": self.metres_per_point,
            "resolved": self.resolved,
            "verified": self.verified,
            "basis": self.basis,
            "method": self.method,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AgentScale":
        return cls(
            metres_per_point=(
                None
                if value.get("metres_per_point") is None
                else float(value["metres_per_point"])
            ),
            resolved=bool(value.get("resolved", False)),
            verified=bool(value.get("verified", False)),
            basis=str(value.get("basis", "")),
            method=str(value.get("method", "")),
        )


@dataclass
class AgentTakeoffSession:
    session_id: str
    name: str
    created_at: str
    updated_at: str
    source_identity: dict[str, Any]
    page_index: int
    page_label: str
    page_width_points: float
    page_height_points: float
    rotation: int
    render_dpi: int = 150
    coordinate_frame: str = CANONICAL_FRAME
    scale: AgentScale = field(default_factory=AgentScale)
    measurements: list[TakeoffMeasurement] = field(default_factory=list)
    context: TakeoffContext = field(default_factory=TakeoffContext)
    decision_log: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.session_id.startswith("S2A-"):
            raise AgentSessionError("session id must start with S2A-")
        if not self.name.strip():
            raise AgentSessionError("session name is required")
        if self.coordinate_frame != CANONICAL_FRAME:
            raise AgentSessionError("unsupported agent coordinate frame")
        if self.page_index < 0:
            raise AgentSessionError("page index must be non-negative")
        if self.page_width_points <= 0 or self.page_height_points <= 0:
            raise AgentSessionError("rendered PDF point dimensions must be positive")
        if self.rotation not in {0, 90, 180, 270}:
            raise AgentSessionError("page rotation must be 0/90/180/270")
        if self.render_dpi <= 0:
            raise AgentSessionError("render DPI must be positive")
        ids = [item.id for item in self.measurements]
        if len(ids) != len(set(ids)):
            raise AgentSessionError("duplicate takeoff ids")
        try:
            self.context.validate_links(ids)
        except TakeoffContextError as exc:
            raise AgentSessionError(str(exc)) from exc

    @property
    def source_path(self) -> Path:
        raw = str(self.source_identity.get("local_path", "")).strip()
        if not raw:
            raise AgentSessionError("session source path is unavailable")
        return Path(raw).expanduser().resolve()

    @property
    def source_sha256(self) -> str:
        return str(self.source_identity.get("sha256", ""))

    @property
    def takeoff_ids(self) -> list[str]:
        return [item.id for item in self.measurements]

    def measurement(self, takeoff_id: str) -> TakeoffMeasurement:
        for item in self.measurements:
            if item.id == takeoff_id:
                return item
        raise AgentSessionError(f"unknown takeoff: {takeoff_id}")

    def next_takeoff_id(self) -> str:
        used: set[int] = set()
        for item in self.measurements:
            try:
                used.add(int(item.id.split("-", 1)[1]))
            except (IndexError, ValueError):
                continue
        sequence = 1
        while sequence in used:
            sequence += 1
        return f"TK-{sequence:04d}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": AGENT_SESSION_SCHEMA,
            "session_id": self.session_id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source_identity": dict(self.source_identity),
            "page_index": self.page_index,
            "page_label": self.page_label,
            "page_width_points": self.page_width_points,
            "page_height_points": self.page_height_points,
            "rotation": self.rotation,
            "render_dpi": self.render_dpi,
            "coordinate_frame": self.coordinate_frame,
            "scale": self.scale.to_dict(),
            "measurements": [item.to_dict() for item in self.measurements],
            "context": self.context.to_dict(),
            "decision_log": list(self.decision_log),
            "qa": self.qa_summary(),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AgentTakeoffSession":
        version = str(value.get("schema_version", ""))
        if version != AGENT_SESSION_SCHEMA:
            raise AgentSessionError(
                f"unsupported agent session schema: {version or '<missing>'}"
            )
        try:
            context = TakeoffContext.from_dict(dict(value.get("context", {})))
        except (TakeoffContextError, TypeError, ValueError) as exc:
            raise AgentSessionError("invalid takeoff context") from exc
        return cls(
            session_id=str(value["session_id"]),
            name=str(value["name"]),
            created_at=str(value.get("created_at", "")),
            updated_at=str(value.get("updated_at", "")),
            source_identity=dict(value.get("source_identity", {})),
            page_index=int(value.get("page_index", 0)),
            page_label=str(value.get("page_label", "1")),
            page_width_points=float(value["page_width_points"]),
            page_height_points=float(value["page_height_points"]),
            rotation=int(value.get("rotation", 0)),
            render_dpi=int(value.get("render_dpi", 150)),
            coordinate_frame=str(value.get("coordinate_frame", CANONICAL_FRAME)),
            scale=AgentScale.from_dict(dict(value.get("scale", {}))),
            measurements=[
                TakeoffMeasurement.from_dict(item)
                for item in value.get("measurements", [])
            ],
            context=context,
            decision_log=list(value.get("decision_log", [])),
        )

    def verify_source_unchanged(self) -> None:
        path = self.source_path
        if not path.is_file():
            raise AgentSessionError(f"source PDF no longer exists: {path}")
        current = sha256_file(path)
        if self.source_sha256 and current != self.source_sha256:
            raise AgentSessionError(
                "source PDF hash changed; create a new session for the new revision"
            )

    def canonical_points(
        self,
        points: Iterable[Iterable[float]],
        *,
        coordinate_frame: str,
        render_dpi: float | None = None,
    ) -> tuple[TakeoffVertex, ...]:
        frame = coordinate_frame.strip().lower()
        rows = [tuple(float(v) for v in point) for point in points]
        if any(len(row) != 2 for row in rows):
            raise AgentSessionError("each point must contain exactly x and y")
        if frame in {"pdf", "pdf_points", "canonical"}:
            factor = 1.0
        elif frame in {"render", "render_px", "pixels"}:
            dpi = float(render_dpi or self.render_dpi)
            if not math.isfinite(dpi) or dpi <= 0:
                raise AgentSessionError("render DPI must be positive")
            factor = POINTS_PER_INCH / dpi
        elif frame in {"opentakeoff", "opentakeoff_px"}:
            # OpenTakeoff's reviewed contract is PDF point x 2.
            factor = 0.5
        else:
            raise AgentSessionError(
                "coordinate_frame must be pdf_points, render_px, or opentakeoff_px"
            )
        vertices = tuple(TakeoffVertex(x * factor, y * factor) for x, y in rows)
        for vertex in vertices:
            if vertex.x > self.page_width_points + 1e-6:
                raise AgentSessionError("takeoff point is outside page width")
            if vertex.y > self.page_height_points + 1e-6:
                raise AgentSessionError("takeoff point is outside page height")
        return vertices

    def render_points(
        self,
        geometry: TakeoffGeometry,
        *,
        render_dpi: float | None = None,
    ) -> list[list[float]]:
        dpi = float(render_dpi or self.render_dpi)
        factor = dpi / POINTS_PER_INCH
        return [[point.x * factor, point.y * factor] for point in geometry.vertices]

    def opentakeoff_points(self, geometry: TakeoffGeometry) -> list[list[float]]:
        return [[point.x * 2.0, point.y * 2.0] for point in geometry.vertices]

    def set_scale_ratio(
        self,
        ratio: float,
        *,
        now: str,
        basis: str,
        verified: bool = False,
    ) -> None:
        ratio = float(ratio)
        if not math.isfinite(ratio) or ratio <= 0:
            raise AgentSessionError("scale ratio must be positive")
        metres_per_point = ratio * METRES_PER_INCH / POINTS_PER_INCH
        self.scale = AgentScale(
            metres_per_point=metres_per_point,
            resolved=True,
            verified=bool(verified),
            basis=basis.strip(),
            method=f"PRINTED_RATIO_1_TO_{ratio:g}",
        )
        self._scale_changed(now=now, action="SCALE_RATIO_SET")

    def calibrate_scale(
        self,
        p1: Iterable[float],
        p2: Iterable[float],
        *,
        known_distance_m: float,
        coordinate_frame: str,
        now: str,
        basis: str,
        verified: bool = False,
        render_dpi: float | None = None,
    ) -> None:
        vertices = self.canonical_points(
            (p1, p2), coordinate_frame=coordinate_frame, render_dpi=render_dpi
        )
        distance_points = math.hypot(
            vertices[1].x - vertices[0].x,
            vertices[1].y - vertices[0].y,
        )
        known_distance_m = float(known_distance_m)
        if distance_points <= 0 or not math.isfinite(known_distance_m) or known_distance_m <= 0:
            raise AgentSessionError("calibration requires a positive known distance")
        self.scale = AgentScale(
            metres_per_point=known_distance_m / distance_points,
            resolved=True,
            verified=bool(verified),
            basis=basis.strip(),
            method="TWO_POINT_CALIBRATION",
        )
        self._scale_changed(now=now, action="SCALE_CALIBRATED")

    def verify_scale(
        self,
        p1: Iterable[float],
        p2: Iterable[float],
        *,
        known_distance_m: float,
        coordinate_frame: str,
        now: str,
        basis: str,
        tolerance_percent: float = 1.0,
        render_dpi: float | None = None,
    ) -> dict[str, float | bool]:
        if not self.scale.resolved or self.scale.metres_per_point is None:
            raise AgentSessionError("resolve scale before independent verification")
        vertices = self.canonical_points(
            (p1, p2), coordinate_frame=coordinate_frame, render_dpi=render_dpi
        )
        points = math.hypot(
            vertices[1].x - vertices[0].x,
            vertices[1].y - vertices[0].y,
        )
        measured = points * self.scale.metres_per_point
        expected = float(known_distance_m)
        if not math.isfinite(expected) or expected <= 0:
            raise AgentSessionError("verification distance must be positive")
        error_percent = abs(measured - expected) / expected * 100.0
        passed = error_percent <= float(tolerance_percent)
        self.scale.verified = passed
        self.scale.basis = basis.strip()
        self.updated_at = now
        self.decision_log.append(
            {
                "at": now,
                "action": "SCALE_VERIFIED" if passed else "SCALE_VERIFY_FAILED",
                "measured_m": measured,
                "expected_m": expected,
                "error_percent": error_percent,
                "tolerance_percent": float(tolerance_percent),
                "basis": basis.strip(),
            }
        )
        if passed:
            for item in self.measurements:
                item.flags.discard("SCALE_UNVERIFIED")
                item.updated_at = now
        return {
            "measured_m": measured,
            "expected_m": expected,
            "error_percent": error_percent,
            "passed": passed,
        }

    def _scale_changed(self, *, now: str, action: str) -> None:
        self.updated_at = now
        for item in self.measurements:
            if item.geometry.kind in {LINE, POLYGON}:
                item.quantity = None
                item.review_status = REVIEW_REQUIRED
                if not self.scale.verified:
                    item.flags.add("SCALE_UNVERIFIED")
                item.updated_at = now
        self.decision_log.append(
            {
                "at": now,
                "action": action,
                "metres_per_point": self.scale.metres_per_point,
                "resolved": self.scale.resolved,
                "verified": self.scale.verified,
                "basis": self.scale.basis,
            }
        )

    def add_takeoff(
        self,
        *,
        rule_id: str,
        geometry_kind: str,
        points: Iterable[Iterable[float]] = (),
        count: int | None = None,
        coordinate_frame: str = "pdf_points",
        render_dpi: float | None = None,
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
        if rule_id not in RULES:
            raise AgentSessionError(f"unknown civil takeoff rule: {rule_id}")
        if geometry_kind not in {LINE, POLYGON, COUNT}:
            raise AgentSessionError("geometry_kind must be LINE, POLYGON, or COUNT")
        rule = RULES[rule_id]
        if geometry_kind != rule.geometry_kind:
            raise AgentSessionError(
                f"{rule_id} requires {rule.geometry_kind}, not {geometry_kind}"
            )
        vertices: tuple[TakeoffVertex, ...] = ()
        if geometry_kind != COUNT:
            vertices = self.canonical_points(
                points,
                coordinate_frame=coordinate_frame,
                render_dpi=render_dpi,
            )
        geometry = TakeoffGeometry(geometry_kind, vertices=vertices, count=count)
        cleaned_flags = {str(flag).strip().upper() for flag in flags if str(flag).strip()}
        if geometry_kind in {LINE, POLYGON} and not self.scale.verified:
            cleaned_flags.add("SCALE_UNVERIFIED")
        item = new_takeoff_proposal(
            takeoff_id=self.next_takeoff_id(),
            rule_id=rule_id,
            page_index=self.page_index,
            page_label=self.page_label,
            geometry=geometry,
            now=now,
            source_engine=source_engine,
            source_method=source_method,
            generated_by=generated_by,
            confidence=confidence,
            external_id=external_id,
            label=label,
            bid_item=bid_item,
            flags=cleaned_flags,
            notes=notes,
        )
        item.provenance.extra.update(
            {
                "coordinate_frame": CANONICAL_FRAME,
                "source_sha256": self.source_sha256,
            }
        )
        self.measurements.append(item)
        self.updated_at = now
        self.context.validate_links(self.takeoff_ids)
        self.decision_log.append(
            {
                "at": now,
                "action": "AI_TAKEOFF_PROPOSED" if generated_by.lower() not in {"human", "manual", "estimator"} else "MANUAL_TAKEOFF_PROPOSED",
                "takeoff_id": item.id,
                "rule_id": item.rule_id,
                "source_engine": source_engine,
                "source_method": source_method,
            }
        )
        return item

    def edit_takeoff(
        self,
        takeoff_id: str,
        *,
        points: Iterable[Iterable[float]],
        coordinate_frame: str,
        now: str,
        reason: str,
        actor: str = "agent",
        render_dpi: float | None = None,
    ) -> TakeoffMeasurement:
        item = self.measurement(takeoff_id)
        if item.approved:
            raise AgentSessionError("approved takeoff cannot be edited by the agent surface")
        if item.geometry.kind == COUNT:
            raise AgentSessionError("count editing is not supported by point geometry")
        vertices = self.canonical_points(
            points,
            coordinate_frame=coordinate_frame,
            render_dpi=render_dpi,
        )
        corrected = TakeoffGeometry(item.geometry.kind, vertices=vertices)
        try:
            correct_takeoff_geometry(
                item,
                corrected,
                now=now,
                actor=actor,
                reason=reason,
            )
        except TakeoffError as exc:
            raise AgentSessionError(str(exc)) from exc
        if not self.scale.verified:
            item.flags.add("SCALE_UNVERIFIED")
        self.updated_at = now
        self.decision_log.append(
            {
                "at": now,
                "action": "TAKEOFF_PROPOSAL_EDITED",
                "takeoff_id": takeoff_id,
                "actor": actor,
                "detail": reason,
            }
        )
        return item

    def flag_takeoff(self, takeoff_id: str, flag: str, *, now: str) -> TakeoffMeasurement:
        item = self.measurement(takeoff_id)
        if item.approved:
            raise AgentSessionError("approved takeoff cannot be re-flagged by the agent surface")
        try:
            set_takeoff_flag(item, flag, now=now)
        except TakeoffError as exc:
            raise AgentSessionError(str(exc)) from exc
        self.updated_at = now
        self.decision_log.append(
            {
                "at": now,
                "action": "TAKEOFF_FLAGGED",
                "takeoff_id": takeoff_id,
                "flag": flag.strip().upper(),
            }
        )
        return item

    def add_evidence(self, evidence: TakeoffEvidenceRef, *, now: str) -> None:
        try:
            self.context.add_evidence(evidence)
        except TakeoffContextError as exc:
            raise AgentSessionError(str(exc)) from exc
        self.updated_at = now
        self.decision_log.append(
            {
                "at": now,
                "action": "TAKEOFF_EVIDENCE_ADDED",
                "evidence_id": evidence.id,
                "kind": evidence.kind,
            }
        )

    def link_evidence(self, relation: TakeoffRelation, *, now: str) -> None:
        try:
            self.context.add_relation(relation, takeoff_ids=self.takeoff_ids)
        except TakeoffContextError as exc:
            raise AgentSessionError(str(exc)) from exc
        self.updated_at = now
        self.decision_log.append(
            {
                "at": now,
                "action": "TAKEOFF_EVIDENCE_LINKED",
                "source_id": relation.source_id,
                "target_id": relation.target_id,
                "relation_type": relation.relation_type,
            }
        )

    def add_question(self, question: TakeoffQuestion, *, now: str) -> None:
        try:
            self.context.add_question(question, takeoff_ids=self.takeoff_ids)
        except TakeoffContextError as exc:
            raise AgentSessionError(str(exc)) from exc
        self.updated_at = now
        self.decision_log.append(
            {
                "at": now,
                "action": "TAKEOFF_QUESTION_ADDED",
                "question_id": question.id,
                "reason_code": question.reason_code,
            }
        )

    def preview_quantity(self, item: TakeoffMeasurement) -> float | None:
        if item.geometry.kind == COUNT:
            return quantity_for(item, metres_per_pixel=None)
        if not self.scale.resolved or self.scale.metres_per_point is None:
            return None
        return quantity_for(item, metres_per_pixel=self.scale.metres_per_point)

    def qa_summary(self) -> dict[str, Any]:
        base = takeoff_qa_summary(self.measurements)
        base["scale"] = self.scale.to_dict()
        base["unresolved"] = self.context.unresolved_summary()
        base["source_sha256"] = self.source_sha256
        return base

    def takeoff_summary(self, item: TakeoffMeasurement) -> dict[str, Any]:
        return {
            "id": item.id,
            "rule_id": item.rule_id,
            "display_name": item.rule.display_name,
            "page_label": item.page_label,
            "geometry_kind": item.geometry.kind,
            "geometry_pdf_points": [point.to_dict() for point in item.geometry.vertices],
            "geometry_render_px": self.render_points(item.geometry),
            "geometry_opentakeoff_px": self.opentakeoff_points(item.geometry),
            "count": item.geometry.count,
            "unit": item.unit,
            "preview_quantity": self.preview_quantity(item),
            "review_status": item.review_status,
            "summable": item.summable,
            "flags": sorted(item.flags),
            "label": item.label,
            "bid_item": item.bid_item,
            "notes": item.notes,
            "source_engine": item.provenance.source_engine,
            "source_method": item.provenance.source_method,
            "confidence": item.provenance.confidence,
            "human_corrected": item.provenance.human_corrected,
        }

    def bluebeam_plan(self) -> dict[str, Any]:
        scale_resolved = "Y" if self.scale.resolved else "N"
        scale_verified = "Y" if self.scale.verified else "N"
        rows: list[dict[str, Any]] = []
        for item in self.measurements:
            rule = item.rule
            subject_prefix = item.bid_item.strip() or "UNMAPPED"
            subject = f"{subject_prefix} | {item.id} | {rule.display_name}"
            comment_parts = [
                f"PLAN_ID={item.id}",
                f"SHEET={self.page_label}",
                f"SOURCE={self.source_identity.get('display_name', '')}",
                f"SOURCE_SHA256={self.source_sha256}",
                f"BIDITEM={item.bid_item or 'UNMAPPED'}",
                "STATUS=AI_PROPOSED",
                f"SCALE_RESOLVED={scale_resolved}",
                f"SCALE_VERIFIED={scale_verified}",
                "CREATED_BY=Screen2XYZ+AI",
            ]
            if item.notes.strip():
                comment_parts.append(f"NOTE={item.notes.strip()}")
            rows.append(
                {
                    "takeoff_id": item.id,
                    "rule_id": item.rule_id,
                    "subject": subject,
                    "label": item.label or item.rule_id,
                    "comment": ";".join(comment_parts),
                    "geometry_kind": item.geometry.kind,
                    "pdf_view_points_top_left": [
                        point.to_dict() for point in item.geometry.vertices
                    ],
                    "render_px_at_session_dpi": self.render_points(item.geometry),
                    "opentakeoff_px": self.opentakeoff_points(item.geometry),
                    "count": item.geometry.count,
                    "preview_quantity": self.preview_quantity(item),
                    "unit": item.unit,
                    "summable": item.summable,
                    "flags": sorted(item.flags),
                    "review_status": item.review_status,
                    "bluebeam_creation_policy": (
                        "REFERENCE_ONLY_DO_NOT_SUM"
                        if not item.summable
                        else "CREATE_NATIVE_MEASUREMENT_THEN_READ_BACK"
                    ),
                }
            )
        return {
            "schema": "screen2xyz-bluebeam-markup-plan/1.0",
            "session_id": self.session_id,
            "source": {
                "path": str(self.source_path),
                "display_name": self.source_identity.get("display_name", ""),
                "sha256": self.source_sha256,
                "page_index": self.page_index,
                "page_label": self.page_label,
                "rotation": self.rotation,
                "render_dpi": self.render_dpi,
            },
            "scale": self.scale.to_dict(),
            "policy": {
                "agent_may_propose": True,
                "agent_may_edit_unapproved": True,
                "agent_may_approve": False,
                "native_bluebeam_creation_requires_live_readback": True,
            },
            "takeoffs": rows,
            "qa": self.qa_summary(),
        }


def new_agent_session(
    pdf_path: Path,
    *,
    page_number: int,
    name: str,
    now: str,
    page_label: str | None = None,
    render_dpi: int = 150,
) -> AgentTakeoffSession:
    source = pdf_path.expanduser().resolve()
    info = inspect_pdf(source)
    if not 1 <= int(page_number) <= info.page_count:
        raise AgentSessionError(
            f"page_number must be between 1 and {info.page_count}"
        )
    page_index = int(page_number) - 1
    page = info.pages[page_index]
    manifest = info.to_manifest(include_local_path=True)
    width = page.rendered_width_points
    height = page.rendered_height_points
    session = AgentTakeoffSession(
        session_id=f"S2A-{secrets.token_hex(6).upper()}",
        name=name.strip() or source.stem,
        created_at=now,
        updated_at=now,
        source_identity=manifest,
        page_index=page_index,
        page_label=(page_label.strip() if page_label and page_label.strip() else str(page_number)),
        page_width_points=width,
        page_height_points=height,
        rotation=page.rotation,
        render_dpi=render_dpi,
    )
    session.decision_log.append(
        {
            "at": now,
            "action": "AGENT_SESSION_CREATED",
            "detail": "Single-sheet AI takeoff proposal session created.",
            "source_sha256": info.sha256,
            "page_index": page_index,
            "page_label": session.page_label,
            "coordinate_frame": CANONICAL_FRAME,
        }
    )
    return session


def save_agent_session(
    session: AgentTakeoffSession,
    path: Path,
    *,
    replace: bool = True,
) -> dict[str, str]:
    target = path.expanduser().resolve()
    if not target.name.endswith(AGENT_SESSION_SUFFIX):
        raise AgentSessionError(
            f"agent session file must end with {AGENT_SESSION_SUFFIX}"
        )
    try:
        session.context.validate_links(session.takeoff_ids)
        atomic_write_json(target, session.to_dict(), replace=replace)
        return {"path": str(target), "sha256": sha256_file(target)}
    except (OSError, ValueError, TakeoffError, TakeoffContextError) as exc:
        raise AgentSessionError("agent session save failed") from exc


def load_agent_session(path: Path, *, verify_source: bool = True) -> AgentTakeoffSession:
    target = path.expanduser().resolve()
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise AgentSessionError("agent session root must be a JSON object")
        session = AgentTakeoffSession.from_dict(value)
        if verify_source:
            session.verify_source_unchanged()
        return session
    except AgentSessionError:
        raise
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
        TakeoffError,
        TakeoffContextError,
    ) as exc:
        raise AgentSessionError("agent session load failed") from exc


def export_bluebeam_plan(
    session: AgentTakeoffSession,
    path: Path,
    *,
    replace: bool = True,
) -> dict[str, str]:
    target = path.expanduser().resolve()
    try:
        atomic_write_json(target, session.bluebeam_plan(), replace=replace)
        return {"path": str(target), "sha256": sha256_file(target)}
    except (OSError, ValueError) as exc:
        raise AgentSessionError("Bluebeam markup plan export failed") from exc
