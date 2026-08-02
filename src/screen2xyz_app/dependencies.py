"""Optional runtime capability detection and operator-facing install guidance."""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass

from screen2xyz_civil.ocr import TesseractOcrAdapter
from screen2xyz_civil.pdf import _resolve_renderer


@dataclass(frozen=True)
class Capability:
    name: str
    available: bool
    feature: str
    install_command: str
    download_url: str
    detail: str


def tesseract_capability() -> Capability:
    available = TesseractOcrAdapter.find_executable() is not None
    fallback = sys.platform == "win32"
    detail = (
        "Tesseract is ready."
        if available
        else (
            "Enhanced OCR is disabled; Screen2XYZ will use the built-in Windows OCR fallback."
            if fallback
            else "OCR capture is disabled until Tesseract is installed."
        )
    )
    return Capability(
        "Tesseract OCR",
        available,
        "enhanced screen and rotated plan-label OCR",
        "winget install --id UB-Mannheim.TesseractOCR --exact",
        "https://tesseract-ocr.github.io/tessdoc/Installation.html",
        detail,
    )


def poppler_capability() -> Capability:
    available = _resolve_renderer(None) is not None
    return Capability(
        "Poppler pdftoppm",
        available,
        "PDF page loading",
        "winget install --id oschwartz10612.Poppler --exact",
        "https://poppler.freedesktop.org/",
        "Poppler is ready." if available else "PDF loading is disabled; image loading still works.",
    )


def runtime_capabilities() -> tuple[Capability, Capability]:
    return tesseract_capability(), poppler_capability()


def command_available(command: str) -> bool:
    return shutil.which(command) is not None
