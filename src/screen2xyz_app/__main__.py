"""Command-line entry point for Screen2XYZ v2."""

from __future__ import annotations

import argparse

from . import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Screen2XYZ v2 capture tool")
    parser.add_argument("--version", action="version", version=__version__)
    parser.parse_args(argv)
    from .ui.app import run

    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
