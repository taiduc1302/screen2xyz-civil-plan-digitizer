from __future__ import annotations

import unittest

from screen2xyz_civil.adapters.opentakeoff import (
    METRES_PER_FOOT,
    OpenTakeoffBridgeError,
    OpenTakeoffCoordinateFrame,
    build_bridge_plan,
    build_measure_call,
    screen2xyz_quantity_from_opentakeoff_reply,
)
from screen2xyz_civil.takeoff import (
    LINE,
    POLYGON,
    TakeoffGeometry,
    TakeoffVertex,
    new_takeoff_proposal,
)


NOW = "2026-09-02T10:40:00-07:00"


def line_item():
    return new_takeoff_proposal(
        takeoff_id="TK-LINE",
        rule_id="DRIVEWAY_CULVERT_300",
        page_index=2,
        page_label="03",
        geometry=TakeoffGeometry(
            LINE,
            (TakeoffVertex(10, 20), TakeoffVertex(30, 40)),
        ),
        now=NOW,
        source_engine="synthetic-test",
        source_method="VECTOR_PROPOSAL",
        generated_by="agent",
    )


def polygon_item():
    return new_takeoff_proposal(
        takeoff_id="TK-AREA",
        rule_id="DITCH_INFILL",
        page_index=2,
        page_label="03",
        geometry=TakeoffGeometry(
            POLYGON,
            (
                TakeoffVertex(10, 20),
                TakeoffVertex(30, 20),
                TakeoffVertex(30, 40),
                TakeoffVertex(10, 40),
            ),
        ),
        now=NOW,
        source_engine="synthetic-test",
        source_method="VECTOR_PROPOSAL",
        generated_by="agent",
    )


class OpenTakeoffBridgeTests(unittest.TestCase):
    def test_144_dpi_review_pixels_equal_engine_pixels(self):
        frame = OpenTakeoffCoordinateFrame(source_dpi=144)
        self.assertAlmostEqual(frame.engine_px_per_source_px, 1.0)
        self.assertEqual(frame.point(TakeoffVertex(12, 34)), [12.0, 34.0])

    def test_72_dpi_review_pixel_maps_to_two_engine_pixels(self):
        frame = OpenTakeoffCoordinateFrame(source_dpi=72)
        self.assertAlmostEqual(frame.engine_px_per_source_px, 2.0)
        self.assertEqual(frame.point(TakeoffVertex(12, 34)), [24.0, 68.0])

    def test_scale_translation_preserves_real_distance(self):
        frame = OpenTakeoffCoordinateFrame(source_dpi=144)
        feet_per_engine_px = frame.feet_per_engine_px(0.01)
        self.assertAlmostEqual(feet_per_engine_px, 0.01 / METRES_PER_FOOT)

    def test_polygon_request_uses_opentakeoff_verts_contract(self):
        call = build_measure_call(
            polygon_item(),
            sheet="plan.pdf#3",
            frame=OpenTakeoffCoordinateFrame(source_dpi=144),
        )
        self.assertEqual(call.tool, "measure_polygon")
        self.assertEqual(call.arguments["sheet"], "plan.pdf#3")
        self.assertEqual(len(call.arguments["verts"]), 4)
        self.assertNotIn("condition", call.arguments)

    def test_line_request_uses_opentakeoff_pts_contract(self):
        call = build_measure_call(
            line_item(),
            sheet="03",
            frame=OpenTakeoffCoordinateFrame(source_dpi=144),
        )
        self.assertEqual(call.tool, "measure_line")
        self.assertEqual(call.arguments["pts"][0], [10.0, 20.0])

    def test_bridge_plan_is_explicit_scale_then_measure(self):
        plan = build_bridge_plan(
            polygon_item(),
            sheet="plan.pdf#3",
            source_dpi=150,
            metres_per_source_px=0.01,
        )
        self.assertEqual([call.tool for call in plan.calls], ["set_scale", "measure_polygon"])
        self.assertNotIn("condition", plan.calls[1].arguments)

    def test_upstream_condition_commit_is_opt_in(self):
        plan = build_bridge_plan(
            polygon_item(),
            sheet="plan.pdf#3",
            source_dpi=150,
            metres_per_source_px=0.01,
            commit_as_condition=True,
        )
        self.assertEqual(plan.calls[1].arguments["condition"], "DITCH_INFILL")

    def test_reply_conversion_is_metric_and_fails_closed_on_missing_fields(self):
        line_m = screen2xyz_quantity_from_opentakeoff_reply(
            line_item(), {"length_lf": 10.0}
        )
        area_m2 = screen2xyz_quantity_from_opentakeoff_reply(
            polygon_item(), {"area_sf": 100.0}
        )
        self.assertAlmostEqual(line_m, 10.0 * METRES_PER_FOOT)
        self.assertAlmostEqual(area_m2, 100.0 * METRES_PER_FOOT**2)
        with self.assertRaises(OpenTakeoffBridgeError):
            screen2xyz_quantity_from_opentakeoff_reply(line_item(), {})


if __name__ == "__main__":
    unittest.main()
