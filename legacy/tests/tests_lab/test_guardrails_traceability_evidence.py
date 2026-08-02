from __future__ import annotations

import csv
import json
import os
import re
import unittest
import uuid
from pathlib import Path

from screen2xyz_lab.config import OUTPUT_CLASSIFICATION
from screen2xyz_lab.evidence import (
    MANDATORY_EVIDENCE_FILENAMES,
    atomic_write_bytes,
    ensure_no_absolute_personal_path,
    finalize_evidence,
    privacy_findings,
    validate_environment_record,
    verify_manifest,
    write_manifest,
)

from helpers import EVIDENCE, FIXTURE, ROOT, load_json

def source_text() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "src/screen2xyz_lab").rglob("*")
        if path.is_file() and path.suffix in {".py", ".ps1"}
    )


class GuardrailTraceabilityEvidenceTests(unittest.TestCase):
    def test_T_PRI_001_privacy_scan(self):
        texts = []
        for path in EVIDENCE.rglob("*"):
            if path.is_file() and path.suffix.lower() not in {".png"}:
                texts.append(path.read_text(encoding="utf-8", errors="strict"))
        self.assertEqual(ensure_no_absolute_personal_path(texts), [])
        combined = "\n".join(texts).lower()
        self.assertNotIn("authorization: bearer", combined)
        self.assertNotIn("ghp_", combined)
        self.assertEqual(privacy_findings("\n".join(texts)), [])
        self.assertIn("IDENTITY_ASSIGNMENT", privacy_findings('{"hostname":"private-workstation"}'))
        self.assertIn("IDENTITY_ASSIGNMENT", privacy_findings('{"username":"private-user"}'))
        self.assertIn("NETWORK_ADDRESS_PRIVATE", privacy_findings('{"version_note":"x","host_address":"10.0.0.1"}'))
        self.assertEqual(privacy_findings('{"mscorlib_assembly_version":"4.0.0.0"}'), [])

    def test_T_PRI_002_copy_on_write_and_manifest(self):
        root = ROOT / ".lab_work" / f"pri002-{os.getpid()}-{uuid.uuid4().hex}"
        root.mkdir(parents=True)
        evidence = root / "evidence"
        atomic_write_bytes(evidence / "a.txt", b"a")
        with self.assertRaises(Exception):
            atomic_write_bytes(evidence / "a.txt", b"changed")
        manifest = write_manifest(evidence, root)
        self.assertEqual(verify_manifest(manifest, root), [])

    def test_T_PRI_003_contamination_and_no_network(self):
        text = source_text().lower()
        for token in ("import socket", "import urllib", "import requests", "http://", "https://"):
            self.assertNotIn(token, text)
        config = load_json(FIXTURE / "fixture_config.json")
        self.assertFalse(any("url" in key.lower() or "host" in key.lower() for key in config))

    def test_T_SCOPE_001_no_service_presets(self):
        text = source_text().lower()
        self.assertNotIn("service_preset", text)
        self.assertNotIn("scrape", text)
        self.assertNotIn("http", json.dumps(load_json(FIXTURE / "fixture_config.json")).lower())

    def test_T_SCOPE_002_generated_images_only(self):
        text = source_text()
        self.assertIn("validate_image", text)
        self.assertNotIn("CopyFromScreen", text)
        self.assertNotIn("ScreenRegionImageSource", text)

    def test_T_SCOPE_003_local_ocr_no_cloud(self):
        text = source_text()
        self.assertIn("Windows.Media.Ocr", text)
        self.assertNotIn("WebRequest", text)
        self.assertNotIn("HttpClient", text)

    def test_T_SCOPE_004_deferred_interfaces(self):
        files = {path.name.lower() for path in (ROOT / "src/screen2xyz_lab").rglob("*") if path.is_file()}
        self.assertFalse(any("cursor" in name or "transform" in name or "capture" in name for name in files))

    def test_T_SCOPE_005_notices_and_claim_boundaries(self):
        required_notice_paths = (
            ROOT / "README.md",
            ROOT / "src/README.md",
            ROOT / "tests/README.md",
            ROOT / "test_data/synthetic/README.md",
            ROOT / "test_data/synthetic/s2xyz_fixture_v0.1/README.md",
            ROOT / "test_data/expected_outputs/README.md",
            ROOT / "examples/README.md",
            ROOT / "examples/synthetic_ocr_lab/README.md",
            ROOT / "docs/public/Screen2XYZ_Local_Run_Guide_v0.2.md",
            ROOT / "docs/public/Screen2XYZ_Kubla_Preparation_Note_v0.1.md",
            ROOT / "docs/control/OWNER_SUMMARY.md",
            ROOT / "prompts/drafts/NEXT_CODEX_TASK.md",
            ROOT / "runs/reports/Screen2XYZ_Run_S2XYZ-CODEX-003_Report_2026-07-15.md",
        )
        for path in required_notice_paths:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertTrue(path.is_file())
                self.assertIn(OUTPUT_CLASSIFICATION, path.read_text(encoding="utf-8"))
        sidecar = load_json(EVIDENCE / "points_source_xyz_metadata.json")
        self.assertEqual(sidecar["output_classification"], OUTPUT_CLASSIFICATION)

    def test_T_TRC_001_complete_traceability(self):
        requirements_text = (ROOT / "docs/requirements/Screen2XYZ_Product_Requirements_v0.1.md").read_text(encoding="utf-8")
        requirement_ids = set(re.findall(r"S2XYZ-REQ-[A-Z]+-[0-9]{3}", requirements_text))
        with (ROOT / "docs/requirements/Screen2XYZ_Requirements_Traceability_Matrix_v0.1.csv").open("r", encoding="utf-8", newline="") as handle:
            rtm = list(csv.DictReader(handle))
        with (ROOT / "docs/testing/Screen2XYZ_Test_Matrix_v0.1.csv").open("r", encoding="utf-8", newline="") as handle:
            tests = list(csv.DictReader(handle))
        self.assertEqual(len(requirement_ids), 40)
        self.assertEqual({row["requirement_id"] for row in rtm}, requirement_ids)
        self.assertEqual(len(tests), 42)
        test_ids = {row["test_id"] for row in tests}
        for row in rtm:
            self.assertTrue(set(row["test_ids"].split(";")) <= test_ids)
            self.assertTrue(row["acceptance_criterion_ids"])
            self.assertTrue(row["planned_evidence"])

    def test_T_EVD_001_required_artifact_set(self):
        pre_manifest = MANDATORY_EVIDENCE_FILENAMES - {"test_results.txt", "evidence_manifest_sha256.txt"}
        actual = {path.name for path in EVIDENCE.iterdir() if path.is_file()}
        self.assertTrue(pre_manifest <= actual)
        root = ROOT / ".lab_work" / f"evd001-{os.getpid()}-{uuid.uuid4().hex}"
        evidence = root / "evidence"
        evidence.mkdir(parents=True)
        for name in pre_manifest:
            atomic_write_bytes(evidence / name, f"synthetic validation placeholder:{name}\n".encode("utf-8"))
        staged = root / "staged-test-results.txt"
        atomic_write_bytes(staged, b"Command: synthetic validation\nExit code: 0\n")
        finalize_evidence(evidence, root, staged)
        self.assertEqual({path.name for path in evidence.iterdir()}, MANDATORY_EVIDENCE_FILENAMES)

    def test_T_EVD_002_manifest_hashes_and_order(self):
        root = ROOT / ".lab_work" / f"evd002-{os.getpid()}-{uuid.uuid4().hex}"
        evidence = root / "evidence"
        atomic_write_bytes(evidence / "b.txt", b"b")
        atomic_write_bytes(evidence / "a.txt", b"a")
        manifest = write_manifest(evidence, root)
        self.assertEqual(verify_manifest(manifest, root), [])
        self.assertNotIn("evidence_manifest_sha256.txt", manifest.read_text(encoding="utf-8"))

    def test_T_EVD_003_sanitized_runtime_evidence(self):
        environment = load_json(EVIDENCE / "environment.json")
        validate_environment_record(environment)
        self.assertEqual(environment["live_capture_status"], "Not executed")
        self.assertIn("python_version", environment)
        inventory = (EVIDENCE / "dependency_inventory.txt").read_text(encoding="utf-8")
        runner_source = (ROOT / "tests/run_all.py").read_text(encoding="utf-8")
        self.assertIn("Direct third-party project dependencies: none", inventory)
        self.assertIn("Exit code:", runner_source)
        self.assertIn("Command:", runner_source)
        self.assertIn(OUTPUT_CLASSIFICATION, inventory)
        self.assertEqual(privacy_findings(json.dumps(environment) + inventory), [])
