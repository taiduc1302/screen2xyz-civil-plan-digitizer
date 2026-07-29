"""Privacy-bounded local source inspection for the guaranteed image core."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from screen2xyz_lab.evidence import sha256_file

from . import contracts as C
from .models import CivilModelError, CropRegion

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class SourceInfo:
    display_name: str
    source_path: str
    sha256: str
    byte_size: int
    width_px: int
    height_px: int
    source_type: str = "PNG"
    page_count: int = 1

    def to_manifest(self, *, include_local_path: bool = True) -> dict[str, object]:
        manifest: dict[str, object] = {
            "display_name": self.display_name,
            "sha256": self.sha256,
            "byte_size": self.byte_size,
            "width_px": self.width_px,
            "height_px": self.height_px,
            "source_type": self.source_type,
            "page_count": self.page_count,
        }
        if include_local_path:
            manifest["local_path"] = self.source_path
        return manifest


def inspect_png(path: Path) -> SourceInfo:
    candidate = path.expanduser().resolve()
    if not candidate.is_file():
        raise CivilModelError("source image does not exist")
    if candidate.suffix.lower() != ".png":
        raise CivilModelError("guaranteed manual core currently accepts PNG images")
    byte_size = candidate.stat().st_size
    if byte_size <= 0 or byte_size > C.MAX_SOURCE_BYTES:
        raise CivilModelError("source image size is outside the allowed boundary")
    header = candidate.read_bytes()[:24]
    if len(header) < 24 or header[:8] != PNG_SIGNATURE or header[12:16] != b"IHDR":
        raise CivilModelError("source is not a valid PNG")
    width, height = struct.unpack(">II", header[16:24])
    if width <= 0 or height <= 0 or width * height > C.MAX_SOURCE_PIXELS:
        raise CivilModelError("source PNG dimensions are outside the allowed boundary")
    return SourceInfo(
        display_name=candidate.name,
        source_path=str(candidate),
        sha256=sha256_file(candidate),
        byte_size=byte_size,
        width_px=width,
        height_px=height,
    )


def validate_crop(crop: CropRegion, source: SourceInfo) -> None:
    if crop.x + crop.width > source.width_px or crop.y + crop.height > source.height_px:
        raise CivilModelError("crop extends outside source image")
