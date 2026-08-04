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
    capture_status: str = "COMPLETE"
    channel_failures: dict[str, str] = field(default_factory=dict)
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
    def z(self) -> float | None:
        value = self.values["z"]
        return None if value is None else float(value)


Reader = Callable[[str, ChannelSource, dict[str, Any]], Reading]


class ChannelReadError(ValueError):
    """One or more mapped channels failed during the same capture attempt."""

    def __init__(
        self,
        failures: dict[str, str],
        successful_readouts: dict[str, str],
    ) -> None:
        self.failures = dict(failures)
        self.successful_readouts = dict(successful_readouts)
        details = "; ".join(f"{name}: {reason}" for name, reason in failures.items())
        super().__init__(f"mapped channel read failed — {details}")


class CapturePipeline:
    def __init__(
        self,
        mapping: ChannelMapping,
        reader: Reader,
        *,
        allow_partial_z: bool = False,
    ) -> None:
        mapping.validate()
        self.mapping = mapping
        self.reader = reader
        self.allow_partial_z = allow_partial_z

    def read(self, context: dict[str, Any] | None = None) -> tuple[CapturedPoint, dict[str, Observation], dict[str, bytes]]:
        context = context or {}
        values: dict[str, float | str | None] = {}
        methods: dict[str, str] = {}
        raw_texts: dict[str, str] = {}
        confidences: dict[str, float | None] = {}
        observations: dict[str, Observation] = {}
        crops: dict[str, bytes] = {}
        failures: dict[str, str] = {}
        for column, source in self.mapping.channels.items():
            try:
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
                    raise ValueError(f"could not be parsed: {parsed.parse_status}")
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
            except (ValueError, RuntimeError) as exc:
                failures[column] = str(exc)
        if failures and not (
            self.allow_partial_z and set(failures) == {"z"}
        ):
            raise ChannelReadError(failures, raw_texts)
        if "z" in failures:
            source = self.mapping.channels["z"]
            values["z"] = None
            methods["z"] = source.source_type
            raw_texts["z"] = ""
            confidences["z"] = None
        status = "PARTIAL_MISSING_Z" if failures else "COMPLETE"
        return CapturedPoint(
            values,
            methods,
            raw_texts,
            confidences,
            status,
            failures,
        ), observations, crops


class AutoCaptureEngine:
    """Poll stable combined values and emit only retained changes."""

    def __init__(
        self,
        pipeline: CapturePipeline,
        on_point: Callable[[CapturedPoint], None],
        *,
        interval_ms: int = 500,
        confirmations: int = 2,
        zone_failure_limit: int = 10,
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
        self.confirmations = confirmations
        self._frame = 0
        self.on_health = on_health
        self.health = health_monitor or ZoneHealthMonitor(
            zone_failure_limit,
            channel_names=pipeline.mapping.channels,
        )
        self.health.bind_channels(pipeline.mapping.channels)
        self.paused = False
        self._partial_candidate: tuple[float, float] | None = None
        self._partial_confirmations = 0
        self._last_partial_emitted: tuple[float, float] | None = None

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
            snapshot = self.health.success(
                dict(point.raw_texts), dict(point.channel_failures)
            )
            if snapshot.paused:
                self.pause()
            self.on_health(snapshot)
        if point.capture_status == "PARTIAL_MISSING_Z":
            signature = (point.x, point.y)
            if signature == self._partial_candidate:
                self._partial_confirmations += 1
            else:
                self._partial_candidate = signature
                self._partial_confirmations = 1
            if (
                self._partial_confirmations >= self.confirmations
                and signature != self._last_partial_emitted
            ):
                self.on_point(point)
                self._last_partial_emitted = signature
                return point
            return None
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
                and point.values.get(column) is not None
                and point.confidences[column] is None
            ):
                raise ValueError(
                    f"{column} automatic OCR confidence is unavailable; "
                    "automatic capture requires Tesseract confidence"
                )

    def stop(self) -> None:
        self.paused = False
        self.scheduler.stop()
