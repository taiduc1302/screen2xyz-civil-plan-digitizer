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


@dataclass(frozen=True)
class AgtekScreenFixture:
    path: Path
    cursor_region: tuple[int, int, int, int]
    status_region: tuple[int, int, int, int]
    elevation: float
    northing: float


def render_agtek_cursor_fixtures(
    output_dir: Path,
    *,
    background: tuple[int, int, int] = (168, 168, 168),
    foreground: tuple[int, int, int] = (72, 72, 72),
    angle: int = -12,
    marker: str = "x",
    values: tuple[float, ...] = AGTEK_ELEVATIONS,
) -> tuple[AgtekCursorFixture, ...]:
    output_dir.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype(str(REGULAR_FONT), 17)
    fixtures = []
    for index, value in enumerate(values, start=1):
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


def render_agtek_screen_fixture(output_path: Path) -> AgtekScreenFixture:
    """Render the observed drawing-label and status-strip geometry together."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    background = (168, 168, 168)
    image = Image.new("RGB", (800, 500), background)
    font = ImageFont.truetype(str(REGULAR_FONT), 17)
    layer = Image.new("RGB", (100, 34), background)
    ImageDraw.Draw(layer).text((4, 7), "x 51.53", font=font, fill=(72, 72, 72))
    rotated = layer.rotate(
        -12,
        expand=True,
        resample=Image.Resampling.BICUBIC,
        fillcolor=background,
    )
    cursor_region = (320, 200, 160, 60)
    cursor_crop = Image.new("RGB", (160, 60), background)
    cursor_crop.paste(
        rotated,
        ((cursor_crop.width - rotated.width) // 2, (cursor_crop.height - rotated.height) // 2),
    )
    image.paste(cursor_crop, cursor_region[:2])

    status_region = (0, 464, 220, 30)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 460, 799, 499), fill=(236, 238, 240))
    status_font = ImageFont.truetype(str(REGULAR_FONT), 12)
    draw.text((8, 470), "North: 2,768.313", font=status_font, fill=(58, 63, 69))
    image.save(output_path)
    return AgtekScreenFixture(
        output_path,
        cursor_region,
        status_region,
        51.53,
        2768.313,
    )
