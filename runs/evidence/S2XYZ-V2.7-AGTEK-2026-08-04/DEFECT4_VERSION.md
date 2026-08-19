# Defect 4 — version provenance evidence

Date: 2026-08-04  
Branch: `feature/v2.7-agtek-field-fixes`  
Baseline: `4c2ca7d`

## RED

The launcher contract was changed first to require runtime version `2.7.0` and
window title `Screen2XYZ v2.7`. Against the prior code it failed because the
runtime still returned `2.5.0`. Raw RED output is retained in
`.lab_work/v2_7_red/defect4_version_red.log`.

## GREEN

- `screen2xyz_app.__version__`: `2.7.0`.
- Application title: `Screen2XYZ v2.7`.
- Bundled quick-start heading: `Screen2XYZ v2.7 quick start`.
- Launcher tests: 6/6.
- Full application suite: 71/71 in 153.130 s.
- Civil suite: 113/113 in 2.812 s.
- M2 suite: 498/498 in 17.992 s.

No release tag was created and no prior historical measurement was relabelled.
