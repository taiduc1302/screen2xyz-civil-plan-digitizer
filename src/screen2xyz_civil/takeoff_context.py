"""Traceable evidence and withheld-question context for civil takeoffs.

The takeoff measurement remains the quantity record.  This module answers two
separate questions that should not be hidden inside a free-form note:

1. What drawing/spec/estimator evidence supports or contradicts the record?
2. What did the system deliberately withhold because it could not resolve it?

The structures are intentionally model- and vendor-neutral so OpenTakeoff,
local PDF parsing, an LLM, or a human can all contribute evidence without
becoming the project database.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable


class TakeoffContextError(ValueError):
    """Evidence/question context violates a review or traceability contract."""


EVIDENCE_KINDS = frozenset(
    {
        "LEGEND",
        "CALLOUT",
        "DIMENSION",
        "VECTOR",
        "TEXT",
        "DETAIL",
        "SPECIFICATION",
        "BID_ITEM",
        "HUMAN_REVIEW",
        "ENGINE_RESULT",
    }
)

DATA_CLASSES = frozenset(
    {
        "PROJECT_PRIVATE",
        "SYNTHETIC_OWNED",
        "OPEN_LICENSED",
        "HUMAN_RULE",
        "UNKNOWN",
    }
)

RELATION_TYPES = frozenset(
    {
        "SUPPORTS",
        "CONTRADICTS",
        "ASSOCIATED_WITH",
        "DERIVED_FROM",
        "CONTINUES_ON",
        "REPLACES",
    }
)

QUESTION_STATUSES = frozenset({"OPEN", "RESOLVED", "DISMISSED"})
QUESTION_SEVERITIES = frozenset({"INFO", "WARNING", "ERROR"})


@dataclass(frozen=True)
class EvidenceBox:
    """Optional pixel-exact locator in the source review image."""

    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self) -> None:
        values = (self.x0, self.y0, self.x1, self.y1)
        if not all(math.isfinite(value) for value in values):
            raise TakeoffContextError("evidence box coordinates must be finite")
        if min(values) < 0:
            raise TakeoffContextError("evidence box coordinates must be non-negative")
        if self.x1 < self.x0 or self.y1 < self.y0:
            raise TakeoffContextError("evidence box must be normalized")

    def to_dict(self) -> dict[str, float]:
        return {
            "x0": float(self.x0),
            "y0": float(self.y0),
            "x1": float(self.x1),
            "y1": float(self.y1),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "EvidenceBox":
        return cls(
            float(value["x0"]),
            float(value["y0"]),
            float(value["x1"]),
            float(value["y1"]),
        )


@dataclass(frozen=True)
class TakeoffEvidenceRef:
    id: str
    kind: str
    page_label: str
    source_method: str
    summary: str
    source_ref: str = ""
    source_sha256: str = ""
    locator: EvidenceBox | None = None
    confidence: float | None = None
    data_class: str = "PROJECT_PRIVATE"
    license_id: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.startswith("EV-"):
            raise TakeoffContextError("evidence id must start with EV-")
        if self.kind not in EVIDENCE_KINDS:
            raise TakeoffContextError(f"unsupported evidence kind: {self.kind}")
        if not self.source_method.strip():
            raise TakeoffContextError("evidence source_method is required")
        if not self.summary.strip():
            raise TakeoffContextError("evidence summary is required")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise TakeoffContextError("evidence confidence must be between 0 and 1")
        if self.data_class not in DATA_CLASSES:
            raise TakeoffContextError(f"unsupported evidence data class: {self.data_class}")
        if self.data_class == "OPEN_LICENSED" and not self.license_id.strip():
            raise TakeoffContextError("open-licensed evidence requires a license id")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "page_label": self.page_label,
            "source_method": self.source_method,
            "summary": self.summary,
            "source_ref": self.source_ref,
            "source_sha256": self.source_sha256,
            "locator": None if self.locator is None else self.locator.to_dict(),
            "confidence": self.confidence,
            "data_class": self.data_class,
            "license_id": self.license_id,
            "attributes": dict(self.attributes),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TakeoffEvidenceRef":
        locator = value.get("locator")
        return cls(
            id=str(value["id"]),
            kind=str(value["kind"]),
            page_label=str(value.get("page_label", "")),
            source_method=str(value["source_method"]),
            summary=str(value["summary"]),
            source_ref=str(value.get("source_ref", "")),
            source_sha256=str(value.get("source_sha256", "")),
            locator=None if locator is None else EvidenceBox.from_dict(locator),
            confidence=(
                None if value.get("confidence") is None else float(value["confidence"])
            ),
            data_class=str(value.get("data_class", "PROJECT_PRIVATE")),
            license_id=str(value.get("license_id", "")),
            attributes=dict(value.get("attributes", {})),
        )


@dataclass(frozen=True)
class TakeoffRelation:
    source_id: str
    target_id: str
    relation_type: str
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.target_id.strip():
            raise TakeoffContextError("relation endpoints are required")
        if self.source_id == self.target_id:
            raise TakeoffContextError("takeoff relation cannot self-reference")
        if self.relation_type not in RELATION_TYPES:
            raise TakeoffContextError(
                f"unsupported takeoff relation: {self.relation_type}"
            )

    def to_dict(self) -> dict[str, str]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TakeoffRelation":
        return cls(
            source_id=str(value["source_id"]),
            target_id=str(value["target_id"]),
            relation_type=str(value["relation_type"]),
            detail=str(value.get("detail", "")),
        )


@dataclass
class TakeoffQuestion:
    """A first-class disclosed uncertainty, not a silent missing takeoff."""

    id: str
    page_label: str
    reason_code: str
    detail: str
    next_action: str
    created_at: str
    severity: str = "WARNING"
    status: str = "OPEN"
    related_takeoff_ids: list[str] = field(default_factory=list)
    related_evidence_ids: list[str] = field(default_factory=list)
    locator: EvidenceBox | None = None
    resolved_at: str = ""
    resolution: str = ""

    def __post_init__(self) -> None:
        if not self.id.startswith("Q-"):
            raise TakeoffContextError("question id must start with Q-")
        if not self.reason_code.strip():
            raise TakeoffContextError("question reason_code is required")
        if not self.detail.strip():
            raise TakeoffContextError("question detail is required")
        if not self.next_action.strip():
            raise TakeoffContextError("question next_action is required")
        if self.severity not in QUESTION_SEVERITIES:
            raise TakeoffContextError("invalid question severity")
        if self.status not in QUESTION_STATUSES:
            raise TakeoffContextError("invalid question status")
        if self.status == "RESOLVED" and not self.resolution.strip():
            raise TakeoffContextError("resolved question requires a resolution")
        if self.status == "OPEN" and (self.resolved_at or self.resolution):
            raise TakeoffContextError("open question cannot carry a resolution")
        self.related_takeoff_ids = list(dict.fromkeys(self.related_takeoff_ids))
        self.related_evidence_ids = list(dict.fromkeys(self.related_evidence_ids))

    def resolve(self, *, now: str, resolution: str) -> None:
        if self.status != "OPEN":
            raise TakeoffContextError("only an open question can be resolved")
        if not resolution.strip():
            raise TakeoffContextError("question resolution is required")
        self.status = "RESOLVED"
        self.resolved_at = now
        self.resolution = resolution.strip()

    def dismiss(self, *, now: str, reason: str) -> None:
        if self.status != "OPEN":
            raise TakeoffContextError("only an open question can be dismissed")
        if not reason.strip():
            raise TakeoffContextError("dismissal reason is required")
        self.status = "DISMISSED"
        self.resolved_at = now
        self.resolution = reason.strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "page_label": self.page_label,
            "reason_code": self.reason_code,
            "detail": self.detail,
            "next_action": self.next_action,
            "created_at": self.created_at,
            "severity": self.severity,
            "status": self.status,
            "related_takeoff_ids": list(self.related_takeoff_ids),
            "related_evidence_ids": list(self.related_evidence_ids),
            "locator": None if self.locator is None else self.locator.to_dict(),
            "resolved_at": self.resolved_at,
            "resolution": self.resolution,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TakeoffQuestion":
        locator = value.get("locator")
        return cls(
            id=str(value["id"]),
            page_label=str(value.get("page_label", "")),
            reason_code=str(value["reason_code"]),
            detail=str(value["detail"]),
            next_action=str(value["next_action"]),
            created_at=str(value.get("created_at", "")),
            severity=str(value.get("severity", "WARNING")),
            status=str(value.get("status", "OPEN")),
            related_takeoff_ids=list(value.get("related_takeoff_ids", [])),
            related_evidence_ids=list(value.get("related_evidence_ids", [])),
            locator=None if locator is None else EvidenceBox.from_dict(locator),
            resolved_at=str(value.get("resolved_at", "")),
            resolution=str(value.get("resolution", "")),
        )


@dataclass
class TakeoffContext:
    evidence: list[TakeoffEvidenceRef] = field(default_factory=list)
    relations: list[TakeoffRelation] = field(default_factory=list)
    questions: list[TakeoffQuestion] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._validate_unique_ids()
        self.validate_links()

    def _validate_unique_ids(self) -> None:
        ids = [item.id for item in self.evidence] + [item.id for item in self.questions]
        if len(ids) != len(set(ids)):
            raise TakeoffContextError("duplicate evidence/question id")

    def known_ids(self, takeoff_ids: Iterable[str] = ()) -> set[str]:
        return (
            {item.id for item in self.evidence}
            | {item.id for item in self.questions}
            | set(takeoff_ids)
        )

    def validate_links(self, takeoff_ids: Iterable[str] = ()) -> None:
        known = self.known_ids(takeoff_ids)
        # During standalone construction relations to TK-* are allowed because
        # the owning workspace validates them with the actual takeoff ids.
        for relation in self.relations:
            for endpoint in (relation.source_id, relation.target_id):
                if endpoint.startswith("TK-"):
                    continue
                if endpoint not in known:
                    raise TakeoffContextError(
                        f"relation references unknown context id: {endpoint}"
                    )
        evidence_ids = {item.id for item in self.evidence}
        for question in self.questions:
            missing = set(question.related_evidence_ids) - evidence_ids
            if missing:
                raise TakeoffContextError(
                    f"question references unknown evidence: {sorted(missing)}"
                )
        if takeoff_ids:
            takeoff_set = set(takeoff_ids)
            for question in self.questions:
                missing = set(question.related_takeoff_ids) - takeoff_set
                if missing:
                    raise TakeoffContextError(
                        f"question references unknown takeoffs: {sorted(missing)}"
                    )
            for relation in self.relations:
                for endpoint in (relation.source_id, relation.target_id):
                    if endpoint.startswith("TK-") and endpoint not in takeoff_set:
                        raise TakeoffContextError(
                            f"relation references unknown takeoff: {endpoint}"
                        )

    def add_evidence(self, item: TakeoffEvidenceRef) -> None:
        if item.id in self.known_ids():
            raise TakeoffContextError(f"duplicate context id: {item.id}")
        self.evidence.append(item)

    def add_relation(self, relation: TakeoffRelation, *, takeoff_ids: Iterable[str] = ()) -> None:
        key = (relation.source_id, relation.target_id, relation.relation_type)
        if any(
            (item.source_id, item.target_id, item.relation_type) == key
            for item in self.relations
        ):
            raise TakeoffContextError("duplicate takeoff relation")
        self.relations.append(relation)
        self.validate_links(takeoff_ids)

    def add_question(self, item: TakeoffQuestion, *, takeoff_ids: Iterable[str] = ()) -> None:
        if item.id in self.known_ids(takeoff_ids):
            raise TakeoffContextError(f"duplicate context id: {item.id}")
        self.questions.append(item)
        self.validate_links(takeoff_ids)

    def question(self, question_id: str) -> TakeoffQuestion:
        for item in self.questions:
            if item.id == question_id:
                return item
        raise TakeoffContextError(f"unknown question: {question_id}")

    def evidence_for(self, entity_id: str) -> list[TakeoffEvidenceRef]:
        evidence_ids: set[str] = set()
        for relation in self.relations:
            if relation.relation_type not in {"SUPPORTS", "CONTRADICTS", "DERIVED_FROM"}:
                continue
            if relation.target_id == entity_id and relation.source_id.startswith("EV-"):
                evidence_ids.add(relation.source_id)
            if relation.source_id == entity_id and relation.target_id.startswith("EV-"):
                evidence_ids.add(relation.target_id)
        by_id = {item.id: item for item in self.evidence}
        return [by_id[item_id] for item_id in sorted(evidence_ids) if item_id in by_id]

    def unresolved_summary(self) -> dict[str, Any]:
        open_items = [item for item in self.questions if item.status == "OPEN"]
        return {
            "open_count": len(open_items),
            "error_count": sum(item.severity == "ERROR" for item in open_items),
            "warning_count": sum(item.severity == "WARNING" for item in open_items),
            "by_reason": {
                reason: sum(item.reason_code == reason for item in open_items)
                for reason in sorted({item.reason_code for item in open_items})
            },
            "question_ids": [item.id for item in open_items],
        }

    def training_evidence(self) -> list[dict[str, Any]]:
        """Return only evidence explicitly classed for reuse beyond a private project."""

        allowed = {"SYNTHETIC_OWNED", "OPEN_LICENSED", "HUMAN_RULE"}
        return [item.to_dict() for item in self.evidence if item.data_class in allowed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence": [item.to_dict() for item in self.evidence],
            "relations": [item.to_dict() for item in self.relations],
            "questions": [item.to_dict() for item in self.questions],
            "unresolved": self.unresolved_summary(),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TakeoffContext":
        return cls(
            evidence=[
                TakeoffEvidenceRef.from_dict(item) for item in value.get("evidence", [])
            ],
            relations=[
                TakeoffRelation.from_dict(item) for item in value.get("relations", [])
            ],
            questions=[
                TakeoffQuestion.from_dict(item) for item in value.get("questions", [])
            ],
        )
