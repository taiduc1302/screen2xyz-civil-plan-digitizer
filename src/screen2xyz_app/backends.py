"""Local screen, OCR, clipboard, and plan-value readers."""

from __future__ import annotations

import hashlib
import io
import sys
import tempfile
from pathlib import Path
from typing import Any

from screen2xyz_civil.ocr import TesseractOcrAdapter, WindowsOcrAdapter

from .capture import Reading
from .mapping import ChannelSource


class ScreenOcrBackend:
    def __init__(self) -> None:
        self.repository_root = Path(__file__).resolve().parents[2]
        self._cache: dict[tuple[int, int, int, int], tuple[str, Reading]] = {}

    @staticmethod
    def _prepare(image):
        from PIL import Image, ImageOps

        fill = image.convert("RGB").getpixel((0, 0))
        prepared = ImageOps.expand(image.convert("RGB"), border=16, fill=fill)
        if image.height < 60:
            prepared = prepared.resize(
                (prepared.width * 3, prepared.height * 3),
                resample=Image.Resampling.LANCZOS,
            )
        return prepared

    def read_zone(self, zone: tuple[int, int, int, int]) -> Reading:
        from PIL import Image
        import mss

        left, top, width, height = zone
        with mss.mss() as capture:
            shot = capture.grab({"left": left, "top": top, "width": width, "height": height})
        image = Image.frombytes("RGB", shot.size, shot.rgb)
        raw_png = io.BytesIO()
        image.save(raw_png, format="PNG")
        png = raw_png.getvalue()
        digest = hashlib.sha256(png).hexdigest()
        cached = self._cache.get(zone)
        if cached is not None and cached[0] == digest:
            prior = cached[1]
            return Reading(prior.raw_text, prior.confidence, digest, png, False)
        prepared = self._prepare(image)
        reading = self._ocr(prepared, digest, png)
        self._cache[zone] = (digest, reading)
        return reading

    def _ocr(self, image, digest: str, png: bytes) -> Reading:
        executable = TesseractOcrAdapter.find_executable()
        if executable is not None:
            import pytesseract
            from pytesseract import Output

            pytesseract.pytesseract.tesseract_cmd = str(executable)
            data = pytesseract.image_to_data(image, config="--psm 7", output_type=Output.DICT)
            words = [text.strip() for text in data["text"] if text.strip()]
            scores = [float(value) for value in data["conf"] if float(value) >= 0]
            confidence = None if not scores else sum(scores) / len(scores) / 100.0
            return Reading(" ".join(words), confidence, digest, png, True)
        if sys.platform != "win32":
            raise RuntimeError("Tesseract was not found and Windows OCR is unavailable")
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temporary:
                temporary_path = Path(temporary.name)
                image.save(temporary, format="PNG")
            result = WindowsOcrAdapter(self.repository_root).extract(temporary_path)
            confidences = [
                word.confidence for line in result.lines for word in line.words
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

    def __call__(self, column: str, source: ChannelSource, context: dict[str, Any]) -> Reading:
        if source.source_type == "screen_zone_ocr":
            assert source.zone is not None
            return self.screen.read_zone(source.zone)
        if source.source_type in {"manual", "plan_click", "plan_label_ocr"}:
            value = context.get(column)
            if value is None:
                raise ValueError(f"{column} requires a capture-time value")
            confidence = context.get(f"{column}_confidence")
            return Reading(str(value), confidence, ocr_executed=source.source_type == "plan_label_ocr")
        if source.source_type == "clipboard":
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            try:
                return Reading(root.clipboard_get(), None, ocr_executed=False)
            finally:
                root.destroy()
        raise ValueError(f"unsupported source type {source.source_type}")
