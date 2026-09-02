"""Read-only inspection of annotations saved in a Bluebeam working PDF.

This is a resilience/fallback surface for the Claude operator. It lets the
agent see already-saved annotations even when a live Bluebeam MCP connection is
not available. It deliberately does not claim Revu editability, ownership,
viewport scale, or live computed measurement values. Those facts require live
Revu readback through a proven route.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


class PdfAnnotationInspectionError(RuntimeError):
    """Saved PDF annotations could not be inspected safely."""


def _resolve(value: Any) -> Any:
    try:
        return value.get_object()
    except Exception:
        return value


def _text(value: Any, *, max_chars: int = 4000) -> str:
    if value is None:
        return ""
    try:
        text = str(_resolve(value))
    except Exception:
        return ""
    return text[:max_chars]


def _numbers(value: Any, *, max_items: int = 2000) -> list[float]:
    raw = _resolve(value)
    if raw is None:
        return []
    try:
        items = list(raw)
    except Exception:
        return []
    result: list[float] = []
    for item in items[:max_items]:
        try:
            result.append(float(_resolve(item)))
        except Exception:
            return []
    return result


def _object_ref(value: Any) -> str:
    idnum = getattr(value, "idnum", None)
    generation = getattr(value, "generation", None)
    if idnum is None:
        return ""
    return f"{idnum} {0 if generation is None else generation} R"


def _measure_summary(measure: Any) -> dict[str, Any]:
    obj = _resolve(measure)
    if not isinstance(obj, dict):
        return {}
    result: dict[str, Any] = {}
    for key in ("/Type", "/Subtype", "/R"):
        if key in obj:
            result[key[1:]] = _text(obj.get(key), max_chars=1000)
    # Measurement dictionaries can contain conversion arrays. Preserve only a
    # bounded structural summary; do not infer a live Revu quantity from them.
    for key in ("/X", "/Y", "/D", "/A", "/T", "/V"):
        if key in obj:
            raw = _resolve(obj.get(key))
            try:
                result[key[1:]] = {"present": True, "items": len(raw)}
            except Exception:
                result[key[1:]] = {"present": True}
    return result


def inspect_page_annotations(
    path: Path,
    page_index: int,
    *,
    limit: int = 1000,
) -> dict[str, Any]:
    """Return bounded saved annotation metadata/geometry for one PDF page.

    Coordinates are raw PDF annotation coordinates as stored in the file. They
    are intentionally not converted into Screen2XYZ top-left rendered-PDF
    points here because PDF annotation coordinate conventions and page rotation
    must be reconciled explicitly before geometry is used for a takeoff edit.
    """

    if limit < 1 or limit > 10000:
        raise PdfAnnotationInspectionError("limit must be between 1 and 10000")
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - diagnosed by doctor
        raise PdfAnnotationInspectionError("pypdf is required") from exc

    pdf = Path(path).expanduser().resolve()
    if not pdf.is_file():
        raise PdfAnnotationInspectionError(f"PDF does not exist: {pdf}")
    try:
        reader = PdfReader(str(pdf))
    except Exception as exc:
        raise PdfAnnotationInspectionError(
            f"unable to open PDF: {type(exc).__name__}: {exc}"
        ) from exc
    if not 0 <= page_index < len(reader.pages):
        raise PdfAnnotationInspectionError("page index is outside the PDF")

    page = reader.pages[page_index]
    raw_annots = _resolve(page.get("/Annots"))
    try:
        refs = [] if raw_annots is None else list(raw_annots)
    except Exception as exc:
        raise PdfAnnotationInspectionError(
            f"unable to enumerate page annotations: {type(exc).__name__}: {exc}"
        ) from exc

    rows: list[dict[str, Any]] = []
    for index, ref in enumerate(refs[:limit]):
        annot = _resolve(ref)
        if not isinstance(annot, dict):
            rows.append(
                {
                    "index": index,
                    "object_ref": _object_ref(ref),
                    "parse_status": "UNREADABLE_ANNOTATION_OBJECT",
                }
            )
            continue
        measure = annot.get("/Measure")
        rows.append(
            {
                "index": index,
                "object_ref": _object_ref(ref),
                "parse_status": "OK",
                "subtype": _text(annot.get("/Subtype"), max_chars=200),
                "intent": _text(annot.get("/IT"), max_chars=500),
                "name_id": _text(annot.get("/NM"), max_chars=1000),
                "subject": _text(annot.get("/Subj"), max_chars=2000),
                "author": _text(annot.get("/T"), max_chars=2000),
                "contents": _text(annot.get("/Contents"), max_chars=4000),
                "modified": _text(annot.get("/M"), max_chars=500),
                "created": _text(annot.get("/CreationDate"), max_chars=500),
                "flags": _text(annot.get("/F"), max_chars=200),
                "opacity": _text(annot.get("/CA"), max_chars=200),
                "rect_pdf": _numbers(annot.get("/Rect"), max_items=4),
                "line_pdf": _numbers(annot.get("/L"), max_items=4),
                "vertices_pdf": _numbers(annot.get("/Vertices"), max_items=2000),
                "color": _numbers(annot.get("/C"), max_items=8),
                "interior_color": _numbers(annot.get("/IC"), max_items=8),
                "has_measure_dictionary": measure is not None,
                "measure_dictionary": _measure_summary(measure),
            }
        )

    return {
        "pdf": str(pdf),
        "page_index": page_index,
        "page_number": page_index + 1,
        "total": len(refs),
        "returned": len(rows),
        "truncated": len(refs) > limit,
        "annotations": rows,
        "trust": "SAVED_PDF_ANNOTATION_EVIDENCE_NOT_LIVE_REVU_STATE",
        "limitations": [
            "Offline annotation inspection does not prove current Revu editability or Studio ownership.",
            "Presence of a /Measure dictionary does not by itself prove the live Revu-computed quantity is correct.",
            "Raw annotation coordinates require explicit page/rotation reconciliation before being reused as Screen2XYZ geometry.",
            "Use live Revu create/save/readback for native measurement acceptance and final quantity QA.",
        ],
    }


def inspect_registered_working_copy(
    session_path: Path,
    *,
    limit: int = 1000,
    preview_dir: Path | None = None,
) -> dict[str, Any]:
    """Inspect only the working PDF already governed by a Screen2XYZ session."""

    from .agent_session import load_agent_session
    from .portable_render import render_pdf_page_portable
    from .working_copy import working_copy_status

    session = load_agent_session(Path(session_path), verify_source=True)
    status = working_copy_status(session)
    if not status.get("safe_for_bluebeam_operator"):
        raise PdfAnnotationInspectionError(
            "registered Bluebeam working copy is not safe: "
            + str(status.get("reason", "UNKNOWN"))
        )
    working = Path(str(status["path"]))
    result = inspect_page_annotations(working, session.page_index, limit=limit)
    result["working_copy"] = status
    result["immutable_source"] = {
        "path": str(session.source_path),
        "sha256": session.source_sha256,
    }
    if preview_dir is not None:
        current_sha = str(status.get("current_sha256", "unknown"))[:16]
        target_dir = Path(preview_dir).expanduser().resolve() / current_sha
        preview = render_pdf_page_portable(
            working,
            session.page_index,
            target_dir,
            dpi=session.render_dpi,
        )
        result["preview_png"] = str(preview)
        result["preview_includes_saved_annotations"] = True
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m screen2xyz_civil.pdf_annotations",
        description=(
            "Read saved annotations from the registered Bluebeam working PDF. "
            "This is offline evidence, not live Revu quantity/editability proof."
        ),
    )
    parser.add_argument("--session", required=True, help="path to .s2a.json")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument(
        "--preview-dir",
        default="",
        help="optional directory for a PDFium PNG preview including saved annotations",
    )
    args = parser.parse_args(argv)
    try:
        result = inspect_registered_working_copy(
            Path(args.session),
            limit=args.limit,
            preview_dir=Path(args.preview_dir) if args.preview_dir else None,
        )
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
