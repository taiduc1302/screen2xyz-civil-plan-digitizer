#!/usr/bin/env python3
"""Executed probes for four findings against `task/plan-layer-extraction`.

Every claim in `PLAN_LAYER_EXTRACTION_FINDINGS.md` is produced by this script.
Nothing here reads a tender drawing: the PDFs are built inline from a few
hundred bytes of content stream, so the evidence is reproducible on any
machine and carries no project data.

Usage
-----
    python docs/audit/plan_layer_probes.py [--src PATH_TO/src]

`--src` points at a checkout that carries `screen2xyz_civil.layer_chains`
(the plan-layer branch). Probes C and D are skipped when it does not.
Probes A and B need only `pymupdf`.
"""

from __future__ import annotations

import argparse
import math
import sys
import tempfile
from pathlib import Path

MEDIA = (0.0, 0.0, 612.0, 792.0)


def build_pdf(path: Path, media, crop=None, rotate: int = 0) -> None:
    """A one-page PDF with a line at user-space (100,100)-(100,200)."""
    content = b"1 w 0 G\n100 100 m 100 200 l S\n"
    crop_entry = ("/CropBox [%g %g %g %g]" % crop) if crop else ""
    rotate_entry = ("/Rotate %d" % rotate) if rotate else ""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            "<< /Type /Page /Parent 2 0 R /MediaBox [%g %g %g %g] %s %s "
            "/Contents 4 0 R /Resources << >> >>" % (media + (crop_entry, rotate_entry))
        ).encode(),
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"endstream",
    ]
    out = bytearray(b"%PDF-1.7\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    startxref = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1) + b"0000000000 65535 f \n"
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        startxref,
    )
    path.write_bytes(bytes(out))


def length(points) -> float:
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def probe_a_cropbox(tmp: Path) -> None:
    """A. A CropBox offset silently displaces every vector-derived coordinate."""
    import pymupdf

    print("=" * 74)
    print("A. CropBox offset vs the raw markup frame")
    print("   A line is drawn at user-space (100,100)-(100,200) on every page.")
    for label, crop, rotate in (
        ("CropBox == MediaBox, rot 0", None, 0),
        ("CropBox inset 20/30, rot 0", (20.0, 30.0, 592.0, 762.0), 0),
        ("CropBox inset 20/30, rot 180", (20.0, 30.0, 592.0, 762.0), 180),
    ):
        pdf = tmp / "probe_a.pdf"
        build_pdf(pdf, MEDIA, crop, rotate)
        document = pymupdf.open(str(pdf))
        page = document[0]
        displayed = []
        for drawing in page.get_drawings():
            for item in drawing["items"]:
                if item[0] == "l":
                    displayed += [(item[1].x, item[1].y), (item[2].x, item[2].y)]
        # what vector_fill.raw_frame does: y -> page.rect.height - y
        height = float(page.rect.height)
        got = [(x, height - y) for x, y in displayed]
        want = [(100.0, 100.0), (100.0, 200.0)]
        print("   " + "-" * 68)
        print("   %s" % label)
        print("     page.rect %s   mediabox %s" % (page.rect, page.mediabox))
        print("     get_drawings()        -> %s" % [(round(a, 2), round(b, 2)) for a, b in displayed])
        print("     raw_frame(page.rect)  -> %s" % [(round(a, 2), round(b, 2)) for a, b in got])
        print("     user-space truth      -> %s" % want)
        print("     ERROR (pt)            -> %s"
              % [(round(g[0] - w[0], 2), round(g[1] - w[1], 2)) for g, w in zip(got, want)])
        document.close()
    print()


