"""M2 command-line entry: UI launch, recovery, real-target validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .paths import run_root


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="screen2xyz_m2",
        description="Screen2XYZ M2-Live opt-in screen-region watcher")
    parser.add_argument("--version", action="version",
                        version=f"screen2xyz_m2 {__version__}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("ui", help="launch the live watcher UI (default)")
    recover = sub.add_parser("recover",
                             help="rebuild exports of an unfinalized run")
    recover.add_argument("run_dir", help="run directory or run id")
    sub.add_parser("validate-real-target",
                   help="guided owner-machine G-E-REAL validation")
    demo = sub.add_parser(
        "demo", help="run the automated self-test against a synthetic "
                     "demo target (no real application needed)")
    demo.add_argument("--interactive", action="store_true",
                      help="just open the demo target window; do not run "
                           "the automated self-test")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = args.command or "ui"
    if command == "recover":
        from .recovery import recover_run
        candidate = Path(args.run_dir)
        if not candidate.exists():
            candidate = run_root() / args.run_dir
        try:
            result = recover_run(candidate)
        except Exception as exc:  # surfaced, not swallowed
            print(json.dumps({"status": "FAILED",
                              "error_type": type(exc).__name__,
                              "error": str(exc)}), file=sys.stderr)
            return 1
        print(json.dumps({"status": "RECOVERED",
                          "events": result["events"],
                          "warnings": result["warnings"]}, sort_keys=True))
        return 0
    if command == "validate-real-target":
        from .validate_real_target import run_validation
        return run_validation()
    if command == "demo":
        from .demo import launch_interactive, run_self_test_with_retries
        if args.interactive:
            session = launch_interactive()
            print(f"Demo target running: pid {session.ready['pid']}, "
                  f"hwnd {session.ready['hwnd']}. Press Enter to close it.")
            input()
            session.quit()
            return 0
        report = run_self_test_with_retries(
            on_progress=lambda msg: print(msg, file=sys.stderr))
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["overall"] == "PASS" else 1
    from .ui.app import launch
    launch()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
