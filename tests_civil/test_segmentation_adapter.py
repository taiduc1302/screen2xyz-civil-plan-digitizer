from __future__ import annotations

import unittest

from screen2xyz_civil.adapters.segmentation import (
    SegmentationProposal,
    SegmentationRequest,
    segmentation_to_takeoff,
)
from screen2xyz_civil.takeoff import TakeoffVertex


NOW = "2026-09-02T11:00:00-07:00"


def request(rule_id: str = "DITCH_INFILL") -> SegmentationRequest:
    return SegmentationRequest(
        page_index=2,
        page_label="03",
        rule_id=rule_id,
        image_reference="synthetic://sheet-03",
        positive_points=(TakeoffVertex(10, 10),),
    )


def proposal() -> SegmentationProposal:
    return SegmentationProposal(
        provider="sam2-local",
        model_revision="synthetic-test",
        vertices=(
            TakeoffVertex(0, 0),
            TakeoffVertex(10, 0),
            TakeoffVertex(10, 10),
            TakeoffVertex(0, 10),
        ),
        confidence=0.91,
    )


class SegmentationAdapterTests(unittest.TestCase):
    def test_segmentation_only_accepts_polygon_takeoff_rules(self):
        with self.assertRaises(ValueError):
            request("DRIVEWAY_CULVERT_300")

    def test_invalid_segmentation_polygon_fails_closed(self):
        with self.assertRaises(ValueError):
            SegmentationProposal(
                provider="sam2-local",
                model_revision="test",
                vertices=(TakeoffVertex(0, 0), TakeoffVertex(1, 1)),
            )

    def test_segmentation_normalizes_to_unverified_takeoff_proposal(self):
        item = segmentation_to_takeoff(
            request(),
            proposal(),
            takeoff_id="TK-SEG",
            now=NOW,
        )
        self.assertEqual(item.provenance.source_method, "RASTER_SEGMENTATION")
        self.assertIn("GEOMETRY_UNVERIFIED", item.blocker_flags)
        self.assertFalse(item.approved)

    def test_segmentation_provenance_keeps_model_and_prompt_points(self):
        item = segmentation_to_takeoff(
            request(),
            proposal(),
            takeoff_id="TK-SEG",
            now=NOW,
        )
        self.assertEqual(item.provenance.extra["model_revision"], "synthetic-test")
        self.assertEqual(item.provenance.extra["positive_points"], [{"x": 10.0, "y": 10.0}])


if __name__ == "__main__":
    unittest.main()
