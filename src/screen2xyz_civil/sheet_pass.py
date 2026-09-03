"""One repeatable opening pass over a new plan sheet.

`PLAN_SHEET_LAYER_METHOD.md` documents thirteen steps. Steps 0-4 - render the
page with anti-aliasing off, take an exact-colour census, subtract the title
block, and say which known layers are actually present - are mechanical, and
until now each sheet re-derived them by hand. That is most of what made a sheet
cost a full session: Sheet 03 took one because the method was being invented on
it, but sheets 04-06 carry the same two layers and should be a re-run, not a
re-derivation.

This module does not measure anything. It hands back what the operator needs
before measuring, so the judgement steps (5-9: which boundary is the real one,
what the legend on *this* sheet calls each colour, where the sheet overlaps its
neighbour) get the attention instead.

The colour-to-scope names below came from the Example Road legends and are a
starting hypothesis, never an answer: `PLAN_SHEET_LAYER_METHOD.md` step 1 says
to read each sheet's legend as that sheet's own dictionary, and Sheet 04 proved
it by carrying three entries Sheet 03 does not.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from .plan_layers import Viewport, colour_census


class SheetPassError(RuntimeError):
    """A sheet could not be opened for measurement."""


# Produced by `derive_title_block_baseline` over the eleven drawing sheets of
# DEMO-001 (pages 3-13) at 90 DPI, 2026-09-03. Every sheet carries the same title
# block and logos, so the smallest count a colour reaches anywhere in the set is
# the part of it that is furniture rather than drawing.
#
# Derived, not transcribed. The first version of this table was typed from the
# prose in PLAN_SHEET_LAYER_METHOD.md ("near-black 4887 | green-Example Contractor
# 2951 | blue 2573 | cyan 1485"), which named the colours by description; the
# RGB values guessed from those names were wrong on five of seven entries, so
# the table matched nothing and suppressed nothing. The counts were right and
# the keys were fiction. Re-run the derivation for a new drawing set rather
# than adapting this one.
TITLE_BLOCK_BASELINE: dict[tuple[int, int, int], int] = {
    (255, 255, 255): 5031747,  # paper
    (0, 0, 0): 113630,  # linework floor
    (34, 31, 31): 4771,  # title-block text
    (83, 83, 83): 3852,  # also a real layer on the storm sheets, at 16x this
    (0, 114, 57): 2921,  # consultant logo green
    (0, 0, 255): 2511,
    (0, 165, 221): 1485,
    (127, 127, 127): 1208,  # also a real hatch layer elsewhere, at up to 20x
    (55, 221, 0): 1197,
    (228, 142, 38): 427,
    (44, 44, 44): 426,
    (101, 102, 102): 303,
    (209, 210, 211): 281,
}

# Starting hypothesis only - confirm against the sheet's own legend. Sheet 04
# carries three entries Sheet 03 does not, and reading only Sheet 03's is what
# turned ditch infill into "landscape/sod".
KNOWN_LAYERS: dict[tuple[int, int, int], str] = {
    (255, 255, 255): "paper",
    (0, 0, 0): "linework - not a fill layer",
    (229, 229, 229): "40mm MILL AND OVERLAY (solid fill)",
    (128, 128, 128): "ROAD WIDENING FULL ROAD STRUCTURE (X-hatch)",
    (127, 127, 127): "hatch - read this sheet's legend for which hatch",
    (255, 255, 0): "PAVEMENT MARKINGS",
    (0, 127, 0): "DITCH INFILL (green dotted) - Sheet 04 legend",
    (83, 83, 83): "unidentified grey-83 layer - present on storm sheets only",
}

BASELINE_TOLERANCE = 1.5

# At 90 DPI one pixel is 0.28 mm on paper, which at 1:250 is 70 mm of ground and
# 0.005 sq m of area. A thousand pixels is therefore about 5 sq m - below that a
# colour cannot be a measurable fill, and on the two storm sheets (24 000+
# distinct colours from raster content) everything below it is compression
# speckle.
MIN_LAYER_PIXELS = 1000

# A legend has a bounded number of entries, and only a few of them are greys.
# Measured over DEMO-001: the eight vector sheets clear the pixel floor with 4-9
# distinct greys and never more than two consecutive values; the two storm
# sheets clear it with 39 and 40, in unbroken runs, because they carry a
# rasterised greyscale image. Past this many, the census is reporting an image's
# tonal ramp and exact-colour separation does not apply to that sheet at all.
MAX_PLAUSIBLE_GREY_LAYERS = 15


@dataclass(frozen=True)
class LayerPresence:
    colour: tuple[int, int, int]
    count: int
    baseline: int
    above_baseline: bool
    name: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "colour": list(self.colour),
            "count": self.count,
            "baseline": self.baseline,
            "above_baseline": self.above_baseline,
            "name": self.name,
        }


def _import_pymupdf() -> Any:
    try:
        import pymupdf  # noqa: PLC0415
    except ImportError:  # pragma: no cover - environment issue, not logic
        try:
            import fitz as pymupdf  # type: ignore  # noqa: PLC0415
        except ImportError as exc:
            raise SheetPassError(
                "pymupdf is required for the sheet opening pass"
            ) from exc
    return pymupdf


def render_page_rgb(
    pdf_path: Path,
    page_index: int,
    *,
    dpi: int = 90,
    clip_points: Sequence[float] | None = None,
) -> list[tuple[int, int, int]]:
    """Render one page to exact RGB pixels with anti-aliasing disabled.

    Anti-aliasing invents intermediate colours at every edge, which turns an
    exact-colour census into noise. `clip_points` is (x0, y0, x1, y1) in PDF
    points if only one viewport should be censused.

    The return is a flat bag of pixels with no width and no row order on
    purpose. It answers "which colours are on this sheet, and how much of
    each", and cannot be used to locate anything: a clipped render does not
    share the page's coordinate frame, and reading geometry back out of one is
    a known trap on this set. Locate geometry with `plan_layers`, which works
    in page points.
    """

    pymupdf = _import_pymupdf()

    source = Path(pdf_path).expanduser().resolve()
    if not source.is_file():
        raise SheetPassError(f"sheet PDF does not exist: {source}")

    # Anti-aliasing is a process-global MuPDF setting, so it has to be put back
    # or every later render in this process silently loses it.
    previous = dict(pymupdf.TOOLS.show_aa_level())
    pymupdf.TOOLS.set_aa_level(0)
    document = None
    try:
        document = pymupdf.open(str(source))
        if not 0 <= page_index < document.page_count:
            raise SheetPassError(
                f"page index {page_index} is outside {source.name} "
                f"({document.page_count} pages)"
            )
        page = document[page_index]
        matrix = pymupdf.Matrix(dpi / 72.0, dpi / 72.0)
        clip = pymupdf.Rect(*clip_points) if clip_points is not None else None
        pixmap = page.get_pixmap(matrix=matrix, clip=clip, alpha=False)
        samples = pixmap.samples
        stride = pixmap.n
        if stride < 3:  # pragma: no cover - alpha=False always gives RGB
            raise SheetPassError(f"render returned {stride} channels, expected RGB")
        return [
            (samples[i], samples[i + 1], samples[i + 2])
            for i in range(0, len(samples), stride)
        ]
    finally:
        if document is not None:
            document.close()
        _restore_aa_level(pymupdf, previous)


def _restore_aa_level(pymupdf: Any, previous: dict[str, Any]) -> None:
    graphics = previous.get("graphics")
    text = previous.get("text")
    if graphics is None:  # pragma: no cover - defensive
        return
    pymupdf.TOOLS.set_aa_level(graphics)
    if text is not None and text != graphics:  # pragma: no cover - rare split
        try:
            pymupdf.mupdf.fz_set_text_aa_level(text)
        except Exception:
            pass


def _is_grey(colour: tuple[int, int, int]) -> bool:
    return colour[0] == colour[1] == colour[2]


def classify_grey_ramp(
    rows: Sequence[LayerPresence],
    *,
    limit: int = MAX_PLAUSIBLE_GREY_LAYERS,
) -> tuple[list[LayerPresence], bool]:
    """Tell an image's tonal ramp apart from a sheet's grey fills.

    Returns the rows that are ramp, and whether the sheet is rasterised at all.
    Below the limit nothing is reclassified: a handful of unnamed greys on a
    vector sheet are real fills somebody still has to look up in the legend, and
    quietly relabelling them as image noise would hide exactly the kind of miss
    that cost this project 978.81 sq m of mill and overlay.

    A named colour is never ramp. The named layers on the storm sheets sit at
    5 000-400 000 px, an order clear of the ramp members, and stay measurable.
    """

    candidates = [row for row in rows if _is_grey(row.colour) and not row.name]
    if len(candidates) <= limit:
        return [], False
    return candidates, True


def derive_title_block_baseline(
    pdf_path: Path,
    page_indices: Sequence[int],
    *,
    dpi: int = 90,
    min_count: int = MIN_LAYER_PIXELS,
) -> dict[tuple[int, int, int], int]:
    """Measure a drawing set's own furniture floor.

    Every sheet in a set shares a title block, logos and border. For a colour
    that appears on all of them, the smallest count it reaches anywhere is the
    part that is furniture; anything above that on a given sheet is drawing.
    This is how `TITLE_BLOCK_BASELINE` was produced, and running it is how a
    different drawing set gets its own.

    Pass only the drawing sheets. A cover or notes page shares the border but
    not the rest, and including one drags every floor down to near zero.
    """

    pages = [int(p) for p in page_indices]
    if len(pages) < 2:
        raise SheetPassError(
            "a baseline needs at least two sheets - one sheet cannot tell "
            "furniture from drawing"
        )

    floors: dict[tuple[int, int, int], int] | None = None
    for page in pages:
        counts = {
            colour: count
            for colour, count in colour_census(
                render_page_rgb(pdf_path, page, dpi=dpi)
            )
            if count >= min_count
        }
        if floors is None:
            floors = dict(counts)
            continue
        floors = {
            colour: min(floor, counts[colour])
            for colour, floor in floors.items()
            if colour in counts
        }
    return dict(sorted((floors or {}).items(), key=lambda kv: -kv[1]))


def layers_above_baseline(
    census: Iterable[Sequence[Any]],
    *,
    baseline: dict[tuple[int, int, int], int] | None = None,
    known: dict[tuple[int, int, int], str] | None = None,
    tolerance: float = BASELINE_TOLERANCE,
    min_count: int = MIN_LAYER_PIXELS,
) -> list[LayerPresence]:
    """Separate real drawing layers from title-block furniture.

    A colour is treated as a layer only when it clears both its furniture floor
    by `tolerance` and `min_count` outright. Without the floor, grey-127
    furniture at ~1 200 px reads as a hatch layer on every sheet in the set;
    without the count, the storm sheets report several hundred raster speckle
    colours as layers.
    """

    base = TITLE_BLOCK_BASELINE if baseline is None else baseline
    names = KNOWN_LAYERS if known is None else known
    rows: list[LayerPresence] = []
    for entry in census:
        colour, count = entry[0], int(entry[1])
        key = tuple(int(v) for v in colour)  # type: ignore[assignment]
        floor = base.get(key, 0)
        rows.append(
            LayerPresence(
                colour=key,  # type: ignore[arg-type]
                count=count,
                baseline=floor,
                above_baseline=count >= min_count and count > floor * tolerance,
                name=names.get(key, ""),
            )
        )
    return rows


def sheet_opening_pass(
    pdf_path: Path,
    page_index: int,
    *,
    viewport: Viewport | None = None,
    dpi: int = 90,
    top_n: int = 15,
) -> dict[str, Any]:
    """Steps 0-4 of the sheet method in one call.

    Returns what is present on the sheet and what it probably means. It
    deliberately stops before measuring: which boundary is the real one, and
    what this sheet's own legend calls each colour, are the operator's calls.
    """

    clip = None
    if viewport is not None:
        clip = (viewport.x0, viewport.y0, viewport.x1, viewport.y1)
    pixels = render_page_rgb(pdf_path, page_index, dpi=dpi, clip_points=clip)
    census = colour_census(pixels)
    present = [row for row in layers_above_baseline(census) if row.above_baseline]

    ramp, rasterised = classify_grey_ramp(present)
    ramp_colours = {row.colour for row in ramp}
    unnamed = [row for row in present if not row.name and row.colour not in ramp_colours]

    next_steps = [
        "Read this sheet's own legend and confirm every colour above - a colour "
        "that means one thing on one sheet can mean another here.",
        "Take outer boundaries from fills and inner boundaries from the drawn "
        "lines, then validate against the printed dimensions before writing.",
        "Resolve the overlap with the neighbouring sheet before summing.",
    ]
    if unnamed:
        next_steps.insert(
            0,
            f"{len(unnamed)} layer(s) present with no known meaning "
            f"({', '.join(str(row.colour) for row in unnamed)}) - identify them "
            "against this sheet's legend before measuring anything.",
        )
    if rasterised:
        next_steps.insert(
            0,
            f"This sheet carries a rasterised image: {len(ramp)} distinct greys "
            "clear the floor, in a tonal ramp. Exact-colour separation does not "
            "work here. The named layers below are still real, but do not treat "
            "an unnamed grey on this sheet as a layer, and do not derive an area "
            "from a colour mask on it.",
        )
    if not present:
        next_steps.insert(
            0,
            "No fill layer on this sheet. It is line work, so the colour-mask "
            "method does not apply - quantities here come from geometry or from "
            "printed values.",
        )
    if viewport is None:
        next_steps.append(
            "This census covered the whole page, so it mixes every view on the "
            "sheet. Declare the viewport before measuring - the set is not "
            "uniform and a plan factor used in a profile is wrong by the ratio "
            "of the two axes."
        )

    return {
        "pdf": str(Path(pdf_path).name),
        "page_index": page_index,
        "dpi": dpi,
        "viewport": None if viewport is None else viewport.name,
        "isotropic": None if viewport is None else viewport.isotropic,
        "pixels_sampled": len(pixels),
        "distinct_colours": len(census),
        "rasterised": rasterised,
        "colour_separation_reliable": not rasterised,
        "layers_present": [row.to_dict() for row in present],
        "layers_unnamed": [row.to_dict() for row in unnamed],
        "raster_ramp": [row.to_dict() for row in ramp],
        "census_top": [
            {"colour": list(colour), "count": count} for colour, count in census[:top_n]
        ],
        "measured": False,
        "next_steps": next_steps,
    }
