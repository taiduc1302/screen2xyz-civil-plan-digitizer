"""Deterministic realistic capture surfaces with explicit ground truth."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSET_ROOT = Path(__file__).resolve().parent / "assets" / "fonts"
REGULAR_FONT = ASSET_ROOT / "LiberationSans-Regular.ttf"
BOLD_FONT = ASSET_ROOT / "LiberationSans-Bold.ttf"


@dataclass(frozen=True)
class StatusStyle:
    name: str
    decimal_separator: str
    grouped: bool
    font_size: int
    foreground: tuple[int, int, int]
    background: tuple[int, int, int]


@dataclass(frozen=True)
class StatusFrame:
    sequence: int
    style: str
    path: str
    x: float
    y: float
    x_text: str
    y_text: str
    x_zone: tuple[int, int, int, int]
    y_zone: tuple[int, int, int, int]


@dataclass(frozen=True)
class PlanLabel:
    label_id: str
    value: float
    text: str
    angle: int
    marker: str
    center: tuple[int, int]
    ocr_region: tuple[int, int, int, int]


STATUS_STYLES = (
    StatusStyle("point-light", "point", False, 11, (58, 63, 69), (236, 238, 240)),
    StatusStyle("point-grouped", "point", True, 14, (32, 37, 42), (217, 221, 225)),
    StatusStyle("comma-dark", "comma", False, 12, (230, 232, 235), (71, 76, 82)),
    StatusStyle("comma-grouped", "comma", True, 13, (45, 48, 51), (229, 231, 233)),
)


def _format(value: float, *, separator: str, grouped: bool) -> str:
    text = f"{value:,.2f}" if grouped else f"{value:.2f}"
    if separator == "comma":
        text = text.translate(str.maketrans({",": ".", ".": ","}))
    return text


def scripted_coordinates(count_per_style: int = 55):
    """Return four realistic paths, totalling at least 200 unique pairs."""
    scenarios = []
    for style_index, style in enumerate(STATUS_STYLES):
        base_x = (512.25 if not style.grouped else 432_100.25) + style_index * 10_000
        base_y = (-120.75 if style_index % 2 == 0 else 5_456_789.75) + style_index * 5_000
        rows = []
        for index in range(count_per_style):
            x = round(base_x + (index + 1) * (1.17 + style_index * 0.03), 2)
            y = round(base_y - (index + 1) * (0.91 + style_index * 0.02), 2)
            rows.append((x, y))
        primer = (round(base_x, 2), round(base_y, 2))
        scenarios.append((style, primer, rows))
    return scenarios


def render_status_frame(
    output_path: Path,
    *,
    sequence: int,
    style: StatusStyle,
    x: float,
    y: float,
) -> StatusFrame:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (620, 42), style.background)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(REGULAR_FONT), style.font_size)
    label_font = ImageFont.truetype(str(BOLD_FONT), max(10, style.font_size - 1))
    border = tuple(max(0, channel - 22) for channel in style.background)
    draw.rectangle((0, 0, 619, 41), outline=border)
    draw.line((0, 1, 619, 1), fill=(255, 255, 255))
    x_text = _format(x, separator=style.decimal_separator, grouped=style.grouped)
    y_text = _format(y, separator=style.decimal_separator, grouped=style.grouped)
    baseline = max(5, (42 - style.font_size) // 2 - 1)
    draw.text((10, baseline), "X:", font=label_font, fill=style.foreground)
    draw.text((52, baseline), x_text, font=font, fill=style.foreground)
    draw.line((305, 5, 305, 36), fill=border)
    draw.text((318, baseline), "Y:", font=label_font, fill=style.foreground)
    draw.text((356, baseline), y_text, font=font, fill=style.foreground)
    image.save(output_path)
    return StatusFrame(
        sequence=sequence,
        style=style.name,
        path=str(output_path),
        x=x,
        y=y,
        x_text=x_text,
        y_text=y_text,
        x_zone=(44, 3, 240, 36),
        y_zone=(348, 3, 260, 36),
    )


def render_status_scenarios(output_dir: Path, count_per_style: int = 55):
    scenarios = []
    sequence = 0
    for style, primer, rows in scripted_coordinates(count_per_style):
        style_dir = output_dir / style.name
        primer_frame = render_status_frame(
            style_dir / "frame-0000.png",
            sequence=sequence,
            style=style,
            x=primer[0],
            y=primer[1],
        )
        frames = []
        for local_index, (x, y) in enumerate(rows, start=1):
            sequence += 1
            frames.append(render_status_frame(
                style_dir / f"frame-{local_index:04d}.png",
                sequence=sequence,
                style=style,
                x=x,
                y=y,
            ))
        scenarios.append((style, primer_frame, frames))
    manifest = {
        "schema_version": "1.0",
        "coordinate_pair_count": sum(len(item[2]) for item in scenarios),
        "styles": [asdict(style) for style in STATUS_STYLES],
        "frames": [
            asdict(frame)
            for _style, primer, frames in scenarios
            for frame in (primer, *frames)
        ],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return scenarios


def render_plan(output_path: Path, *, label_count: int = 48):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1800, 2200), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((35, 35, 1765, 2165), outline=(35, 45, 55), width=3)
    for x in range(100, 1700, 100):
        draw.line((x, 80, x, 1950), fill=(225, 230, 234), width=1)
    for y in range(100, 1950, 100):
        draw.line((80, y, 1720, y), fill=(225, 230, 234), width=1)
    draw.line((100, 350, 1650, 1750), fill=(110, 120, 130), width=5)
    draw.line((130, 320, 1680, 1720), fill=(160, 170, 178), width=2)
    title_font = ImageFont.truetype(str(BOLD_FONT), 30)
    draw.rectangle((1050, 1960, 1740, 2135), outline=(40, 50, 60), width=2)
    draw.text((1080, 1990), "SYNTHETIC GRADING PLAN", font=title_font, fill=(30, 40, 50))
    draw.text((1080, 2040), "NOT FOR CONSTRUCTION", font=title_font, fill=(120, 35, 35))

    angles = (0, 15, -15, 20, -20, 25, -25, 0)
    labels: list[PlanLabel] = []
    # Plan labels are rendered at a scale comparable to a high-DPI plan view.
    # The status-bar fixtures above deliberately retain the harder 11--14 px
    # text required by the proof contract.
    font = ImageFont.truetype(str(REGULAR_FONT), 24)
    bold = ImageFont.truetype(str(BOLD_FONT), 24)
    for index in range(label_count):
        column = index % 6
        row = index // 6
        anchor_x = 175 + column * 270
        anchor_y = 180 + row * 215
        value = round(40.0 + index * 0.37, 2)
        text = f"{value:.2f}"
        angle = angles[index % len(angles)]
        marker = "design_oval" if index % 2 else "existing_cross"
        if marker == "existing_cross":
            draw.line((anchor_x - 34, anchor_y, anchor_x - 10, anchor_y), fill=(20, 20, 20), width=2)
            draw.line((anchor_x - 22, anchor_y - 12, anchor_x - 22, anchor_y + 12), fill=(20, 20, 20), width=2)
        else:
            draw.ellipse((anchor_x - 45, anchor_y - 18, anchor_x - 9, anchor_y + 18), outline=(30, 70, 120), width=2)
        selected_font = bold if marker == "design_oval" else font
        bounds = selected_font.getbbox(text)
        text_width = bounds[2] - bounds[0]
        text_height = bounds[3] - bounds[1]
        glyph_padding = 5
        text_layer = Image.new(
            "RGB",
            (text_width + glyph_padding * 2, text_height + glyph_padding * 2),
            "white",
        )
        text_draw = ImageDraw.Draw(text_layer)
        text_draw.text(
            (glyph_padding - bounds[0], glyph_padding - bounds[1]),
            text,
            font=selected_font,
            fill=(20, 25, 30),
        )
        rotated = text_layer.rotate(
            angle,
            expand=True,
            resample=Image.Resampling.BICUBIC,
            fillcolor="white",
        )
        paste_x = anchor_x + 5
        paste_y = anchor_y - rotated.height // 2
        image.paste(rotated, (paste_x, paste_y))
        padding = 8
        region = (
            max(0, paste_x - padding),
            max(0, paste_y - padding),
            min(image.width - paste_x + padding, rotated.width + padding * 2),
            min(image.height - paste_y + padding, rotated.height + padding * 2),
        )
        labels.append(PlanLabel(
            label_id=f"L{index + 1:03d}",
            value=value,
            text=text,
            angle=angle,
            marker=marker,
            center=(paste_x + rotated.width // 2, paste_y + rotated.height // 2),
            ocr_region=region,
        ))
    image.save(output_path)
    manifest = {
        "schema_version": "1.0",
        "image": output_path.name,
        "label_count": len(labels),
        "labels": [asdict(label) for label in labels],
    }
    (output_path.parent / "plan_ground_truth.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return labels
