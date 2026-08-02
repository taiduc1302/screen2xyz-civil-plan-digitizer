# Screen2XYZ v2 guide

Screen2XYZ captures X/Y/Z point rows from live screen zones, a local PDF, or a local image. Start with the root README for installation.

## A typical mixed capture

1. Choose **Load PDF** or **Load image**.
2. Select a project folder and plan.
3. Map X and Y to `screen_zone_ocr`; use **Pick** and verify both previews.
4. Map Z to `plan_label_ocr`.
5. Choose **Start**, then click an elevation label on the plan.
6. Confirm the live X/Y/Z status and row count.
7. Choose **Export XLSX** and inspect both workbook sheets.

For an all-screen mapping, Start polls continuously and retains a row only after the combined mapped value stabilizes and changes. Stop ends polling without deleting prior rows.

Mapping profiles and the SQLite database live under `.screen2xyz` in the selected project folder. Keep that folder out of source control when it contains project information.

> Screen2XYZ output is preliminary data for conceptual estimating. It is not certified survey data and must be checked against an authoritative source.
