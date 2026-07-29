from __future__ import annotations

import unittest

from .benchmark_civil import DATASET_ID, run_benchmark


class BenchmarkTests(unittest.TestCase):
    def test_synthetic_benchmark_is_exact_and_repeatable(self) -> None:
        result = run_benchmark(iterations=2)
        self.assertEqual(result["dataset_id"], DATASET_ID)
        self.assertEqual(result["classification"]["exact_type_accuracy"], 1.0)
        self.assertEqual(result["association"]["accuracy"], 1.0)
        self.assertEqual(result["numeric"]["max_absolute_error"], 0.0)
        self.assertLess(result["transform"]["max_round_trip_error_px"], 1e-9)
        self.assertTrue(result["repeatability"]["identical"])
        self.assertIn("real-drawing OCR accuracy", result["not_measured"])
        repeated = run_benchmark(iterations=2)
        self.assertEqual(
            result["deterministic_sha256"],
            repeated["deterministic_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
