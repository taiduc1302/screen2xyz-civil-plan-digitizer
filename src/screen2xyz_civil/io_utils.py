"""Standalone deterministic and atomic file helpers for civil artifacts."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path
from typing import Any, Iterable


class ArtifactWriteError(OSError):
    """A retained civil artifact could not be written atomically."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_bytes(path: Path, data: bytes, *, replace: bool = False) -> None:
    """Write one file through a same-directory temporary and ``os.replace``."""

    target = path.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not replace:
        raise ArtifactWriteError(
            f"refusing to overwrite retained artifact: {target.name}"
        )
    temporary = target.with_name(f".{target.name}.tmp-{os.getpid()}")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if target.exists() and not replace:
            raise ArtifactWriteError(
                f"refusing to overwrite retained artifact: {target.name}"
            )
        os.replace(temporary, target)
    except Exception as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        if isinstance(exc, ArtifactWriteError):
            raise
        raise ArtifactWriteError(
            f"atomic write failed for {target.name}"
        ) from exc


def atomic_write_json(path: Path, value: Any, *, replace: bool = False) -> None:
    data = (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )
    json.loads(data.decode("utf-8"))
    atomic_write_bytes(path, data, replace=replace)


def csv_bytes(
    rows: Iterable[dict[str, Any]],
    header: tuple[str, ...],
) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=list(header),
        lineterminator="\r\n",
        quoting=csv.QUOTE_MINIMAL,
        extrasaction="raise",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in header})
    return output.getvalue().encode("utf-8")


def formula_safe_display(raw_text: str) -> str:
    display = str(raw_text or "").replace("\r", "\\r").replace(
        "\n", "\\n"
    ).replace("\t", "\\t")
    if display.startswith(("=", "+", "-", "@")):
        display = "'" + display
    return display


def write_manifest(
    artifact_root: Path,
    repository_root: Path,
    *,
    replace: bool = False,
) -> Path:
    """Write a deterministic SHA-256 inventory that excludes itself."""

    root = artifact_root.expanduser().resolve()
    repository = repository_root.expanduser().resolve()
    manifest = root / "evidence_manifest_sha256.txt"
    files = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and path != manifest
        and ".tmp-" not in path.name
    ]
    entries = [
        f"{sha256_file(path)}  {path.relative_to(repository).as_posix()}"
        for path in sorted(
            files,
            key=lambda item: item.relative_to(repository).as_posix(),
        )
    ]
    atomic_write_bytes(
        manifest,
        ("\n".join(entries) + "\n").encode("utf-8"),
        replace=replace,
    )
    return manifest
