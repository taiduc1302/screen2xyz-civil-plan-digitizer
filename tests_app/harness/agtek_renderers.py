"""Locally generated AGTEK-style field fixtures with explicit ground truth."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .renderers import REGULAR_FONT


AGTEK_ELEVATIONS = (
    51.53, 49.37, 47.82, 50.14, 52.68, 48.91,
    53.26, 46.75, 54.08, 45.62, 55.41, 44.39,
)


@dataclass(frozen=True)
class AgtekCursorFixture:
    fixture_id: str
    value: float
    path: Path
    background: tuple[int, int, int]
    foreground: tuple[int, int, int]
    angle: int
    marker: str


def render_agtek_cursor_fixtures(
    output_dir: Path,
    *,
    background: tuple[int, int, int] = (168, 168, 168),
    foreground: tuple[int, int, int] = (72, 72, 72),
    angle: int = -12,
    marker: str = "x",
) -> tuple[AgtekCursorFixture, ...]:
    output_dir.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype(str(REGULAR_FONT), 17)
    fixtures = []
    for index, value in enumerate(AGTEK_ELEVATIONS, start=1):
        layer = Image.new("RGB", (100, 34), background)
        draw = ImageDraw.Draw(layer)
        draw.text((4, 7), f"{marker} {value:.2f}", font=font, fill=foreground)
        rotated = layer.rotate(
            angle,
            expand=True,
            resample=Image.Resampling.BICUBIC,
            fillcolor=background,
        )
        image = Image.new("RGB", (160, 60), background)
        image.paste(
            rotated,
            ((image.width - rotated.width) // 2, (image.height - rotated.height) // 2),
        )
        path = output_dir / f"agtek-{index:02d}.png"
        image.save(path)
        fixtures.append(AgtekCursorFixture(
            f"AGTEK-{index:02d}", value, path,
            background, foreground, angle, marker,
        ))
    return tuple(fixtures)
