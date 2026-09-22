"""Local Bluebeam MCP discovery and Claude Code registration helpers.

Bluebeam documents its local stdio MCP executable for supported desktop hosts.
Claude Code can host arbitrary local stdio MCP servers, but Bluebeam does not
currently publish a dedicated Claude Code setup guide.  Therefore discovery and
registration here establish only a plausible CURRENT_SURFACE route.  They do
not establish LIVE_TESTED native measurement creation; the owner-machine
acceptance gate must still pass create/save/readback for Length and Area.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


BLUEBEAM_MCP_RELATIVE = Path(
    "Bluebeam Software/Bluebeam Revu/21/Revu/mcp/Bluebeam MCP Server.exe"
)
BLUEBEAM_OVERRIDE_ENV = "SCREEN2XYZ_BLUEBEAM_MCP_EXE"


def candidate_bluebeam_mcp_paths(
    environ: Mapping[str, str] | None = None,
) -> tuple[Path, ...]:
    """Return deterministic candidate paths without launching Bluebeam."""

    env = os.environ if environ is None else environ
    candidates: list[Path] = []
    override = str(env.get(BLUEBEAM_OVERRIDE_ENV, "")).strip()
    if override:
        candidates.append(Path(override).expanduser())

    for key in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
        root = str(env.get(key, "")).strip()
        if root:
            candidates.append(Path(root) / BLUEBEAM_MCP_RELATIVE)

    # Useful when an intentionally minimal environment omits ProgramFiles.
    candidates.append(Path(r"C:\Program Files") / BLUEBEAM_MCP_RELATIVE)

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        marker = str(candidate).casefold()
        if marker not in seen:
            seen.add(marker)
            unique.append(candidate)
    return tuple(unique)


def resolve_bluebeam_mcp_executable(
    environ: Mapping[str, str] | None = None,
) -> Path | None:
    """Return the first existing Bluebeam MCP executable, if any."""

    for candidate in candidate_bluebeam_mcp_paths(environ):
        try:
            if candidate.is_file():
                return candidate.resolve()
        except OSError:
            continue
    return None


def _ps_quote(value: str) -> str:
    """PowerShell single-quote escaping for human-copyable commands."""

    return "'" + value.replace("'", "''") + "'"


def claude_stdio_add_command(
    *,
    name: str,
    executable: Path,
    args: tuple[str, ...] = (),
    env: Mapping[str, str] | None = None,
) -> str:
    """Render a copy/paste Claude Code local-stdio registration command."""

    if not name.strip():
        raise ValueError("MCP server name is required")
    parts = ["claude", "mcp", "add", "--transport", "stdio"]
    for key, value in (env or {}).items():
        if not key.strip():
            raise ValueError("MCP environment variable name is required")
        parts.extend(["--env", _ps_quote(f"{key}={value}")])
    parts.extend([name.strip(), "--", _ps_quote(str(executable))])
    parts.extend(_ps_quote(str(arg)) for arg in args)
    return " ".join(parts)


def bluebeam_claude_registration(
    environ: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Describe the direct local-stdio route without claiming it passed."""

    executable = resolve_bluebeam_mcp_executable(environ)
    if executable is None:
        return {
            "available": False,
            "executable": "",
            "claude_command": "",
            "capability_state": "NOT_DISCOVERED",
            "live_tested": False,
            "note": (
                "Bluebeam MCP executable was not found. Confirm Revu 21.10+, Max, "
                "and MCP Enabled, or set SCREEN2XYZ_BLUEBEAM_MCP_EXE."
            ),
        }
    return {
        "available": True,
        "executable": str(executable),
        "claude_command": claude_stdio_add_command(
            name="bluebeam-revu",
            executable=executable,
        ),
        "capability_state": "DISCOVERED_STDIO_ROUTE_NOT_LIVE_TESTED",
        "live_tested": False,
        "note": (
            "Registration only. After Claude Code lists Bluebeam tools, run the "
            "disposable Revu Length+Area create/save/readback acceptance gate before "
            "production native measurement creation."
        ),
    }
