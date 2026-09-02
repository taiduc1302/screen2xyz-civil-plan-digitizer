"""One-command environment diagnostics for the civil takeoff/Claude pilot."""

from __future__ import annotations

import asyncio
import importlib.util
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from .opentakeoff_runtime import probe_opentakeoff, resolve_opentakeoff_command


def _module(name: str, *, required: bool) -> dict[str, Any]:
    available = importlib.util.find_spec(name) is not None
    return {
        "name": name,
        "kind": "python-module",
        "required": required,
        "available": available,
        "status": "PASS" if available else ("FAIL" if required else "OPTIONAL_MISSING"),
    }


def _executable(name: str, *, required: bool) -> dict[str, Any]:
    path = shutil.which(name)
    return {
        "name": name,
        "kind": "executable",
        "required": required,
        "available": bool(path),
        "path": path or "",
        "status": "PASS" if path else ("FAIL" if required else "OPTIONAL_MISSING"),
    }


def environment_report(*, deep: bool = False) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    py_ok = sys.version_info >= (3, 10)
    checks.append(
        {
            "name": "python>=3.10",
            "kind": "runtime",
            "required": True,
            "available": py_ok,
            "version": sys.version.split()[0],
            "status": "PASS" if py_ok else "FAIL",
        }
    )
    for name, required in (
        ("tkinter", True),
        ("pypdf", True),
        ("pypdfium2", True),
        ("PIL", True),
        ("openpyxl", True),
        ("mcp", True),
        ("defusedxml", True),
    ):
        checks.append(_module(name, required=required))

    # The Claude/operator path uses bundled PDFium through pypdfium2. Poppler
    # remains a supported legacy renderer fallback, but is no longer a hard
    # prerequisite for the operator pilot.
    checks.append(_executable("pdftoppm", required=False))
    checks.append(_executable("tesseract", required=False))
    checks.append(_executable("claude", required=False))
    checks.append(_executable("node", required=False))
    checks.append(_executable("npm", required=False))
    checks.append(_executable("npx", required=False))

    command = resolve_opentakeoff_command()
    checks.append(
        {
            "name": "opentakeoff-mcp",
            "kind": "optional-engine",
            "required": False,
            "available": command is not None,
            "command": None if command is None else command.to_dict(),
            "status": "PASS" if command is not None else "OPTIONAL_MISSING",
            "note": (
                "Required only for auto_trace_area; manual/agent line and polygon proposals still work without it."
            ),
        }
    )

    deep_probe: dict[str, Any] | None = None
    if deep and command is not None and importlib.util.find_spec("mcp") is not None:
        try:
            deep_probe = asyncio.run(probe_opentakeoff()).to_dict()
        except Exception as exc:  # pragma: no cover - host dependent diagnostic
            deep_probe = {
                "available": False,
                "compatible": False,
                "error": f"probe failed: {type(exc).__name__}: {exc}",
            }

    required_failures = [
        item["name"] for item in checks if item["required"] and item["status"] != "PASS"
    ]
    claude_available = any(
        item["name"] == "claude" and item["available"] for item in checks
    )
    return {
        "overall": "PASS" if not required_failures else "FAIL",
        "required_failures": required_failures,
        "checks": checks,
        "opentakeoff_deep_probe": deep_probe,
        "environment": {
            "platform": sys.platform,
            "cwd": str(Path.cwd()),
            "SCREEN2XYZ_OPENTAKEOFF_CMD": os.environ.get(
                "SCREEN2XYZ_OPENTAKEOFF_CMD", ""
            ),
        },
        "readiness": {
            "screen2xyz_mcp_server": not required_failures,
            "claude_code_client": bool(not required_failures and claude_available),
            "manual_agent_proposals": not required_failures,
            "opentakeoff_auto_trace": bool(
                not required_failures
                and command is not None
                and (deep_probe is None or deep_probe.get("compatible", False))
            ),
        },
    }


def format_environment_report(report: dict[str, Any]) -> str:
    lines = [f"Screen2XYZ doctor: {report['overall']}"]
    for item in report["checks"]:
        suffix = ""
        if item.get("path"):
            suffix = f" ({item['path']})"
        elif item.get("version"):
            suffix = f" ({item['version']})"
        lines.append(f"  {item['status']:16} {item['name']}{suffix}")
    probe = report.get("opentakeoff_deep_probe")
    if probe is not None:
        lines.append(
            "  {:16} {}{}".format(
                "PASS" if probe.get("compatible") else "OPTIONAL_FAIL",
                "OpenTakeoff protocol probe",
                f" - {probe.get('error')}" if probe.get("error") else "",
            )
        )
    if report["required_failures"]:
        lines.append("Required failures: " + ", ".join(report["required_failures"]))
    else:
        lines.append("Required local Screen2XYZ runtime checks passed.")
    if not report["readiness"]["claude_code_client"]:
        lines.append(
            "Claude Code executable was not found; Screen2XYZ can still run/test locally, "
            "but install/configure Claude Code before the operator pilot."
        )
    return "\n".join(lines)