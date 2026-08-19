from __future__ import annotations

import unittest

from screen2xyz_app.backends import DefaultReader
from screen2xyz_app.capture import Reading
from screen2xyz_app.mapping import ChannelSource
from tests_app.harness import runner


class CursorPolicyDriftTests(unittest.TestCase):
    def test_production_cursor_policy_is_not_weaker_than_measured_policy(self) -> None:
        class CapturingBackend:
            def read_cursor(self, cursor, box_size, *, policy, snap_radius_px):
                del cursor, box_size, snap_radius_px
                self.policy = policy
                return Reading("49.78", 0.95)

        backend = CapturingBackend()
        source = ChannelSource(
            "screen_cursor_ocr",
            numeric_range=(30.0, 100.0),
            precision_min=2,
        )
        DefaultReader(
            backend,
            cursor_position_provider=lambda: (-500, 1000),
        )("z", source, {})
        production = backend.policy
        measured = runner.create_cursor_harness_policy(source)
        self.assertGreaterEqual(production.confidence_min, measured.confidence_min)
        self.assertGreaterEqual(production.consensus_min, measured.consensus_min)
        self.assertGreaterEqual(production.precision_min, measured.precision_min)
        self.assertEqual(production.psm_modes, measured.psm_modes)
        self.assertLessEqual(production.upscale, measured.upscale)

    def test_expected_decimal_count_round_trips_and_defaults_to_two(self) -> None:
        source = ChannelSource("screen_cursor_ocr")
        self.assertEqual(source.precision_min, 2)
        self.assertEqual(ChannelSource.from_json(source.to_json()), source)


if __name__ == "__main__":
    unittest.main()
