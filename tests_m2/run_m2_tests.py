"""Deterministic M2 test runner (no display, no worker, no network).

Frozen expected count: update EXPECTED_TEST_COUNT intentionally in the same
commit that adds or removes tests. Integration tests live in
`run_m2_integration.py` and are counted separately.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_TEST_COUNT = 498  # frozen 2026-07-21; update intentionally with tests


def main() -> int:
    suite = unittest.defaultTestLoader.discover(
        str(ROOT / "tests_m2"), pattern="test_*.py",
        top_level_dir=str(ROOT))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    count_ok = (EXPECTED_TEST_COUNT == 0
                or result.testsRun == EXPECTED_TEST_COUNT)
    ok = result.wasSuccessful() and count_ok and not result.skipped
    for test, reason in result.skipped:
        print(f"SKIPPED {test.id()}: {reason}")
    print(f"M2 tests executed: {result.testsRun}"
          f" (expected {EXPECTED_TEST_COUNT or 'unfrozen'});"
          f" failures: {len(result.failures)};"
          f" errors: {len(result.errors)};"
          f" skipped: {len(result.skipped)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
