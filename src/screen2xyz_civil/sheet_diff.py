"""What changed between two issues of a sheet, layer by layer.

An addendum re-issues a sheet and the takeoff already done on the old one is
now suspect. A person answers "what changed" by hunting for revision clouds;
a layered PDF answers it directly: every drawing object carries its layer,
so objects that exist in one issue and not the other can be listed per
layer with their positions, and a count table says where to look first.

Two functions:

* ``match_revised_sheet`` - an addendum's "Sheet 10" is not the base PDF's
  page 10 (DEMO-001's base page 10 is a cross-section sheet). The right base
  page is the one whose layer signature matches.
* ``diff_pages`` - per layer: objects only in A, only in B, unchanged, by a
  geometry signature (rounded raw-frame points, stroke, fill). Positions are
  raw-frame boxes, ready for a render window or a markup flag.

Signature matching is exact after rounding, so a line moved by more than the
rounding step counts as removed-and-added. That is the honest reading: the
tool says *where* something differs; whether it is a move, a redraw or a
new item is read from the sheet.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable

from .cad_layers import objects_on_layer, short_name

#: Points are rounded to this many decimals before comparison (0.1 pt).
ROUND = 1


def _signature(obj: dict[str, Any]) -> tuple:
    pts = tuple((round(x, ROUND), round(y, ROUND)) for x, y in obj["points_raw"])
    if pts and pts[0] > pts[-1]:
        pts = pts[::-1]  # orientation-free
    stroke = tuple(round(v, 3) for v in obj["stroke"]) if obj.get("stroke") else None
    fill = tuple(round(v, 3) for v in obj["fill"]) if obj.get("fill") else None
    return (pts, stroke, fill, round(obj.get("width") or 0, 2))


def layer_counts(doc: Any, page_index: int) -> Counter:
    """Objects per short layer name on one page."""

    c: Counter = Counter()
    for d in doc[page_index].get_drawings():
        c[short_name(d.get("layer") or "(none)")] += 1
    return c


def signature_similarity(a: Counter, b: Counter) -> float:
    """0..1: how alike two pages' layer tables are.

    Weighted Jaccard over layer names with counts, so a page sharing most
    layers *and* similar object counts scores high, and a page sharing only
    the title-block layers scores low.
    """

    keys = set(a) | set(b)
    if not keys:
        return 0.0
    num = sum(min(a.get(k, 0), b.get(k, 0)) for k in keys)
    den = sum(max(a.get(k, 0), b.get(k, 0)) for k in keys)
    return num / den if den else 0.0


def match_revised_sheet(
    rev_doc: Any, rev_page: int, base_doc: Any, *, candidates: Iterable[int] | None = None
) -> dict[str, Any]:
    """Which base page is this revised sheet a new issue of?

    Returns the best page by layer-signature similarity and the full ranked
    list, so a close second is visible rather than silently discarded.
    """

    rev = layer_counts(rev_doc, rev_page)
    pages = list(candidates) if candidates is not None else list(range(base_doc.page_count))
    ranked = sorted(
        ((signature_similarity(rev, layer_counts(base_doc, p)), p) for p in pages),
        key=lambda t: (-t[0], t[1]),
    )
    best_score, best_page = ranked[0]
    second = ranked[1][0] if len(ranked) > 1 else 0.0
    return {
        "revised_page": rev_page,
        "base_page": best_page,
        "similarity": best_score,
        "runner_up": ranked[1][1] if len(ranked) > 1 else None,
        "runner_up_similarity": second,
        "ambiguous": best_score - second < 0.1,
        "ranked": [(p, round(s, 3)) for s, p in ranked],
    }


def _bbox(objs: list[dict[str, Any]]) -> tuple[float, float, float, float] | None:
    if not objs:
        return None
    xs0 = [o["rect_raw"][0] for o in objs]
    ys0 = [o["rect_raw"][1] for o in objs]
    xs1 = [o["rect_raw"][2] for o in objs]
    ys1 = [o["rect_raw"][3] for o in objs]
    return (min(xs0), min(ys0), max(xs1), max(ys1))


def diff_pages(
    doc_a: Any, page_a: int, doc_b: Any, page_b: int, *, layers: Iterable[str] | None = None
) -> dict[str, Any]:
    """Objects only in A, only in B and common, per layer, by geometry signature.

    ``layers`` restricts the comparison to short layer names; default is every
    layer present on either page. Each layer row carries the counts, the
    changed objects with raw-frame boxes, and the bounding box of the change
    - the window to render and look at.
    """

    ca, cb = layer_counts(doc_a, page_a), layer_counts(doc_b, page_b)
    names = sorted(set(layers) if layers is not None else set(ca) | set(cb))
    rows: list[dict[str, Any]] = []
    for name in names:
        if name == "(none)":
            continue
        oa = objects_on_layer(doc_a, page_a, name)
        ob = objects_on_layer(doc_b, page_b, name)
        sa: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
        sb: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
        for o in oa:
            sa[_signature(o)].append(o)
        for o in ob:
            sb[_signature(o)].append(o)
        only_a: list[dict[str, Any]] = []
        only_b: list[dict[str, Any]] = []
        common = 0
        for sig in set(sa) | set(sb):
            na, nb = len(sa.get(sig, [])), len(sb.get(sig, []))
            common += min(na, nb)
            if na > nb:
                only_a.extend(sa[sig][nb:])
            elif nb > na:
                only_b.extend(sb[sig][na:])
        if not only_a and not only_b and not (oa or ob):
            continue
        rows.append({
            "layer": name,
            "count_a": len(oa),
            "count_b": len(ob),
            "common": common,
            "only_in_a": [{"rect_raw": o["rect_raw"], "kind": o["kind"], "points": len(o["points_raw"])} for o in only_a],
            "only_in_b": [{"rect_raw": o["rect_raw"], "kind": o["kind"], "points": len(o["points_raw"])} for o in only_b],
            "changed_bbox_a": _bbox(only_a),
            "changed_bbox_b": _bbox(only_b),
            "unchanged": not only_a and not only_b,
        })
    changed = [r for r in rows if not r["unchanged"]]
    changed.sort(key=lambda r: -(len(r["only_in_a"]) + len(r["only_in_b"])))
    return {
        "page_a": page_a,
        "page_b": page_b,
        "layers_compared": len(rows),
        "layers_changed": len(changed),
        "rows": rows,
        "changed": changed,
    }


def diff_report(diff: dict[str, Any], *, top: int = 20) -> str:
    """A short text table of the changed layers, biggest change first."""

    lines = [f"layers compared {diff['layers_compared']}, changed {diff['layers_changed']}",
             f"{'layer':<28} {'A':>6} {'B':>6} {'only A':>7} {'only B':>7}  change box (B, raw)"]
    for r in diff["changed"][:top]:
        box = r["changed_bbox_b"] or r["changed_bbox_a"]
        boxs = "(" + ", ".join(f"{v:.0f}" for v in box) + ")" if box else "-"
        lines.append(f"{r['layer']:<28} {r['count_a']:>6} {r['count_b']:>6} "
                     f"{len(r['only_in_a']):>7} {len(r['only_in_b']):>7}  {boxs}")
    return "\n".join(lines)
