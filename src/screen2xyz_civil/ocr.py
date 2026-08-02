"""Bounded, local OCR adapter interface with word bounding boxes."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from . import contracts as C
from .detection import Rect, TextCandidate


class OcrAdapterError(RuntimeError):
    """Local OCR was unavailable, unsafe to invoke, or failed."""


@dataclass(frozen=True)
class OcrWord:
    text: str
    bbox: Rect
    confidence: float | None = None


@dataclass(frozen=True)
class OcrLine:
    text: str
    words: tuple[OcrWord, ...]


@dataclass(frozen=True)
class OcrResult:
    status: str
    raw_text: str
    engine: str
    language: str
    duration_ms: int
    lines: tuple[OcrLine, ...]

    def text_candidates(
        self,
        *,
        page_index: int,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        coordinate_scale: float = 1.0,
    ) -> list[TextCandidate]:
        if coordinate_scale <= 0:
            raise ValueError("OCR coordinate scale must be positive")
        candidates: list[TextCandidate] = []
        sequence = 0
        for line in self.lines:
            for word in line.words:
                sequence += 1
                bbox = Rect(
                    word.bbox.x0 / coordinate_scale + offset_x,
                    word.bbox.y0 / coordinate_scale + offset_y,
                    word.bbox.x1 / coordinate_scale + offset_x,
                    word.bbox.y1 / coordinate_scale + offset_y,
                )
                candidates.append(
                    TextCandidate(
                        id=f"OCR-T{sequence:05d}",
                        text=word.text,
                        bbox=bbox,
                        page_index=page_index,
                        source_method=C.LOCAL_OCR,
                        confidence=word.confidence if word.confidence is not None else 0.75,
                        context=line.text,
                    )
                )
        return candidates


class OcrAdapter(Protocol):
    def extract(self, image: Path, *, language: str = "en-US") -> OcrResult:
        ...


class WindowsOcrAdapter:
    def __init__(self, repository_root: Path, *, timeout_seconds: float = 30.0) -> None:
        self.repository_root = repository_root.resolve()
        self.timeout_seconds = timeout_seconds

    def extract(self, image: Path, *, language: str = "en-US") -> OcrResult:
        candidate = image.expanduser().resolve()
        if (
            not candidate.is_file()
            or candidate.suffix.lower() != ".png"
            or candidate.stat().st_size <= 0
            or candidate.stat().st_size > C.MAX_SOURCE_BYTES
        ):
            raise OcrAdapterError("OCR input must be a bounded local PNG")
        script = (
            self.repository_root
            / "src/screen2xyz_civil/adapters/ocr_windows_boxes.ps1"
        )
        command = [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-ImagePath",
            str(candidate),
            "-Language",
            language,
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="strict",
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise OcrAdapterError("local OCR timed out") from exc
        except OSError as exc:
            raise OcrAdapterError("PowerShell OCR host is unavailable") from exc
        if completed.returncode != 0:
            raise OcrAdapterError(
                f"local OCR adapter exited with code {completed.returncode}"
            )
        try:
            return _result_from_payload(json.loads(completed.stdout))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise OcrAdapterError("local OCR returned an invalid result") from exc


class TesseractOcrAdapter:
    """Local multi-angle OCR for small diagonal civil-plan annotations."""

    def __init__(
        self,
        repository_root: Path,
        *,
        executable: Path | None = None,
        timeout_seconds: float = 45.0,
        angles: tuple[int, ...] = (15, 20, 25),
    ) -> None:
        self.repository_root = repository_root.resolve()
        self.executable = (
            executable.resolve()
            if executable is not None
            else self.find_executable()
        )
        self.timeout_seconds = timeout_seconds
        self.angles = tuple(int(angle) for angle in angles)

    @staticmethod
    def find_executable() -> Path | None:
        command = shutil.which("tesseract")
        local_app_data = os.environ.get("LOCALAPPDATA")
        candidates = [
            Path(command) if command else None,
            (
                Path(local_app_data) / "Programs/Tesseract-OCR/tesseract.exe"
                if local_app_data else None
            ),
            Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
            Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
        ]
        return next(
            (
                candidate.resolve()
                for candidate in candidates
                if candidate is not None and candidate.is_file()
            ),
            None,
        )

    @property
    def available(self) -> bool:
        return self.executable is not None and self.executable.is_file()

    def extract(self, image: Path, *, language: str = "eng") -> OcrResult:
        candidate = image.expanduser().resolve()
        if (
            not candidate.is_file()
            or candidate.suffix.lower() != ".png"
            or candidate.stat().st_size <= 0
            or candidate.stat().st_size > C.MAX_SOURCE_BYTES
        ):
            raise OcrAdapterError("OCR input must be a bounded local PNG")
        if not self.available:
            raise OcrAdapterError("local Tesseract executable is unavailable")
        if not self.angles or any(abs(angle) > 45 for angle in self.angles):
            raise OcrAdapterError("Tesseract OCR angles must stay within 45 degrees")
        script = (
            self.repository_root
            / "src/screen2xyz_civil/adapters/ocr_tesseract_rotated.ps1"
        )
        command = [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-ImagePath",
            str(candidate),
            "-TesseractPath",
            str(self.executable),
            "-Angles",
            ",".join(str(angle) for angle in self.angles),
            "-Language",
            language,
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="strict",
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise OcrAdapterError("local Tesseract OCR timed out") from exc
        except OSError as exc:
            raise OcrAdapterError("PowerShell OCR host is unavailable") from exc
        if completed.returncode != 0:
            raise OcrAdapterError(
                f"local Tesseract adapter exited with code {completed.returncode}"
            )
        try:
            return _dedupe_result(
                _result_from_payload(json.loads(completed.stdout))
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise OcrAdapterError(
                "local Tesseract OCR returned an invalid result"
            ) from exc


class MockOcrAdapter:
    def __init__(self, result: OcrResult) -> None:
        self.result = result

    def extract(self, image: Path, *, language: str = "en-US") -> OcrResult:
        del image, language
        return self.result


def _result_from_payload(value: dict) -> OcrResult:
    if value.get("schema_version") != "1.0" or value.get("status") != "SUCCESS":
        raise ValueError("unexpected OCR adapter schema/status")
    lines = []
    word_count = 0
    for line in value.get("lines", []):
        words = []
        for word in line.get("words", []):
            word_count += 1
            if word_count > 5000:
                raise ValueError("OCR result exceeds word safety boundary")
            confidence = word.get("confidence")
            words.append(
                OcrWord(
                    text=str(word["text"]),
                    bbox=Rect(
                        float(word["x"]),
                        float(word["y"]),
                        float(word["x"]) + float(word["width"]),
                        float(word["y"]) + float(word["height"]),
                    ),
                    confidence=(
                        None if confidence is None else float(confidence)
                    ),
                )
            )
        lines.append(OcrLine(str(line.get("text", "")), tuple(words)))
    raw_text = str(value.get("raw_text", ""))
    if len(raw_text.encode("utf-8")) > 1024 * 1024:
        raise ValueError("OCR result exceeds local safety boundary")
    return OcrResult(
        status="SUCCESS",
        raw_text=raw_text,
        engine=str(value["engine"]),
        language=str(value["language"]),
        duration_ms=max(0, int(value["duration_ms"])),
        lines=tuple(lines),
    )


def _dedupe_result(result: OcrResult) -> OcrResult:
    ranked: list[tuple[str, OcrWord]] = []
    for line in result.lines:
        for word in line.words:
            ranked.append((line.text, word))
    ranked.sort(
        key=lambda item: (
            -(item[1].confidence or 0.0),
            item[1].bbox.y0,
            item[1].bbox.x0,
        )
    )
    accepted: list[tuple[str, OcrWord]] = []
    for context, word in ranked:
        normalized = re.sub(r"\s+", "", word.text).casefold()
        duplicate = any(
            normalized
            == re.sub(r"\s+", "", existing.text).casefold()
            and _bbox_overlap_ratio(word.bbox, existing.bbox) >= 0.45
            for _existing_context, existing in accepted
        )
        if not duplicate:
            accepted.append((context, word))
    accepted.sort(key=lambda item: (item[1].bbox.y0, item[1].bbox.x0, item[1].text))
    return OcrResult(
        status=result.status,
        raw_text="\n".join(word.text for _context, word in accepted),
        engine=result.engine,
        language=result.language,
        duration_ms=result.duration_ms,
        lines=tuple(
            OcrLine(context, (word,))
            for context, word in accepted
        ),
    )


def _bbox_overlap_ratio(left: Rect, right: Rect) -> float:
    intersection_width = max(
        0.0,
        min(left.x1, right.x1) - max(left.x0, right.x0),
    )
    intersection_height = max(
        0.0,
        min(left.y1, right.y1) - max(left.y0, right.y0),
    )
    intersection = intersection_width * intersection_height
    smaller = min(left.width * left.height, right.width * right.height)
    return 0.0 if smaller <= 0 else intersection / smaller
