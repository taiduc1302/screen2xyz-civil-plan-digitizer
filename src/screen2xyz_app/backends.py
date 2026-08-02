"""Local screen, OCR, clipboard, and plan-value readers."""

from __future__ import annotations

import hashlib
import io
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Hashable

from screen2xyz_civil.ocr import TesseractOcrAdapter, WindowsOcrAdapter
from screen2xyz_m2.parsing import parse_number

from .capture import Reading
from .mapping import ChannelSource


class OcrUnavailableError(RuntimeError):
    """No supported local OCR engine is available."""


class OcrConfidenceError(ValueError):
    """OCR did not produce a safely parseable value above the gate."""


@dataclass(frozen=True)
class OcrPolicy:
    separator_mode: str = "point"
    numeric: bool = True
    confidence_min: float = 0.35
    numeric_range: tuple[float, float] | None = None
    precision_min: int | None = None
    consensus_min: int = 1
    whitelist: str = "0123456789.,-"
    psm_modes: tuple[int, ...] = (7, 8, 13)
    rotation_angles: tuple[int, ...] = (0,)
    upscale: int = 4
    binarize: bool = True

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence_min <= 1.0:
            raise ValueError("OCR confidence gate must be between 0 and 1")
        if self.upscale < 1 or self.upscale > 6:
            raise ValueError("OCR upscale must be between 1 and 6")
        if self.precision_min is not None and self.precision_min < 0:
            raise ValueError("OCR minimum precision cannot be negative")
        if self.consensus_min < 1:
            raise ValueError("OCR consensus minimum must be at least one")
        if not self.psm_modes:
            raise ValueError("at least one Tesseract PSM mode is required")
        if not self.rotation_angles or any(abs(angle) > 30 for angle in self.rotation_angles):
            raise ValueError("OCR rotation angles must stay within 30 degrees")


