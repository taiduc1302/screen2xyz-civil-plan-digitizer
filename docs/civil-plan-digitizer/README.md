# Civil Plan Digitizer User Guide

Status: local feature-branch implementation; preliminary estimator workflow;
not merged, released, or downstream-certified.

> All PDF/image-derived coordinates and elevations are preliminary and require
> estimator or survey review. They are not certified survey data.

## Install and launch

From the repository root on Windows:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-civil.txt
powershell -ExecutionPolicy Bypass -File .\run_civil_plan_digitizer.ps1
```

The guaranteed manual PNG workflow uses the Python standard library and
Tkinter. PDF inspection needs the pinned `pypdf` dependency. PDF page
rendering also needs a local `pdftoppm` executable from Poppler on `PATH`.
Windows Media OCR is invoked locally through a bounded PowerShell adapter.
Nothing is sent to a network service.

You can also choose **Civil Plan Digitizer** from
`run_screen2xyz_menu.ps1`.

## Recommended first project

1. Choose **New from PDF/PNG** and a local plan.
2. For a PDF, choose one page; Screen2XYZ renders only that page.
3. Drag the analysis crop around the civil plan area. Exclude the title block,
   legend, profiles, cross-sections, notes, and other metadata.
4. Calibrate with two endpoints of a known horizontal plan distance, then set
   the local origin and click a point in the positive-East direction.
5. Enter optional local East/North origin offsets. These remain local
   coordinates; no coordinate reference system is inferred.
6. Use **Verify second distance** on a separate known dimension.
7. Add manual points, or run vector PDF extraction/local OCR to create
   candidates.
8. Review each candidate. Correct the elevation, class, or marker association;
   then explicitly approve or reject it.
9. Add reviewed boundary, exclusion, breakline, or no-cross geometry if a
   preliminary surface is needed.
10. Run **QA summary**, save the `.s2c.json` project, and export a new
    versioned handoff folder.

## Review controls

- `A`: approve selected point.
- `R`: reject selected point.
- `E`: classify selected point as Existing Ground.
- `D`: classify selected point as Design Grade.
- `M`: add a manual point.
- Up/Down: select adjacent candidate.
- Delete: delete an explicitly manual point after confirmation.
- Escape: cancel the active canvas tool.
- **Use next association**: cycle an extracted label through recorded symbol
  alternatives; this returns the point to review.

Editing, moving, reclassifying, or changing an association invalidates prior
approval. Recalibration creates a revision, recomputes local coordinates, and
marks prior exports stale.

## Detection behavior

Extraction proposes candidates; it never silently approves them. Percentages,
dates, drawing scales, station notation, title-block metadata, and utility or
slab annotations are not exported as terrain points by default. A cross
proposes Existing Ground; an oval proposes Design Grade. Ambiguous text,
unassociated decimals, and uncertain markers remain review-required.

See `DETECTION_RULES.md` for the exact first-pass rules.

## Surface preview

Existing and Design TINs are built and displayed separately from explicitly
approved points. The preview honors reviewed boundaries, exclusion polygons,
no-cross lines, disabled triangles, and breakline barriers. Long or steep
triangles are flagged. Breaklines are not yet inserted as constrained TIN
edges, and the cut/fill view is point-sampled elevation delta only—not a volume
or quantity calculation.

LandXML export is off by default. It requires a reviewed boundary, enough
approved points for a surface, and an explicit in-project acceptance of the
preliminary triangulation.

## Project and export data

Projects are schema-versioned `.s2c.json` files saved atomically. Source image
coordinates, extraction reasons, alternatives, review history, calibration
revisions, decisions, QA results, and export history are retained. Export
manifests redact the source's local path.

The versioned handoff contains approved terrain points only. Existing and
Design CSV files remain separate. See `AGTEK_WORKFLOW.md` and
`QA_CHECKLIST.md` before importing anything.
