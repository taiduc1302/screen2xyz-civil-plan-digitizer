"""Screen2XYZ M1 — opt-in still-image capture review laboratory.

Explicit local PNG selection → secure validation → OCR → deterministic
parsing/validation/classification → human review, correction, and approval →
approved-only deterministic export with a local provenance package.

The deterministic core reuses the sealed baseline pipeline in
``screen2xyz_lab`` and adds only intake, review state, exports, and an
optional (disabled-by-default) external-assistance boundary.
"""

__version__ = "0.1.0"
