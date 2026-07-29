# AGTEK Handoff Workflow

Status: AGTEK-ready CSV preset for estimator review. No AGTEK import has been
executed or certified in this feature run.

## Before export

Complete the checklist in `QA_CHECKLIST.md`. In particular, confirm the units,
scale check, local origin, positive-East direction, point classes, duplicate
conflicts, and boundary/exclusion geometry. Unreviewed, rejected, utility,
slab, metadata, and slope records are excluded by default.

## Versioned handoff contents

Each export creates a new `<project>_export_<id>` directory and refuses to
overwrite an existing directory.

| File | Purpose |
|---|---|
| `Existing_Points.csv` | Approved Existing Ground points only |
| `Design_Points.csv` | Approved Design Grade points only |
| `All_Reviewed_Points.csv` | All approved terrain-relevant points with class/review/source fields |
| `Reviewed_Points.xyz` | Point ID/East/North/Elevation local-coordinate preset |
| `Reviewed_Points.nez` | Point ID/North/East/Elevation local-coordinate preset |
| `Reviewed_Points.geojson` | Local-coordinate features with non-geodetic warning |
| `Reviewed_Points.dxf` | Point and reviewed breakline entities |
| `Breaklines.geojson` | Reviewed breakline features |
| `Preliminary_Surfaces.xml` | Optional gated preliminary LandXML |
| `Calibration_Report.md` | Scale, basis, origin, revision, and second check |
| `QA_Summary.md` | Counts, issues, duplicates/conflicts, coordinate extents |
| `Project_Audit.json` | Full point/review/decision/calibration audit record |
| `Source_Manifest.json` | Source identity with local path removed |
| `Handoff_Manifest.json` | Counts, coordinate order, warnings, hashes |
| `AGTEK_Import_Instructions.md` | Package-specific import precautions |
| `MANIFEST.sha256` | File integrity manifest |

The CSV preset order is Point, Northing, Easting, Elevation, Description.
Values are metres in the user-defined local frame. A caller may explicitly
request the alternate East/North order, which is recorded in the manifest.

## Estimator import gate

1. Copy the export folder; never alter the source project as the import file.
2. Verify `MANIFEST.sha256` and read the calibration/QA reports.
3. In AGTEK, create or use a non-production test project.
4. Confirm the import column mapping, metres, local coordinate frame, point
   descriptions, and Existing versus Design destination.
5. Import Existing and Design files separately.
6. Compare at least two known control distances and spot elevations.
7. Visually inspect for axis swap, Y inversion, unit mismatch, offset, and
   duplicate points.
8. Record the application/version, mapping, discrepancies, and disposition.
9. Do not promote the output until a qualified estimator accepts it.

No current evidence supports a claim that AGTEK, Civil 3D, Kubla, or another
downstream application accepts every generated file.
