"""Governed Bluebeam working-copy support for the Claude takeoff pilot.

The Screen2XYZ source PDF is immutable evidence and is guarded by its exact
SHA-256. Revu markups must therefore be written to a separate working PDF. A
working PDF is allowed to change at the file-byte level as annotations are
saved, but its selected page must continue to match the immutable source's
underlying drawing content.

This module stores the working-copy declaration inside the existing
`source_identity` mapping under `bluebeam_working_copy`, so the pilot session
schema remains backwards-compatible. It never weakens the immutable source
hash check.
"""

from __future__ import annotations

import hashlib
import math
import shutil
from pathlib import Path
from typing import Any

from .io_utils import sha256_file


WORKING_COPY_KEY = "bluebeam_working_copy"


class WorkingCopyError(RuntimeError):
    """The Bluebeam working copy cannot be trusted for this source session."""


def _box_tuple(box: Any) -> tuple[float, float, float, float]:
    return tuple(float(value) for value in (box.left, box.bottom, box.right, box.top))


def _rounded_box(box: tuple[float, float, float, float]) -> list[float]:
    return [round(value, 6) for value in box]


def page_drawing_fingerprint(path: Path, page_index: int) -> dict[str, Any]:
    """Fingerprint page drawing content while intentionally ignoring annotations.

    Full PDF bytes are unsuitable for a Revu working file because saving
    annotations legitimately changes them. The decoded page content stream plus
    page geometry/rotation is a narrower invariant: ordinary annotation saves
    may change `/Annots`, metadata, IDs, or object layout without changing the
    underlying drawing stream.
    """

    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - diagnosed by doctor
        raise WorkingCopyError("pypdf is required for working-copy validation") from exc

    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise WorkingCopyError(f"PDF does not exist: {source}")
    reader = PdfReader(str(source))
    if not 0 <= page_index < len(reader.pages):
        raise WorkingCopyError("page index is outside the PDF")
    page = reader.pages[page_index]
    contents = page.get_contents()
    if contents is None:
        data = b""
    else:
        try:
            data = bytes(contents.get_data())
        except Exception as exc:
            raise WorkingCopyError(
                f"unable to read decoded page content stream: {type(exc).__name__}: {exc}"
            ) from exc
    media = _box_tuple(page.mediabox)
    crop = _box_tuple(page.cropbox)
    rotation = int(page.get("/Rotate", 0) or 0) % 360
    if rotation not in {0, 90, 180, 270}:
        raise WorkingCopyError(f"unsupported page rotation: {rotation}")
    digest = hashlib.sha256()
    digest.update(data)
    digest.update(repr(tuple(round(value, 6) for value in media)).encode("ascii"))
    digest.update(repr(tuple(round(value, 6) for value in crop)).encode("ascii"))
    digest.update(str(rotation).encode("ascii"))
    return {
        "sha256": digest.hexdigest(),
        "content_stream_sha256": hashlib.sha256(data).hexdigest(),
        "content_bytes": len(data),
        "media_box": _rounded_box(media),
        "crop_box": _rounded_box(crop),
        "rotation": rotation,
        "page_count": len(reader.pages),
    }


