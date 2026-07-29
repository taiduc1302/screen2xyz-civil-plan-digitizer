"""Excel cell update via COM automation on the ALREADY-RUNNING instance
(§12.G "a safe mechanism that visibly updates selected synthetic values
during recording"). This is scriptable Office automation, not keyboard/
mouse simulation - PowerShell's GetActiveObject attaches to the real Excel
process the scenario already launched and sets one cell, which Excel
re-renders on screen exactly as if a user had typed it and pressed Enter.
Never used to read cells for assertions (that would bypass OCR) - only to
produce a real, visible, on-screen change for the capture pipeline to
observe."""

from __future__ import annotations

import subprocess


def ps_single_quote(value) -> str:
    """A PowerShell single-quoted string literal for `value`. PowerShell's
    ONLY escaping rule inside single quotes is doubling an embedded quote
    (`'` -> `''`); single-quoted strings never interpolate `$variables` or
    `$(subexpressions)`, unlike double-quoted strings.

    Independent audit MAJOR: the previous version built this string with
    Python's `repr()`, which follows Python's quoting rules, not
    PowerShell's - a value containing a single quote flips `repr()` to a
    DOUBLE-quoted Python string, which is then embedded verbatim into a
    PowerShell command line as a PowerShell DOUBLE-quoted string (which
    DOES interpolate). A value containing both a `'` and a `$(...)`
    sequence would have had that subexpression executed as PowerShell
    code - a real injection path, not just a syntax break. This helper's
    single-quote-only construction cannot be escaped into interpolation
    regardless of the input."""

    return "'" + str(value).replace("'", "''") + "'"


def set_cell(cell_ref: str, value) -> None:
    script = (
        "$xl = [Runtime.InteropServices.Marshal]::GetActiveObject("
        "'Excel.Application'); "
        f"$xl.ActiveWorkbook.Sheets(1).Range({ps_single_quote(cell_ref)})"
        f".Value = {ps_single_quote(value)}; "
        "$xl.ActiveWorkbook.Save()")
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
         script], capture_output=True, timeout=15, check=True)
