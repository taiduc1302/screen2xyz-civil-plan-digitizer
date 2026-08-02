"""Command-line entry point for the M1 opt-in capture review lab."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .evaluation import evaluate, generate_eval_fixture

RUN_ROOT_RELATIVE = Path(".lab_work/m1_runs")


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Screen2XYZ M1 opt-in capture review lab")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("review", help="open the local review interface")
    sub.add_parser("generate-eval", help="generate or verify the M1 evaluation fixture")
    run_eval = sub.add_parser("evaluate", help="run the M1 controlled evaluation")
    run_eval.add_argument("--run-id", default=None, help="fresh run id under .lab_work/m1_runs")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = repository_root()
    fixture = root / "test_data/synthetic/m1_eval_v0.1"
    try:
        if args.command == "review":
            from .ui import launch

            launch(root, root / RUN_ROOT_RELATIVE)
            return 0
        if args.command == "generate-eval":
            result = generate_eval_fixture(root, fixture)
        else:
            run_id = args.run_id or default_run_id()
            metrics = evaluate(root, fixture, root / RUN_ROOT_RELATIVE, run_id)
            result = {key: value for key, value in metrics.items() if key != "outcomes"}
            result["run_id"] = run_id
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        print(
            json.dumps({"status": "FAILED", "error_type": type(exc).__name__, "error": str(exc)}),
            file=sys.stderr,
        )
        return 30


if __name__ == "__main__":
    raise SystemExit(main())
