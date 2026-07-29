"""PowerShell-friendly command-line entry point for the synthetic lab."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from .config import ARIAL_FILE_BYTES, ARIAL_FILE_SHA256, OUTPUT_CLASSIFICATION, TASK_ID
from .evidence import (
    EvidenceError,
    ManifestEvidenceError,
    atomic_write_bytes,
    atomic_write_json,
    finalize_evidence,
    validate_environment_record,
    verify_manifest,
)
from .fixture import generate_fixture
from .pipeline import RunTimeoutError, evaluate_fixture, publish_evidence, transactional_publish_directory


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _bounded_path(root: Path, value: str) -> Path:
    candidate = (root / Path(value)).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise ValueError("path is outside repository")
    return candidate


def _environment_evidence(root: Path, evidence_root: Path) -> None:
    adapter = root / "src/screen2xyz_lab/adapters/environment_windows.ps1"
    observed_result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(adapter)],
        capture_output=True, text=True, encoding="utf-8", timeout=10, check=True,
    )
    observed = json.loads(observed_result.stdout.strip())
    expected_adapter_keys = {
        "schema_version", "powershell_version", "os_version", "dotnet_release",
        "mscorlib_assembly_version", "mscorlib_file_version", "font_file_bytes", "font_file_sha256",
    }
    if set(observed) != expected_adapter_keys:
        raise EvidenceError("environment adapter schema differs")
    if observed["font_file_bytes"] != ARIAL_FILE_BYTES or observed["font_file_sha256"] != ARIAL_FILE_SHA256:
        raise EvidenceError("selected font identity changed")
    distribution_count = sum(1 for _ in importlib.metadata.distributions())
    if distribution_count != 0:
        raise EvidenceError("repository-local environment contains unexpected distributions")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
        encoding="utf-8", timeout=10, check=True,
    ).stdout.strip()
    environment = {
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "git_commit_at_evaluation": commit,
        "operating_system": "Windows",
        "os_version": observed["os_version"],
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "powershell_version": observed["powershell_version"],
        "dotnet_release": observed["dotnet_release"],
        "mscorlib_assembly_version": observed["mscorlib_assembly_version"],
        "mscorlib_file_version": observed["mscorlib_file_version"],
        "ocr_engine": "Windows.Media.Ocr",
        "ocr_engine_version": "not_exposed",
        "ocr_language": "en-US",
        "renderer": "System.Drawing/GDI+",
        "font": "Arial regular; OS-provided and used in place",
        "font_file_bytes": observed["font_file_bytes"],
        "font_file_sha256": observed["font_file_sha256"],
        "render_conditions": ["baseline:32px", "scale_125:40px", "scale_150:48px"],
        "live_capture_status": "Not executed",
        "support_boundary": "Current-machine experimental unpackaged host; broader compatibility was not tested.",
        "output_classification": OUTPUT_CLASSIFICATION,
    }
    validate_environment_record(environment)
    inventory = "\n".join(
        (
            "Screen2XYZ relevant dependency inventory",
            f"Task: {TASK_ID}",
            f"CPython: {platform.python_version()} (PSF-2.0 dependency evidence; repository licence not selected)",
            f"Windows PowerShell: {observed['powershell_version']} (OS-provided; used in place; not redistributed)",
            f".NET Framework: Release {observed['dotnet_release']}; mscorlib assembly {observed['mscorlib_assembly_version']}; file {observed['mscorlib_file_version']} (revalidated)",
            "System.Drawing/GDI+: OS-provided on Windows; used in place; not redistributed",
            "Windows.Media.Ocr: OS-managed; semantic version not_exposed; en-US; no model redistributed",
            f"Arial regular: {ARIAL_FILE_BYTES} bytes; sha256 {ARIAL_FILE_SHA256}; used in place; not redistributed",
            f"Repository-local .venv: --without-pip; include-system-site-packages=false; observed installed distributions={distribution_count}",
            "Direct third-party project dependencies: none",
            "No legal approval or repository licence selection is claimed.",
            OUTPUT_CLASSIFICATION,
            "",
        )
    )
    stage = evidence_root.parent / f".{evidence_root.name}.environment-staging-{os.getpid()}"
    if stage.exists():
        raise EvidenceError("environment evidence staging collision")
    stage.mkdir(parents=True)
    try:
        atomic_write_json(stage / "environment.json", environment)
        atomic_write_bytes(stage / "dependency_inventory.txt", inventory.encode("utf-8"))
        transactional_publish_directory(stage, evidence_root)
    except Exception:
        safe_stage = stage.resolve()
        if safe_stage.parent == evidence_root.parent.resolve() and safe_stage.name.startswith(f".{evidence_root.name}.environment-staging-"):
            shutil.rmtree(safe_stage, ignore_errors=True)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Screen2XYZ generated-image OCR laboratory")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("generate", help="generate or verify the deterministic synthetic fixture")
    evaluate = sub.add_parser("evaluate", help="run actual local OCR on all 60 generated PNGs")
    evaluate.add_argument("--output", required=True, help="fresh repository-relative work output")
    evaluate.add_argument("--run-timeout-seconds", type=float, default=None, help=argparse.SUPPRESS)
    publish = sub.add_parser("publish", help="publish two-run comparison into retained evidence")
    publish.add_argument("--run-a", required=True)
    publish.add_argument("--run-b", required=True)
    sub.add_parser("environment", help="write sanitized runtime/dependency evidence")
    finalize = sub.add_parser("finalize-evidence", help="publish fresh test results and write the manifest last")
    finalize.add_argument("--test-results", required=True, help="fresh repository-relative staged test result")
    sub.add_parser("verify-evidence", help="verify the final evidence manifest")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = repository_root()
    fixture = root / "test_data/synthetic/s2xyz_fixture_v0.1"
    evidence = root / "runs/evidence/S2XYZ-CODEX-003"
    try:
        if args.command == "generate":
            result = generate_fixture(root, fixture)
        elif args.command == "evaluate":
            result = evaluate_fixture(root, fixture, _bounded_path(root, args.output), run_timeout_seconds=args.run_timeout_seconds)
        elif args.command == "publish":
            result = publish_evidence(fixture, _bounded_path(root, args.run_a), _bounded_path(root, args.run_b), evidence)
        elif args.command == "environment":
            _environment_evidence(root, evidence)
            result = {"status": "COMPLETED", "files": ["environment.json", "dependency_inventory.txt"]}
        elif args.command == "finalize-evidence":
            path = finalize_evidence(evidence, root, _bounded_path(root, args.test_results))
            result = {"status": "COMPLETED", "manifest": path.relative_to(root).as_posix()}
        elif args.command == "verify-evidence":
            errors = verify_manifest(evidence / "evidence_manifest_sha256.txt", root)
            result = {"status": "PASS" if not errors else "FAIL", "errors": errors}
            print(json.dumps(result, sort_keys=True))
            return 0 if not errors else 1
        else:  # pragma: no cover
            raise AssertionError("unreachable")
        print(json.dumps(result, sort_keys=True))
        return 0
    except RunTimeoutError:
        print(json.dumps({"status": "RUN_FATAL", "code": "RUN_TIMEOUT"}, sort_keys=True), file=sys.stderr)
        return 32
    except ManifestEvidenceError:
        print(json.dumps({"status": "RUN_FATAL", "code": "RUN_MANIFEST_WRITE_FAILURE"}, sort_keys=True), file=sys.stderr)
        return 33
    except EvidenceError:
        print(json.dumps({"status": "RUN_FATAL", "code": "RUN_OUTPUT_WRITE_FAILURE"}, sort_keys=True), file=sys.stderr)
        return 31
    except Exception as exc:
        code = getattr(exc, "code", "RUN_CONFIG_INVALID")
        print(json.dumps({"status": "RUN_FATAL", "code": code, "error_type": type(exc).__name__}, sort_keys=True), file=sys.stderr)
        return 30


if __name__ == "__main__":
    raise SystemExit(main())
