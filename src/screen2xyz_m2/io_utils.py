"""Small deterministic I/O helpers owned by the active M2 core."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path
from typing import Any, Iterable


class EvidenceError(RuntimeError):
    code = "RUN_OUTPUT_WRITE_FAILURE"


class ManifestEvidenceError(EvidenceError):
    code = "RUN_MANIFEST_WRITE_FAILURE"


def csv_bytes(rows: Iterable[dict[str, Any]], header: tuple[str, ...]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output, fieldnames=header, lineterminator="\r\n",
        quoting=csv.QUOTE_MINIMAL, extrasaction="raise",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in header})
    return output.getvalue().encode("utf-8")


def formula_safe_display(raw_text: str) -> str:
    display = raw_text.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    return "'" + display if display.startswith(("=", "+", "-", "@")) else display


def _sha256_file(path: Path) -> str:
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
        temporary.unlink(missing_ok=True)
        if isinstance(exc, EvidenceError):
            raise
        raise EvidenceError(f"atomic write failed for {path.name}") from exc


def atomic_write_json(path: Path, value: Any, *, replace: bool = False) -> None:
    data = (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")
    json.loads(data.decode("utf-8"))
    atomic_write_bytes(path, data, replace=replace)


def write_manifest(
    evidence_root: Path, repository_root: Path, *, replace: bool = False
) -> Path:
    try:
        manifest_path = evidence_root / "evidence_manifest_sha256.txt"
        files = [
            path for path in evidence_root.rglob("*")
            if path.is_file() and path != manifest_path and ".tmp-" not in path.name
        ]
        entries = [
            f"{_sha256_file(path)}  {path.relative_to(repository_root).as_posix()}"
            for path in sorted(
                files, key=lambda item: item.relative_to(repository_root).as_posix()
            )
        ]
        atomic_write_bytes(
            manifest_path, ("\n".join(entries) + "\n").encode("utf-8"),
            replace=replace,
        )
        return manifest_path
    except ManifestEvidenceError:
        raise
    except Exception as exc:
        raise ManifestEvidenceError("manifest could not be published") from exc