class ScreenOcrBackend:
    """Capture/crop bytes and run a bounded numeric OCR retry ladder."""

    def __init__(self, *, executable: Path | None = None) -> None:
        self.repository_root = Path(__file__).resolve().parents[2]
        self.executable = executable or TesseractOcrAdapter.find_executable()
        self._cache: dict[Hashable, tuple[str, Reading]] = {}

    @property
    def available(self) -> bool:
        return self.executable is not None or sys.platform == "win32"

    @staticmethod
    def _png_bytes(image) -> bytes:
        output = io.BytesIO()
        image.convert("RGB").save(output, format="PNG")
        return output.getvalue()

    @staticmethod
    def _prepare_variants(image, policy: OcrPolicy):
        from PIL import Image, ImageOps

        source = image.convert("RGB")
        fill = source.getpixel((0, 0))
        variants = []
        for angle in policy.rotation_angles:
            rgb = (
                source
                if angle == 0
                else source.rotate(angle, expand=True, fillcolor=fill)
            )
            padded = ImageOps.expand(rgb, border=16, fill=fill)
            factor = (
                policy.upscale
                if image.height < 80 else max(1, policy.upscale - 1)
            )
            if factor > 1:
                padded = padded.resize(
                    (padded.width * factor, padded.height * factor),
                    resample=Image.Resampling.LANCZOS,
                )
            variants.append((f"color-{angle}", padded))
            if policy.binarize:
                gray = ImageOps.autocontrast(padded.convert("L"))
                threshold = gray.point(lambda pixel: 255 if pixel >= 155 else 0)
                variants.append((f"binary-{angle}", threshold))
        return variants

    def read_zone(
        self,
        zone: tuple[int, int, int, int],
        *,
        policy: OcrPolicy | None = None,
    ) -> Reading:
        from PIL import Image
        import mss

        left, top, width, height = zone
        with mss.mss() as capture:
            shot = capture.grab(
                {"left": left, "top": top, "width": width, "height": height}
            )
        image = Image.frombytes("RGB", shot.size, shot.rgb)
        return self.read_image(image, cache_key=("screen", zone), policy=policy)

    def read_image_region(
        self,
        image_or_path,
        region: tuple[int, int, int, int],
        *,
        cache_key: Hashable | None = None,
        policy: OcrPolicy | None = None,
    ) -> Reading:
        from PIL import Image

        if isinstance(image_or_path, (str, Path)):
            with Image.open(image_or_path) as opened:
                image = opened.convert("RGB")
        else:
            image = image_or_path.convert("RGB")
        left, top, width, height = region
        crop = image.crop((left, top, left + width, top + height))
        return self.read_image(crop, cache_key=cache_key, policy=policy)

    def read_image(
        self,
        image,
        *,
        cache_key: Hashable | None = None,
        policy: OcrPolicy | None = None,
    ) -> Reading:
        policy = policy or OcrPolicy()
        png = self._png_bytes(image)
        digest = hashlib.sha256(png).hexdigest()
        key = None if cache_key is None else (cache_key, policy)
        cached = None if key is None else self._cache.get(key)
        if cached is not None and cached[0] == digest:
            prior = cached[1]
            return Reading(prior.raw_text, prior.confidence, digest, png, False)
        variants = self._prepare_variants(image, policy)
        reading = self._ocr(variants, policy, digest, png)
        if key is not None:
            self._cache[key] = (digest, reading)
        return reading

    def _ocr(self, variants, policy: OcrPolicy, digest: str, png: bytes) -> Reading:
        if self.executable is not None:
            reading = self._ocr_tesseract(variants, policy, digest, png)
        elif sys.platform == "win32":
            reading = self._ocr_windows(variants[0][1], digest, png)
        else:
            raise OcrUnavailableError(
                "Tesseract was not found and Windows OCR is unavailable"
            )
        if (
            reading.confidence is not None
            and reading.confidence < policy.confidence_min
        ):
            raise OcrConfidenceError(
                f"OCR confidence {reading.confidence:.3f} is below "
                f"{policy.confidence_min:.3f}"
            )
        return reading

    def _ocr_tesseract(
        self, variants, policy: OcrPolicy, digest: str, png: bytes
    ) -> Reading:
        import pytesseract
        from pytesseract import Output

        pytesseract.pytesseract.tesseract_cmd = str(self.executable)
        candidates: list[tuple[bool, float, str, str | None]] = []
        for _variant_name, image in variants:
            for psm in policy.psm_modes:
                whitelist = (
                    f" -c tessedit_char_whitelist={policy.whitelist}"
                    if policy.numeric and policy.whitelist else ""
                )
                data = pytesseract.image_to_data(
                    image,
                    config=f"--psm {psm}{whitelist}",
                    output_type=Output.DICT,
                )
                words = [str(text).strip() for text in data["text"] if str(text).strip()]
                raw_text = " ".join(words)
                scores = [
                    float(value) for value in data["conf"] if float(value) >= 0
                ]
                confidence = 0.0 if not scores else sum(scores) / len(scores) / 100.0
                candidate_text = raw_text
                valid = bool(candidate_text)
                if policy.numeric:
                    outcome = parse_number(
                        candidate_text,
                        separator_mode=policy.separator_mode,
                        numeric_range=policy.numeric_range,
                    )
                    if outcome.parse_status != "OK":
                        # A configured locale is authoritative. Tesseract can
                        # substitute the visually similar decimal glyph; only
                        # repair a single-separator token, never mixed/grouped
                        # punctuation where the interpretation is ambiguous.
                        if (
                            policy.separator_mode == "comma"
                            and "." in candidate_text
                            and "," not in candidate_text
                        ):
                            candidate_text = candidate_text.replace(".", ",")
                        elif (
                            policy.separator_mode == "point"
                            and "," in candidate_text
                            and "." not in candidate_text
                        ):
                            candidate_text = candidate_text.replace(",", ".")
                        outcome = parse_number(
                            candidate_text,
                            separator_mode=policy.separator_mode,
                            numeric_range=policy.numeric_range,
                        )
                    valid = outcome.parse_status == "OK"
                    if valid and policy.precision_min is not None:
                        fraction = (outcome.normalized_value or "").partition(".")[2]
                        valid = len(fraction) >= policy.precision_min
                normalized = outcome.normalized_value if policy.numeric and valid else candidate_text
                candidates.append((valid, confidence, candidate_text, normalized))
                if (
                    policy.consensus_min == 1
                    and valid
                    and confidence >= max(0.85, policy.confidence_min)
                ):
                    return Reading(candidate_text, confidence, digest, png, True)
        valid_candidates = [item for item in candidates if item[0]]
        if not valid_candidates:
            observed = sorted({item[2] for item in candidates if item[2]})
            raise OcrConfidenceError(
                "OCR retry ladder produced no parseable value"
                + (f": {observed}" if observed else "")
            )
        if policy.consensus_min > 1:
            votes = Counter(item[3] for item in valid_candidates)
            normalized, count = max(
                votes.items(),
                key=lambda item: (
                    item[1],
                    max(
                        candidate[1]
                        for candidate in valid_candidates
                        if candidate[3] == item[0]
                    ),
                ),
            )
            if count < policy.consensus_min:
                raise OcrConfidenceError(
                    f"OCR retry ladder did not reach {policy.consensus_min}-reading consensus"
                )
            _, confidence, text, _ = max(
                (item for item in valid_candidates if item[3] == normalized),
                key=lambda item: item[1],
            )
        else:
            _, confidence, text, _ = max(
                valid_candidates, key=lambda item: item[1]
            )
        return Reading(text, confidence, digest, png, True)

    def _ocr_windows(self, image, digest: str, png: bytes) -> Reading:
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temporary:
                temporary_path = Path(temporary.name)
                image.save(temporary, format="PNG")
            result = WindowsOcrAdapter(self.repository_root).extract(temporary_path)
            confidences = [
                word.confidence
                for line in result.lines
                for word in line.words
                if word.confidence is not None
            ]
            confidence = None if not confidences else sum(confidences) / len(confidences)
            return Reading(result.raw_text, confidence, digest, png, True)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)


class DefaultReader:
    def __init__(self, screen: ScreenOcrBackend | None = None) -> None:
        self.screen = screen or ScreenOcrBackend()

    def __call__(
        self, column: str, source: ChannelSource, context: dict[str, Any]
    ) -> Reading:
        if source.source_type == "screen_zone_ocr":
            assert source.zone is not None
            return self.screen.read_zone(
                source.zone,
                policy=OcrPolicy(
                    separator_mode=source.decimal_separator,
                    numeric=source.data_type != "text",
                ),
            )
        if source.source_type in {"manual", "plan_click", "plan_label_ocr"}:
            value = context.get(column)
            if value is None:
                raise ValueError(f"{column} requires a capture-time value")
            confidence = context.get(f"{column}_confidence")
            return Reading(
                str(value), confidence,
                ocr_executed=source.source_type == "plan_label_ocr",
            )
        if source.source_type == "clipboard":
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            try:
                return Reading(root.clipboard_get(), None, ocr_executed=False)
            finally:
                root.destroy()
        raise ValueError(f"unsupported source type {source.source_type}")
