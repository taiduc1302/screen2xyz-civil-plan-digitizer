"""Conservative sheet and revision inference from PDF title-block text."""

from __future__ import annotations

import re
from typing import Iterable

from .detection import TextCandidate


_SHEET_RE = re.compile(r"^[A-Z][0O]\d{1,2}$", re.IGNORECASE)
_REVISION_RE = re.compile(r"^[A-Z]$")


def infer_sheet_metadata(
    candidates: Iterable[TextCandidate],
    *,
    width_px: float,
    height_px: float,
) -> dict[str, str]:
    """Return high-specificity title-block metadata without guessing.

    Sheet IDs must be in the bottom quarter. A revision is accepted only from
    the bottom-right title-block zone and is chosen nearest the sheet token.
    """

    if width_px <= 0 or height_px <= 0:
        return {}
    items = tuple(candidates)
    sheet_tokens = [
        item
        for item in items
        if item.bbox.center.y >= height_px * 0.75
        and _SHEET_RE.fullmatch(item.text.strip())
    ]
    if not sheet_tokens:
        return {}
    sheet = max(
        sheet_tokens,
        key=lambda item: (item.bbox.center.x, item.bbox.center.y),
    )
    sheet_id = sheet.text.strip().upper()
    sheet_id = f"{sheet_id[0]}0{sheet_id[2:]}"
    result = {"sheet_id": sheet_id}
    revision_tokens = [
        item
        for item in items
        if item.bbox.center.x >= width_px * 0.72
        and item.bbox.center.y >= height_px * 0.72
        and _REVISION_RE.fullmatch(item.text.strip())
    ]
    if revision_tokens:
        revision = min(
            revision_tokens,
            key=lambda item: (
                abs(item.bbox.center.y - sheet.bbox.center.y),
                abs(item.bbox.center.x - sheet.bbox.center.x),
            ),
        )
        result["revision"] = revision.text.strip().upper()
    return result
