from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from screen2xyz_app.backends import OcrPolicy, ScreenOcrBackend


def _data(words: list[str], confidences: list[float]) -> dict[str, list[object]]:
    return {
        "text": words,
        "conf": [str(value) for value in confidences],
        "left": [10 + index * 80 for index in range(len(words))],
        "top": [5 for _word in words],
        "width": [70 for _word in words],
        "height": [18 for _word in words],
    }


class RealViewerTokenConfidenceTests(unittest.TestCase):
    def _read(self, data, policy: OcrPolicy):
        backend = ScreenOcrBackend(executable=Path("tesseract"))
        image = Image.new("RGB", (300, 28), "white")
        with patch("pytesseract.image_to_data", return_value=data) as mocked:
            reading = backend._ocr_tesseract(
                [("fixture", image)], policy, "pixel-hash", b"png"
            )
        return reading, mocked

    def test_label_prefixed_grouped_integer_uses_numeric_word_confidence(self):
        reading, _mocked = self._read(
            _data(["North:", "2,380,658"], [0.0, 92.0]),
            OcrPolicy(separator_mode="point"),
        )
        self.assertEqual(reading.raw_text, "2,380,658")
        self.assertAlmostEqual(reading.confidence, 0.92)

    def test_single_stray_colon_does_not_zero_correct_number(self):
        reading, _mocked = self._read(
            _data([":", "2,380,658"], [0.0, 91.0]),
            OcrPolicy(separator_mode="point"),
        )
        self.assertEqual(reading.raw_text, "2,380,658")
        self.assertAlmostEqual(reading.confidence, 0.91)

    def test_numeric_token_cases_cover_sign_and_both_separator_modes(self):
        cases = (
            ("2,380,658", "point", "2,380,658", 0.93),
            ("-49.78", "point", "-49.78", 0.94),
            ("49,78", "comma", "49,78", 0.95),
            ("-49,47", "comma", "-49,47", 0.96),
        )
        for token, mode, expected, confidence in cases:
            with self.subTest(token=token, mode=mode):
                reading, _mocked = self._read(
                    _data([token], [confidence * 100]),
                    OcrPolicy(separator_mode=mode),
                )
                self.assertEqual(reading.raw_text, expected)
                self.assertAlmostEqual(reading.confidence, confidence)

    def test_suppressed_non_numeric_word_is_excluded_from_confidence(self):
        reading, _mocked = self._read(
            _data(["", "2,380,658"], [0.0, 92.0]),
            OcrPolicy(separator_mode="point", whitelist="0123456789.,-"),
        )
        self.assertAlmostEqual(reading.confidence, 0.92)

    def test_production_policy_keeps_whitelist_optional(self):
        _reading, mocked = self._read(
            _data(["North:", "2,380,658"], [95.0, 92.0]),
            OcrPolicy(separator_mode="point"),
        )
        self.assertNotIn("tessedit_char_whitelist", mocked.call_args.kwargs["config"])


if __name__ == "__main__":
    unittest.main()
