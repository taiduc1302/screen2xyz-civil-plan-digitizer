"""The two coordinate frames the Bluebeam host speaks, and how to convert.

The host exposes markup geometry through two APIs that use OPPOSITE y origins,
and nothing in either tool's schema says so. On 2026-09-03 this put five sheet 11
storm markers into the profile half of the drawing and let them pass a read-back
check, because the write and the read used the same API and therefore agreed with
each other while both disagreed with the file.

    get_markup_shape / set_markup_shape   "rect" = "x y width height"
        RAW frame: the unrotated PDF user space, origin bottom-left.
        This is the authoritative frame. It is what a path in `markup_path`
        uses, what pymupdf's get_drawings needs after `raw_frame`, and what
        you must render from when you verify.

    list_markups_in_pdf / set_markup_property   "x", "y", "width", "height"
        VIEW frame: the page as displayed after /Rotate, origin TOP-left.
        Convenient for a human reading a markup list; wrong for geometry.

Measured on the Example Road tender set, both directions confirmed against the
values the host actually returned:

    page 11, /Rotate 0    view_y = H - raw_y - h
        rect "1125 583 8 8" -> list y 1093, and 1684 - 583 - 8 = 1093
    page 12, /Rotate 180  view_x = W - raw_x - w
        rect "813.1 985.8 8 8" -> list x 1562.9, and 2384 - 813.1 - 8 = 1562.9

That single rule explains why sheet 11 was uniquely bad in this set: it is the
only /Rotate 0 page, so its discrepancy falls on y - the axis every band, edge
profile and invert reading is reasoned about - while on every /Rotate 180 page
it falls harmlessly on x, where nobody was comparing.

Rule of thumb for an operator: WRITE with set_markup_shape rect, READ BACK with
get_markup_shape, and RENDER from that. Treat `list_markups_in_pdf` x/y as a
label for a human, never as an input to geometry. If you must use one of the
view-frame numbers, run it through `view_to_raw` first.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "HostFrameError",
    "Rect",
    "parse_rect",
    "format_rect",
    "raw_to_view",
    "view_to_raw",
    "raw_centre",
    "rect_from_centre",
]

_ALLOWED_ROTATIONS = (0, 90, 180, 270)


class HostFrameError(ValueError):
    """A frame conversion was asked for something it cannot answer honestly."""


@dataclass(frozen=True)
class Rect:
    """A markup rectangle: lower-left x/y plus size, in whichever frame you say."""

    x: float
    y: float
    width: float
    height: float

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.x, self.y, self.width, self.height)


def parse_rect(value: str) -> Rect:
    """Parse the host's `"x y width height"` rect string."""
    parts = value.split()
    if len(parts) != 4:
        raise HostFrameError(f"a rect needs 4 values, got {len(parts)}: {value!r}")
    try:
        x, y, w, h = (float(p) for p in parts)
    except ValueError as exc:
        raise HostFrameError(f"non-numeric rect: {value!r}") from exc
    if w < 0 or h < 0:
        raise HostFrameError(f"negative extent in rect: {value!r}")
    return Rect(x, y, w, h)


def format_rect(rect: Rect, *, precision: int = 1) -> str:
    """Render a Rect back into the host's rect string."""
    return " ".join(f"{v:.{precision}f}".rstrip("0").rstrip(".") or "0" for v in rect.as_tuple())


def _check(page_width: float, page_height: float, rotation: int) -> None:
    if page_width <= 0 or page_height <= 0:
        raise HostFrameError("page width and height must be positive")
    if rotation not in _ALLOWED_ROTATIONS:
        raise HostFrameError(
            f"rotation {rotation} is not one of {_ALLOWED_ROTATIONS}; "
            "read it from the page rather than assuming 180"
        )
    if rotation in (90, 270):
        raise HostFrameError(
            "90/270 rotation swaps the page axes and has not been measured against "
            "this host; do not guess a conversion for it"
        )


def raw_to_view(rect: Rect, page_width: float, page_height: float, rotation: int) -> Rect:
    """RAW (bottom-left, unrotated) -> VIEW (top-left, as displayed).

    This is what `list_markups_in_pdf` will report for a markup whose stored
    rect is `rect`.
    """
    _check(page_width, page_height, rotation)
    if rotation == 0:
        return Rect(rect.x, page_height - rect.y - rect.height, rect.width, rect.height)
    return Rect(page_width - rect.x - rect.width, rect.y, rect.width, rect.height)


def view_to_raw(rect: Rect, page_width: float, page_height: float, rotation: int) -> Rect:
    """VIEW (top-left, as displayed) -> RAW (bottom-left, unrotated).

    Both conversions are involutions, so this is the same arithmetic; it is a
    separate name so that call sites say which direction they meant.
    """
    return raw_to_view(rect, page_width, page_height, rotation)


def raw_centre(rect: Rect) -> tuple[float, float]:
    """Centre of a rect, in whatever frame the rect is already in."""
    return (rect.x + rect.width / 2.0, rect.y + rect.height / 2.0)


def rect_from_centre(cx: float, cy: float, size: float = 8.0) -> Rect:
    """The rect for a point marker centred on `(cx, cy)`.

    Point markers are the ones that hide placement errors: a host thumbnail
    auto-zooms to the markup, so an 8 pt square fills the frame with no
    surrounding drawing and looks correct wherever it is.
    """
    if size <= 0:
        raise HostFrameError("a marker needs a positive size")
    return Rect(cx - size / 2.0, cy - size / 2.0, size, size)
