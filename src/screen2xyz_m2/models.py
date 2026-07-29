"""Source / session / observation models with contract validation."""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field
from typing import Any

from . import contracts as C


class ValidationError(ValueError):
    """A contract-violating configuration value."""


_SOURCE_ID_RE = re.compile(r"^src-[a-z0-9-]+$")


def new_source_id() -> str:
    return f"src-{secrets.token_hex(4)}"


@dataclass
class SourceConfig:
    source_id: str
    display_name: str
    data_type: str = "number"
    semantic_role: str = "none"
    enabled: bool = True
    unit: str = ""
    numeric_range: tuple[float, float] | None = None
    decimal_precision_max: int | None = None
    decimal_separator: str = "point"
    rect: tuple[int, int, int, int] = (0, 0, 0, 0)  # x, y, w, h physical px
    coordinate_basis: str = "client_area"
    ocr_language: str = "en-US"
    upscale_factor: int = 1
    confirmations: int | None = None
    min_change_threshold: float | None = None
    debounce_ms: int | None = None
    notes: str = ""
    # Phase 2 (2026-07-19): the real target's coordinate readout is ONE
    # thin overlay line holding lat+long+elev together (e.g. "49°08'
    # 20.06"N 123°03'41.61"W 87.05m") - drawing three separate,
    # pixel-precise sub-regions inside it is impractical (see
    # M2_IMPLEMENTATION_REPORT.md §5k Phase 2.1's measured evidence).
    # line_part lets several fields share ONE drawn region (the whole
    # line): each field is parsed from only the line_part-th whitespace-
    # separated token of that region's OCR text, not the full text. None
    # (default) means "parse the whole raw text" - existing single-value
    # fields are completely unaffected.
    line_part: int | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": C.SCHEMA_VERSION,
            "source_id": self.source_id,
            "display_name": self.display_name,
            "enabled": self.enabled,
            "data_type": self.data_type,
            "semantic_role": self.semantic_role,
            "unit": self.unit,
            "numeric_range": (None if self.numeric_range is None else
                              {"min": self.numeric_range[0],
                               "max": self.numeric_range[1]}),
            "decimal_precision_max": self.decimal_precision_max,
            "decimal_separator": self.decimal_separator,
            "rect": {"x": self.rect[0], "y": self.rect[1],
                     "w": self.rect[2], "h": self.rect[3]},
            "coordinate_basis": self.coordinate_basis,
            "ocr_language": self.ocr_language,
            "preprocess": {"upscale_factor": self.upscale_factor},
            "stability": {"confirmations": self.confirmations,
                          "min_change_threshold": self.min_change_threshold,
                          "debounce_ms": self.debounce_ms},
            "notes": self.notes,
            "line_part": self.line_part,
        }

    @classmethod
    def from_json(cls, value: dict[str, Any]) -> "SourceConfig":
        rng = value.get("numeric_range")
        rect = value.get("rect") or {}
        stability = value.get("stability") or {}
        return cls(
            source_id=value.get("source_id", ""),
            display_name=value.get("display_name", ""),
            enabled=bool(value.get("enabled", True)),
            data_type=value.get("data_type", "number"),
            semantic_role=value.get("semantic_role", "none"),
            unit=value.get("unit", ""),
            numeric_range=(None if not rng else
                           (float(rng["min"]), float(rng["max"]))),
            decimal_precision_max=value.get("decimal_precision_max"),
            decimal_separator=value.get("decimal_separator", "point"),
            rect=(int(rect.get("x", 0)), int(rect.get("y", 0)),
                  int(rect.get("w", 0)), int(rect.get("h", 0))),
            coordinate_basis=value.get("coordinate_basis", "client_area"),
            ocr_language=value.get("ocr_language", "en-US"),
            upscale_factor=int((value.get("preprocess") or {})
                               .get("upscale_factor", 1)),
            confirmations=stability.get("confirmations"),
            min_change_threshold=stability.get("min_change_threshold"),
            debounce_ms=stability.get("debounce_ms"),
            notes=value.get("notes", ""),
            line_part=value.get("line_part"),
        )


