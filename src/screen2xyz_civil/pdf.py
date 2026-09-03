"""Local vector-PDF inspection and replaceable raster-render adapter."""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import contracts as C
from .detection import Rect, TextCandidate, VectorShape
from .io_utils import sha256_file


class PdfAdapterError(RuntimeError):
    """PDF dependency, input, extraction, or rendering failed safely."""


@dataclass(frozen=True)
class PdfPageInfo:
    page_index: int
    width_points: float
    height_points: float
    rotation: int
    has_vector_text: bool

    @property
    def rendered_width_points(self) -> float:
        return self.height_points if self.rotation in {90, 270} else self.width_points

    @property
    def rendered_height_points(self) -> float:
        return self.width_points if self.rotation in {90, 270} else self.height_points


@dataclass(frozen=True)
class PdfDocumentInfo:
    display_name: str
    local_path: str
    sha256: str
    byte_size: int
    page_count: int
    pages: tuple[PdfPageInfo, ...]

    def to_manifest(self, *, include_local_path: bool = True) -> dict[str, Any]:
        value: dict[str, Any] = {
            "display_name": self.display_name,
            "sha256": self.sha256,
            "byte_size": self.byte_size,
            "source_type": "PDF",
            "page_count": self.page_count,
            "pages": [
                {
                    "page_index": page.page_index,
                    "width_points": page.width_points,
                    "height_points": page.height_points,
                    "rotation": page.rotation,
                    "has_vector_text": page.has_vector_text,
                }
                for page in self.pages
            ],
        }
        if include_local_path:
            value["local_path"] = self.local_path
        return value


def pypdf_available() -> bool:
    return importlib.util.find_spec("pypdf") is not None


def _effective_page_size(page: Any) -> tuple[float, float]:
    """Return the rendered box size: CropBox clipped to MediaBox, else MediaBox."""

    try:
        media = [float(value) for value in page.mediabox]
        crop = [float(value) for value in page.cropbox]
    except Exception:
        return float(page.mediabox.width), float(page.mediabox.height)
    left = max(min(media[0], media[2]), min(crop[0], crop[2]))
    bottom = max(min(media[1], media[3]), min(crop[1], crop[3]))
    right = min(max(media[0], media[2]), max(crop[0], crop[2]))
    top = min(max(media[1], media[3]), max(crop[1], crop[3]))
    width, height = right - left, top - bottom
    if width <= 0 or height <= 0:
        return float(page.mediabox.width), float(page.mediabox.height)
    return width, height


def inspect_pdf(path: Path) -> PdfDocumentInfo:
    candidate = path.expanduser().resolve()
    if not candidate.is_file() or candidate.suffix.lower() != ".pdf":
        raise PdfAdapterError("PDF source does not exist or has the wrong extension")
    if candidate.stat().st_size <= 0 or candidate.stat().st_size > C.MAX_SOURCE_BYTES:
        raise PdfAdapterError("PDF source size is outside the allowed boundary")
    PdfReader = _pdf_reader()
    try:
        reader = PdfReader(str(candidate))
        if reader.is_encrypted:
            raise PdfAdapterError("encrypted PDFs require an unlocked local copy")
        pages = []
        for index, page in enumerate(reader.pages):
            # The page frame must be the box the renderer actually rasterises.
            # PDFium (portable_render) and Revu both draw the CropBox, so taking
            # the MediaBox here silently scaled and offset every measurement made
            # on a trimmed sheet -- ordinary for plotted/CAD drawing PDFs.
            width, height = _effective_page_size(page)
            rotation = int(page.rotation or 0) % 360
            if width <= 0 or height <= 0:
                raise PdfAdapterError("PDF page dimensions are invalid")
            probe = (page.extract_text() or "").strip()
            pages.append(
                PdfPageInfo(
                    page_index=index,
                    width_points=width,
                    height_points=height,
                    rotation=rotation,
                    has_vector_text=bool(probe),
                )
            )
        if not pages:
            raise PdfAdapterError("PDF contains no pages")
        return PdfDocumentInfo(
            display_name=candidate.name,
            local_path=str(candidate),
            sha256=sha256_file(candidate),
            byte_size=candidate.stat().st_size,
            page_count=len(pages),
            pages=tuple(pages),
        )
    except PdfAdapterError:
        raise
    except Exception as exc:
        raise PdfAdapterError("PDF inspection failed") from exc


