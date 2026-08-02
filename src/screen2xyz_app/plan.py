"""Thin adapters over the Civil source, PDF, transform, and assisted capture core."""

from __future__ import annotations

import tempfile
import sys
from pathlib import Path

from screen2xyz_civil.assisted_capture import ElevationUnderCursorService
from screen2xyz_civil.assisted_capture import CandidateEvidence, SpatialCandidateIndex
from screen2xyz_civil import contracts as civil_contracts
from screen2xyz_civil.detection import Rect, TextCandidate, classify_candidate
from screen2xyz_civil.models import Calibration, PixelPoint
from screen2xyz_civil.ocr import WindowsOcrAdapter
from screen2xyz_civil.pdf import inspect_pdf, render_pdf_page
from screen2xyz_civil.source import inspect_image
from screen2xyz_civil.transform import to_local


def inspect_plan(path: Path):
    return inspect_pdf(path) if path.suffix.lower() == ".pdf" else inspect_image(path)


def render_plan_page(path: Path, output_dir: Path, *, page_index: int = 0, dpi: int = 200):
    return render_pdf_page(path, page_index, output_dir, dpi=dpi)


def plan_click_xy(point: PixelPoint, calibration: Calibration) -> tuple[float, float]:
    return to_local(point, calibration)


def plan_label_z(
    point: PixelPoint,
    service: ElevationUnderCursorService,
    *,
    capture_mode: str,
) -> tuple[float, float | None]:
    suggestion = service.suggest(point, capture_mode=capture_mode)
    if not suggestion.capturable or suggestion.evidence is None:
        raise ValueError(f"no capturable elevation near click: {suggestion.snap_status}")
    return float(suggestion.evidence.elevation), suggestion.evidence.confidence


class PlanLabelBackend:
    """OCR a bounded area around a plan click and use Civil assisted snapping."""

    def read_nearest(
        self,
        image_path: Path,
        point: PixelPoint,
        *,
        radius_px: int = 140,
    ) -> tuple[float, float | None, str]:
        from PIL import Image
        import pytesseract
        from pytesseract import Output
        from screen2xyz_civil.ocr import TesseractOcrAdapter

        executable = TesseractOcrAdapter.find_executable()
        with Image.open(image_path) as source:
            left = max(0, int(point.x) - radius_px)
            top = max(0, int(point.y) - radius_px)
            right = min(source.width, int(point.x) + radius_px)
            bottom = min(source.height, int(point.y) + radius_px)
            crop = source.convert("RGB").crop((left, top, right, bottom))
        records: list[tuple[str, int, int, int, int, float]] = []
        if executable is not None:
            pytesseract.pytesseract.tesseract_cmd = str(executable)
            data = pytesseract.image_to_data(crop, config="--psm 11", output_type=Output.DICT)
            records = [
                (
                    str(text), int(data["left"][index]), int(data["top"][index]),
                    int(data["width"][index]), int(data["height"][index]),
                    max(0.0, float(data["conf"][index]) / 100.0),
                )
                for index, text in enumerate(data["text"])
            ]
        elif sys.platform == "win32":
            temporary_path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temporary:
                    temporary_path = Path(temporary.name)
                    crop.save(temporary, format="PNG")
                root = Path(__file__).resolve().parents[2]
                result = WindowsOcrAdapter(root).extract(temporary_path)
                records = [
                    (
                        word.text, int(word.bbox.x0), int(word.bbox.y0),
                        int(word.bbox.width), int(word.bbox.height),
                        0.75 if word.confidence is None else word.confidence,
                    )
                    for line in result.lines for word in line.words
                ]
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)
        else:
            raise RuntimeError("Tesseract was not found and Windows OCR is unavailable")
        evidence: list[CandidateEvidence] = []
        for index, (text, local_x, local_y, width, height, confidence) in enumerate(records):
            text = text.strip()
            if not text:
                continue
            x = left + local_x
            y = top + local_y
            candidate = TextCandidate(
                id=f"click-{index}", text=text,
                bbox=Rect(x, y, x + width, y + height), page_index=0,
                source_method=civil_contracts.LOCAL_OCR, confidence=confidence,
            )
            classification = classify_candidate(candidate)
            normalized = classification.normalized
            if normalized is None:
                continue
            likely_type = (
                classification.point_type
                if classification.point_type in civil_contracts.TERRAIN_POINT_TYPES
                else civil_contracts.EXISTING_GROUND
            )
            evidence.append(CandidateEvidence(
                candidate_id=candidate.id, page_index=0, page_label="1",
                pixel=candidate.bbox.center, elevation=normalized.value,
                likely_type=likely_type, source_method=candidate.source_method,
                detected_text=text, normalized_text=normalized.normalized_text,
                text_confidence=confidence, symbol_type="NONE", symbol_confidence=None,
                association_confidence=None,
                classification_confidence=classification.confidence,
                reasons=classification.reasons, text_bbox=candidate.bbox.to_dict(),
                alternative_associations=(), rejected=False, rejection_category="",
            ))
        service = ElevationUnderCursorService(
            SpatialCandidateIndex(evidence), snap_radius_px=float(radius_px)
        )
        suggestion = service.suggest(point, capture_mode=civil_contracts.EXISTING_GROUND)
        if not suggestion.can_capture or suggestion.evidence is None:
            raise ValueError("no elevation label was recognized near the click")
        item = suggestion.evidence
        return float(item.elevation), item.text_confidence, item.detected_text
