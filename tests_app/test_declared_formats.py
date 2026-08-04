from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from screen2xyz_app.backends import OcrPolicy, ScreenOcrBackend
from screen2xyz_app.mapping import ChannelSource, DECLARED_NUMBER_FORMATS
from screen2xyz_m2.parsing import parse_number


class DeclaredNumberFormatTests(unittest.TestCase):
    def test_all_four_declared_formats_parse_clean_values(self) -> None:
        cases = (
            ("1,234.56", "1,718.819", "1718.819"),
            ("1.234,56", "1.718,819", "1718.819"),
            ("1234.56", "1718.819", "1718.819"),
            ("1234,56", "1718,819", "1718.819"),
        )
        self.assertEqual(tuple(DECLARED_NUMBER_FORMATS), tuple(case[0] for case in cases))
        for declared_format, text, expected in cases:
            with self.subTest(declared_format=declared_format):
                outcome = parse_number(text, declared_format=declared_format)
                self.assertEqual(outcome.parse_status, "OK")
                self.assertEqual(outcome.normalized_value, expected)

    def test_plain_formats_reject_grouping_without_a_range(self) -> None:
        cases = (("1234.56", "1,234.56"), ("1234,56", "1.234,56"))
        for declared_format, text in cases:
            with self.subTest(declared_format=declared_format):
                self.assertEqual(
                    parse_number(text, declared_format=declared_format).parse_status,
                    "MALFORMED_NUMBER",
                )

    def test_repeated_separator_slip_is_disambiguated_only_by_range(self) -> None:
        cases = (
            ("1,234.56", "1.844.850"),
            ("1.234,56", "1,844,850"),
            ("1234.56", "1.844.850"),
            ("1234,56", "1,844,850"),
        )
        for declared_format, text in cases:
            with self.subTest(declared_format=declared_format):
                outcome = parse_number(
                    text,
                    declared_format=declared_format,
                    numeric_range=(1_800.0, 1_900.0),
                )
                self.assertEqual(outcome.parse_status, "OK")
                self.assertAlmostEqual(float(outcome.normalized_value), 1844.85)

    def test_repeated_separator_slip_rejects_zero_or_multiple_range_matches(self) -> None:
        zero = parse_number(
            "1.844.850",
            declared_format="1,234.56",
            numeric_range=(2_000.0, 2_100.0),
        )
        multiple = parse_number(
            "1.844.850",
            declared_format="1,234.56",
            numeric_range=(0.0, 2_000_000.0),
        )
        self.assertEqual(zero.parse_status, "OUT_OF_RANGE")
        self.assertEqual(multiple.parse_status, "AMBIGUOUS_NUMBER_FORMAT")

    def test_malformed_grouped_token_never_calls_auto_fallback(self) -> None:
        with patch("screen2xyz_m2.parsing.parse_auto") as auto:
            outcome = parse_number(
                "1.844.850", declared_format="1,234.56"
            )
        self.assertEqual(outcome.parse_status, "MALFORMED_NUMBER")
        auto.assert_not_called()

    def test_channel_source_persists_declared_format(self) -> None:
        source = ChannelSource(
            "screen_zone_ocr",
            (-582, 1009, 112, 29),
            declared_format="1,234.56",
        )
        self.assertEqual(ChannelSource.from_json(source.to_json()), source)

    def test_ocr_failure_names_value_format_and_operator_action(self) -> None:
        backend = ScreenOcrBackend(executable=Path("tesseract"))
        image = Image.new("RGB", (220, 29), "white")
        data = {
            "text": ["East:", "1.844.850"],
            "conf": ["91", "88"],
            "left": [5, 60],
            "top": [5, 5],
            "width": [45, 90],
            "height": [16, 16],
        }
        with patch("pytesseract.image_to_data", return_value=data):
            with self.assertRaisesRegex(
                ValueError,
                r"value reads as 1\.844\.850.*declared format 1,234\.56.*zone edges.*format setting",
            ):
                backend._ocr_tesseract(
                    [("fixture", image)],
                    OcrPolicy(
                        separator_mode="point",
                        declared_format="1,234.56",
                    ),
                    "hash",
                    b"png",
                )


if __name__ == "__main__":
    unittest.main()
