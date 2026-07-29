from __future__ import annotations

import unittest

from screen2xyz_civil import contracts as C
from screen2xyz_civil.models import CivilModelError, CropRegion, PixelPoint
from screen2xyz_civil.qa import duplicate_pairs, qa_summary
from screen2xyz_civil.source import inspect_png, validate_crop

from .helpers_civil import add_approved, fresh_dir, make_png, project_and_workflow


class SourceQaTests(unittest.TestCase):
    def test_png_source_identity_and_dimensions(self):
        path = make_png(fresh_dir() / "plan.png", 64, 32)
        source = inspect_png(path)
        self.assertEqual((source.width_px, source.height_px), (64, 32))
        self.assertEqual(len(source.sha256), 64)

    def test_non_png_rejected(self):
        path = fresh_dir() / "plan.png"
        path.write_bytes(b"not png")
        with self.assertRaises(CivilModelError):
            inspect_png(path)

    def test_crop_boundary(self):
        path = make_png(fresh_dir() / "plan.png", 64, 32)
        source = inspect_png(path)
        validate_crop(CropRegion(0, 0, 64, 32), source)
        with self.assertRaises(CivilModelError):
            validate_crop(CropRegion(60, 20, 10, 20), source)

    def test_duplicate_and_conflict_detection(self):
        project, flow = project_and_workflow()
        add_approved(flow, pixel=PixelPoint(60, 90), elevation=49)
        add_approved(flow, pixel=PixelPoint(60.1, 90.1), elevation=49.5)
        pairs = duplicate_pairs(project)
        self.assertEqual(len(pairs), 1)
        self.assertTrue(pairs[0]["conflicting"])

    def test_qa_counts_review_and_approved_separately(self):
        project, flow = project_and_workflow()
        add_approved(flow)
        flow.add_manual_point(
            pixel=PixelPoint(80, 80),
            elevation=50,
            point_type=C.DESIGN_GRADE,
        )
        summary = qa_summary(project)
        self.assertEqual(summary["existing_approved"], 1)
        self.assertEqual(summary["design_approved"], 0)
        self.assertEqual(summary["review_required"], 1)

    def test_qa_coordinate_extents(self):
        project, flow = project_and_workflow()
        first = add_approved(flow, pixel=PixelPoint(50, 100), elevation=49)
        second = add_approved(flow, pixel=PixelPoint(100, 50), elevation=51)
        extents = qa_summary(project)["coordinate_extents"]
        self.assertEqual(extents["min_east"], first.local_east)
        self.assertEqual(extents["max_north"], second.local_north)