def _same_path(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return str(a.absolute()).casefold() == str(b.absolute()).casefold()


def _base_identity(session: Any) -> tuple[Path, str, int]:
    source_path = session.source_path
    source_sha = session.source_sha256
    if not source_sha:
        raise WorkingCopyError("session has no immutable source SHA-256")
    return source_path, source_sha, int(session.page_index)


def register_working_copy(
    session: Any,
    working_pdf: Path,
    *,
    now: str,
    created_from_source: bool = False,
) -> dict[str, Any]:
    """Register an editable Revu PDF whose drawing page matches the source.

    The working file may already contain markups. Exact file SHA equality is
    therefore required only when Screen2XYZ itself just copied the immutable
    source. In all cases the selected page drawing fingerprint must match.
    """

    source_path, source_sha, page_index = _base_identity(session)
    working = Path(working_pdf).expanduser().resolve()
    if not working.is_file():
        raise WorkingCopyError(f"working PDF does not exist: {working}")
    if _same_path(source_path, working):
        raise WorkingCopyError(
            "Bluebeam working PDF must be a separate file; never register the immutable source itself"
        )
    source_fp = page_drawing_fingerprint(source_path, page_index)
    working_fp = page_drawing_fingerprint(working, page_index)
    if source_fp["sha256"] != working_fp["sha256"]:
        raise WorkingCopyError(
            "working PDF page drawing does not match the immutable source page"
        )
    working_sha = sha256_file(working)
    if created_from_source and working_sha != source_sha:
        raise WorkingCopyError(
            "new working copy is not byte-identical to immutable source at creation time"
        )
    identity = {
        "local_path": str(working),
        "display_name": working.name,
        "registered_at": now,
        "initial_sha256": working_sha,
        "source_sha256": source_sha,
        "page_index": page_index,
        "page_label": str(session.page_label),
        "drawing_fingerprint_sha256": source_fp["sha256"],
        "created_from_source": bool(created_from_source),
        "policy": "MUTABLE_ANNOTATIONS_IMMUTABLE_DRAWING",
    }
    session.source_identity[WORKING_COPY_KEY] = identity
    session.updated_at = now
    session.decision_log.append(
        {
            "at": now,
            "action": "BLUEBEAM_WORKING_COPY_REGISTERED",
            "working_display_name": working.name,
            "working_initial_sha256": working_sha,
            "source_sha256": source_sha,
            "drawing_fingerprint_sha256": source_fp["sha256"],
            "created_from_source": bool(created_from_source),
        }
    )
    return dict(identity)


def create_working_copy(
    session: Any,
    target: Path,
    *,
    now: str,
    replace: bool = False,
) -> dict[str, Any]:
    """Copy immutable source bytes to a separate Revu file and register it."""

    source_path, _source_sha, _page_index = _base_identity(session)
    target_path = Path(target).expanduser().resolve()
    if _same_path(source_path, target_path):
        raise WorkingCopyError("working copy target must differ from immutable source")
    if target_path.exists() and not replace:
        raise WorkingCopyError(f"working copy already exists: {target_path}")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target_path)
    return register_working_copy(
        session,
        target_path,
        now=now,
        created_from_source=True,
    )


def working_copy_status(session: Any) -> dict[str, Any]:
    """Validate the mutable working file against the immutable drawing source."""

    raw = session.source_identity.get(WORKING_COPY_KEY)
    if not isinstance(raw, dict) or not str(raw.get("local_path", "")).strip():
        return {
            "configured": False,
            "available": False,
            "drawing_match": False,
            "modified_since_registration": None,
            "safe_for_bluebeam_operator": False,
            "reason": "NO_BLUEBEAM_WORKING_COPY_REGISTERED",
        }
    source_path, source_sha, page_index = _base_identity(session)
    working = Path(str(raw["local_path"])).expanduser().resolve()
    status: dict[str, Any] = {
        "configured": True,
        "path": str(working),
        "display_name": str(raw.get("display_name", working.name)),
        "available": working.is_file(),
        "drawing_match": False,
        "modified_since_registration": None,
        "safe_for_bluebeam_operator": False,
        "initial_sha256": str(raw.get("initial_sha256", "")),
        "source_sha256": source_sha,
        "policy": str(raw.get("policy", "MUTABLE_ANNOTATIONS_IMMUTABLE_DRAWING")),
    }
    if not working.is_file():
        status["reason"] = "BLUEBEAM_WORKING_COPY_MISSING"
        return status
    if _same_path(source_path, working):
        status["reason"] = "WORKING_COPY_IS_IMMUTABLE_SOURCE"
        return status
    try:
        source_fp = page_drawing_fingerprint(source_path, page_index)
        working_fp = page_drawing_fingerprint(working, page_index)
        current_sha = sha256_file(working)
    except WorkingCopyError as exc:
        status["reason"] = f"WORKING_COPY_VALIDATION_FAILED: {exc}"
        return status
    status["current_sha256"] = current_sha
    initial_sha = str(raw.get("initial_sha256", ""))
    status["modified_since_registration"] = bool(initial_sha and current_sha != initial_sha)
    expected_fp = str(raw.get("drawing_fingerprint_sha256", source_fp["sha256"]))
    drawing_match = (
        source_fp["sha256"] == working_fp["sha256"] == expected_fp
    )
    status["drawing_match"] = drawing_match
    status["drawing_fingerprint_sha256"] = working_fp["sha256"]
    status["safe_for_bluebeam_operator"] = drawing_match
    status["reason"] = "OK" if drawing_match else "WORKING_DRAWING_CHANGED_OR_WRONG_REVISION"
    return status