def validate_source(source: SourceConfig,
                    scope_size: tuple[int, int] | None = None) -> None:
    if not _SOURCE_ID_RE.match(source.source_id):
        raise ValidationError(f"invalid source_id {source.source_id!r}")
    name_bytes = len(source.display_name.encode("utf-8"))
    if not source.display_name.strip() or name_bytes > C.DISPLAY_NAME_MAX_BYTES:
        raise ValidationError("display_name empty or over 80 UTF-8 bytes")
    if len(source.notes.encode("utf-8")) > C.NOTES_MAX_BYTES:
        raise ValidationError("notes over 512 UTF-8 bytes")
    if source.data_type not in C.DATA_TYPES:
        raise ValidationError(f"invalid data_type {source.data_type!r}")
    if source.semantic_role not in C.SEMANTIC_ROLES:
        raise ValidationError(f"invalid semantic_role {source.semantic_role!r}")
    if source.semantic_role in ("x", "y", "z") and \
            source.data_type not in ("number", "coordinate"):
        # `coordinate` (Phase 1) produces the same decimal-degrees numeric
        # output `number` does - it's a stricter, corruption-safe parser
        # for lat/long text, not a different value shape - so it is just
        # as valid an X/Y/Z holder as a plain number field.
        raise ValidationError(
            "x/y/z roles require data_type number or coordinate")
    if source.decimal_separator not in C.DECIMAL_SEPARATORS:
        raise ValidationError("invalid decimal_separator")
    if source.coordinate_basis not in C.COORDINATE_BASES:
        raise ValidationError("invalid coordinate_basis")
    if not (C.UPSCALE_MIN <= source.upscale_factor <= C.UPSCALE_MAX):
        raise ValidationError("upscale_factor outside 1..4")
    if source.min_change_threshold is not None and \
            source.data_type not in ("number", "coordinate"):
        raise ValidationError(
            "min_change_threshold only valid for number or coordinate")
    if source.line_part is not None and source.line_part < 0:
        raise ValidationError("line_part must be >= 0")
    if source.confirmations is not None and not (
            C.STABILITY_CONFIRMATIONS_RANGE[0] <= source.confirmations
            <= C.STABILITY_CONFIRMATIONS_RANGE[1]):
        raise ValidationError("confirmations outside 1..5")
    if source.debounce_ms is not None and not (
            C.DEBOUNCE_RANGE_MS[0] <= source.debounce_ms
            <= C.DEBOUNCE_RANGE_MS[1]):
        raise ValidationError("debounce_ms outside 0..5000")
    x, y, w, h = source.rect
    if w < C.REGION_MIN_PX or h < C.REGION_MIN_PX:
        raise ValidationError("region smaller than 8x8 px")
    if w > C.REGION_MAX_W or h > C.REGION_MAX_H:
        raise ValidationError("region larger than 2000x800 px")
    if x < 0 or y < 0:
        raise ValidationError("region origin negative")
    if scope_size is not None:
        if x + w > scope_size[0] or y + h > scope_size[1]:
            raise ValidationError("region outside scope bounds")


def validate_source_set(sources: list[SourceConfig],
                        scope_size: tuple[int, int] | None = None,
                        require_nonempty: bool = True) -> None:
    """require_nonempty=False skips the >=1-enabled-source lower bound only
    (the upper bound and every other shape/dedup/role check still applies).
    This lets a caller that legitimately has no fields configured yet - the
    controller at construction time, before Step 3 "Add fields" has run -
    still validate the *shape* of whatever sources it does have without
    being forced to already hold a complete field set."""
    enabled = [source for source in sources if source.enabled]
    lower_bound = C.SOURCE_COUNT_MIN if require_nonempty else 0
    if not (lower_bound <= len(enabled) <= C.SOURCE_COUNT_MAX):
        raise ValidationError(
            f"enabled source count outside {lower_bound}..{C.SOURCE_COUNT_MAX}")
    names = [source.display_name for source in sources]
    if len(set(names)) != len(names):
        raise ValidationError("duplicate source display names")
    ids = [source.source_id for source in sources]
    if len(set(ids)) != len(ids):
        raise ValidationError("duplicate source ids")
    for role in ("x", "y", "z"):
        holders = [source for source in enabled
                   if source.semantic_role == role]
        if len(holders) > 1:
            raise ValidationError(f"role {role} assigned to multiple sources")
    for source in sources:
        validate_source(source, scope_size)


