# Civil Candidate Detection Rules

These rules generate review proposals only. Confidence is supporting evidence,
not permission to export.

## Numeric normalization

- Trim surrounding whitespace and normalize Unicode minus/dash to `-`.
- Accept a standalone finite decimal, including sign and leading decimal.
- Convert a decimal comma only when no decimal point is also present.
- Remove internal spaces only for a constrained numeric/OCR character set and
  mark the result ambiguous.
- Convert `O`/`o` between digits to zero and mark the result ambiguous.
- Reject mixed comma/point notation and unsafe characters.
- Reject integer-only and incomplete decimal fragments as ambiguous evidence;
  do not promote them into terrain elevations.
- Reject percentages, dates, drawing scales, and station notation as
  elevations.
- Values outside the configured plausible elevation range remain unknown and
  review-required.

## Context classes

| Evidence | Proposed class | Terrain-export default |
|---|---|---|
| `%` notation | Slope Annotation | Excluded |
| `INV` or `INVERT` | Utility Invert | Excluded |
| `RIM` | Utility Rim | Excluded |
| `SLAB`, `FFE`, or `FFL` | Slab Elevation | Excluded |
| `SCALE`, `DATE`, `SHEET`, `REV`, `DRAWING` | Drawing Metadata | Excluded |
| Reviewed exclusion polygon | Drawing Metadata | Excluded |

Context classification takes precedence over terrain symbol association.

## Symbol proposals

- Closed ellipse/oval geometry proposes `DESIGN_OVAL`.
- Compact perpendicular strokes/cross geometry proposes `EXISTING_CROSS`.
- A compact closed dot/circle proposes `POINT_DOT`.
- A leader or endpoint shape provides a leader signal.
- Unrecognized paths remain unknown symbols.

PDF path interpretation is intentionally conservative and first-pass. Stroke
color and layer fields are preserved where available but are not treated as
authoritative.

## Label-to-symbol association

Each nearby symbol receives a bounded score from independently recorded
signals:

- overlap/containment;
- pixel proximity;
- expected label-on-right layout;
- leader presence;
- recognized civil symbol shape;
- optional local repeated-pattern match;
- source symbol confidence.

The best three candidates are retained in deterministic score/distance order.
The selected association and alternatives remain visible and editable. An oval
proposes Design Grade. A cross, dot, or survey-like marker proposes Existing
Ground. A plausible decimal without a reliable terrain symbol remains
review-required.

Two labels competing for the same marker are not capturable until the
association is disambiguated. Strict slope, utility, title-block, crop, and
range rejections guard nearby clicks; soft OCR fragments are retained as
evidence but do not mask a separate valid label on the same marker.

## Review state

Even a high-scoring proposal is not approved. OCR ambiguity caps confidence.
Changing an association or any point value invalidates prior approval.
Approved-only export then applies the independent terrain-relevance and QA
gates.

## Known gaps

The current rules do not learn sheet-specific symbology, infer contours from
line topology, solve overlapping leader networks, or provide measured
precision/recall on real authorized civil plans. Those require a separately
approved labelled validation set.
