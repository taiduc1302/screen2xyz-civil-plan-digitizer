from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from screen2xyz_app.backends import DefaultReader, ScreenOcrBackend, cursor_ocr_policy
from screen2xyz_app.mapping import ChannelSource
from screen2xyz_civil.ocr import TesseractOcrAdapter
from screen2xyz_m2.parsing import parse_number
from tests_app.harness.agtek_renderers import (
    render_agtek_cursor_fixtures,
    render_agtek_screen_fixture,
)
from tests_app.harness.renderers import render_plan


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
                    self.assertNotIn("x", reading.raw_text.lower())
                    self.assertNotIn("*", reading.raw_text)
                    self.assertGreaterEqual(reading.confidence or 0.0, 0.60)
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

    def test_grey_background_accuracy_is_reported_by_contrast(self) -> None:
        results = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for foreground in (72, 100, 124):
                fixtures = render_agtek_cursor_fixtures(
                    root / f"contrast-{168 - foreground}",
                    background=(168, 168, 168),
                    foreground=(foreground, foreground, foreground),
                    values=(51.53,),
                )
                with Image.open(fixtures[0].path) as opened:
                    image = opened.convert("RGB")
                reader = DefaultReader(
                    ScreenOcrBackend(
                        capture_provider=lambda _zone, current=image: current,
                        cache_enabled=False,
                    ),
                    cursor_position_provider=lambda: (-500, 1000),
                )
                try:
                    reading = reader(
                        "z",
                        ChannelSource(
                            "screen_cursor_ocr",
                            numeric_range=(30.0, 100.0),
                        ),
                        {},
                    )
                    actual = float(reading.raw_text)
                    status = "correct" if actual == 51.53 else f"wrong:{actual}"
                except (ValueError, RuntimeError) as exc:
                    status = f"rejected:{type(exc).__name__}"
                results.append((168 - foreground, status))
        self.assertEqual(
            results,
            [(96, "correct"), (68, "correct"), (44, "correct")],
        )

    def test_combined_agtek_geometry_reads_status_and_cursor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = render_agtek_screen_fixture(Path(temporary) / "agtek-screen.png")
            with Image.open(fixture.path) as opened:
                screen = opened.convert("RGB")
            left, top, width, height = fixture.cursor_region
            cursor_crop = screen.crop((left, top, left + width, top + height))
            reader = DefaultReader(
                ScreenOcrBackend(
                    capture_provider=lambda _zone: cursor_crop,
                    cache_enabled=False,
                ),
                cursor_position_provider=lambda: (-500, 1000),
            )
            cursor = reader(
                "z",
                ChannelSource("screen_cursor_ocr", numeric_range=(30.0, 100.0)),
                {},
            )
            status = ScreenOcrBackend(cache_enabled=False).read_image_region(
                screen,
                fixture.status_region,
            )
            parsed = parse_number(
                status.raw_text,
                separator_mode="point",
                numeric_range=(2000.0, 3000.0),
                declared_format="1,234.56",
            )
            self.assertEqual(float(cursor.raw_text), fixture.elevation)
            self.assertNotIn("x", cursor.raw_text.lower())
            self.assertEqual(parsed.parse_status, "OK", status.raw_text)
            self.assertEqual(float(parsed.normalized_value), fixture.northing)

    def test_general_plan_ocr_never_accepts_the_ten_weak_consensus_errors(self) -> None:
        formerly_wrong = {
            42.22, 43.70, 45.18, 48.14, 49.99,
            52.21, 53.32, 55.54, 56.28, 56.65,
        }
        correct = wrong = rejected = 0
        with tempfile.TemporaryDirectory() as temporary:
            plan_path = Path(temporary) / "plan.png"
            labels = render_plan(plan_path)
            backend = ScreenOcrBackend(cache_enabled=False)
            policy = cursor_ocr_policy(
                ChannelSource("screen_cursor_ocr", numeric_range=(30.0, 100.0))
            )
            for label in labels:
                if label.value not in formerly_wrong:
                    continue
                try:
                    reading = backend.read_image_region(
                        plan_path, label.ocr_region, policy=policy
                    )
                    if float(reading.raw_text) == label.value:
                        correct += 1
                    else:
                        wrong += 1
                except (ValueError, RuntimeError):
                    rejected += 1
        detail = f"correct={correct} wrong={wrong} rejected={rejected}"
        self.assertEqual(wrong, 0, detail)
        self.assertEqual(correct + rejected, 10, detail)


if __name__ == "__main__":
    unittest.main()
