"""Source-agnostic capture pipeline with M2 stability and scheduling."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from screen2xyz_m2.models import Observation, SourceConfig
from screen2xyz_m2.parsing import bound_raw, parse_for_source
from screen2xyz_m2.scheduler import TickScheduler
from screen2xyz_m2.stability import StabilityEngine

from .mapping import ChannelMapping, ChannelSource
from .operations import ZoneHealthMonitor, ZoneHealthSnapshot


@dataclass(frozen=True)
class Reading:
    raw_text: str
    confidence: float | None = None
    pixel_sha256: str | None = None
    crop_png: bytes | None = None
    ocr_executed: bool = True


@dataclass(frozen=True)
class CapturedPoint:
    values: dict[str, float | str | None]
    source_methods: dict[str, str]
    raw_texts: dict[str, str]
    confidences: dict[str, float | None]
    created_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    )

    @property
    def x(self) -> float:
        return float(self.values["x"])

    @property
    def y(self) -> float:
        return float(self.values["y"])

    @property
    def z(self) -> float:
        return float(self.values["z"])


Reader = Callable[[str, ChannelSource, dict[str, Any]], Reading]


class CapturePipeline:
    def __init__(self, mapping: ChannelMapping, reader: Reader) -> None:
        mapping.validate()
        self.mapping = mapping
        self.reader = reader

    def read(self, context: dict[str, Any] | None = None) -> tuple[CapturedPoint, dict[str, Observation], dict[str, bytes]]:
        context = context or {}
        values: dict[str, float | str | None] = {}
        methods: dict[str, str] = {}
        raw_texts: dict[str, str] = {}
        confidences: dict[str, float | None] = {}
        observations: dict[str, Observation] = {}
        crops: dict[str, bytes] = {}
        for column, source in self.mapping.channels.items():
            reading = self.reader(column, source, context)
            raw = bound_raw(reading.raw_text)
            parsed = parse_for_source(
                raw,
                source.data_type,
                separator_mode=source.decimal_separator,
                numeric_range=source.numeric_range,
                declared_format=source.declared_format,
            )
            if parsed.parse_status != "OK":
                raise ValueError(f"{column} could not be parsed: {parsed.parse_status}")
            normalized: float | str | None
            if source.data_type == "text":
                normalized = parsed.normalized_value
            elif parsed.normalized_value is None:
                normalized = None
            else:
                normalized = float(parsed.normalized_value)
            values[column] = normalized
            methods[column] = source.source_type
            raw_texts[column] = raw.raw_text
            confidences[column] = reading.confidence
            source_id = f"src-v2-{column.replace('_', '-')}"
            observations[source_id] = Observation(
                source_id=source_id,
                capture_status="OK",
                crop_content_status="CONTENT",
                ocr_status="OK",
                parse_status="OK",
                stability_status="NOT_EVALUATED",
                value_status="OK",
                raw_text=raw.raw_text,
                raw_truncated=raw.raw_truncated,
                raw_original_utf8_bytes=raw.raw_original_utf8_bytes,
                normalized_value=parsed.normalized_value,
                value_kind=parsed.value_kind,
                pixel_sha256=reading.pixel_sha256,
                ocr_executed=reading.ocr_executed,
                confirmation="new_ocr" if reading.ocr_executed else "pixel_hash_cache",
            )
            if reading.crop_png is not None:
                crops[source_id] = reading.crop_png
        return CapturedPoint(values, methods, raw_texts, confidences), observations, crops


class AutoCaptureEngine:
    """Poll stable combined values and emit only retained changes."""

    def __init__(
        self,
        pipeline: CapturePipeline,
        on_point: Callable[[CapturedPoint], None],
        *,
        interval_ms: int = 500,
        confirmations: int = 2,
        zone_failure_limit: int = 3,
        on_health: Callable[[ZoneHealthSnapshot], None] | None = None,
        health_monitor: ZoneHealthMonitor | None = None,
    ) -> None:
        if not pipeline.mapping.automatic:
            raise ValueError("automatic capture only supports screen OCR and clipboard")
        self.pipeline = pipeline
        self.on_point = on_point
        configs = []
        for column, source in pipeline.mapping.channels.items():
            configs.append(SourceConfig(
                source_id=f"src-v2-{column.replace('_', '-')}",
                display_name=column.replace("_", " ").title(),
                data_type=source.data_type,
                semantic_role=column if column in {"x", "y", "z"} else "none",
                decimal_separator=source.decimal_separator,
                numeric_range=source.numeric_range,
                rect=source.zone or (0, 0, 8, 8),
                coordinate_basis="monitor",
            ))
        self.stability = StabilityEngine(
            configs,
            confirmations=confirmations,
            debounce_ms=0,
            min_change_threshold=None,
            retention_mode="changed_only",
        )
        self.scheduler = TickScheduler(interval_ms, self.poll, lambda: None)
        self._frame = 0
        self.on_health = on_health
        self.health = health_monitor or ZoneHealthMonitor(zone_failure_limit)
        self.paused = False

    def poll(self) -> CapturedPoint | None:
        display_event = self.health.check_display()
        if display_event is not None:
            self.pause()
            if self.on_health is not None:
                self.on_health(display_event)
            return None
        try:
            point, observations, crops = self.pipeline.read()
            self._require_automatic_ocr_confidence(point)
        except (ValueError, RuntimeError) as exc:
            if self.on_health is None:
                raise
            snapshot = self.health.failure(exc)
            if snapshot.paused:
                self.pause()
            self.on_health(snapshot)
            return None
        if self.on_health is not None:
            self.on_health(self.health.success(dict(point.raw_texts)))
        self._frame += 1
        decision = self.stability.process_tick(
            observations,
            frame_id=f"v2-{self._frame:08d}-{secrets.token_hex(3)}",
            monotonic_ms=time.monotonic() * 1000.0,
            crop_bytes=crops,
        )
        if decision.event_status == "RETAINED_CHANGE":
            self.on_point(point)
            return point
        return None

    def start(self) -> None:
        self.paused = False
        self.scheduler.start()

    def pause(self) -> None:
        self.paused = True
        self.scheduler.pause()

    def resume(self) -> None:
        self.paused = False
        self.scheduler.resume()

    def force_capture(self) -> CapturedPoint:
        point, _observations, _crops = self.pipeline.read()
        self._require_automatic_ocr_confidence(point)
        self.on_point(point)
        return point

    def _require_automatic_ocr_confidence(self, point: CapturedPoint) -> None:
        for column, source in self.pipeline.mapping.channels.items():
            if (
                source.source_type in {"screen_zone_ocr", "screen_cursor_ocr"}
                and point.confidences[column] is None
            ):
                raise ValueError(
                    f"{column} automatic OCR confidence is unavailable; "
                    "automatic capture requires Tesseract confidence"
                )

    def stop(self) -> None:
        self.paused = False
        self.scheduler.stop()
