"""Command-line entry point for the local Civil Plan Digitizer."""

from __future__ import annotations

import argparse

from . import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="screen2xyz_civil",
        description=(
            "Screen2XYZ Civil Plan Digitizer — local, review-first, "
            "preliminary civil point workflow"
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("ui", help="launch the civil review workspace (default)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if (args.command or "ui") == "ui":
        from .ui.app import launch

        launch()
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
