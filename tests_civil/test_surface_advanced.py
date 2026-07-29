from __future__ import annotations

import json
import unittest
import xml.etree.ElementTree as ET

from screen2xyz_civil import PRELIMINARY_WARNING
from screen2xyz_civil import contracts as C
from screen2xyz_civil.advanced_exports import (
    breaklines_geojson_bytes,
    dxf_bytes,
    geojson_bytes,
    landxml_bytes,
    nez_bytes,
    xyz_bytes,
)
from screen2xyz_civil.models import PixelPoint
from screen2xyz_civil.surface import (
    SurfaceError,
    build_project_surface,
    cut_fill_preview,
)

from .helpers_civil import add_approved, project_and_workflow


def square_points(flow, point_type: str, elevation_offset: float = 0.0):
    values = []
    for pixel, elevation in (
        (PixelPoint(50, 100), 10),
        (PixelPoint(100, 100), 11),
        (PixelPoint(100, 50), 12),
        (PixelPoint(50, 50), 11),
    ):
        values.append(
            add_approved(
                flow,
                pixel=pixel,
                elevation=elevation + elevation_offset,
                point_type=point_type,
            )
        )
    return values


class SurfaceAdvancedTests(unittest.TestCase):
    def test_square_triangulates_deterministically(self):
        project, flow = project_and_workflow()
        square_points(flow, C.EXISTING_GROUND)
        surface = build_project_surface(project, C.EXISTING_GROUND)
        self.assertEqual(len(surface.vertices), 4)
        self.assertEqual(len(surface.triangles), 2)
        self.assertEqual(
            [triangle.id for triangle in surface.triangles], ["T-0001", "T-0002"]
        )

    def test_existing_and_design_surfaces_remain_separate(self):
        project, flow = project_and_workflow()
        square_points(flow, C.EXISTING_GROUND)
        square_points(flow, C.DESIGN_GRADE, 1)
        existing = build_project_surface(project, C.EXISTING_GROUND)
        design = build_project_surface(project, C.DESIGN_GRADE)
        self.assertTrue(
            all(vertex.id.startswith("PT-000") for vertex in existing.vertices)
        )
        self.assertNotEqual(
            {vertex.id for vertex in existing.vertices},
            {vertex.id for vertex in design.vertices},
        )

    def test_reviewed_boundary_is_preserved(self):
        project, flow = project_and_workflow()
        square_points(flow, C.EXISTING_GROUND)
        boundary = [
            PixelPoint(50, 100),
            PixelPoint(100, 100),
            PixelPoint(100, 50),
            PixelPoint(50, 50),
        ]
        flow.set_boundary(boundary)
        surface = build_project_surface(project, C.EXISTING_GROUND)
        self.assertEqual(len(surface.boundary), 4)
        self.assertEqual(len(surface.triangles), 2)

    def test_exclusion_polygon_prevents_crossing(self):
        project, flow = project_and_workflow()
        square_points(flow, C.EXISTING_GROUND)
        flow.add_exclusion_polygon(
            [
                PixelPoint(70, 80),
                PixelPoint(80, 80),
                PixelPoint(80, 70),
                PixelPoint(70, 70),
            ]
        )
        surface = build_project_surface(project, C.EXISTING_GROUND)
        self.assertEqual(len(surface.exclusions), 1)
        self.assertEqual(len(surface.triangles), 0)

    def test_no_cross_line_filters_crossing_triangles(self):
        project, flow = project_and_workflow()
        square_points(flow, C.EXISTING_GROUND)
        flow.add_no_cross_line([PixelPoint(75, 110), PixelPoint(75, 40)])
        surface = build_project_surface(project, C.EXISTING_GROUND)
        self.assertLess(len(surface.triangles), 2)

    def test_long_and_steep_flags(self):
        project, flow = project_and_workflow()
        square_points(flow, C.EXISTING_GROUND)
        surface = build_project_surface(
            project,
            C.EXISTING_GROUND,
            long_edge_threshold_m=1,
            steep_slope_ratio=0.01,
        )
        self.assertTrue(
            all("LONG_TRIANGLE" in triangle.flags for triangle in surface.triangles)
        )
        self.assertTrue(
            any("STEEP_TRIANGLE" in triangle.flags for triangle in surface.triangles)
        )

    def test_triangle_disable_is_applied(self):
        project, flow = project_and_workflow()
        square_points(flow, C.EXISTING_GROUND)
        flow.disable_triangle("T-0001")
        surface = build_project_surface(project, C.EXISTING_GROUND)
        self.assertTrue(surface.triangles[0].disabled)

    def test_collinear_surface_rejected(self):
        project, flow = project_and_workflow()
        for x in (50, 60, 70):
            add_approved(
                flow,
                pixel=PixelPoint(x, 100),
                elevation=10,
                point_type=C.EXISTING_GROUND,
            )
        with self.assertRaises(SurfaceError):
            build_project_surface(project, C.EXISTING_GROUND)

    def test_cut_fill_is_point_sample_preview_not_volume(self):
        project, flow = project_and_workflow()
        square_points(flow, C.EXISTING_GROUND)
        square_points(flow, C.DESIGN_GRADE, 1)
        result = cut_fill_preview(
            build_project_surface(project, C.EXISTING_GROUND),
            build_project_surface(project, C.DESIGN_GRADE),
        )
        self.assertEqual(result["sample_count"], 4)
        self.assertAlmostEqual(result["mean_design_minus_existing_m"], 1.0)
        self.assertEqual(
            result["classification"], "PRELIMINARY_POINT_SAMPLES_NOT_VOLUME"
        )

    def test_xyz_nez_and_geojson_are_local(self):
        project, flow = project_and_workflow()
        point = add_approved(flow)
        self.assertTrue(xyz_bytes([point]).startswith(b"1001.000000 2001.000000"))
        self.assertTrue(nez_bytes([point]).startswith(b"2001.000000 1001.000000"))
        geojson = json.loads(geojson_bytes(project, [point]))
        self.assertEqual(
            geojson["coordinate_basis"], "LOCAL_EAST_NORTH_METRES_NOT_GEODETIC"
        )
        self.assertEqual(geojson["screen2xyz_warning"], PRELIMINARY_WARNING)

    def test_dxf_and_breakline_export(self):
        project, flow = project_and_workflow()
        point = add_approved(flow)
        flow.add_breakline([PixelPoint(50, 100), PixelPoint(100, 50)])
        dxf = dxf_bytes(project, [point]).decode("ascii")
        self.assertIn("S2XYZ_BREAKLINE", dxf)
        data = json.loads(breaklines_geojson_bytes(project))
        self.assertEqual(len(data["features"]), 1)
        self.assertFalse(data["features"][0]["properties"]["inferred"])

    def test_landxml_requires_acceptance_and_boundary(self):
        project, flow = project_and_workflow()
        square_points(flow, C.EXISTING_GROUND)
        surface = build_project_surface(project, C.EXISTING_GROUND)
        with self.assertRaises(ValueError):
            landxml_bytes(project, [surface])
        project.feature_flags["landxml"] = True
        with self.assertRaises(ValueError):
            landxml_bytes(project, [surface])

    def test_landxml_is_valid_and_preliminary(self):
        project, flow = project_and_workflow()
        square_points(flow, C.EXISTING_GROUND)
        flow.set_boundary(
            [
                PixelPoint(50, 100),
                PixelPoint(100, 100),
                PixelPoint(100, 50),
                PixelPoint(50, 50),
            ]
        )
        project.feature_flags["landxml"] = True
        payload = landxml_bytes(
            project, [build_project_surface(project, C.EXISTING_GROUND)]
        )
        root = ET.fromstring(payload)
        self.assertTrue(root.tag.endswith("LandXML"))
        self.assertIn(b"PRELIMINARY", payload)
