from __future__ import annotations

import unittest
from unittest import mock

from screen2xyz_m1 import intake
from screen2xyz_m1.intake import IntakeError, validate_source_png

from .helpers_m1 import BASELINE_IMAGE, fresh_run_root

_PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _ihdr(width: int, height: int) -> bytes:
    body = width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00"
    return (13).to_bytes(4, "big") + b"IHDR" + body + b"\x00\x00\x00\x00"


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.root = fresh_run_root()

    def _expect(self, code: str, path) -> None:
        with self.assertRaises(IntakeError) as caught:
            validate_source_png(path)
        self.assertEqual(caught.exception.code, code)

    def test_valid_png_accepted_with_identity(self):
        source = validate_source_png(BASELINE_IMAGE)
        self.assertEqual(source.display_name, "S001.png")
        self.assertEqual((source.width_px, source.height_px), (1600, 260))
        self.assertEqual(len(source.sha256), 64)
        # Intake must not modify the source image.
        self.assertEqual(source.sha256, validate_source_png(BASELINE_IMAGE).sha256)

    def test_missing_file_rejected(self):
        self._expect("SOURCE_MISSING", self.root / "absent.png")

    def test_directory_rejected(self):
        target = self.root / "dir.png"
        target.mkdir()
        self._expect("SOURCE_NOT_FILE", target)

    def test_wrong_extension_rejected(self):
        target = self.root / "image.jpg"
        target.write_bytes(_PNG_SIG + _ihdr(10, 10))
        self._expect("SOURCE_NOT_PNG", target)

    def test_bad_signature_rejected(self):
        target = self.root / "fake.png"
        target.write_bytes(b"NOTAPNG!" + _ihdr(10, 10) * 3)
        self._expect("PNG_SIGNATURE", target)

    def test_truncated_png_rejected(self):
        target = self.root / "cut.png"
        target.write_bytes(BASELINE_IMAGE.read_bytes()[:-20])
        self._expect("PNG_STRUCTURE", target)

    def test_trailing_garbage_rejected(self):
        target = self.root / "trail.png"
        target.write_bytes(BASELINE_IMAGE.read_bytes() + b"extra")
        self._expect("PNG_STRUCTURE", target)

    def test_oversized_bytes_rejected(self):
        target = self.root / "big.png"
        target.write_bytes(BASELINE_IMAGE.read_bytes())
        with mock.patch.object(intake, "MAX_SOURCE_BYTES", 100):
            self._expect("SOURCE_TOO_LARGE", target)

    def test_oversized_dimensions_rejected(self):
        target = self.root / "wide.png"
        target.write_bytes(_PNG_SIG + _ihdr(100_000, 10) + b"\x00" * 30)
        self._expect("PNG_DIMENSIONS", target)

    def test_excess_pixel_count_rejected(self):
        target = self.root / "dense.png"
        target.write_bytes(_PNG_SIG + _ihdr(8_000, 8_000) + b"\x00" * 30)
        self._expect("PNG_DIMENSIONS", target)

    def test_zero_dimension_rejected(self):
        target = self.root / "zero.png"
        target.write_bytes(_PNG_SIG + _ihdr(0, 10) + b"\x00" * 30)
        self._expect("PNG_DIMENSIONS", target)
