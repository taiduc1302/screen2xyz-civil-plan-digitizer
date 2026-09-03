"""Command-line entry point for the local Civil Plan Digitizer and takeoff pilot."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="screen2xyz_civil",
        description=(
            "Screen2XYZ Civil Plan Digitizer / review-first civil takeoff gateway"
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("ui", help="launch the existing civil terrain/point review workspace")

    doctor = sub.add_parser("doctor", help="check local PDF/MCP/takeoff dependencies")
    doctor.add_argument("--json", action="store_true", dest="as_json")
    doctor.add_argument(
        "--deep",
        action="store_true",
        help="also launch/probe the configured OpenTakeoff MCP process",
    )

    init = sub.add_parser(
        "agent-init",
        help="create a single-sheet .s2a.json session for Claude/AI takeoff proposals",
    )
    init.add_argument("pdf", help="immutable local tender/source PDF path")
    init.add_argument("--page", type=int, required=True, help="1-based PDF page number")
    init.add_argument("--page-label", default="", help="drawing sheet label, e.g. 03")
    init.add_argument("--name", default="", help="session/project display name")
    init.add_argument("--out", required=True, help="output path ending .s2a.json")
    init.add_argument("--render-dpi", type=int, default=150)

    working = sub.add_parser(
        "agent-working-copy",
        help="copy immutable source PDF to a separate editable Bluebeam working PDF",
    )
    working.add_argument("--session", required=True)
    working.add_argument("--out", required=True, help="editable Revu working PDF path")
    working.add_argument(
        "--replace",
        action="store_true",
        help="explicitly replace an existing working PDF with a fresh source copy",
    )

    register_working = sub.add_parser(
        "agent-register-working-copy",
        help="register an existing annotated Revu PDF after drawing-content validation",
    )
    register_working.add_argument("--session", required=True)
    register_working.add_argument("--pdf", required=True, help="existing editable Revu PDF")

    ratio = sub.add_parser(
        "agent-scale-ratio",
        help="resolve a whole-sheet pilot scale from a printed 1:N ratio",
    )
    ratio.add_argument("--session", required=True)
    ratio.add_argument("--ratio", type=float, required=True, help="N in printed 1:N")
    ratio.add_argument("--basis", required=True)
    ratio.add_argument(
        "--verified",
        action="store_true",
        help="human assertion only: basis includes an independent scale check",
    )

    calibrate = sub.add_parser(
        "agent-calibrate",
        help="resolve scale from two points and a known real distance",
    )
    calibrate.add_argument("--session", required=True)
    calibrate.add_argument("--x1", type=float, required=True)
    calibrate.add_argument("--y1", type=float, required=True)
    calibrate.add_argument("--x2", type=float, required=True)
    calibrate.add_argument("--y2", type=float, required=True)
    calibrate.add_argument("--known-m", type=float, required=True)
    calibrate.add_argument(
        "--frame",
        choices=("render_px", "pdf_points", "opentakeoff_px"),
        default="render_px",
    )
    calibrate.add_argument("--dpi", type=float, default=None)
    calibrate.add_argument("--basis", required=True)
    calibrate.add_argument(
        "--verified",
        action="store_true",
        help="human assertion only: this calibration is independently verified",
    )

    verify = sub.add_parser(
        "agent-verify-scale",
        help="independently verify an already resolved scale against another dimension",
    )
    verify.add_argument("--session", required=True)
    verify.add_argument("--x1", type=float, required=True)
    verify.add_argument("--y1", type=float, required=True)
    verify.add_argument("--x2", type=float, required=True)
    verify.add_argument("--y2", type=float, required=True)
    verify.add_argument("--known-m", type=float, required=True)
    verify.add_argument(
        "--frame",
        choices=("render_px", "pdf_points", "opentakeoff_px"),
        default="render_px",
    )
    verify.add_argument("--dpi", type=float, default=None)
    verify.add_argument("--basis", required=True)
    verify.add_argument("--tolerance-percent", type=float, default=1.0)

    plan = sub.add_parser(
        "agent-plan",
        help="export deterministic Bluebeam markup-plan JSON from the current session",
    )
    plan.add_argument("--session", required=True)
    plan.add_argument("--out", default="")

    status = sub.add_parser("agent-status", help="print session/scope/QA status")
    status.add_argument("--session", required=True)

    config = sub.add_parser(
        "agent-claude-config",
        help="print copy/paste Claude Code MCP registration for the session and Bluebeam",
    )
    config.add_argument("--session", required=True)
    config.add_argument("--json", action="store_true", dest="as_json")

    mcp = sub.add_parser(
        "mcp",
        help="serve one .s2a.json takeoff session to Claude Code or another MCP host",
    )
    mcp.add_argument("--session", required=True)
    mcp.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
    )
    mcp.add_argument("--host", default="127.0.0.1")
    mcp.add_argument("--port", type=int, default=8765)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = args.command or "ui"
    try:
        if command == "ui":
            from .ui.app import launch

            launch()
            return 0

        if command == "doctor":
            from .doctor import environment_report, format_environment_report

            report = environment_report(deep=args.deep)
            if args.as_json:
                print(json.dumps(report, indent=2, sort_keys=True))
            else:
                print(format_environment_report(report))
            return 0 if report["overall"] == "PASS" else 1

        if command == "agent-init":
            from .agent_session import new_agent_session, save_agent_session

            session = new_agent_session(
                Path(args.pdf),
                page_number=args.page,
                name=args.name or Path(args.pdf).stem,
                now=_now(),
                page_label=args.page_label or None,
                render_dpi=args.render_dpi,
            )
            identity = save_agent_session(session, Path(args.out), replace=False)
            print(json.dumps({"session": session.to_dict(), "saved": identity}, indent=2))
            return 0

        if command == "agent-working-copy":
            from .agent_session import load_agent_session, save_agent_session
            from .working_copy import create_working_copy, working_copy_status

            path = Path(args.session)
            session = load_agent_session(path)
            registered = create_working_copy(
                session,
                Path(args.out),
                now=_now(),
                replace=args.replace,
            )
            saved = save_agent_session(session, path, replace=True)
            print(
                json.dumps(
                    {
                        "working_copy": registered,
                        "status": working_copy_status(session),
                        "saved": saved,
                    },
                    indent=2,
                )
            )
            return 0

        if command == "agent-register-working-copy":
            from .agent_session import load_agent_session, save_agent_session
            from .working_copy import register_working_copy, working_copy_status

            path = Path(args.session)
            session = load_agent_session(path)
            registered = register_working_copy(
                session,
                Path(args.pdf),
                now=_now(),
                created_from_source=False,
            )
            saved = save_agent_session(session, path, replace=True)
            print(
                json.dumps(
                    {
                        "working_copy": registered,
                        "status": working_copy_status(session),
                        "saved": saved,
                    },
                    indent=2,
                )
            )
            return 0

        if command == "agent-scale-ratio":
            from .agent_session import load_agent_session, save_agent_session

            path = Path(args.session)
            session = load_agent_session(path)
            session.set_scale_ratio(
                args.ratio,
                now=_now(),
                basis=args.basis,
                verified=args.verified,
            )
            identity = save_agent_session(session, path, replace=True)
            print(json.dumps({"scale": session.scale.to_dict(), "saved": identity}, indent=2))
            return 0

        if command == "agent-calibrate":
            from .agent_session import load_agent_session, save_agent_session

            path = Path(args.session)
            session = load_agent_session(path)
            session.calibrate_scale(
                (args.x1, args.y1),
                (args.x2, args.y2),
                known_distance_m=args.known_m,
                coordinate_frame=args.frame,
                render_dpi=args.dpi,
                now=_now(),
                basis=args.basis,
                verified=args.verified,
            )
            identity = save_agent_session(session, path, replace=True)
            print(json.dumps({"scale": session.scale.to_dict(), "saved": identity}, indent=2))
            return 0

        if command == "agent-verify-scale":
            from .agent_session import load_agent_session, save_agent_session

            path = Path(args.session)
            session = load_agent_session(path)
            result = session.verify_scale(
                (args.x1, args.y1),
                (args.x2, args.y2),
                known_distance_m=args.known_m,
                coordinate_frame=args.frame,
                render_dpi=args.dpi,
                now=_now(),
                basis=args.basis,
                tolerance_percent=args.tolerance_percent,
            )
            identity = save_agent_session(session, path, replace=True)
            print(json.dumps({"verification": result, "scale": session.scale.to_dict(), "saved": identity}, indent=2))
            return 0 if result["passed"] else 1

        if command == "agent-plan":
            from .agent_session import (
                export_bluebeam_plan,
                load_agent_session,
                resolve_markup_plan_target,
            )
            from .scope_ledger import scope_summary
            from .working_copy import (
                bind_working_copy_to_markup_plan,
                working_copy_status,
            )

            path = Path(args.session)
            session = load_agent_session(path)
            target = resolve_markup_plan_target(
                session,
                path,
                args.out,
                confine_to_session_dir=False,
            )
            export_bluebeam_plan(session, target, replace=True)
            identity = bind_working_copy_to_markup_plan(session, target)
            print(
                json.dumps(
                    {
                        "saved": identity,
                        "working_copy": working_copy_status(session),
                        "scope": scope_summary(session),
                        "qa": session.qa_summary(),
                    },
                    indent=2,
                )
            )
            return 0

        if command == "agent-status":
            from .agent_session import load_agent_session
            from .scope_ledger import scope_summary
            from .working_copy import working_copy_status

            session = load_agent_session(Path(args.session))
            print(
                json.dumps(
                    {
                        "session_id": session.session_id,
                        "name": session.name,
                        "immutable_source": str(session.source_path),
                        "source_sha256": session.source_sha256,
                        "bluebeam_working_copy": working_copy_status(session),
                        "page_label": session.page_label,
                        "scale": session.scale.to_dict(),
                        "takeoffs": [
                            session.takeoff_summary(item) for item in session.measurements
                        ],
                        "scope": scope_summary(session),
                        "qa": session.qa_summary(),
                    },
                    indent=2,
                )
            )
            return 0

        if command == "agent-claude-config":
            from .agent_session import load_agent_session
            from .bluebeam_runtime import (
                bluebeam_claude_registration,
                claude_stdio_add_command,
            )
            from .working_copy import working_copy_status

            session_path = Path(args.session).expanduser().resolve()
            session = load_agent_session(session_path)
            working = working_copy_status(session)
            src_root = Path(__file__).resolve().parents[1]
            screen2xyz_command = claude_stdio_add_command(
                name="screen2xyz",
                executable=Path(sys.executable).resolve(),
                args=(
                    "-m",
                    "screen2xyz_civil",
                    "mcp",
                    "--session",
                    str(session_path),
                ),
                env={"PYTHONPATH": str(src_root)},
            )
            bluebeam = bluebeam_claude_registration()
            bluebeam["working_copy"] = working
            bluebeam["operator_ready"] = bool(
                bluebeam.get("available") and working.get("safe_for_bluebeam_operator")
            )
            if not working.get("safe_for_bluebeam_operator"):
                bluebeam["operator_blocker"] = working.get(
                    "reason", "NO_SAFE_BLUEBEAM_WORKING_COPY"
                )
            payload = {
                "session": {
                    "id": session.session_id,
                    "page_label": session.page_label,
                    "immutable_source": str(session.source_path),
                    "source_sha256": session.source_sha256,
                    "bluebeam_working_copy": working,
                },
                "screen2xyz": {
                    "capability_state": "LOCAL_STDIO_SERVER",
                    "claude_command": screen2xyz_command,
                },
                "bluebeam": bluebeam,
                "next_steps": [
                    "Keep the immutable source PDF unchanged; Screen2XYZ deliberately verifies its exact SHA-256.",
                    "Open/save native Revu markups only in the registered Bluebeam working copy, never in the immutable source.",
                    "Run the Screen2XYZ claude_command once, then confirm it with `claude mcp get screen2xyz` or `/mcp`.",
                    "If Bluebeam operator_ready is true, open the exact registered working-copy PDF in Revu, enable MCP, run the Bluebeam claude_command, and confirm tools appear in `/mcp`.",
                    "Bluebeam discovery/registration is not LIVE_TESTED measurement capability. Run the disposable native Length+Area acceptance gate before production native measurement creation.",
                    "Start Claude Code from this repository and use prompts/CLAUDE_CODE_BLUEBEAM_TAKEOFF_PROMPT.md.",
                ],
            }
            if args.as_json:
                print(json.dumps(payload, indent=2))
            else:
                print("Immutable Screen2XYZ source:\n" + str(session.source_path))
                print("\nScreen2XYZ Claude Code registration:\n" + screen2xyz_command)
                if not working.get("safe_for_bluebeam_operator"):
                    print(
                        "\nBluebeam registration withheld: first create/register a separate "
                        "working PDF (`agent-working-copy` or `agent-register-working-copy`). "
                        f"Reason: {working.get('reason')}"
                    )
                elif bluebeam["available"]:
                    print("\nOpen this editable PDF in Revu:\n" + str(working["path"]))
                    print("\nBluebeam Revu MCP candidate registration (NOT LIVE_TESTED):\n" + str(bluebeam["claude_command"]))
                else:
                    print("\nBluebeam Revu MCP: not discovered on this machine.")
                print("\nThen verify connected servers with `/mcp` before running the takeoff prompt.")
            return 0

        if command == "mcp":
            from .mcp_gateway import run_mcp_server

            run_mcp_server(
                Path(args.session),
                transport=args.transport,
                host=args.host,
                port=args.port,
            )
            return 0

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())