"""Synthetic Excel workbook generator for overnight QA (openpyxl is a
dev-only fixture-generation dependency - never imported by production
src/screen2xyz_m2 code). Every workbook uses fabricated, non-confidential
values. Output must only ever be written under the ignored
.lab_work/fixture_gallery/excel/ directory."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


def simple_coordinates(path: Path) -> dict:
    """A. Simple X/Y/Z coordinates in the top-left corner, default zoom -
    the layout every scenario's synthetic-value assertions are keyed to."""

    wb = Workbook()
    ws = wb.active
    ws.title = "coords"
    ws["A1"], ws["B1"] = "X", 123.456
    ws["A2"], ws["B2"] = "Y", -78.9
    ws["A3"], ws["B3"] = "Z", 4200.0
    wb.save(path)
    return {"X": "123.456", "Y": "-78.9", "Z": "4200"}


def wide_estimating_table(path: Path) -> dict:
    """B. Wide estimating-style table across the full width."""

    wb = Workbook()
    ws = wb.active
    ws.title = "estimate"
    headers = ["Item", "Description", "Quantity", "Unit", "Unit Price",
              "Total", "Status"]
    for col, text in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col, value=text)
        cell.font = Font(bold=True)
    rows = [
        (101, "Excavation, common", 450, "CY", 12.50, 5625.00, "Active"),
        (102, "Granular base course", 220, "TON", 34.10, 7502.00, "Active"),
        (103, "Concrete curb and gutter", 610, "LF", 18.75, 11437.50,
         "Pending"),
    ]
    for r, row in enumerate(rows, start=2):
        for c, value in enumerate(row, start=1):
            ws.cell(row=r, column=c, value=value)
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 16
    wb.save(path)
    return {"row2_total": "5625"}


def sparse_positions(path: Path) -> dict:
    """C. Values at top-left/top-right/center/bottom-left/bottom-right."""

    wb = Workbook()
    ws = wb.active
    ws.title = "sparse"
    ws["A1"] = "TL-1"
    ws["T1"] = "TR-2"
    ws["J20"] = "CENTER-3"
    ws["A40"] = "BL-4"
    ws["T40"] = "BR-5"
    wb.save(path)
    return {"A1": "TL-1", "T1": "TR-2", "J20": "CENTER-3", "A40": "BL-4",
           "T40": "BR-5"}


def formatting_variants(path: Path) -> dict:
    """D. integer/decimal/negative/thousands/currency/percentage/
    scientific/Unicode-minus/blank/malformed."""

    wb = Workbook()
    ws = wb.active
    ws.title = "formats"
    labels = ["integer", "decimal", "negative", "thousands", "currency",
             "percentage", "scientific", "unicode_minus", "blank",
             "malformed"]
    values = [42, 3.14159, -17, "12,345", "$1,250.00", "12.5%", "6.02E23",
             "−15.0", "", "N/A-ish??"]
    for r, (label, value) in enumerate(zip(labels, values), start=1):
        ws.cell(row=r, column=1, value=label)
        ws.cell(row=r, column=2, value=value)
    wb.save(path)
    return dict(zip(labels, [str(v) for v in values]))


def visual_variants(path: Path) -> dict:
    """E. merged headers/alternating fills/dark-on-light/small+large
    font/borders touching values/conditional-formatting-like fill."""

    wb = Workbook()
    ws = wb.active
    ws.title = "visual"
    ws.merge_cells("A1:C1")
    ws["A1"] = "MERGED HEADER"
    ws["A1"].alignment = Alignment(horizontal="center")
    for r in range(2, 6):
        fill = PatternFill("solid", fgColor="DDDDDD" if r % 2 == 0
                           else "FFFFFF")
        cell = ws.cell(row=r, column=1, value=f"row-{r}")
        cell.fill = fill
    dark = ws.cell(row=7, column=1, value="LIGHT-ON-DARK")
    dark.fill = PatternFill("solid", fgColor="222222")
    dark.font = Font(color="FFFFFF")
    small = ws.cell(row=8, column=1, value="small-9pt")
    small.font = Font(size=9)
    large = ws.cell(row=9, column=1, value="large-24pt")
    large.font = Font(size=24, bold=True)
    warn = ws.cell(row=10, column=1, value="OVER_BUDGET")
    warn.fill = PatternFill("solid", fgColor="FFC7CE")
    warn.font = Font(color="9C0006")
    wb.save(path)
    return {"A1": "MERGED HEADER", "A10": "OVER_BUDGET"}


def scrolling_workbook(path: Path) -> dict:
    """F. Values below the initial viewport and far to the right -
    horizontal and vertical scrolling required to reach them."""

    wb = Workbook()
    ws = wb.active
    ws.title = "scrolling"
    ws["A1"] = "visible-without-scrolling"
    ws.cell(row=80, column=1, value="needs-vertical-scroll")
    ws.cell(row=1, column=60, value="needs-horizontal-scroll")
    ws.cell(row=80, column=60, value="needs-both-scrolls")
    wb.save(path)
    return {"A1": "visible-without-scrolling",
           "A80": "needs-vertical-scroll",
           "BH1": "needs-horizontal-scroll",
           "BH80": "needs-both-scrolls"}


def changing_workbook(path: Path, tick: int) -> dict:
    """G. A safe mechanism that visibly updates selected synthetic values -
    called repeatedly with an increasing tick while the SAME file stays open
    in Excel (Excel auto-reloads-on-focus is unreliable, so the scenario
    runner instead re-saves and asks the owner/production OCR to re-read
    after a Ctrl+S+re-render cycle is simulated by the runner itself)."""

    wb = Workbook()
    ws = wb.active
    ws.title = "changing"
    ws["A1"] = "TICK"
    ws["B1"] = tick
    ws["A2"] = "VALUE"
    ws["B2"] = round(100.0 + tick * 1.5, 2)
    wb.save(path)
    return {"tick": str(tick), "value": str(round(100.0 + tick * 1.5, 2))}


GENERATORS = {
    "A_simple_coordinates": simple_coordinates,
    "B_wide_estimating_table": wide_estimating_table,
    "C_sparse_positions": sparse_positions,
    "D_formatting_variants": formatting_variants,
    "E_visual_variants": visual_variants,
    "F_scrolling_workbook": scrolling_workbook,
}


def generate_all(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    truth = {}
    for name, fn in GENERATORS.items():
        path = out_dir / f"{name}.xlsx"
        truth[name] = {"path": str(path), "expected": fn(path)}
    truth["G_changing_workbook"] = {
        "path": str(out_dir / "G_changing_workbook.xlsx"),
        "expected": changing_workbook(out_dir / "G_changing_workbook.xlsx",
                                      tick=0)}
    return truth


if __name__ == "__main__":
    import json
    import sys
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        ".lab_work/fixture_gallery/excel")
    result = generate_all(target)
    print(json.dumps(result, indent=2))