def extract_pdf_text_candidates(
    path: Path,
    page_index: int,
    *,
    dpi: float = 150.0,
) -> list[TextCandidate]:
    if dpi <= 0:
        raise PdfAdapterError("render DPI must be positive")
    info = inspect_pdf(path)
    if not 0 <= page_index < info.page_count:
        raise PdfAdapterError("page index is outside the PDF")
    PdfReader = _pdf_reader()
    try:
        page = PdfReader(str(path.expanduser().resolve())).pages[page_index]
        page_info = info.pages[page_index]
        fragments: list[tuple[str, float, float, float, float]] = []

        def visitor(
            text: str,
            _cm: list[float],
            tm: list[float],
            font_dict: dict[str, Any] | None,
            font_size: float,
        ) -> None:
            if text and text.strip():
                fragments.append(
                    (
                        text,
                        float(tm[4]),
                        float(tm[5]),
                        float(font_size),
                        _pdf_text_confidence(font_dict),
                    )
                )

        page.extract_text(visitor_text=visitor)
        candidates: list[TextCandidate] = []
        sequence = 0
        for fragment, base_x, base_y, font_size, confidence in fragments:
            safe_size = max(1.0, abs(font_size))
            for match in re.finditer(r"\S+", fragment):
                token = match.group(0)
                sequence += 1
                x0 = base_x + match.start() * safe_size * 0.52
                width = max(safe_size * 0.45, len(token) * safe_size * 0.52)
                # PDF text matrices use a bottom-left origin. Store PDF boxes
                # top-left so they match review-canvas and Poppler raster space.
                y0 = page_info.height_points - base_y - safe_size
                pdf_bbox = Rect(x0, y0, x0 + width, y0 + safe_size * 1.25)
                pixel_bbox = pdf_rect_to_render_pixels(pdf_bbox, page_info, dpi)
                candidates.append(
                    TextCandidate(
                        id=f"PDF-T{sequence:05d}",
                        text=token,
                        bbox=pixel_bbox,
                        page_index=page_index,
                        source_method=C.PDF_TEXT,
                        confidence=confidence,
                        context=fragment.strip(),
                        pdf_bbox=pdf_bbox,
                    )
                )
        return candidates
    except PdfAdapterError:
        raise
    except Exception as exc:
        raise PdfAdapterError("vector PDF text extraction failed") from exc


def _pdf_text_confidence(font_dict: dict[str, Any] | None) -> float:
    """Flag embedded-font mappings that need raster-glyph confirmation."""

    if not font_dict:
        return 0.65
    encoding = font_dict.get("/Encoding")
    if isinstance(encoding, dict) and encoding.get("/Differences"):
        return 0.70
    if not font_dict.get("/ToUnicode"):
        return 0.72
    return 0.98


def extract_pdf_vector_shapes(
    path: Path,
    page_index: int,
    *,
    dpi: float = 150.0,
) -> list[VectorShape]:
    """Extract auditable first-pass vector path geometry from PDF operators."""

    info = inspect_pdf(path)
    if not 0 <= page_index < info.page_count:
        raise PdfAdapterError("page index is outside the PDF")
    PdfReader = _pdf_reader()
    try:
        page = PdfReader(str(path.expanduser().resolve())).pages[page_index]
        page_info = info.pages[page_index]
        shapes: list[VectorShape] = []
        current_points: list[tuple[float, float]] = []
        line_segments = 0
        curve_segments = 0
        closed = False
        sequence = 0

        def flush() -> None:
            nonlocal current_points, line_segments, curve_segments, closed, sequence
            if not current_points:
                return
            sequence += 1
            xs = [point[0] for point in current_points]
            ys = [point[1] for point in current_points]
            pdf_bbox = Rect(min(xs), min(ys), max(xs), max(ys))
            pixel_bbox = pdf_rect_to_render_pixels(pdf_bbox, page_info, dpi)
            kind = "path"
            if curve_segments >= 4 and closed:
                kind = "ellipse"
            elif line_segments == 1:
                kind = (
                    "leader"
                    if max(pixel_bbox.width, pixel_bbox.height) >= 25
                    else "line"
                )
            shapes.append(
                VectorShape(
                    id=f"PDF-V{sequence:05d}",
                    bbox=pixel_bbox,
                    kind=kind,
                    closed=closed,
                    line_segments=line_segments,
                    has_leader=kind == "leader",
                    confidence=0.8 if kind == "ellipse" else 0.65,
                )
            )
            current_points = []
            line_segments = 0
            curve_segments = 0
            closed = False

        def visitor(
            operator: bytes,
            operands: list[Any],
            cm: list[float],
            _tm: list[float],
        ) -> None:
            nonlocal line_segments, curve_segments, closed
            op = operator.decode("ascii", errors="ignore")
            values = [float(value) for value in operands if _number_like(value)]
            if op == "m" and len(values) >= 2:
                flush()
                current_points.append(
                    _pdf_operand_point(values[0], values[1], cm, page_info)
                )
            elif op == "l" and len(values) >= 2:
                current_points.append(
                    _pdf_operand_point(values[0], values[1], cm, page_info)
                )
                line_segments += 1
            elif op in {"c", "v", "y"} and len(values) >= 4:
                for index in range(0, len(values) - 1, 2):
                    current_points.append(
                        _pdf_operand_point(
                            values[index], values[index + 1], cm, page_info
                        )
                    )
                curve_segments += 1
            elif op == "re" and len(values) >= 4:
                flush()
                x, y, width, height = values[:4]
                current_points.extend(
                    [
                        _pdf_operand_point(x, y, cm, page_info),
                        _pdf_operand_point(x + width, y, cm, page_info),
                        _pdf_operand_point(x + width, y + height, cm, page_info),
                        _pdf_operand_point(x, y + height, cm, page_info),
                    ]
                )
                line_segments = 4
                closed = True
            elif op == "h":
                closed = True
            elif op in {"S", "s", "f", "F", "f*", "B", "B*", "b", "b*", "n"}:
                if op in {"s", "b", "b*"}:
                    closed = True
                flush()

        page.extract_text(visitor_operand_before=visitor)
        flush()
        return shapes
    except PdfAdapterError:
        raise
    except Exception as exc:
        raise PdfAdapterError("vector PDF path extraction failed") from exc


