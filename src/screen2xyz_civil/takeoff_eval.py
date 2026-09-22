"""Small, dependency-free evaluation contracts for civil takeoff proposals.

The module deliberately separates *pipeline/synthetic* results from *real-plan*
accuracy.  It also rewards disclosed uncertainty: an expected item that is
explicitly withheld for review is accounted for differently from a silent miss.

These metrics are coarse by design.  `bbox_iou` is a localization diagnostic,
not polygon IoU; final quantity error is measured separately in real units.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable

from .takeoff import TakeoffGeometry


class TakeoffEvalError(ValueError):
    """Evaluation data is incomplete, contradictory, or misrepresented."""


SYNTHETIC_BOARD = "SYNTHETIC"
REAL_BOARD = "REAL"
EVAL_BOARDS = frozenset({SYNTHETIC_BOARD, REAL_BOARD})


@dataclass(frozen=True)
class EvalBox:
    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self) -> None:
        values = (self.x0, self.y0, self.x1, self.y1)
        if not all(math.isfinite(value) for value in values):
            raise TakeoffEvalError("evaluation box coordinates must be finite")
        if self.x1 < self.x0 or self.y1 < self.y0:
            raise TakeoffEvalError("evaluation box must be normalized")

    @property
    def area(self) -> float:
        return max(0.0, self.x1 - self.x0) * max(0.0, self.y1 - self.y0)


def geometry_box(geometry: TakeoffGeometry) -> EvalBox | None:
    if not geometry.vertices:
        return None
    xs = [point.x for point in geometry.vertices]
    ys = [point.y for point in geometry.vertices]
    return EvalBox(min(xs), min(ys), max(xs), max(ys))


def bbox_iou(left: EvalBox, right: EvalBox) -> float:
    x0 = max(left.x0, right.x0)
    y0 = max(left.y0, right.y0)
    x1 = min(left.x1, right.x1)
    y1 = min(left.y1, right.y1)
    intersection = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    union = left.area + right.area - intersection
    if union <= 0:
        return 1.0 if left == right else 0.0
    return intersection / union


@dataclass(frozen=True)
class MatchedTakeoff:
    expected_id: str
    expected_rule_id: str
    actual_rule_id: str
    expected_quantity: float
    actual_quantity: float
    unit: str
    expected_box: EvalBox | None = None
    actual_box: EvalBox | None = None

    def __post_init__(self) -> None:
        if not self.expected_id.strip():
            raise TakeoffEvalError("expected takeoff id is required")
        if self.unit not in {"m", "m2", "ea"}:
            raise TakeoffEvalError("unsupported evaluation unit")
        for value in (self.expected_quantity, self.actual_quantity):
            if not math.isfinite(value) or value < 0:
                raise TakeoffEvalError("evaluation quantities must be finite and non-negative")

    @property
    def rule_correct(self) -> bool:
        return self.expected_rule_id == self.actual_rule_id

    @property
    def absolute_error(self) -> float:
        return abs(self.actual_quantity - self.expected_quantity)

    @property
    def relative_error(self) -> float | None:
        if self.expected_quantity == 0:
            return None
        return self.absolute_error / self.expected_quantity

    @property
    def localization_iou(self) -> float | None:
        if self.expected_box is None or self.actual_box is None:
            return None
        return bbox_iou(self.expected_box, self.actual_box)


@dataclass(frozen=True)
class CoverageAccounting:
    expected_ids: frozenset[str]
    proposed_ids: frozenset[str]
    withheld_ids: frozenset[str]

    def __post_init__(self) -> None:
        if self.proposed_ids - self.expected_ids:
            raise TakeoffEvalError("proposed ids contain items outside the evaluation gold set")
        if self.withheld_ids - self.expected_ids:
            raise TakeoffEvalError("withheld ids contain items outside the evaluation gold set")
        overlap = self.proposed_ids & self.withheld_ids
        if overlap:
            raise TakeoffEvalError(
                f"an expected item cannot be both proposed and withheld: {sorted(overlap)}"
            )

    @property
    def silent_miss_ids(self) -> frozenset[str]:
        return self.expected_ids - self.proposed_ids - self.withheld_ids

    @property
    def accounted_ids(self) -> frozenset[str]:
        return self.proposed_ids | self.withheld_ids

    @property
    def accounted_rate(self) -> float:
        if not self.expected_ids:
            return 1.0
        return len(self.accounted_ids) / len(self.expected_ids)

    @property
    def proposal_rate(self) -> float:
        if not self.expected_ids:
            return 1.0
        return len(self.proposed_ids) / len(self.expected_ids)

    @property
    def silent_miss_rate(self) -> float:
        if not self.expected_ids:
            return 0.0
        return len(self.silent_miss_ids) / len(self.expected_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_count": len(self.expected_ids),
            "proposed_count": len(self.proposed_ids),
            "withheld_count": len(self.withheld_ids),
            "silent_miss_count": len(self.silent_miss_ids),
            "accounted_rate": self.accounted_rate,
            "proposal_rate": self.proposal_rate,
            "silent_miss_rate": self.silent_miss_rate,
            "silent_miss_ids": sorted(self.silent_miss_ids),
        }


@dataclass(frozen=True)
class TakeoffEvaluationResult:
    board: str
    dataset_id: str
    matched_count: int
    metrics: dict[str, Any]
    coverage: CoverageAccounting
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.board not in EVAL_BOARDS:
            raise TakeoffEvalError("evaluation board must be SYNTHETIC or REAL")
        if not self.dataset_id.strip():
            raise TakeoffEvalError("evaluation dataset id is required")
        if self.matched_count < 0:
            raise TakeoffEvalError("matched count cannot be negative")

    @property
    def is_real_accuracy_evidence(self) -> bool:
        return self.board == REAL_BOARD

    def assert_accuracy_claim_allowed(self) -> None:
        if not self.is_real_accuracy_evidence:
            raise TakeoffEvalError(
                "synthetic/pipeline evaluation cannot be reported as real-plan accuracy"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "board": self.board,
            "dataset_id": self.dataset_id,
            "matched_count": self.matched_count,
            "metrics": dict(self.metrics),
            "coverage": self.coverage.to_dict(),
            "notes": list(self.notes),
            "is_real_accuracy_evidence": self.is_real_accuracy_evidence,
        }


def _mean(values: Iterable[float]) -> float | None:
    data = list(values)
    if not data:
        return None
    return sum(data) / len(data)


def evaluate_matched_takeoffs(
    matches: Iterable[MatchedTakeoff],
    *,
    board: str,
    dataset_id: str,
    coverage: CoverageAccounting,
    notes: Iterable[str] = (),
) -> TakeoffEvaluationResult:
    records = list(matches)
    relative_errors = [
        error
        for record in records
        if (error := record.relative_error) is not None
    ]
    localization = [
        score
        for record in records
        if (score := record.localization_iou) is not None
    ]
    metrics = {
        "rule_accuracy": (
            1.0
            if not records
            else sum(record.rule_correct for record in records) / len(records)
        ),
        "mean_absolute_quantity_error": _mean(
            record.absolute_error for record in records
        ),
        "mean_absolute_percentage_error": _mean(relative_errors),
        "quantity_within_2pct_rate": (
            None
            if not relative_errors
            else sum(error <= 0.02 for error in relative_errors) / len(relative_errors)
        ),
        "quantity_within_5pct_rate": (
            None
            if not relative_errors
            else sum(error <= 0.05 for error in relative_errors) / len(relative_errors)
        ),
        "mean_bbox_iou": _mean(localization),
        "bbox_iou_note": "Coarse localization metric; not polygon IoU.",
    }
    return TakeoffEvaluationResult(
        board=board,
        dataset_id=dataset_id,
        matched_count=len(records),
        metrics=metrics,
        coverage=coverage,
        notes=tuple(notes),
    )


def coverage_accounting(
    *,
    expected_ids: Iterable[str],
    proposed_ids: Iterable[str],
    withheld_ids: Iterable[str] = (),
) -> CoverageAccounting:
    return CoverageAccounting(
        expected_ids=frozenset(expected_ids),
        proposed_ids=frozenset(proposed_ids),
        withheld_ids=frozenset(withheld_ids),
    )
