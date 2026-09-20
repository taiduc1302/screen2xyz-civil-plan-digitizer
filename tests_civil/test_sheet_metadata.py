from __future__ import annotations

import unittest

from screen2xyz_civil import contracts as C
from screen2xyz_civil.detection import Rect, TextCandidate
from screen2xyz_civil.sheet_metadata import infer_sheet_metadata


def _token(token_id: str, text: str, x: float, y: float) -> TextCandidate:
    return TextCandidate(
        token_id,
        text,
        Rect(x, y, x + 20, y + 10),
        2,
        C.PDF_TEXT,
        1.0,
    )


class SheetMetadataTests(unittest.TestCase):
    def test_infers_sheet_and_revision_from_bottom_right_title_block(self):
        result = infer_sheet_metadata(
            [
                _token("title", "CO3", 1700, 1530),
                _token("revision", "G", 1810, 1510),
                _token("north", "C02", 200, 300),
            ],
            width_px=1900,
            height_px=1600,
        )
        self.assertEqual(result, {"sheet_id": "C03", "revision": "G"})

    def test_does_not_promote_sheet_like_text_outside_title_block(self):
        result = infer_sheet_metadata(
            [_token("plan-note", "C03", 500, 400)],
            width_px=1900,
            height_px=1600,
        )
        self.assertEqual(result, {})

    def test_sheet_inference_does_not_guess_revision(self):
        result = infer_sheet_metadata(
            [
                _token("title", "C03", 1700, 1530),
                _token("unrelated-letter", "G", 500, 400),
            ],
            width_px=1900,
            height_px=1600,
        )
        self.assertEqual(result, {"sheet_id": "C03"})


if __name__ == "__main__":
    unittest.main()
