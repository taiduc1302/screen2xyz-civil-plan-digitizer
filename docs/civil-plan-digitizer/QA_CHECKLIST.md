# Civil Plan Digitizer QA Checklist

Use this checklist for every project. An application-generated PASS is not a
substitute for estimator or survey review.

## Source and scope

- [ ] The drawing is authorized for local use.
- [ ] Correct PDF page/revision and intended work area are selected.
- [ ] Crop excludes title block, legend, schedules, profiles, cross-sections,
      notes, revision tables, and irrelevant utilities.
- [ ] Source hash/display name and page selection are recorded.

## Calibration

- [ ] Units are confirmed as metres for this workflow.
- [ ] The primary known distance uses unambiguous endpoints.
- [ ] Local origin offset is intentional.
- [ ] Positive-East direction is visually confirmed.
- [ ] A separate second-distance check is recorded and within the project
      tolerance, or its warning has a documented disposition.
- [ ] Recalibration history and stale-export indicator have been reviewed.

## Points and classification

- [ ] Every exported point is explicitly approved.
- [ ] Existing and Design points were reviewed separately.
- [ ] Candidate text, source box, marker location, elevation, type, and reasons
      agree with the drawing.
- [ ] Alternative symbol associations were inspected where ambiguous.
- [ ] Percent grades, dates, scales, station labels, utilities, slab/FFE, and
      drawing metadata are excluded from terrain export.
- [ ] Duplicates and conflicting elevations are merged/rejected or explained.
- [ ] No approved point is outside the reviewed crop or plausible range.

## Surface controls

- [ ] Existing and Design previews were inspected separately.
- [ ] Boundary is reviewed and closes the intended work area.
- [ ] Exclusion polygons cover intentional holes only.
- [ ] Breaklines/no-cross lines are explicitly drawn; none were inferred.
- [ ] Long and steep triangles were inspected.
- [ ] Incorrect triangles were disabled and the result rechecked.
- [ ] The reviewer understands that breaklines are barriers, not constrained
      inserted edges in this version.
- [ ] Cut/fill samples are not treated as volumes or quantities.
- [ ] Preliminary LandXML acceptance is recorded only after the above review.

## Export and downstream gate

- [ ] QA summary has no critical export blocker.
- [ ] Coordinate extents and counts are plausible.
- [ ] A new versioned export folder was created.
- [ ] Existing and Design file counts match expectations.
- [ ] Source local path is absent from the handoff.
- [ ] Hash manifest verifies before downstream use.
- [ ] Import was tested in a non-production project with explicit units and
      column mapping.
- [ ] Known controls and spot elevations were checked after import.
- [ ] Qualified estimator/survey disposition is recorded outside Screen2XYZ.