def xyz_eligibility(sources: list[SourceConfig]) -> dict[str, Any]:
    enabled = [source for source in sources if source.enabled]
    assignment: dict[str, str] = {}
    for role in ("x", "y", "z"):
        holders = [source for source in enabled
                   if source.semantic_role == role
                   and source.data_type in ("number", "coordinate")]
        if len(holders) != 1:
            return {"eligible": False,
                    "reason": f"exactly one enabled number source must hold "
                              f"role {role}"}
        assignment[f"{role}_source_id"] = holders[0].source_id
    return {"eligible": True, "reason": "", **assignment}


def xyz_missing_axes(sources: list[SourceConfig]) -> list[str]:
    """Which of X/Y/Z are NOT satisfied by exactly one enabled number field
    (uppercase axis letters). Empty list == eligible. Reports ALL unmet axes
    at once so the UI can say "Missing: Y, Z" instead of revealing them one
    at a time on repeated attempts."""
    enabled = [source for source in sources if source.enabled]
    missing: list[str] = []
    for role in ("x", "y", "z"):
        holders = [source for source in enabled
                   if source.semantic_role == role
                   and source.data_type in ("number", "coordinate")]
        if len(holders) != 1:
            missing.append(role.upper())
    return missing


@dataclass
class SessionDefaults:
    interval_ms: int = C.INTERVAL_DEFAULT_MS
    retention_mode: str = C.RETENTION_DEFAULT
    confirmations: int = C.STABILITY_CONFIRMATIONS_DEFAULT
    debounce_ms: int = C.DEBOUNCE_DEFAULT_MS
    min_change_threshold: float | None = None
    cursor_metadata: bool = False

    def validate(self) -> None:
        if not (C.INTERVAL_MIN_MS <= self.interval_ms <= C.INTERVAL_MAX_MS):
            raise ValidationError("interval outside 250..10000 ms")
        if self.retention_mode not in C.RETENTION_MODES:
            raise ValidationError("invalid retention mode")
        if not (C.STABILITY_CONFIRMATIONS_RANGE[0] <= self.confirmations
                <= C.STABILITY_CONFIRMATIONS_RANGE[1]):
            raise ValidationError("confirmations outside 1..5")
        if not (C.DEBOUNCE_RANGE_MS[0] <= self.debounce_ms
                <= C.DEBOUNCE_RANGE_MS[1]):
            raise ValidationError("debounce outside 0..5000 ms")


@dataclass
class Observation:
    source_id: str
    capture_status: str = "OK"
    crop_content_status: str = "NOT_EVALUATED"
    ocr_status: str = "NOT_RUN_CAPTURE_FAILED"
    parse_status: str = "NOT_RUN"
    stability_status: str = "NOT_EVALUATED"
    value_status: str = "CAPTURE_FAILURE"
    raw_text: str = ""
    raw_truncated: bool = False
    raw_original_utf8_bytes: int | None = None
    warning_codes: tuple[str, ...] = field(default_factory=tuple)
    normalized_value: str | None = None
    value_kind: str = "number"
    pixel_sha256: str | None = None
    crop_w: int = 0
    crop_h: int = 0
    ocr_executed: bool = False
    confirmation: str = "new_ocr"
    ocr_ms: int = 0
    ocr_ref: str | None = None
    sign_normalized: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "capture_status": self.capture_status,
            "crop_content_status": self.crop_content_status,
            "ocr_status": self.ocr_status,
            "parse_status": self.parse_status,
            "stability_status": self.stability_status,
            "value_status": self.value_status,
            "raw_text": self.raw_text,
            "raw_truncated": self.raw_truncated,
            "raw_original_utf8_bytes": self.raw_original_utf8_bytes,
            "warning_codes": list(self.warning_codes),
            "normalized_value": self.normalized_value,
            "value_kind": self.value_kind,
            "pixel_sha256": self.pixel_sha256,
            "crop_w": self.crop_w,
            "crop_h": self.crop_h,
            "ocr_executed": self.ocr_executed,
            "confirmation": self.confirmation,
            "ocr_ms": self.ocr_ms,
            "ocr_ref": self.ocr_ref,
            "sign_normalized": self.sign_normalized,
        }
