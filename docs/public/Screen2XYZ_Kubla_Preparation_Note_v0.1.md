# Screen2XYZ Kubla Preparation Note v0.1

| Field | Value |
|---|---|
| Scope | Documentation-only preparation note |
| Automated integration | Not implemented |
| Import test | Not executed |
| Compatibility conclusion | None |
| Output classification | Conceptual and preliminary estimating data only. |

The laboratory writes `points_source_xyz.txt` only as a deterministic source-coordinate XYZ demonstration:

- `X = longitude`;
- `Y = latitude`;
- `Z = elevation_m`;
- horizontal CRS label `EPSG:4326`;
- axis handling `longitude_latitude`;
- elevation unit metres;
- vertical reference `SYNTHETIC_LOCAL`.

These X/Y values are geographic degrees. They are not proven suitable for Kubla or any downstream import workflow. No coordinate transformation was performed, no import was attempted, and no compatibility or ready-to-use claim is made.

Any future import evaluation requires a separately approved task that selects a controlled target coordinate reference, preserves source/target metadata, creates an appropriate transformed test artifact, and retains actual import evidence. This note does not authorize that work.

Conceptual and preliminary estimating data only.
