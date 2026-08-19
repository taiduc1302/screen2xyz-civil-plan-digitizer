from __future__ import annotations

import math
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from screen2xyz_app.backends import (
    CursorOcrCandidate,
    DefaultReader,
    OcrConfidenceError,
    OcrPolicy,
    ScreenOcrBackend,
)
from screen2xyz_app.capture import Reading
from screen2xyz_app.mapping import ChannelSource
from screen2xyz_civil.detection import Rect


def _token(text: str, confidence: float = 90.0):
    return SimpleNamespace(text=text, confidence=confidence)


def _candidate(value: float, x: float, y: float, variant: str):
    return CursorOcrCandidate(
        str(value), value, 0.90, Rect(x - 4, y - 4, x + 4, y + 4),
        0, variant, 7,
    )


class GeneralConsensusSafetyTests(unittest.TestCase):
    def _read(self, passes):
        backend = ScreenOcrBackend(executable=Path("tesseract"))
        backend._tesseract_passes = lambda _variants, _policy: iter(passes)
        return backend._ocr_tesseract(
            [("unused", Image.new("RGB", (20, 20), "white"))],
            OcrPolicy(
                consensus_min=7,
                precision_min=2,
                numeric_range=(30.0, 100.0),
                psm_modes=(7,),
            ),
            "hash",
            b"png",
        )

    def test_later_stronger_value_beats_subthreshold_early_noise(self):
        passes = [
            (f"wrong-{index}", 7, (_token("56.69"),))
            for index in range(6)
        ] + [
            (f"correct-{index}", 7, (_token("56.65"),))
            for index in range(9)
        ]
        self.assertEqual(float(self._read(passes).raw_text), 56.65)

    def test_two_independent_consensus_values_fail_closed(self):
        passes = [
            (f"wrong-{index}", 7, (_token("56.69"),))
            for index in range(7)
        ] + [
            (f"correct-{index}", 7, (_token("56.65"),))
            for index in range(9)
        ]
        with self.assertRaisesRegex(OcrConfidenceError, "competing consensus"):
            self._read(passes)


class CursorSpatialConsensusTests(unittest.TestCase):
    def _backend(self, candidates):
        return ScreenOcrBackend(
            executable=Path("tesseract"),
            capture_provider=lambda _zone: Image.new("RGB", (200, 100), "white"),
            cursor_candidate_provider=lambda _image, _policy: tuple(candidates),
            cache_enabled=False,
        )

    @staticmethod
    def _policy():
        return OcrPolicy(
            confidence_min=0.6,
            consensus_min=7,
            numeric_range=(30.0, 100.0),
            precision_min=2,
        )

    def test_variants_from_different_locations_cannot_manufacture_consensus(self):
        candidates = [
            _candidate(51.53, 15 + index * 25, 25 + (index % 2) * 40, f"v{index}")
            for index in range(7)
        ]
        with self.assertRaisesRegex(OcrConfidenceError, "no numeric candidate"):
            self._backend(candidates).read_cursor(
                (0, 0), (200, 100), policy=self._policy(), snap_radius_px=200,
            )

    def test_spatially_separate_consensus_labels_remain_selectable(self):
        candidates = [
            _candidate(51.53, 95, 50, f"a{index}") for index in range(7)
        ] + [
            _candidate(62.25, 135, 50, f"b{index}") for index in range(7)
        ]
        reading = self._backend(candidates).read_cursor(
            (0, 0), (200, 100), policy=self._policy(), snap_radius_px=100,
        )
        self.assertEqual(float(reading.raw_text), 51.53)

    def test_competing_values_at_one_location_fail_closed(self):
        candidates = [
            _candidate(51.53, 100, 50, f"a{index}") for index in range(7)
        ] + [
            _candidate(51.58, 100, 50, f"b{index}") for index in range(7)
        ]
        with self.assertRaisesRegex(OcrConfidenceError, "no numeric candidate"):
            self._backend(candidates).read_cursor(
                (0, 0), (200, 100), policy=self._policy(), snap_radius_px=100,
            )

    def test_dominant_consensus_beats_a_smaller_punctuation_hallucination(self):
        candidates = [
            _candidate(51.53, 100, 50, f"correct-{index}")
            for index in range(14)
        ] + [
            _candidate(51.58, 100, 50, f"noise-{index}")
            for index in range(7)
        ]
        reading = self._backend(candidates).read_cursor(
            (0, 0), (200, 100), policy=self._policy(), snap_radius_px=100,
        )
        self.assertEqual(float(reading.raw_text), 51.53)

    def test_captured_cursor_image_uses_the_same_spatial_consensus_path(self):
        candidates = [
            _candidate(51.53, 100, 50, f"v{index}") for index in range(7)
        ]
        reading = self._backend(candidates).read_cursor_image(
            Image.new("RGB", (200, 100), "white"),
            policy=self._policy(),
            snap_radius_px=100,
        )
        self.assertEqual(float(reading.raw_text), 51.53)

    def test_rotated_box_is_mapped_back_to_source_coordinates(self):
        width = height = 100
        angle = 15
        source_x, source_y = 80.0, 50.0
        radians = math.radians(angle)
        rotated_x = 50.0 + math.cos(radians) * (source_x - 50.0)
        rotated_y = 50.0 - math.sin(radians) * (source_x - 50.0)
        mapped = ScreenOcrBackend._source_bbox(
            Rect(rotated_x, rotated_y, rotated_x, rotated_y),
            angle,
            width,
            height,
        )
        self.assertAlmostEqual(mapped.center.x, source_x, places=6)
        self.assertAlmostEqual(mapped.center.y, source_y, places=6)


class FixedZonePolicyTests(unittest.TestCase):
    def test_fixed_zone_honors_declared_minimum_precision(self):
        class FakeScreen:
            policy = None

            def read_zone(self, _zone, *, policy):
                self.policy = policy
                return Reading("1.234", 0.99)

        screen = FakeScreen()
        reader = DefaultReader(screen=screen, cursor_position_provider=lambda: (0, 0))
        reader(
            "x",
            ChannelSource(
                "screen_zone_ocr", (0, 0, 20, 20), precision_min=3,
            ),
            {},
        )
        self.assertEqual(screen.policy.precision_min, 3)


if __name__ == "__main__":
    unittest.main()
