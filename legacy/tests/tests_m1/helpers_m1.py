from __future__ import annotations

import os
import uuid
from pathlib import Path

from screen2xyz_lab.models import OcrObservation

ROOT = Path(__file__).resolve().parents[1]
BASELINE_IMAGE = ROOT / "test_data/synthetic/s2xyz_fixture_v0.1/images/S001.png"
WORK = ROOT / ".lab_work"


def fresh_run_root() -> Path:
    root = WORK / f"m1-test-{os.getpid()}-{uuid.uuid4().hex}"
    root.mkdir(parents=True)
    return root


def fake_ocr(text: str) -> OcrObservation:
    return OcrObservation("SUCCESS", text, 1, "")


def failed_ocr() -> OcrObservation:
    return OcrObservation("FAILURE", "", 1, "OCR_FAILURE")