def probe_b_clip_origin(tmp: Path) -> None:
    """B. get_pixmap snaps the clip to whole pixels; the assumed origin is off."""
    import pymupdf

    print("=" * 74)
    print("B. RenderFrame assumes the pixmap starts exactly at clip[0], clip[1]")
    pdf = tmp / "probe_b.pdf"
    build_pdf(pdf, MEDIA)
    document = pymupdf.open(str(pdf))
    page = document[0]
    for dpi, clip in (
        (90, (100.3, 200.7, 300.3, 400.7)),
        (90, (100.0, 200.0, 300.0, 400.0)),
        (150, (100.3, 200.7, 300.3, 400.7)),
    ):
        zoom = dpi / 72.0
        pixmap = page.get_pixmap(
            matrix=pymupdf.Matrix(zoom, zoom), clip=pymupdf.Rect(*clip), alpha=False
        )
        irect = tuple(pixmap.irect)
        origin_x, origin_y = irect[0] / zoom, irect[1] / zoom
        print("   dpi=%3d clip=%s" % (dpi, clip))
        print("     requested %.3f x %.3f px -> actual %d x %d px ; irect=%s"
              % ((clip[2] - clip[0]) * zoom, (clip[3] - clip[1]) * zoom,
                 pixmap.w, pixmap.h, irect))
        print("     origin (%.4f, %.4f) pt   assumed (%.4f, %.4f) pt   ERROR (%+.4f, %+.4f) pt"
              % (origin_x, origin_y, clip[0], clip[1],
                 origin_x - clip[0], origin_y - clip[1]))
        print("     points_per_pixel = %.4f pt, so the error is up to one whole pixel"
              % (72.0 / dpi))
    document.close()
    print()


def probe_c_dedupe(chain_fragments) -> None:
    """C. dedupe_fragments compares endpoints only, never the path between them."""
    print("=" * 74)
    print("C. A shape drawn as two polylines A->B loses one of them")
    top = [(0.0, 0.0), (10.0, 6.0), (30.0, 6.0), (40.0, 0.0)]
    bottom = [(0.0, 0.0), (10.0, -6.0), (30.0, -6.0), (40.0, 0.0)]
    truth = length(top) + length(bottom)
    report = chain_fragments([top, bottom])
    print("   top side %.2f pt + bottom side %.2f pt = %.2f pt of drawn line"
          % (length(top), length(bottom), truth))
    print("   -> fragments_used=%d duplicates_removed=%d total_length=%.2f pt"
          % (report["fragments_used"], report["duplicates_removed"], report["total_length"]))
    print("   -> UNDER-COUNT %.2f pt (%.0f%%), with no finding raised"
          % (truth - report["total_length"], 100.0 * (truth - report["total_length"]) / truth))
    print()


def probe_d_gap_tolerance(chain_fragments, nearest_gap_stats) -> None:
    """D. `p90` is the maximum for any layer of ten fragments or fewer."""
    print("=" * 74)
    print("D. nearest_gap_stats: gaps[int(n*0.9)] is the maximum while n <= 10")
    for n in (5, 8, 10, 20, 404):
        gaps = list(range(1, n + 1))
        index = min(n - 1, int(n * 0.9))
        print("   n=%3d -> p90 = gaps[%d] = %d, max = %d%s"
              % (n, index, gaps[index], gaps[-1],
                 "   <-- p90 IS the max" if gaps[index] == gaps[-1] else ""))
    fragments = [[(x, 0.0), (x + 10.0, 0.0)] for x in (0.0, 12.0, 24.0, 36.0)]
    fragments.append([(300.0, 0.0), (310.0, 0.0)])  # a separate line, 254 pt away
    report = chain_fragments(fragments)
    drawn = sum(length(f) for f in fragments)
    print("   5 fragments: a run of 4 dashes, plus one separate line 254 pt away")
    print("     gap_stats = %s" % {k: round(v, 2) for k, v in report["gap_stats"].items()})
    print("     auto gap_tol = %.2f pt" % report["gap_tol"])
    print("     chains = %d (correct: 2)   total_length = %.2f pt (drawn line = %.2f pt)"
          % (len(report["chains"]), report["total_length"], drawn))
    print()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", default=str(Path(__file__).resolve().parents[2] / "src"))
    args = parser.parse_args()

    try:
        import pymupdf  # noqa: F401
    except ImportError:
        print("pymupdf is not installed; probes A and B cannot run.")
        return 2

    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        probe_a_cropbox(tmp)
        probe_b_clip_origin(tmp)

    sys.path.insert(0, args.src)
    try:
        from screen2xyz_civil.layer_chains import chain_fragments, nearest_gap_stats
    except ImportError:
        print("=" * 74)
        print("C/D skipped: screen2xyz_civil.layer_chains is not in %s" % args.src)
        print("   Point --src at a checkout of task/plan-layer-extraction.")
        return 0
    probe_c_dedupe(chain_fragments)
    probe_d_gap_tolerance(chain_fragments, nearest_gap_stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