def pdf_rect_to_render_pixels(
    bbox: Rect, page: PdfPageInfo, dpi: float
) -> Rect:
    corners = (
        (bbox.x0, bbox.y0),
        (bbox.x1, bbox.y0),
        (bbox.x1, bbox.y1),
        (bbox.x0, bbox.y1),
    )
    transformed = [
        _rotate_top_left(x, y, page.width_points, page.height_points, page.rotation)
        for x, y in corners
    ]
    scale = dpi / 72.0
    xs = [point[0] * scale for point in transformed]
    ys = [point[1] * scale for point in transformed]
    return Rect(min(xs), min(ys), max(xs), max(ys))


def render_pdf_page(
    path: Path,
    page_index: int,
    output_dir: Path,
    *,
    dpi: int = 150,
    renderer: str | None = None,
    timeout_seconds: float = 60.0,
) -> Path:
    info = inspect_pdf(path)
    if not 0 <= page_index < info.page_count:
        raise PdfAdapterError("page index is outside the PDF")
    executable = _resolve_renderer(renderer)
    if not executable:
        raise PdfAdapterError(
            "local PDF renderer unavailable; install Poppler pdftoppm or use a PNG"
        )
    target_dir = output_dir.expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    prefix = target_dir / f"page-{page_index + 1:04d}-{dpi}dpi"
    output = prefix.with_suffix(".png")
    if output.exists():
        return output
    command = [
        executable,
        "-f",
        str(page_index + 1),
        "-l",
        str(page_index + 1),
        "-singlefile",
        "-r",
        str(dpi),
        "-png",
        str(path.expanduser().resolve()),
        str(prefix),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PdfAdapterError("local PDF page rendering failed") from exc
    if completed.returncode != 0 or not output.is_file():
        raise PdfAdapterError(
            f"local PDF renderer exited with code {completed.returncode}"
        )
    return output


def _rotate_top_left(
    x: float, y: float, width: float, height: float, rotation: int
) -> tuple[float, float]:
    if rotation == 0:
        return x, y
    if rotation == 90:
        return height - y, x
    if rotation == 180:
        return width - x, height - y
    if rotation == 270:
        return y, width - x
    raise PdfAdapterError(f"unsupported PDF page rotation: {rotation}")


def _number_like(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _pdf_operand_point(
    x: float, y: float, cm: list[float], page: PdfPageInfo
) -> tuple[float, float]:
    transformed_x = x * float(cm[0]) + y * float(cm[2]) + float(cm[4])
    transformed_y_bottom = (
        x * float(cm[1]) + y * float(cm[3]) + float(cm[5])
    )
    return transformed_x, page.height_points - transformed_y_bottom


def _pdf_reader():
    if not pypdf_available():
        raise PdfAdapterError(
            "optional pypdf dependency is unavailable; "
            "install requirements-civil.txt or use the manual PNG workflow"
        )
    from pypdf import PdfReader

    return PdfReader


def _resolve_renderer(renderer: str | None) -> str | None:
    if renderer:
        return renderer
    discovered = shutil.which("pdftoppm")
    if not discovered:
        return None
    path = Path(discovered)
    # Some managed runtimes expose a forwarding .cmd while the actual,
    # non-interactive executable lives in a sibling dependency folder. Prefer
    # the executable when that documented wrapper layout is present; a normal
    # Poppler installation continues to use the PATH result unchanged.
    if path.suffix.lower() in {".cmd", ".bat"} and len(path.parents) >= 3:
        direct = (
            path.parents[2]
            / "native"
            / "poppler"
            / "Library"
            / "bin"
            / "pdftoppm.exe"
        )
        if direct.is_file():
            return str(direct)
    return discovered
