"""Synthetic image fixture gallery for overnight QA (Pillow is a dev-only
fixture-generation dependency - never imported by production
src/screen2xyz_m2 code). Every image is generated from fabricated values.
Output must only ever be written under the ignored
.lab_work/fixture_gallery/images/ directory."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CANVAS = (640, 400)


def _font(size: int = 28):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _base(bg=(255, 255, 255), size=None):
    return Image.new("RGB", size or CANVAS, bg)


def _save(img: Image.Image, out_dir: Path, name: str) -> Path:
    ext = "jpg" if name.endswith("_jpeg") else "png"
    path = out_dir / f"{name}.{ext}"
    img.convert("RGB").save(path, quality=90 if ext == "jpg" else None)
    return path


def _scenarios(out_dir: Path) -> dict:
    truth: dict[str, dict] = {}

    def emit(name, value_text, draw_fn, region=None, canvas=None):
        img = _base(size=canvas)
        d = ImageDraw.Draw(img)
        draw_fn(img, d)
        path = _save(img, out_dir, name)
        size = canvas or CANVAS
        truth[name] = {"path": str(path), "expected": value_text,
                       "region": region or (0, 0, size[0], size[1])}

    fnt = _font()

    emit("01_top_left", "1000.5",
        lambda im, d: d.text((10, 10), "1000.5", fill="black", font=fnt),
        region=(0, 0, 160, 50))
    emit("02_top_right", "2000.5",
        lambda im, d: d.text((CANVAS[0] - 140, 10), "2000.5", fill="black",
                            font=fnt),
        region=(CANVAS[0] - 160, 0, 160, 50))
    emit("03_center", "3000.5",
        lambda im, d: d.text((CANVAS[0] // 2 - 60, CANVAS[1] // 2 - 15),
                            "3000.5", fill="black", font=fnt),
        region=(CANVAS[0] // 2 - 80, CANVAS[1] // 2 - 35, 180, 60))
    emit("04_bottom_left", "4000.5",
        lambda im, d: d.text((10, CANVAS[1] - 40), "4000.5", fill="black",
                            font=fnt),
        region=(0, CANVAS[1] - 60, 160, 60))
    emit("05_bottom_right", "5000.5",
        lambda im, d: d.text((CANVAS[0] - 140, CANVAS[1] - 40), "5000.5",
                            fill="black", font=fnt),
        region=(CANVAS[0] - 160, CANVAS[1] - 60, 160, 60))
    emit("06_multiple_separated", "111.1 / 222.2 / 333.3",
        lambda im, d: (d.text((10, 10), "111.1", fill="black", font=fnt),
                      d.text((10, 180), "222.2", fill="black", font=fnt),
                      d.text((10, 350), "333.3", fill="black", font=fnt)),
        region=(0, 0, 160, 50))

    def white_dark(im, d):
        d.text((40, 160), "6543.2", fill="black", font=fnt)
    emit("07_white_bg_dark_text", "6543.2", white_dark,
        region=(30, 150, 180, 60))

    def dark_light(im, d):
        d.rectangle([0, 0, CANVAS[0], CANVAS[1]], fill=(20, 20, 20))
        d.text((40, 160), "7654.3", fill="white", font=fnt)
    emit("08_dark_bg_light_text", "7654.3", dark_light,
        region=(30, 150, 180, 60))

    def low_contrast(im, d):
        d.rectangle([0, 0, CANVAS[0], CANVAS[1]], fill=(210, 210, 210))
        d.text((40, 160), "8765.4", fill=(190, 190, 190), font=fnt)
    emit("09_low_contrast", "8765.4 (low contrast - OCR may warn)",
        low_contrast, region=(30, 150, 180, 60))

    small_fnt = _font(11)
    emit("10_small_font", "9.1",
        lambda im, d: d.text((40, 190), "9.1", fill="black",
                            font=small_fnt),
        region=(30, 180, 100, 30))
    large_fnt = _font(64)
    emit("11_large_font", "10.2",
        lambda im, d: d.text((30, 150), "10.2", fill="black",
                            font=large_fnt),
        region=(20, 140, 260, 90))
    emit("12_label_plus_value", "42.7",
        lambda im, d: d.text((30, 180), "Reading: 42.7", fill="black",
                            font=fnt),
        region=(20, 170, 220, 50))

    def gridlines(im, d):
        for x in range(0, CANVAS[0], 40):
            d.line([(x, 0), (x, CANVAS[1])], fill=(230, 230, 230))
        for y in range(0, CANVAS[1], 40):
            d.line([(0, y), (CANVAS[0], y)], fill=(230, 230, 230))
        d.text((40, 180), "13.5", fill="black", font=fnt)
    emit("13_gridlines_near_value", "13.5", gridlines,
        region=(30, 170, 140, 50))

    def large_image(im, d):
        d.text((1400, 900), "14000.0", fill="black", font=_font(48))
    # Independent audit finding: this scenario claimed a 2000x1200 image
    # but the module-level CANVAS constant is fixed at 640x400, so both
    # the drawn text and the declared region were entirely off-canvas -
    # Pillow silently drops out-of-bounds draws, producing a blank image
    # this scenario's own name/expected text never matched. emit() now
    # takes an explicit canvas override so this one is genuinely large.
    emit("14_large_needs_zoom",
        "14000.0 (image is 2000x1200, needs Fit/Zoom/scroll)",
        large_image, region=(1390, 890, 300, 80), canvas=(2000, 1200))

    def touching_edge(im, d):
        d.text((0, CANVAS[1] // 2), "15.9", fill="black", font=fnt)
    emit("15_text_touching_edge", "15.9", touching_edge,
        region=(0, CANVAS[1] // 2 - 10, 100, 50))

    def obscured(im, d):
        d.text((40, 180), "16543.2", fill="black", font=fnt)
        d.rectangle([90, 175, 130, 210], fill="black")
    emit("17_partially_obscured", "16?43.2 (expected warning: obscured)",
        obscured, region=(30, 170, 220, 50))

    emit("17_blank", "(blank field - expected empty/no-value)",
        lambda im, d: None, region=(30, 170, 220, 50))

    def near_uniform_dark(im, d):
        d.rectangle([0, 0, CANVAS[0], CANVAS[1]], fill=(15, 15, 15))
    emit("18_near_uniform_dark", "(near-uniform dark - expected FAIL)",
        near_uniform_dark, region=(30, 170, 220, 50))

    def near_uniform_light(im, d):
        d.rectangle([0, 0, CANVAS[0], CANVAS[1]], fill=(245, 245, 245))
    emit("19_near_uniform_light", "(near-uniform light - expected FAIL)",
        near_uniform_light, region=(30, 170, 220, 50))

    emit("20_malformed_number", "12O.5 (letter O for zero - malformed)",
        lambda im, d: d.text((40, 180), "12O.5", fill="black", font=fnt),
        region=(30, 170, 160, 50))
    emit("21_unicode_minus", "-25.4",
        lambda im, d: d.text((40, 180), "−25.4", fill="black",
                            font=fnt),
        region=(30, 170, 160, 50))
    emit("22_decimal_comma", "1234,56",
        lambda im, d: d.text((40, 180), "1234,56", fill="black", font=fnt),
        region=(30, 170, 200, 50))
    emit("23_decimal_point", "1234.56",
        lambda im, d: d.text((40, 180), "1234.56", fill="black", font=fnt),
        region=(30, 170, 200, 50))

    def duplicates(im, d):
        d.text((40, 60), "77.7", fill="black", font=fnt)
        d.text((400, 300), "77.7", fill="black", font=fnt)
    # Independent audit finding: the declared region only covered the
    # FIRST occurrence (x:30-180, y:50-100), so the actual OCR/parse
    # result was a single clean "77.7" - a plain OK read, never the
    # AMBIGUOUS_MULTIPLE_NUMBERS path this scenario exists to exercise.
    # Widened to genuinely cover both locations; the correct/expected
    # outcome is now that the parser refuses to silently pick one value
    # (an "ambiguous" negative case, like the blank/near-uniform ones).
    emit("24_duplicate_values",
        "ambiguous (77.7 appears twice, different locations - must not "
        "silently resolve to a single value)",
        duplicates, region=(30, 50, 440, 320))

    emit("25_long_text", "STATUS: PENDING OWNER REVIEW - SEE NOTES BELOW",
        lambda im, d: d.text(
            (20, 180), "STATUS: PENDING OWNER REVIEW - SEE NOTES BELOW",
            fill="black", font=_font(18)),
        region=(10, 170, 600, 50))

    def rotated(im, d):
        txt = Image.new("RGBA", (200, 60), (255, 255, 255, 0))
        td = ImageDraw.Draw(txt)
        td.text((0, 0), "26.6", fill="black", font=fnt)
        txt = txt.rotate(25, expand=True)
        im.paste(txt, (200, 150), txt)
    emit("26_rotated_text", "26.6 (rotated - expected warning)", rotated,
        region=(190, 140, 220, 100))

    def skewed(im, d):
        d.text((40, 180), "27.7", fill="black", font=fnt)
        d.line([(30, 220), (150, 210)], fill=(200, 200, 200))
    emit("27_slight_skew", "27.7 (slight skew - expected warning)", skewed,
        region=(30, 170, 160, 60))

    def multi_weight(im, d):
        d.text((40, 100), "28.1", fill="black", font=_font(28))
        d.text((40, 220), "28.2", fill="black", font=ImageFont.load_default())
    emit("28_multiple_font_weights", "28.1 / 28.2", multi_weight,
        region=(30, 90, 160, 150))

    def boxed(im, d):
        d.rectangle([30, 160, 220, 220], outline="black", width=3)
        d.text((45, 175), "29.3", fill="black", font=fnt)
    emit("29_value_in_colored_box", "29.3", boxed, region=(25, 155, 200, 70))

    def beside_icon(im, d):
        d.ellipse([20, 170, 60, 210], fill=(30, 120, 200))
        d.text((70, 175), "30.4", fill="black", font=fnt)
    emit("30_value_beside_icon", "30.4", beside_icon,
        region=(10, 160, 160, 60))

    return truth


def generate_all(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    return _scenarios(out_dir)


if __name__ == "__main__":
    import json
    import sys
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        ".lab_work/fixture_gallery/images")
    result = generate_all(target)
    print(json.dumps(result, indent=2))
    print(f"generated {len(result)} image fixtures")
