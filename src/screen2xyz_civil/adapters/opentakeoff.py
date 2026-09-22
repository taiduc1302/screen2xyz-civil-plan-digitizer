"""Optional bridge contract for the Apache-2.0 OpenTakeoff MCP engine.

The core Civil Plan Digitizer never shells out to Node or assumes that the MCP
server is installed.  This module only performs explicit, testable coordinate
and request translation.  A process/service runner may execute the returned
calls later.

OpenTakeoff snapshot reviewed for this contract:
Kentucky-ai/opentakeoff@d5b9ba5b766911143a35fa36926a6ca3bfba794b

At that snapshot OpenTakeoff states one MCP coordinate frame: image pixels at
render scale 2.0 (PDF points x 2), top-left origin, y down.  `measure_polygon`
uses `verts`; `measure_line` uses `pts`; `set_scale.upp` is real feet per
OpenTakeoff image pixel.  We keep those assumptions named here rather than
letting them leak through the civil domain.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ..takeoff import LINE, POLYGON, TakeoffError, TakeoffMeasurement, TakeoffVertex


OPEN_TAKEOFF_RENDER_PX_PER_PDF_POINT = 2.0
PDF_POINTS_PER_INCH = 72.0
METRES_PER_FOOT = 0.3048


class OpenTakeoffBridgeError(TakeoffError):
    """A takeoff cannot be represented safely in the OpenTakeoff contract."""


@dataclass(frozen=True)
class OpenTakeoffCall:
    tool: str
    arguments: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"tool": self.tool, "arguments": dict(self.arguments)}


@dataclass(frozen=True)
class OpenTakeoffCoordinateFrame:
    """Map one Screen2XYZ PDF render into OpenTakeoff's render-scale-2 frame."""

    source_dpi: float
    engine_px_per_pdf_point: float = OPEN_TAKEOFF_RENDER_PX_PER_PDF_POINT

    def __post_init__(self) -> None:
        if not math.isfinite(self.source_dpi) or self.source_dpi <= 0:
            raise OpenTakeoffBridgeError("source DPI must be positive")
        if (
            not math.isfinite(self.engine_px_per_pdf_point)
            or self.engine_px_per_pdf_point <= 0
        ):
            raise OpenTakeoffBridgeError("engine pixel scale must be positive")

    @property
    def engine_px_per_source_px(self) -> float:
        source_px_per_pdf_point = self.source_dpi / PDF_POINTS_PER_INCH
        return self.engine_px_per_pdf_point / source_px_per_pdf_point

    def point(self, vertex: TakeoffVertex) -> list[float]:
        factor = self.engine_px_per_source_px
        return [vertex.x * factor, vertex.y * factor]

    def metres_per_engine_px(self, metres_per_source_px: float) -> float:
        if not math.isfinite(metres_per_source_px) or metres_per_source_px <= 0:
            raise OpenTakeoffBridgeError("metres_per_source_px must be positive")
        # One engine pixel spans source_px_per_engine_px source pixels.
        source_px_per_engine_px = 1.0 / self.engine_px_per_source_px
        return metres_per_source_px * source_px_per_engine_px

    def feet_per_engine_px(self, metres_per_source_px: float) -> float:
        return self.metres_per_engine_px(metres_per_source_px) / METRES_PER_FOOT


@dataclass(frozen=True)
class OpenTakeoffBridgePlan:
    """Pure request plan; execution is deliberately outside the core package."""

    sheet: str
    calls: tuple[OpenTakeoffCall, ...]
    upstream_commit: str = "d5b9ba5b766911143a35fa36926a6ca3bfba794b"

    def to_dict(self) -> dict[str, Any]:
        return {
            "sheet": self.sheet,
            "upstream_commit": self.upstream_commit,
            "calls": [call.to_dict() for call in self.calls],
        }


