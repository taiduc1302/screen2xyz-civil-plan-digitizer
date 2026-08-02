"""Atomic, deterministic and privacy-bounded evidence utilities."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

from .config import canonical_json_bytes


class EvidenceError(RuntimeError):
    code = "RUN_OUTPUT_WRITE_FAILURE"


class ManifestEvidenceError(EvidenceError):
    code = "RUN_MANIFEST_WRITE_FAILURE"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_bytes(path: Path, data: bytes, *, replace: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not replace:
        raise EvidenceError(f"refusing to overwrite retained artifact: {path.name}")
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists() and not replace:
            raise EvidenceError(f"refusing to overwrite retained artifact: {path.name}")
        os.replace(temporary, path)
    except Exception as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        if isinstance(exc, EvidenceError):
            raise
        raise EvidenceError(f"atomic write failed for {path.name}") from exc


def atomic_write_json(path: Path, value: Any, *, replace: bool = False) -> None:
    data = canonical_json_bytes(value)
    json.loads(data.decode("utf-8"))
    atomic_write_bytes(path, data, replace=replace)


def atomic_copy(source: Path, destination: Path, *, replace: bool = False) -> None:
    atomic_write_bytes(destination, source.read_bytes(), replace=replace)


def write_manifest(evidence_root: Path, repository_root: Path, *, replace: bool = False) -> Path:
    try:
        manifest_path = evidence_root / "evidence_manifest_sha256.txt"
        files = [
            path
            for path in evidence_root.rglob("*")
            if path.is_file() and path != manifest_path and ".tmp-" not in path.name
        ]
        entries = []
        for path in sorted(files, key=lambda item: item.relative_to(repository_root).as_posix()):
            entries.append(f"{sha256_file(path)}  {path.relative_to(repository_root).as_posix()}")
        atomic_write_bytes(
            manifest_path,
            ("\n".join(entries) + "\n").encode("utf-8"),
            replace=replace,
        )
        return manifest_path
    except ManifestEvidenceError:
        raise
    except Exception as exc:
        raise ManifestEvidenceError("manifest could not be published") from exc


def verify_manifest(manifest_path: Path, repository_root: Path) -> list[str]:
    try:
        errors: list[str] = []
        lines = manifest_path.read_text(encoding="utf-8").splitlines()
        paths: list[str] = []
        for line in lines:
            if len(line) < 67 or line[64:66] != "  ":
                errors.append("invalid manifest line")
                continue
            expected, relpath = line[:64], line[66:]
            paths.append(relpath)
            path = repository_root / Path(relpath)
            if not path.is_file():
                errors.append(f"missing:{relpath}")
            elif sha256_file(path) != expected:
                errors.append(f"hash:{relpath}")
        if paths != sorted(paths):
            errors.append("manifest paths are not ordinally sorted")
        if manifest_path.relative_to(repository_root).as_posix() in paths:
            errors.append("manifest includes itself")
        evidence_root = manifest_path.parent
        actual_paths = sorted(
            path.relative_to(repository_root).as_posix()
            for path in evidence_root.rglob("*")
            if path.is_file() and path != manifest_path and ".tmp-" not in path.name
        )
        if paths != actual_paths:
            errors.append("manifest coverage differs from retained evidence files")
        return errors
    except ManifestEvidenceError:
        raise
    except Exception as exc:
        raise ManifestEvidenceError("manifest could not be verified") from exc


def ensure_no_absolute_personal_path(texts: Iterable[str]) -> list[str]:
    findings: list[str] = []
    for text in texts:
        findings.extend(code for code in privacy_findings(text) if code.startswith("ABSOLUTE_PERSONAL_PATH"))
    return sorted(set(findings))


_PRIVACY_PATTERNS = (
    ("ABSOLUTE_PERSONAL_PATH_WINDOWS", re.compile(r"(?i)\b[A-Z]:[\\/]+Users[\\/]")),
    ("ABSOLUTE_PERSONAL_PATH_POSIX", re.compile(r"(?i)(?:^|[\s\"'])/(?:home|Users)/")),
    ("ENVIRONMENT_DUMP", re.compile(r"(?im)^(?:PATH|USERNAME|USERPROFILE|USERDOMAIN|COMPUTERNAME|HOSTNAME|HOME)\s*=")),
    ("CREDENTIAL_BEARER", re.compile(r"(?i)authorization\s*:\s*bearer\s+\S+")),
    ("CREDENTIAL_GITHUB_TOKEN", re.compile(r"(?i)\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("CREDENTIAL_ASSIGNMENT", re.compile(r"(?i)\b(?:password|passwd|secret|access[_-]?token|api[_-]?key)\s*[:=]\s*\S+")),
    ("CREDENTIAL_URL", re.compile(r"(?i)https?://[^/\s:@]+:[^/\s@]+@")),
    ("IDENTITY_ASSIGNMENT", re.compile(r"(?i)[\"']?(?:username|user_name|hostname|host_name|computername|computer_name|user[_-]domain|domain[_-]name)[\"']?\s*[:=]\s*[\"']?[^\s,;\"'{}\[\]]+")),
    ("MAC_ADDRESS", re.compile(r"(?i)\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b")),
    ("HARDWARE_SERIAL", re.compile(r"(?i)\bserial(?:\s+number)?\s*[:=]\s*\S+")),
)


ENVIRONMENT_ALLOWED_KEYS = {
    "schema_version", "task_id", "git_commit_at_evaluation", "operating_system", "os_version",
    "architecture", "python_version", "powershell_version", "dotnet_release",
    "mscorlib_assembly_version", "mscorlib_file_version", "ocr_engine", "ocr_engine_version",
    "ocr_language", "renderer", "font", "font_file_bytes", "font_file_sha256",
    "render_conditions", "live_capture_status", "support_boundary", "output_classification",
}

MANDATORY_EVIDENCE_FILENAMES = {
    "ground_truth.csv", "raw_ocr_readings.csv", "accepted_points.csv", "rejected_readings.csv",
    "points_source_xyz.txt", "points_source_xyz_metadata.json", "metrics.json", "environment.json",
    "dependency_inventory.txt", "test_results.txt", "evidence_manifest_sha256.txt",
}


def privacy_findings(text: str) -> list[str]:
    findings = [code for code, pattern in _PRIVACY_PATTERNS if pattern.search(text)]
    address_pattern = re.compile(r"(?<![0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9])")
    for match in address_pattern.finditer(text):
        candidate = match.group(0)
        try:
            address = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        line = text[line_start : len(text) if line_end < 0 else line_end]
        prefix = line[: match.start() - line_start]
        if re.search(
            r"(?i)(?:[\"']?(?:os|python|powershell|mscorlib_(?:assembly|file))_version[\"']?\s*:\s*[\"']?|mscorlib\s+assembly\s+)$",
            prefix,
        ):
            continue
        if address.is_private:
            findings.append("NETWORK_ADDRESS_PRIVATE")
        elif re.search(r"(?i)\b(?:ip|address|host|server|network)\b", line):
            findings.append("NETWORK_ADDRESS_PUBLIC")
    return sorted(set(findings))


def validate_environment_record(value: dict[str, Any]) -> None:
    if set(value) != ENVIRONMENT_ALLOWED_KEYS:
        raise EvidenceError("environment evidence keys differ from the privacy allowlist")
    findings = privacy_findings(json.dumps(value, sort_keys=True))
    if findings:
        raise EvidenceError("environment evidence failed privacy scanning")


def finalize_evidence(
    evidence_root: Path,
    repository_root: Path,
    test_results_source: Path,
) -> Path:
    """Add a fresh test result and publish the one final manifest last."""

    required_before = MANDATORY_EVIDENCE_FILENAMES - {"test_results.txt", "evidence_manifest_sha256.txt"}
    missing = sorted(name for name in required_before if not (evidence_root / name).is_file())
    if missing:
        raise EvidenceError(f"mandatory pre-manifest evidence missing: {missing}")
    target = evidence_root / "test_results.txt"
    manifest = evidence_root / "evidence_manifest_sha256.txt"
    if target.exists() or manifest.exists():
        raise EvidenceError("refusing to overwrite retained test results or manifest")
    data = test_results_source.read_bytes()
    text = data.decode("utf-8")
    if privacy_findings(text) or "Exit code:" not in text or "Command:" not in text:
        raise EvidenceError("test result evidence is unsanitized or incomplete")
    atomic_write_bytes(target, data)
    try:
        published = write_manifest(evidence_root, repository_root)
        errors = verify_manifest(published, repository_root)
        if errors:
            raise ManifestEvidenceError(f"final manifest verification failed: {errors}")
    except Exception:
        manifest.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        raise
    actual = {name for name in MANDATORY_EVIDENCE_FILENAMES if (evidence_root / name).is_file()}
    if actual != MANDATORY_EVIDENCE_FILENAMES:
        manifest.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        raise ManifestEvidenceError("mandatory evidence set is incomplete after publication")
    return published
