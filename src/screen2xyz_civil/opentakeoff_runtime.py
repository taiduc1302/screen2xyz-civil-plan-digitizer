"""Real optional OpenTakeoff MCP subprocess integration.

Unlike :mod:`screen2xyz_civil.adapters.opentakeoff`, which is a pure coordinate
contract, this module actually launches an installed ``opentakeoff-mcp`` stdio
server through the official MCP Python client.  It remains optional: failure to
find/start OpenTakeoff never corrupts the Screen2XYZ session and the agent can
fall back to explicit manual polygon/line proposals.
"""

from __future__ import annotations

import os
import shlex
import shutil
from dataclasses import dataclass
from typing import Any

from .agent_session import AgentSessionError, AgentTakeoffSession


OPENTAKEOFF_EXPECTED_VERSION = "0.9.68"
REQUIRED_TOOLS = frozenset(
    {
        "load_plan",
        "sheet_info",
        "set_scale",
        "one_click",
        "measure_polygon",
        "measure_line",
        "view_sheet",
    }
)
METRES_PER_FOOT = 0.3048


class OpenTakeoffRuntimeError(RuntimeError):
    """The optional OpenTakeoff process/protocol failed safely."""


@dataclass(frozen=True)
class OpenTakeoffCommand:
    command: str
    args: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"command": self.command, "args": list(self.args)}


@dataclass(frozen=True)
class OpenTakeoffProbe:
    available: bool
    command: OpenTakeoffCommand | None
    server_name: str = ""
    server_version: str = ""
    tools: tuple[str, ...] = ()
    missing_tools: tuple[str, ...] = ()
    error: str = ""

    @property
    def compatible(self) -> bool:
        return self.available and not self.missing_tools

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "compatible": self.compatible,
            "command": None if self.command is None else self.command.to_dict(),
            "server_name": self.server_name,
            "server_version": self.server_version,
            "expected_reviewed_version": OPENTAKEOFF_EXPECTED_VERSION,
            "tools": list(self.tools),
            "missing_tools": list(self.missing_tools),
            "error": self.error,
        }


def resolve_opentakeoff_command() -> OpenTakeoffCommand | None:
    """Return a local command only; never auto-download packages at runtime."""

    override = os.environ.get("SCREEN2XYZ_OPENTAKEOFF_CMD", "").strip()
    if override:
        parts = shlex.split(override, posix=os.name != "nt")
        if not parts:
            return None
        return OpenTakeoffCommand(parts[0], tuple(parts[1:]))
    executable = shutil.which("opentakeoff-mcp")
    if executable:
        return OpenTakeoffCommand(executable)
    return None


def _mcp_imports():
    try:
        from mcp import Client, StdioServerParameters
    except ImportError as exc:  # pragma: no cover - diagnosed by doctor command
        raise OpenTakeoffRuntimeError(
            "MCP Python SDK is unavailable; install requirements-civil.txt"
        ) from exc
    return Client, StdioServerParameters


async def probe_opentakeoff() -> OpenTakeoffProbe:
    command = resolve_opentakeoff_command()
    if command is None:
        return OpenTakeoffProbe(
            available=False,
            command=None,
            error=(
                "opentakeoff-mcp was not found on PATH. Install the reviewed "
                f"OpenTakeoff MCP package (target {OPENTAKEOFF_EXPECTED_VERSION}) "
                "or set SCREEN2XYZ_OPENTAKEOFF_CMD."
            ),
        )
    Client, StdioServerParameters = _mcp_imports()
    params = StdioServerParameters(command=command.command, args=list(command.args))
    try:
        async with Client(params) as client:
            listed = await client.list_tools()
            names = tuple(sorted(tool.name for tool in listed.tools))
            missing = tuple(sorted(REQUIRED_TOOLS - set(names)))
            info = client.server_info
            return OpenTakeoffProbe(
                available=True,
                command=command,
                server_name="" if info is None else str(info.name),
                server_version=(
                    "" if info is None or getattr(info, "version", None) is None
                    else str(info.version)
                ),
                tools=names,
                missing_tools=missing,
            )
    except Exception as exc:
        return OpenTakeoffProbe(
            available=False,
            command=command,
            error=f"OpenTakeoff MCP launch/probe failed: {type(exc).__name__}: {exc}",
        )


def _tool_payload(result: Any, tool_name: str) -> dict[str, Any]:
    if getattr(result, "is_error", False):
        text_parts: list[str] = []
        for block in getattr(result, "content", []) or []:
            text = getattr(block, "text", None)
            if text:
                text_parts.append(str(text))
        detail = " ".join(text_parts).strip() or "unknown MCP tool error"
        raise OpenTakeoffRuntimeError(f"OpenTakeoff {tool_name} failed: {detail}")
    payload = getattr(result, "structured_content", None)
    if not isinstance(payload, dict):
        raise OpenTakeoffRuntimeError(
            f"OpenTakeoff {tool_name} returned no structured content"
        )
    return dict(payload)


def _sheet_key(load_payload: dict[str, Any], page_number: int) -> str:
    for sheet in load_payload.get("sheets", []):
        if int(sheet.get("page", -1)) == int(page_number):
            return str(sheet["sheet"])
    raise OpenTakeoffRuntimeError(
        f"OpenTakeoff load_plan did not expose page {page_number}"
    )


