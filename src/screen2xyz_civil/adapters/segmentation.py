"""Optional raster-segmentation boundary for civil takeoff proposals.

This module deliberately has no ML dependency.  SAM 2 (Apache-2.0) may be
implemented behind this protocol in a separate optional environment, but the
core application treats every segmentation result as unverified proposal
geometry and never as an approved quantity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..takeoff import (
    POLYGON,
    TakeoffGeometry,
    TakeoffMeasurement,
    TakeoffVertex,
    new_takeoff_proposal,
    takeoff_rule,
)


@dataclass(frozen=True)
class SegmentationRequest:
    page_index: int
    page_label: str
    rule_id: str
    image_reference: str
    positive_points: tuple[TakeoffVertex, ...] = ()
    negative_points: tuple[TakeoffVertex, ...] = ()

    def __post_init__(self) -> None:
        rule = takeoff_rule(self.rule_id)
        if rule.geometry_kind != POLYGON:
            raise ValueError("segmentation provider is only valid for polygon rules")
        if self.page_index < 0:
            raise ValueError("segmentation page index must be non-negative")
        if not self.image_reference.strip():
            raise ValueError("segmentation image reference is required")


@dataclass(frozen=True)
class SegmentationProposal:
    provider: str
    model_revision: str
    vertices: tuple[TakeoffVertex, ...]
    confidence: float | None = None
    external_id: str = ""

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("segmentation provider is required")
        # Reuse the takeoff polygon contract for vertex/area validation.
        TakeoffGeometry(POLYGON, self.vertices)
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("segmentation confidence must be between 0 and 1")


class SegmentationProvider(Protocol):
    """Interface satisfied by optional local segmentation implementations."""

    def propose(self, request: SegmentationRequest) -> SegmentationProposal:
        ...


def segmentation_to_takeoff(
    request: SegmentationRequest,
    proposal: SegmentationProposal,
    *,
    takeoff_id: str,
    now: str,
    bid_item: str = "",
    label: str = "",
) -> TakeoffMeasurement:
    """Normalize any provider result into the review-first takeoff domain."""

    item = new_takeoff_proposal(
        takeoff_id=takeoff_id,
        rule_id=request.rule_id,
        page_index=request.page_index,
        page_label=request.page_label,
        geometry=TakeoffGeometry(POLYGON, proposal.vertices),
        now=now,
        source_engine=proposal.provider,
        source_method="RASTER_SEGMENTATION",
        generated_by="agent",
        confidence=proposal.confidence,
        external_id=proposal.external_id,
        label=label,
        bid_item=bid_item,
        flags=("GEOMETRY_UNVERIFIED",),
        notes=(
            "Raster segmentation proposal. Verify against vector/CAD evidence or "
            "the rendered drawing before approval."
        ),
    )
    item.provenance.extra.update(
        {
            "model_revision": proposal.model_revision,
            "image_reference": request.image_reference,
            "positive_points": [point.to_dict() for point in request.positive_points],
            "negative_points": [point.to_dict() for point in request.negative_points],
        }
    )
    return item
