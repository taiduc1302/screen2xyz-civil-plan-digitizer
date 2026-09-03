"""Render a host markup over the base drawing, at a zoom you choose.

`create_markup_thumbnail` is the first check and the cheapest: the host draws
the markup in place, from the live document, with its own computed quantity,
and no coordinate arithmetic is involved. Use it first, always.

It has one blind spot. It auto-zooms to the markup extent, so a point marker
fills the frame and shows no surroundings: the Example Road manhole count markers
looked correct in the host thumbnail and were sitting in the title block. And
on a 100 m band it cannot resolve an edge error of one line width.

This module covers both cases. It draws a read-back path over the immutable
base PDF and renders a window you control, so a point marker gets context and
a long band gets 15-20x on the stretch that matters.

**The frame trap, which has now cost two sessions a wrong first attempt.** On a
180-rotated page these are different transforms:

* `draw_polyline` works in UNROTATED page coordinates - a raw-frame point is
  drawn at `(x, H - y)`;
* `get_pixmap(clip=...)` works in DISPLAYED coordinates - the same point is
  clipped around at `(W - x, y)`.

Use one for both and the window lands in the profile while the geometry is in
the plan, which reads as "the markup is nowhere near the drawing" when nothing
is wrong with the markup at all.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Sequence


class MarkupViewError(RuntimeError):
    """A markup could not be rendered over its drawing."""


def parse_path(path: str) -> list[tuple[float, float]]:
    """Points of a Bluebeam SVG-subset path (`M`/`L`/`H`), in the raw frame."""

    numbers = [float(t) for t in re.findall(r"-?\d+\.?\d*", path)]
    if len(numbers) < 4 or len(numbers) % 2:
        raise MarkupViewError(f"path does not parse to point pairs: {path[:60]}")
    return list(zip(numbers[0::2], numbers[1::2]))


def parse_rect(rect: str) -> tuple[float, float, float, float]:
    """`x y width height`, as returned for Square and FreeText markups."""

    parts = [float(t) for t in rect.split()]
    if len(parts) != 4:
        raise MarkupViewError(f"rect does not parse to x y w h: {rect!r}")
    return (parts[0], parts[1], parts[2], parts[3])


def rect_corners(rect: str) -> list[tuple[float, float]]:
    x, y, w, h = parse_rect(rect)
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def to_page(point, *, rotation: int, height: float) -> tuple[float, float]:
    """Raw frame -> the frame `draw_polyline` uses."""

    x, y = point
    if rotation == 180:
        return (x, height - y)
    if rotation == 0:
        return (x, y)
    raise MarkupViewError(f"page rotation {rotation} is not handled")


def to_clip(point, *, rotation: int, width: float) -> tuple[float, float]:
    """Raw frame -> the frame `get_pixmap(clip=...)` uses."""

    x, y = point
    if rotation == 180:
        return (width - x, y)
    if rotation == 0:
        return (x, y)
    raise MarkupViewError(f"page rotation {rotation} is not handled")


def clip_around(points, *, rotation: int, width: float, margin: float):
    """Clip rectangle around raw-frame points, in displayed coordinates."""

    mapped = [to_clip(p, rotation=rotation, width=width) for p in points]
    xs = [p[0] for p in mapped]
    ys = [p[1] for p in mapped]
    return (min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin)


def render_over_drawing(
    pdf_path: Path,
    page_index: int,
    shapes: Iterable,
    out_png: Path,
    *,
    window=None,
    margin: float = 60.0,
    zoom: float = 6.0,
    line_width: float = 1.0,
) -> Path:
    """Draw raw-frame shapes over the page and render one window.

    `shapes` is (points, closed, rgb). `window` is a raw-frame box; omit it to
    frame the shapes with `margin` points of context. Small margin plus high
    zoom inspects one stretch of a long band; the default margin keeps a point
    marker's surroundings visible.
    """

    try:
        import pymupdf  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover
        raise MarkupViewError("pymupdf is required to render a markup") from exc

    source = Path(pdf_path).expanduser().resolve()
    if not source.is_file():
        raise MarkupViewError(f"drawing does not exist: {source}")
    document = pymupdf.open(str(source))
    try:
        if not 0 <= page_index < document.page_count:
            raise MarkupViewError(f"page index {page_index} is outside {source.name}")
        page = document[page_index]
        rotation = int(page.rotation)
        width, height = float(page.rect.width), float(page.rect.height)
        drawn: list[tuple[float, float]] = []
        for points, closed, colour in shapes:
            pts = [tuple(p) for p in points]
            if len(pts) < 2:
                continue
            drawn += pts
            mapped = [pymupdf.Point(*to_page(p, rotation=rotation, height=height)) for p in pts]
            shape = page.new_shape()
            shape.draw_polyline(mapped + ([mapped[0]] if closed else []))
            shape.finish(color=colour, width=line_width, closePath=False)
            shape.commit()
        if not drawn:
            raise MarkupViewError("nothing to draw")
        if window is None:
            clip = clip_around(drawn, rotation=rotation, width=width, margin=margin)
        else:
            x0, y0, x1, y1 = window
            a = to_clip((x0, y0), rotation=rotation, width=width)
            b = to_clip((x1, y1), rotation=rotation, width=width)
            clip = (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))
        out = Path(out_png)
        out.parent.mkdir(parents=True, exist_ok=True)
        page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=pymupdf.Rect(*clip)).save(str(out))
        return out
    finally:
        document.close()
