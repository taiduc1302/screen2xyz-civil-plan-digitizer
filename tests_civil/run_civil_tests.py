"""Frozen-count runner for the Civil Plan Digitizer deterministic suite."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

EXPECTED_TEST_COUNT = 198


def main() -> int:
    suite = unittest.defaultTestLoader.discover(
        str(ROOT / "tests_civil"), pattern="test_*.py", top_level_dir=str(ROOT)
    )
    count = suite.countTestCases()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(
        f"Civil tests executed: {count} (expected {EXPECTED_TEST_COUNT}); "
        f"failures: {len(result.failures)}; errors: {len(result.errors)}; "
        f"skipped: {len(result.skipped)}"
    )
    return 0 if result.wasSuccessful() and count == EXPECTED_TEST_COUNT else 1


if __name__ == "__main__":
    raise SystemExit(main())
