"""Application orchestration kept independent from Tkinter."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .backends import DefaultReader
from .capture import AutoCaptureEngine, CapturePipeline, CapturedPoint, Reader
from .export import advanced_estimator_export, export_csv, export_xlsx
from .mapping import ChannelMapping
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
    ) -> None:
        self.mapping = mapping
        self.store = SessionStore(project_dir)
        self.session_id = self.store.start_session(mapping, calibration=calibration)
        self.pipeline = CapturePipeline(mapping, reader or DefaultReader())
        self.on_point = on_point
        self.row_count = 0
        self.last_point: CapturedPoint | None = None
        self.auto: AutoCaptureEngine | None = None

    def _retain(self, point: CapturedPoint) -> int:
        point_id = self.store.append_point(self.session_id, point)
        self.row_count += 1
        self.last_point = point
        if self.on_point is not None:
            self.on_point(point, self.row_count)
        return point_id

    def capture_click(self, context: dict[str, Any] | None = None) -> CapturedPoint:
        point, _observations, _crops = self.pipeline.read(context)
        self._retain(point)
        return point

    def start_auto(self, *, interval_ms: int = 500, confirmations: int = 2) -> None:
        if self.auto is not None:
            raise RuntimeError("automatic capture is already running")
        self.auto = AutoCaptureEngine(
            self.pipeline, self._retain,
            interval_ms=interval_ms, confirmations=confirmations,
        )
        self.auto.start()

    def stop(self) -> None:
        if self.auto is not None:
            self.auto.stop()
            self.auto = None

    def export_xlsx(self, path: Path) -> Path:
        return export_xlsx(self.store, self.session_id, path)

    def export_csv(self, path: Path) -> Path:
        return export_csv(self.store, self.session_id, path)

    def advanced_export(self, output_root: Path) -> dict[str, object]:
        return advanced_estimator_export(self.store, self.session_id, output_root)

    def close(self) -> None:
        self.stop()
        self.store.close()
