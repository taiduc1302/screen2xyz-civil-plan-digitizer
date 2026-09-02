from __future__ import annotations

import unittest
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    TextStringObject,
)

from screen2xyz_civil.agent_session import new_agent_session, save_agent_session
from screen2xyz_civil.pdf_annotations import (
    PdfAnnotationInspectionError,
    inspect_page_annotations,
    inspect_registered_working_copy,
)
from screen2xyz_civil.working_copy import register_working_copy

from .helpers_civil import fresh_dir, make_vector_pdf


NOW = "2026-09-02T21:30:00+00:00"


def add_synthetic_line_annotation(source: Path, target: Path) -> None:
    reader = PdfReader(str(source))
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)
    annot = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Annot"),
            NameObject("/Subtype"): NameObject("/Line"),
            NameObject("/Rect"): ArrayObject(
                [FloatObject(100), FloatObject(100), FloatObject(300), FloatObject(120)]
            ),
            NameObject("/L"): ArrayObject(
                [FloatObject(100), FloatObject(110), FloatObject(300), FloatObject(110)]
            ),
            NameObject("/NM"): TextStringObject("S2XYZ-SYN-001"),
            NameObject("/Subj"): TextStringObject("33.01 | 300 dia culvert - North Driveway"),
            NameObject("/T"): TextStringObject("Synthetic Estimator"),
            NameObject("/Contents"): TextStringObject("Saved annotation evidence"),
            NameObject("/IT"): NameObject("/LineDimension"),
        }
    )
    writer.add_annotation(page_number=0, annotation=annot)
    with target.open("wb") as handle:
        writer.write(handle)


class PdfAnnotationInspectionTests(unittest.TestCase):
    def test_saved_line_annotation_subject_and_geometry_are_inspectable(self):
        root = fresh_dir()
        base = make_vector_pdf(root / "base.pdf", "SHEET 03 PLAN 1:250", with_shapes=True)
        working = root / "working.pdf"
        add_synthetic_line_annotation(base, working)
        result = inspect_page_annotations(working, 0)
        self.assertEqual(result["total"], 1)
        row = result["annotations"][0]
        self.assertEqual(row["subtype"], "/Line")
        self.assertEqual(row["intent"], "/LineDimension")
        self.assertEqual(row["name_id"], "S2XYZ-SYN-001")
        self.assertIn("300 dia culvert", row["subject"])
        self.assertEqual(row["line_pdf"], [100.0, 110.0, 300.0, 110.0])
        self.assertEqual(
            result["trust"], "SAVED_PDF_ANNOTATION_EVIDENCE_NOT_LIVE_REVU_STATE"
        )

    def test_registered_annotated_working_copy_can_be_inspected_and_previewed(self):
        root = fresh_dir()
        base = make_vector_pdf(root / "IssuedForTender_BASE.pdf", "SHEET 03 PLAN 1:250", with_shapes=True)
        working = root / "TAKEOFF_WORKING.pdf"
        add_synthetic_line_annotation(base, working)
        session = new_agent_session(
            base,
            page_number=1,
            page_label="03",
            name="Annotation fallback",
            now=NOW,
            render_dpi=96,
        )
        register_working_copy(session, working, now=NOW)
        session_path = root / "sheet03.s2a.json"
        save_agent_session(session, session_path)

        result = inspect_registered_working_copy(
            session_path,
            preview_dir=root / "preview",
        )
        self.assertTrue(result["working_copy"]["safe_for_bluebeam_operator"])
        self.assertEqual(result["annotations"][0]["name_id"], "S2XYZ-SYN-001")
        preview = Path(result["preview_png"])
        self.assertTrue(preview.is_file())
        self.assertGreater(preview.stat().st_size, 100)
        self.assertTrue(result["preview_includes_saved_annotations"])

    def test_unregistered_working_copy_fails_closed(self):
        root = fresh_dir()
        base = make_vector_pdf(root / "base.pdf", "SHEET 03", with_shapes=True)
        session = new_agent_session(
            base,
            page_number=1,
            page_label="03",
            name="No working copy",
            now=NOW,
        )
        session_path = root / "sheet03.s2a.json"
        save_agent_session(session, session_path)
        with self.assertRaisesRegex(PdfAnnotationInspectionError, "not safe"):
            inspect_registered_working_copy(session_path)


if __name__ == "__main__":
    unittest.main()
