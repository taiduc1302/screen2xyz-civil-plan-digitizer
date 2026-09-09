"""Self-contained PDF page rendering for the Claude/takeoff operator.

The historical Civil Plan Digitizer uses a host-installed Poppler `pdftoppm`.
That remains supported for the legacy UI, but the AI operator must be easy to
install on a normal Windows workstation.  This module therefore prefers the
pinned pypdfium2/Pillow wheel stack and falls back to the existing Poppler
adapter only when PDFium is unavailable.

pypdfium2 is distributed under Apache-2.0/BSD-3-Clause terms and bundles
PDFium under BSD-style/dependency licences; redistribution obligations still
need to be preserved if Screen2XYZ is later packaged for public/commercial
redistribution.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from .pdf import PdfAdapterError, inspect_pdf, render_pdf_page


class PortableRenderError(PdfAdapterError):
    """No safe local renderer could produce the requested page image."""


def pdfium_available() -> bool:
    return (
        importlib.util.find_spec("pypdfium2") is not None
        and importlib.util.find_spec("PIL") is not None
    )


def render_pdf_page_portable(
    path: Path,
    page_index: int,
    output_dir: Path,
    *,
    dpi: int = 150,
) -> Path:
    """Render one PDF page to PNG with PDFium, then legacy Poppler fallback."""

    if dpi <= 0:
        raise PortableRenderError("render DPI must be positive")
    info = inspect_pdf(path)
    if not 0 <= page_index < info.page_count:
        raise PortableRenderError("page index is outside the PDF")
    target_dir = output_dir.expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    output = target_dir / f"page-{page_index + 1:04d}-{dpi}dpi-pdfium.png"
    if output.is_file() and output.stat().st_size > 0:
        return output

    if pdfium_available():
        try:
            import pypdfium2 as pdfium

            document = pdfium.PdfDocument(str(path.expanduser().resolve()))
            try:
                page = document[page_index]
                try:
                    # PDF canvas units are normally 1/72 inch. Intrinsic page
                    # rotation is handled by PDFium; `rotation=0` means no
                    # additional operator rotation.
                    bitmap = page.render(
                        scale=float(dpi) / 72.0,
                        rotation=0,
                        draw_annots=True,
                    )
                    try:
                        image = bitmap.to_pil()
                        image.save(output, format="PNG")
                    finally:
                        bitmap.close()
                finally:
                    page.close()
            finally:
                document.close()
            if not output.is_file() or output.stat().st_size <= 0:
                raise PortableRenderError("PDFium produced no page image")
            return output
        except PortableRenderError:
            raise
        except Exception as exc:
            raise PortableRenderError(
                f"local PDFium page rendering failed: {type(exc).__name__}: {exc}"
            ) from exc

    # Keep the proven historical path available on workstations where Poppler
    # is already installed, but do not make it a prerequisite for the Claude
    # operator once PDFium wheels are installed.
    try:
        return render_pdf_page(
            path,
            page_index,
            target_dir,
            dpi=dpi,
        )
    except PdfAdapterError as exc:
        raise PortableRenderError(
            "no local PDF renderer is available; install requirements-civil.txt "
            "(pypdfium2/Pillow) or provide Poppler pdftoppm on PATH"
        ) from exc
