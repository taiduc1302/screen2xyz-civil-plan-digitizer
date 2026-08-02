"""Small immutable domain records for the synthetic OCR laboratory."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ParseResult:
    latitude: Decimal | None
    longitude: Decimal | None
    elevation_m: Decimal | None
    codes: tuple[str, ...]


@dataclass(frozen=True)
class TemporalResult:
    classification: str
    primary_code: str
    all_codes: tuple[str, ...]
    reference_scenario_id: str


@dataclass(frozen=True)
class OcrObservation:
    status: str
    raw_text: str
    duration_ms: int
    error_code: str
    engine: str = "Windows.Media.Ocr"
    engine_version: str = "not_exposed"
    language: str = "en-US"
