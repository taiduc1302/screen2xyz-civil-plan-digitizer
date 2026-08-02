"""Application orchestration kept independent from Tkinter."""

from __future__ import annotations

from pathlib import Path
from dataclasses import replace
from typing import Any, Callable

from .backends import DefaultReader
from .capture import AutoCaptureEngine, CapturePipeline, CapturedPoint, Reader
from .export import advanced_estimator_export, export_csv, export_xlsx
from .mapping import ChannelMapping
from .operations import SessionOptions, ZoneHealthSnapshot
from .store import SessionStore


class CaptureSessionController:
    def __init__(
        self,
        project_dir: Path,
        mapping: ChannelMapping,
        *,
        reader: Reader | None = None,
        calibration: dict[str, Any] | None = None,
        on_point: Callable[[CapturedPoint, int], None] | None = None,
        on_health: Callable[[ZoneHealthSnapshot], None] | None = None,
        options: SessionOptions | None = None,
    ) -> None:
        self.mapping = mapping
        self.store = SessionStore(project_dir)
        self.session_id = self.store.start_session(mapping, calibration=calibration)
        self.reader = reader or DefaultReader()
        self.pipeline = CapturePipeline(mapping, self.reader)
        self.on_point = on_point
        self.on_health = on_health
        self.options = options or SessionOptions()
        self.row_count = 0
        self.last_point: CapturedPoint | None = None
        self._last_retained_xy: tuple[float, float] | None = None
        self.auto: AutoCaptureEngine | None = None
        self.stopped = False

    def _retain(self, point: CapturedPoint) -> int | None:
        if not self.options.accepts(self._last_retained_xy, point.x, point.y):
            return None
        values = dict(point.values)
        if not values.get("point_number"):
            values["point_number"] = self.options.point_number(self.row_count)
            point = replace(point, values=values)
        point_id = self.store.append_point(self.session_id, point)
        self.row_count += 1
        self.last_point = point
        self._last_retained_xy = (point.x, point.y)
        if self.on_point is not None:
            self.on_point(point, self.row_count)
        return point_id

    def capture_click(self, context: dict[str, Any] | None = None) -> CapturedPoint:
        if self.stopped:
            raise RuntimeError("capture is stopped; start a new session first")
        point, _observations, _crops = self.pipeline.read(context)
        self._retain(point)
        return point

    def start_auto(self, *, interval_ms: int = 500, confirmations: int = 2) -> None:
        if self.stopped:
            raise RuntimeError("capture is stopped; start a new session first")
        if self.auto is not None:
            raise RuntimeError("automatic capture is already running")
        self.auto = AutoCaptureEngine(
            self.pipeline, self._retain,
            interval_ms=interval_ms, confirmations=confirmations,
            zone_failure_limit=self.options.zone_failure_limit,
            on_health=self.on_health,
        )
        self.auto.start()

    @property
    def paused(self) -> bool:
        return bool(self.auto and self.auto.paused)

    def pause(self) -> None:
        if self.auto is not None:
            self.auto.pause()

    def resume(self) -> None:
        if self.auto is not None:
            self.auto.resume()

    def toggle_pause(self) -> None:
        if self.auto is None:
            self.start_auto()
        elif self.auto.paused:
            self.auto.resume()
        else:
            self.auto.pause()

    def force_capture(self) -> CapturedPoint:
        if self.stopped:
            raise RuntimeError("capture is stopped; force capture is unavailable")
        if self.auto is not None:
            return self.auto.force_capture()
        return self.capture_click()

    def test_mapping(self, context: dict[str, Any] | None = None) -> CapturedPoint:
        point, _observations, _crops = self.pipeline.read(context)
        return point

    def stop(self) -> None:
        if self.auto is not None:
            self.auto.stop()
            self.auto = None
        self.stopped = True

    def reconfigure(self, mapping: ChannelMapping) -> None:
        """Replace zones in the active session without abandoning retained rows."""
        if self.stopped:
            raise RuntimeError("a stopped session cannot be reconfigured")
        was_automatic = self.auto is not None
        if self.auto is not None:
            self.auto.stop()
            self.auto = None
        self.store.update_session_mapping(self.session_id, mapping)
        self.mapping = mapping
        self.pipeline = CapturePipeline(mapping, self.reader)
        if was_automatic and mapping.automatic:
            self.start_auto()

    def export_xlsx(self, path: Path) -> Path:
        return export_xlsx(self.store, self.session_id, path)

    def export_csv(self, path: Path) -> Path:
        return export_csv(self.store, self.session_id, path)

    def advanced_export(self, output_root: Path) -> dict[str, object]:
        return advanced_estimator_export(self.store, self.session_id, output_root)

    def points(self):
        return self.store.points(self.session_id)

    def edit_point(self, point_id: int, changes: dict[str, Any]) -> None:
        self.store.edit_point(self.session_id, point_id, changes)

    def delete_point(self, point_id: int) -> None:
        self.store.delete_point(self.session_id, point_id)
        self.row_count = len(self.store.points(self.session_id))

    def close(self) -> None:
        self.stop()
        self.store.close()