def build_measure_call(
    measurement: TakeoffMeasurement,
    *,
    sheet: str,
    frame: OpenTakeoffCoordinateFrame,
    condition: str | None = None,
) -> OpenTakeoffCall:
    """Translate normalized civil geometry into one OpenTakeoff measure call."""

    if not sheet.strip():
        raise OpenTakeoffBridgeError("OpenTakeoff sheet key is required")
    if measurement.geometry.kind == POLYGON:
        arguments: dict[str, Any] = {
            "sheet": sheet,
            "verts": [frame.point(vertex) for vertex in measurement.geometry.vertices],
            "role": "floor_area",
        }
        if condition:
            arguments["condition"] = condition
        return OpenTakeoffCall("measure_polygon", arguments)
    if measurement.geometry.kind == LINE:
        arguments = {
            "sheet": sheet,
            "pts": [frame.point(vertex) for vertex in measurement.geometry.vertices],
        }
        if condition:
            arguments["condition"] = condition
        return OpenTakeoffCall("measure_line", arguments)
    raise OpenTakeoffBridgeError(
        "initial civil OpenTakeoff bridge supports line and polygon measurements only"
    )


def build_scale_call(
    *,
    sheet: str,
    frame: OpenTakeoffCoordinateFrame,
    metres_per_source_px: float,
) -> OpenTakeoffCall:
    """Translate reviewed Screen2XYZ scale to OpenTakeoff `upp` feet/image-px."""

    if not sheet.strip():
        raise OpenTakeoffBridgeError("OpenTakeoff sheet key is required")
    return OpenTakeoffCall(
        "set_scale",
        {
            "sheet": sheet,
            "upp": frame.feet_per_engine_px(metres_per_source_px),
        },
    )


def build_bridge_plan(
    measurement: TakeoffMeasurement,
    *,
    sheet: str,
    source_dpi: float,
    metres_per_source_px: float,
    commit_as_condition: bool = False,
) -> OpenTakeoffBridgePlan:
    """Build the minimal explicit scale + measure sequence for one civil record.

    `commit_as_condition=False` is the safe default: OpenTakeoff is used as a
    measurement/overlay engine while Screen2XYZ remains the owner of approval.
    When a caller intentionally wants an upstream shape for visual review, the
    civil rule id is used as the OpenTakeoff condition tag.
    """

    frame = OpenTakeoffCoordinateFrame(source_dpi=source_dpi)
    condition = measurement.rule_id if commit_as_condition else None
    return OpenTakeoffBridgePlan(
        sheet=sheet,
        calls=(
            build_scale_call(
                sheet=sheet,
                frame=frame,
                metres_per_source_px=metres_per_source_px,
            ),
            build_measure_call(
                measurement,
                sheet=sheet,
                frame=frame,
                condition=condition,
            ),
        ),
    )


def screen2xyz_quantity_from_opentakeoff_reply(
    measurement: TakeoffMeasurement,
    reply: dict[str, Any],
) -> float:
    """Normalize OpenTakeoff imperial reply values without making them final.

    OpenTakeoff reports `length_lf` for lines and `area_sf` for polygons.  The
    returned metric value is evidence/check math only.  The estimator approval
    path still computes the authoritative quantity from Screen2XYZ geometry and
    reviewed project calibration.
    """

    if measurement.geometry.kind == LINE:
        if "length_lf" not in reply:
            raise OpenTakeoffBridgeError("OpenTakeoff line reply lacks length_lf")
        value = float(reply["length_lf"]) * METRES_PER_FOOT
    elif measurement.geometry.kind == POLYGON:
        if "area_sf" not in reply:
            raise OpenTakeoffBridgeError("OpenTakeoff polygon reply lacks area_sf")
        value = float(reply["area_sf"]) * METRES_PER_FOOT * METRES_PER_FOOT
    else:
        raise OpenTakeoffBridgeError("unsupported OpenTakeoff reply geometry")
    if not math.isfinite(value) or value <= 0:
        raise OpenTakeoffBridgeError("OpenTakeoff reply quantity must be positive")
    return value
