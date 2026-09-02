from __future__ import annotations

import json
import unittest

from pypdf import PdfReader, PdfWriter

from screen2xyz_civil.agent_session import (
    export_bluebeam_plan,
    load_agent_session,
    new_agent_session,
    save_agent_session,
)
from screen2xyz_civil.io_utils import sha256_file
from screen2xyz_civil.working_copy import (
    WorkingCopyError,
    bind_working_copy_to_markup_plan,
    create_working_copy,
    register_working_copy,
    working_copy_status,
)

from .helpers_civil import fresh_dir, make_vector_pdf


NOW = "2026-09-02T20:00:00+00:00"


class WorkingCopyTests(unittest.TestCase):
    def make_session(self):
        root = fresh_dir()
        source = make_vector_pdf(
            root / "IssuedForTender_BASE.pdf",
            "SHEET 03 PLAN 1:250 DITCH INFILL",
            with_shapes=True,
        )
        session = new_agent_session(
            source,
            page_number=1,
            page_label="03",
            name="Working-copy pilot",
            now=NOW,
        )
        session_path = root / "sheet03.s2a.json"
        save_agent_session(session, session_path)
        return root, source, session_path, session

    def test_fresh_working_copy_is_separate_registered_and_source_hash_stays_authority(self):
        root, source, session_path, session = self.make_session()
        working = root / "KingRoad_S03_TAKEOFF_WORKING.pdf"
        identity = create_working_copy(session, working, now=NOW)
        save_agent_session(session, session_path, replace=True)
        self.assertNotEqual(source.resolve(), working.resolve())
        self.assertEqual(identity["initial_sha256"], sha256_file(source))
        self.assertEqual(identity["source_sha256"], session.source_sha256)
        restored = load_agent_session(session_path, verify_source=True)
        status = working_copy_status(restored)
        self.assertTrue(status["safe_for_bluebeam_operator"])
        self.assertFalse(status["modified_since_registration"])
        self.assertEqual(restored.source_sha256, sha256_file(source))

    def test_working_pdf_byte_changes_are_allowed_when_drawing_stream_is_unchanged(self):
        root, source, _session_path, session = self.make_session()
        working = root / "TAKEOFF_WORKING.pdf"
        create_working_copy(session, working, now=NOW)
        initial = sha256_file(working)

        reader = PdfReader(str(working))
        writer = PdfWriter()
        writer.append_pages_from_reader(reader)
        writer.add_metadata({"/Producer": "Synthetic Revu annotation-save analogue"})
        rewritten = root / "rewritten.pdf"
        with rewritten.open("wb") as handle:
            writer.write(handle)
        rewritten.replace(working)

        self.assertNotEqual(initial, sha256_file(working))
        self.assertEqual(session.source_sha256, sha256_file(source))
        status = working_copy_status(session)
        self.assertTrue(status["modified_since_registration"])
        self.assertTrue(status["drawing_match"])
        self.assertTrue(status["safe_for_bluebeam_operator"])

    def test_existing_rewritten_copy_can_be_registered_when_selected_drawing_matches(self):
        root, source, _session_path, session = self.make_session()
        working = root / "Existing_Bluebeam_Working.pdf"
        reader = PdfReader(str(source))
        writer = PdfWriter()
        writer.append_pages_from_reader(reader)
        writer.add_metadata({"/Subject": "Existing markup working copy analogue"})
        with working.open("wb") as handle:
            writer.write(handle)

        self.assertNotEqual(sha256_file(source), sha256_file(working))
        identity = register_working_copy(session, working, now=NOW)
        self.assertFalse(identity["created_from_source"])
        self.assertTrue(working_copy_status(session)["safe_for_bluebeam_operator"])

    def test_wrong_revision_or_drawing_is_rejected_even_if_pdf_is_valid(self):
        root, _source, _session_path, session = self.make_session()
        wrong = make_vector_pdf(
            root / "WrongRevision.pdf",
            "DIFFERENT SHEET CONTENT REV B",
            with_shapes=True,
        )
        with self.assertRaisesRegex(WorkingCopyError, "does not match"):
            register_working_copy(session, wrong, now=NOW)

    def test_immutable_source_itself_can_never_be_registered_as_working_pdf(self):
        _root, source, _session_path, session = self.make_session()
        with self.assertRaisesRegex(WorkingCopyError, "separate file"):
            register_working_copy(session, source, now=NOW)

    def test_markup_plan_embeds_immutable_source_and_revu_target_contract(self):
        root, source, _session_path, session = self.make_session()
        working = root / "TAKEOFF_WORKING.pdf"
        create_working_copy(session, working, now=NOW)
        plan = root / "sheet03.bluebeam-markup-plan.json"
        export_bluebeam_plan(session, plan)
        identity = bind_working_copy_to_markup_plan(session, plan)
        self.assertEqual(identity["sha256"], sha256_file(plan))
        payload = json.loads(plan.read_text(encoding="utf-8"))
        contract = payload["document_contract"]
        self.assertEqual(contract["immutable_source"]["path"], str(source.resolve()))
        self.assertEqual(
            contract["bluebeam_working_copy"]["path"], str(working.resolve())
        )
        self.assertTrue(contract["native_bluebeam_target_ready"])
        self.assertIn("NEVER_MUTATE_IMMUTABLE_SOURCE", contract["policy"])


if __name__ == "__main__":
    unittest.main()