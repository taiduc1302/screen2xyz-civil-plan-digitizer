"""Deterministic M1 test runner (mirrors tests/run_all.py conventions)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The M1 stable suite is frozen at this count; update it intentionally in
# the same change that adds or removes a test.
EXPECTED_TEST_COUNT = 34


def main() -> int:
    suite = unittest.defaultTestLoader.discover(
        str(ROOT / "tests_m1"), pattern="test_*.py", top_level_dir=str(ROOT)
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    ok = (
        result.wasSuccessful()
        and result.testsRun == EXPECTED_TEST_COUNT
        and not result.skipped
    )
    print(
        f"M1 tests executed: {result.testsRun} (expected {EXPECTED_TEST_COUNT}); "
        f"failures: {len(result.failures)}; errors: {len(result.errors)}; "
        f"skipped: {len(result.skipped)}"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
