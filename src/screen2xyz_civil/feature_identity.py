"""What told you this is the feature, and what told you where its edge is.

Two failures on DEMO-001 had the same shape, and neither was visible in any
coordinate:

* An angle filter kept strokes at 30-60/120-150 degrees. That correctly found
  the hatch and silently discarded the region's horizontal **outline**, drawn
  in the same pen. The boundary could then only ever be the hatch envelope.
  **The filter that found the item defined its edge, and so hid its line.**
* Five arcs were identified by least-squares radius: 10.00 m against a printed
  10.0, rms 0.01 pt. One of them was the storm line and two gas lines.
  Utilities are laid concentric with the curb, so they share its centre and
  radius. **A geometric match is evidence, not identification.**

Both passed every numeric check. So the gate here is not on geometry, it is on
provenance: name the thing in the drawing that told you what this feature is,
and separately name the thing that told you where its boundary runs. A pen you
chose is neither.

The ranking is not about confidence. It is about what a source can *do*: a
legend swatch and a callout leader say what a thing IS; a printed station,
dimension or table row fixes WHERE it runs; a pen or a curve fit can only
narrow a field of candidates.
"""

from __future__ import annotations

from typing import Any, Iterable

# --- what can identify a feature -------------------------------------------

#: The sheet's own legend names this pattern, colour or symbol.
LEGEND_SWATCH = "LEGEND_SWATCH"
#: A callout leader whose arrow ends on the feature names it. A leader points
#: where its arrow ends - that is the drawing telling you which one it means.
CALLOUT_LEADER = "CALLOUT_LEADER"
#: A printed station and offset, or a printed dimension, fixing its position.
PRINTED_STATION_OFFSET = "PRINTED_STATION_OFFSET"
#: A row of a printed table on the sheet set (curb returns, drainage).
DRAWING_TABLE = "DRAWING_TABLE"
#: The drawing's own vector outline object for the region.
DRAWN_OUTLINE = "DRAWN_OUTLINE"
#: A colour, line width or angle filter that the operator chose.
PEN_ONLY = "PEN_ONLY"
#: A radius, length or area that matches a printed value.
GEOMETRIC_FIT = "GEOMETRIC_FIT"

#: Sources that can say what a feature is.
NAMES_THE_FEATURE = frozenset({LEGEND_SWATCH, CALLOUT_LEADER, DRAWING_TABLE})
#: Sources that can say where it runs.
FIXES_THE_POSITION = frozenset({PRINTED_STATION_OFFSET, DRAWN_OUTLINE, DRAWING_TABLE})
#: Sources that only narrow a field of candidates. Never sufficient alone.
NARROWS_ONLY = frozenset({PEN_ONLY, GEOMETRIC_FIT})

ALL_SOURCES = NAMES_THE_FEATURE | FIXES_THE_POSITION | NARROWS_ONLY


class FeatureIdentityError(ValueError):
    """An identification claim was malformed."""


def _check(sources: Iterable[str], field: str) -> list[str]:
    rows = [str(s).strip().upper() for s in sources if str(s).strip()]
    if not rows:
        raise FeatureIdentityError(f"{field} must name at least one source")
    unknown = [s for s in rows if s not in ALL_SOURCES]
    if unknown:
        raise FeatureIdentityError(
            f"{field} has unknown source(s) {unknown}; use one of {sorted(ALL_SOURCES)}"
        )
    return rows


def _finding(code: str, detail: str, *, blocking: bool) -> dict[str, Any]:
    return {"code": code, "severity": "ERROR" if blocking else "WARNING",
            "detail": detail, "blocking": blocking}


def identification_report(
    *,
    identified_by: Iterable[str],
    boundary_from: Iterable[str] | None = None,
    is_a_boundary: bool = True,
) -> dict[str, Any]:
    """Is this feature identified, and does its boundary come from elsewhere?

    `identified_by` says what told you this is the feature. `boundary_from`
    says what told you where its edge runs; omit it for a count or a marker,
    where `is_a_boundary=False`.

    Blocking when the identification cannot name the feature at all, when the
    boundary rests on a pen or on nothing that fixes a position, and when one
    thing you *derived* is the sole basis for both. A printed source shared
    between the two is fine: a table's row label and its length column are two
    independently checkable facts, not one derivation used twice.
    """

    identity = _check(identified_by, "identified_by")
    findings: list[dict[str, Any]] = []

    if not (set(identity) & NAMES_THE_FEATURE):
        weak = sorted(set(identity) & NARROWS_ONLY)
        findings.append(_finding(
            "FEATURE_NOT_IDENTIFIED",
            f"identified only by {weak or sorted(identity)}. A pen you chose and a curve that "
            "fits a printed number narrow the candidates; neither says which feature this is. "
            "Five arcs once matched a printed 10.0 m radius to 0.01 pt and one was the storm "
            "line - utilities run concentric with the curb. Name a legend swatch, a callout "
            "leader whose arrow ends on it, or a table row.",
            blocking=True,
        ))

    boundary: list[str] = []
    if is_a_boundary:
        if boundary_from is None:
            raise FeatureIdentityError(
                "boundary_from is required when is_a_boundary is true; say what told you "
                "where the edge runs, or set is_a_boundary=False for a count or marker"
            )
        boundary = _check(boundary_from, "boundary_from")

        if PEN_ONLY in boundary:
            findings.append(_finding(
                "BOUNDARY_FROM_A_PEN",
                "the boundary comes from a colour, width or angle filter. A pattern's extent "
                "oscillates at its own pitch and a mask lands on a pixel edge; neither is the "
                "line the drawing draws. Take it from the region's own outline object, a "
                "printed dimension, or a station and offset.",
                blocking=True,
            ))
        if not (set(boundary) & FIXES_THE_POSITION):
            findings.append(_finding(
                "BOUNDARY_NOT_FIXED_BY_THE_DRAWING",
                f"nothing in {sorted(set(boundary))} fixes where the edge runs. A legend swatch "
                "says what a thing is, not where it stops.",
                blocking=True,
            ))
        # The hazard is one **derivation** both finding the item and drawing its
        # edge, because then an error in that derivation is invisible - the
        # angle filter that found the hatch and discarded the outline drawn in
        # the same pen. A printed source is not a derivation: sheet 07's curb
        # return table names the return in its row label and gives its length
        # in a separate printed column, and the two are independently checkable
        # (they were, three ways, worst discrepancy 6 mm). So this fires only
        # when the shared source is something the operator derived.
        shared = set(identity) & set(boundary)
        if shared and shared <= NARROWS_ONLY and set(identity) == set(boundary):
            findings.append(_finding(
                "SAME_DERIVATION_IDENTIFIES_AND_BOUNDS",
                f"identity and boundary both rest on {sorted(shared)} alone, which you derived "
                "rather than read. An angle filter that correctly found the hatch discarded the "
                "outline drawn in the same pen, so the edge could only be the hatch envelope - "
                "one derivation, two uses, and no way for its error to show.",
                blocking=True,
            ))

    return {
        "identified_by": identity,
        "boundary_from": boundary,
        "is_a_boundary": is_a_boundary,
        "names_the_feature": sorted(set(identity) & NAMES_THE_FEATURE),
        "fixes_the_position": sorted(set(boundary) & FIXES_THE_POSITION),
        "findings": findings,
        "blocking": any(f["blocking"] for f in findings),
        "safe_to_write": not any(f["blocking"] for f in findings),
    }
