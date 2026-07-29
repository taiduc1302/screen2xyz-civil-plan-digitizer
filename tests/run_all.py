from __future__ import annotations

import argparse
import io
import re
import sys
import unittest
from pathlib import Path

from screen2xyz_lab.config import OUTPUT_CLASSIFICATION, TASK_ID
from screen2xyz_lab.evidence import atomic_write_bytes


ROOT = Path(__file__).resolve().parents[1]
EXACT_COMMAND = ".\\.venv\\Scripts\\python.exe tests\\run_all.py --output .lab_work\\S2XYZ-CODEX-003-test-results.txt"

# The retained S2XYZ-CODEX-003 evidence recorded 41 tests. The 2026-07-17
# audit added T-PRI-004 (repository sanitization scan), so current suites
# must contain exactly 42 mapped tests.
EXPECTED_TEST_COUNT = 42


def test_id(test: unittest.TestCase) -> str:
    method = test.id().rsplit(".", 1)[-1]
    match = re.match(r"test_(T_[A-Z]+_[0-9]{3})", method)
    return match.group(1).replace("_", "-") if match else method


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.statuses: dict[str, str] = {}

    def addSuccess(self, test):
        self.statuses[test_id(test)] = "PASS"
        super().addSuccess(test)

    def addFailure(self, test, err):
        self.statuses[test_id(test)] = "FAIL"
        super().addFailure(test, err)

    def addError(self, test, err):
        self.statuses[test_id(test)] = "ERROR"
        super().addError(test, err)

    def addSkip(self, test, reason):
        self.statuses[test_id(test)] = "SKIP"
        super().addSkip(test, reason)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="fresh repository-relative staged test-results path")
    args = parser.parse_args(argv)

    output_path = (ROOT / args.output).resolve() if args.output else None
    if output_path is not None:
        work_root = (ROOT / ".lab_work").resolve()
        if not output_path.is_relative_to(work_root):
            raise SystemExit("test output must be a fresh path under .lab_work")

    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=RecordingResult)
    result: RecordingResult = runner.run(suite)
    exit_code = 0 if result.wasSuccessful() and result.testsRun == EXPECTED_TEST_COUNT and not result.skipped else 1
    ordered_statuses = sorted(result.statuses.items())
    content = "\n".join(
        (
            "Screen2XYZ automated test results",
            f"Task: {TASK_ID}",
            f"Command: {EXACT_COMMAND}",
            f"Tests executed: {result.testsRun}",
            f"Passed: {sum(status == 'PASS' for _, status in ordered_statuses)}",
            f"Failures: {len(result.failures)}",
            f"Errors: {len(result.errors)}",
            f"Skipped: {len(result.skipped)}",
            f"Exit code: {exit_code}",
            "Live capture: Not executed",
            "Test IDs:",
            *(f"{identifier}: {status}" for identifier, status in ordered_statuses),
            "Transcript:",
            stream.getvalue().rstrip(),
            OUTPUT_CLASSIFICATION,
            "",
        )
    )
    print(content)

    if output_path is not None:
        atomic_write_bytes(output_path, content.encode("utf-8"))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
