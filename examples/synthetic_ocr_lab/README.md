# Synthetic OCR Lab Example

The example is the versioned fixture at `test_data/synthetic/s2xyz_fixture_v0.1/` and its retained run evidence under `runs/evidence/S2XYZ-CODEX-003/`. The command-line runner sends every generated PNG to actual local Windows OCR, retains raw OCR text, parses and validates labelled values, classifies duplicate/stale readings, and produces source-coordinate demonstration outputs.

Only generated images are in scope. Live screen capture, real-source operation, coordinate transformation, downstream import, terrain calculation, and earthwork calculation are not implemented or tested.

Conceptual and preliminary estimating data only.
