from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from screen2xyz_app.backends import DefaultReader, ScreenOcrBackend
from screen2xyz_app.mapping import ChannelSource
from screen2xyz_civil.ocr import TesseractOcrAdapter
from screen2xyz_m2.parsing import parse_number
from tests_app.harness.agtek_renderers import render_agtek_cursor_fixtures


@unittest.skipUnless(TesseractOcrAdapter.find_executable(), "Tesseract unavailable")
class AgtekRealCursorOcrTests(unittest.TestCase):
    def test_real_default_reader_has_zero_wrong_accepted_values(self) -> None:
        correct = wrong = rejected = 0
        captured_zones = []
        outcomes = []
        with tempfile.TemporaryDirectory() as temporary:
            fixtures = render_agtek_cursor_fixtures(Path(temporary))
            for fixture in fixtures:
                with Image.open(fixture.path) as opened:
                    image = opened.convert("RGB")

                def capture(zone, current=image):
                    captured_zones.append(zone)
                    return current

                reader = DefaultReader(
                    ScreenOcrBackend(
                        capture_provider=capture,
                        cache_enabled=False,
                    ),
                    cursor_position_provider=lambda: (-500, 1000),
                )
                source = ChannelSource(
                    "screen_cursor_ocr",
                    numeric_range=(30.0, 100.0),
                )
                try:
                    reading = reader("z", source, {})
                    outcome = parse_number(
                        reading.raw_text,
                        separator_mode="point",
                        numeric_range=source.numeric_range,
                    )
                    if outcome.parse_status != "OK":
                        rejected += 1
                        outcomes.append((fixture.fixture_id, "rejected-parse"))
                        continue
                    actual = float(outcome.normalized_value)
                    if abs(actual - fixture.value) < 0.0001:
                        correct += 1
                        outcomes.append((fixture.fixture_id, "correct"))
                    else:
                        wrong += 1
                        outcomes.append((fixture.fixture_id, f"wrong:{actual}"))
                except (ValueError, RuntimeError):
                    rejected += 1
                    outcomes.append((fixture.fixture_id, "rejected-ocr"))
        self.assertEqual(set(captured_zones), {(-580, 970, 160, 60)})
        detail = f"correct={correct} wrong={wrong} rejected={rejected} outcomes={outcomes}"
        self.assertEqual(wrong, 0, detail)
        self.assertEqual(correct, 12, detail)
        self.assertEqual(rejected, 0, detail)


if __name__ == "__main__":
    unittest.main()