def _agent_point_to_opentakeoff(
    session: AgentTakeoffSession,
    x: float,
    y: float,
    *,
    coordinate_frame: str,
    render_dpi: float | None,
) -> tuple[float, float]:
    points = session.canonical_points(
        ((x, y),),
        coordinate_frame=coordinate_frame,
        render_dpi=render_dpi,
    )
    point = points[0]
    return point.x * 2.0, point.y * 2.0


async def auto_trace_area(
    session: AgentTakeoffSession,
    *,
    x: float,
    y: float,
    coordinate_frame: str = "render_px",
    render_dpi: float | None = None,
    sensitivity: float | None = None,
    layers_include: list[str] | None = None,
    layers_exclude: list[str] | None = None,
) -> dict[str, Any]:
    """Run OpenTakeoff One-Click and return a normalized uncommitted trace.

    The OpenTakeoff process is intentionally short-lived for the pilot: each
    call loads the source PDF, optionally sets the Screen2XYZ-resolved scale,
    traces one region with ``return_verts=true``, then shuts down.  Screen2XYZ
    remains the persistent project/state owner.
    """

    session.verify_source_unchanged()
    command = resolve_opentakeoff_command()
    if command is None:
        raise OpenTakeoffRuntimeError(
            "opentakeoff-mcp is not installed or configured"
        )
    if sensitivity is not None and not 0.0 <= float(sensitivity) <= 1.0:
        raise OpenTakeoffRuntimeError("sensitivity must be between 0 and 1")
    Client, StdioServerParameters = _mcp_imports()
    params = StdioServerParameters(command=command.command, args=list(command.args))
    page_number = session.page_index + 1
    seed_x, seed_y = _agent_point_to_opentakeoff(
        session,
        float(x),
        float(y),
        coordinate_frame=coordinate_frame,
        render_dpi=render_dpi,
    )
    try:
        async with Client(params) as client:
            listed = await client.list_tools()
            names = {tool.name for tool in listed.tools}
            missing = REQUIRED_TOOLS - names
            if missing:
                raise OpenTakeoffRuntimeError(
                    f"OpenTakeoff is missing required tool(s): {sorted(missing)}"
                )
            loaded = _tool_payload(
                await client.call_tool("load_plan", {"path": str(session.source_path)}),
                "load_plan",
            )
            sheet = _sheet_key(loaded, page_number)
            scale_reply: dict[str, Any] | None = None
            if session.scale.resolved and session.scale.metres_per_point is not None:
                # OpenTakeoff coordinate pixel = half a PDF point, so each engine
                # pixel spans 0.5 canonical points.
                metres_per_engine_px = session.scale.metres_per_point / 2.0
                feet_per_engine_px = metres_per_engine_px / METRES_PER_FOOT
                scale_reply = _tool_payload(
                    await client.call_tool(
                        "set_scale",
                        {"sheet": sheet, "upp": feet_per_engine_px},
                    ),
                    "set_scale",
                )
            arguments: dict[str, Any] = {
                "sheet": sheet,
                "x": seed_x,
                "y": seed_y,
                "return_verts": True,
            }
            if sensitivity is not None:
                arguments["sensitivity"] = float(sensitivity)
            if layers_include or layers_exclude:
                layers: dict[str, Any] = {}
                if layers_include:
                    layers["include"] = list(layers_include)
                if layers_exclude:
                    layers["exclude"] = list(layers_exclude)
                arguments["layers"] = layers
            trace = _tool_payload(
                await client.call_tool("one_click", arguments),
                "one_click",
            )
    except OpenTakeoffRuntimeError:
        raise
    except Exception as exc:
        raise OpenTakeoffRuntimeError(
            f"OpenTakeoff auto-trace failed: {type(exc).__name__}: {exc}"
        ) from exc

    verts = trace.get("verts")
    if not isinstance(verts, list) or len(verts) < 3:
        raise OpenTakeoffRuntimeError(
            "OpenTakeoff one_click returned no usable polygon vertices"
        )
    canonical = session.canonical_points(
        verts,
        coordinate_frame="opentakeoff_px",
    )
    return {
        "engine": "OpenTakeoff",
        "reviewed_upstream_version": OPENTAKEOFF_EXPECTED_VERSION,
        "sheet": sheet,
        "seed_opentakeoff_px": [seed_x, seed_y],
        "scale_reply": scale_reply,
        "geometry_pdf_points": [point.to_dict() for point in canonical],
        "geometry_opentakeoff_px": verts,
        "nverts": len(canonical),
        "confidence": trace.get("confidence"),
        "confidence_factors": trace.get("confidence_factors", []),
        "raster_traced": bool(trace.get("raster_traced", False)),
        "hatch_filtered": bool(trace.get("hatch_filtered", False)),
        "gap_bridged_px": trace.get("gap_bridged_px"),
        "gap_sealed_px": trace.get("gap_sealed_px"),
        "warning": trace.get("warning"),
        "area_sf": trace.get("area_sf"),
        "perimeter_lf": trace.get("perimeter_lf"),
        "area_px2": trace.get("area_px2"),
        "perimeter_px": trace.get("perimeter_px"),
        "raw": trace,
    }
