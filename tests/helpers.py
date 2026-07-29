from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "test_data/synthetic/s2xyz_fixture_v0.1"
EVIDENCE = ROOT / "runs/evidence/S2XYZ-CODEX-003"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def csv_rows(path: Path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
