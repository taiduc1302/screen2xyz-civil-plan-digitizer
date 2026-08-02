"""Secure intake validation for explicitly user-selected PNG files.

The source image is never modified, moved, or copied; intake only reads it
to establish identity (SHA-256), structural validity, and bounded size.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from screen2xyz_lab.evidence import sha256_file

from .config import (
    MAX_SOURCE_BYTES,
    MAX_SOURCE_HEIGHT_PX,
    MAX_SOURCE_PIXELS,
    MAX_SOURCE_WIDTH_PX,
)

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class IntakeError(ValueError):
    """A rejected source image; ``code`` is a stable machine reason."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SourceImage:
    path: Path
    display_name: str
    sha256: str
    byte_size: int
    width_px: int
    height_px: int


def _walk_chunks(data: bytes) -> None:
    """Require a structurally complete PNG chunk stream ending at IEND."""

    offset = 8
    seen_iend = False
    while offset + 12 <= len(data):
        length = int.from_bytes(data[offset : offset + 4], "big")
        if length > len(data):
            raise IntakeError("PNG_STRUCTURE", "chunk length exceeds file size")
        name = data[offset + 4 : offset + 8]
        if not all(65 <= b <= 90 or 97 <= b <= 122 for b in name):
            raise IntakeError("PNG_STRUCTURE", "invalid chunk type")
        offset += 12 + length
        if name == b"IEND":
            seen_iend = True
            break
    if not seen_iend or offset != len(data):
        raise IntakeError("PNG_STRUCTURE", "truncated or trailing PNG data")


def validate_source_png(path: Path) -> SourceImage:
    """Validate one explicitly user-selected PNG without modifying it."""

    if not isinstance(path, Path):
        path = Path(path)
    if not path.exists():
        raise IntakeError("SOURCE_MISSING", "selected file does not exist")
    if not path.is_file():
        raise IntakeError("SOURCE_NOT_FILE", "selected path is not a regular file")
    if path.suffix.lower() != ".png":
        raise IntakeError("SOURCE_NOT_PNG", "only .png files are supported")
    byte_size = path.stat().st_size
    if byte_size > MAX_SOURCE_BYTES:
        raise IntakeError("SOURCE_TOO_LARGE", f"file exceeds {MAX_SOURCE_BYTES} bytes")
    if byte_size < 8 + 25:  # signature + minimal IHDR chunk
        raise IntakeError("PNG_STRUCTURE", "file too small to be a PNG")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise IntakeError("SOURCE_READ_ERROR", "selected file could not be read") from exc
    if data[:8] != _PNG_SIGNATURE:
        raise IntakeError("PNG_SIGNATURE", "not a PNG file")
    if data[12:16] != b"IHDR" or len(data) < 24:
        raise IntakeError("PNG_STRUCTURE", "missing IHDR header")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    if width <= 0 or height <= 0:
        raise IntakeError("PNG_DIMENSIONS", "non-positive image dimensions")
    if width > MAX_SOURCE_WIDTH_PX or height > MAX_SOURCE_HEIGHT_PX:
        raise IntakeError("PNG_DIMENSIONS", "image dimensions exceed the supported maximum")
    if width * height > MAX_SOURCE_PIXELS:
        raise IntakeError("PNG_DIMENSIONS", "image pixel count exceeds the supported maximum")
    _walk_chunks(data)
    return SourceImage(
        path=path,
        display_name=path.name,
        sha256=sha256_file(path),
        byte_size=byte_size,
        width_px=width,
        height_px=height,
    )
