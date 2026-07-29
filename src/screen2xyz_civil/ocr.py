"""Bounded, local OCR adapter interface with word bounding boxes."""

from __future__ import annotations

import json
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
    ) -> list[TextCandidate]:
        candidates: list[TextCandidate] = []
        sequence = 0
        for line in self.lines:
            for word in line.words:
                sequence += 1
                bbox = Rect(
                    word.bbox.x0 + offset_x,
                    word.bbox.y0 + offset_y,
                    word.bbox.x1 + offset_x,
                    word.bbox.y1 + offset_y,
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
            value = json.loads(completed.stdout)
            if value.get("schema_version") != "1.0" or value.get("status") != "SUCCESS":
                raise ValueError("unexpected OCR adapter schema/status")
            lines = []
            for line in value.get("lines", []):
                words = tuple(
                    OcrWord(
                        text=str(word["text"]),
                        bbox=Rect(
                            float(word["x"]),
                            float(word["y"]),
                            float(word["x"]) + float(word["width"]),
                            float(word["y"]) + float(word["height"]),
                        ),
                    )
                    for word in line.get("words", [])
                )
                lines.append(OcrLine(str(line.get("text", "")), words))
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
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise OcrAdapterError("local OCR returned an invalid result") from exc


class MockOcrAdapter:
    def __init__(self, result: OcrResult) -> None:
        self.result = result

    def extract(self, image: Path, *, language: str = "en-US") -> OcrResult:
        del image, language
        return self.result
