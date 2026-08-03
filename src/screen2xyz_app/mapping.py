"""Channel-to-source configuration for each capture session."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from screen2xyz_m2.models import SourceConfig

SOURCE_TYPES = (
    "screen_zone_ocr",
    "screen_cursor_ocr",
    "plan_click",
    "plan_label_ocr",
    "clipboard",
    "manual",
)
REQUIRED_COLUMNS = ("x", "y", "z")
OPTIONAL_COLUMNS = ("description", "point_number")
ALL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS


@dataclass(frozen=True)
class ChannelSource:
    source_type: str
    zone: tuple[int, int, int, int] | None = None
    decimal_separator: str = "point"
    data_type: str = "number"
    numeric_range: tuple[float, float] | None = None
    cursor_box_size: tuple[int, int] = (160, 60)
    cursor_snap_radius_px: float = 30.0

    def validate(self) -> None:
        if self.source_type not in SOURCE_TYPES:
            raise ValueError(f"unsupported source type: {self.source_type}")
        if self.source_type == "screen_zone_ocr":
            if self.zone is None or self.zone[2] < 8 or self.zone[3] < 8:
                raise ValueError("screen_zone_ocr requires a zone at least 8x8 pixels")
            if self.zone[3] > 48:
                raise ValueError(
                    f"screen_zone_ocr zone is {self.zone[3]} px tall; pick one numeric line no taller than 48 px"
                )
        elif self.zone is not None:
            raise ValueError("only screen_zone_ocr accepts a zone")
        if self.source_type == "screen_cursor_ocr":
            width, height = self.cursor_box_size
            if width < 16 or height < 16:
                raise ValueError("screen_cursor_ocr requires a cursor box at least 16x16 pixels")
            if self.cursor_snap_radius_px <= 0:
                raise ValueError("cursor snap radius must be positive")
        if self.decimal_separator not in {"point", "comma", "auto"}:
            raise ValueError("decimal_separator must be point, comma, or auto")
        if self.numeric_range is not None:
            low, high = self.numeric_range
            if low > high:
                raise ValueError("numeric range minimum cannot exceed maximum")

    def to_json(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "zone": list(self.zone) if self.zone is not None else None,
            "decimal_separator": self.decimal_separator,
            "data_type": self.data_type,
            "numeric_range": list(self.numeric_range) if self.numeric_range is not None else None,
            "cursor_box_size": list(self.cursor_box_size),
            "cursor_snap_radius_px": self.cursor_snap_radius_px,
        }

    @classmethod
    def from_json(cls, value: dict[str, Any]) -> "ChannelSource":
        zone = value.get("zone")
        numeric_range = value.get("numeric_range")
        cursor_box_size = value.get("cursor_box_size", (160, 60))
        return cls(
            source_type=str(value["source_type"]),
            zone=None if zone is None else tuple(int(v) for v in zone),
            decimal_separator=str(value.get("decimal_separator", "point")),
            data_type=str(value.get("data_type", "number")),
            numeric_range=(
                None if numeric_range is None
                else (float(numeric_range[0]), float(numeric_range[1]))
            ),
            cursor_box_size=(int(cursor_box_size[0]), int(cursor_box_size[1])),
            cursor_snap_radius_px=float(value.get("cursor_snap_radius_px", 30.0)),
        )


@dataclass(frozen=True)
class ChannelMapping:
    channels: dict[str, ChannelSource] = field(default_factory=dict)

    def validate(self) -> None:
        unknown = set(self.channels) - set(ALL_COLUMNS)
        if unknown:
            raise ValueError(f"unknown output columns: {sorted(unknown)}")
        missing = set(REQUIRED_COLUMNS) - set(self.channels)
        if missing:
            raise ValueError(f"missing required mappings: {sorted(missing)}")
        for source in self.channels.values():
            source.validate()

    @property
    def automatic(self) -> bool:
        return all(
            source.source_type in {"screen_zone_ocr", "screen_cursor_ocr", "clipboard"}
            for source in self.channels.values()
        )

    @property
    def click_driven(self) -> bool:
        return any(
            source.source_type in {"plan_click", "plan_label_ocr"}
            for source in self.channels.values()
        )

    def to_json(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": "2.0",
            "channels": {
                name: source.to_json() for name, source in sorted(self.channels.items())
            },
        }

    @classmethod
    def from_json(cls, value: dict[str, Any]) -> "ChannelMapping":
        if value.get("schema_version") != "2.0":
            raise ValueError("unsupported mapping profile schema")
        mapping = cls(
            channels={
                str(name): ChannelSource.from_json(source)
                for name, source in (value.get("channels") or {}).items()
            }
        )
        mapping.validate()
        return mapping

    def m2_sources(self) -> list[SourceConfig]:
        """Represent OCR zones with the proven M2 SourceConfig contract."""
        result: list[SourceConfig] = []
        for column, source in self.channels.items():
            if source.source_type != "screen_zone_ocr" or source.zone is None:
                continue
            result.append(
                SourceConfig(
                    source_id=f"src-v2-{column.replace('_', '-')}",
                    display_name=column.replace("_", " ").title(),
                    data_type=source.data_type,
                    semantic_role=column if column in REQUIRED_COLUMNS else "none",
                    decimal_separator=source.decimal_separator,
                    numeric_range=source.numeric_range,
                    rect=source.zone,
                    coordinate_basis="monitor",
                    upscale_factor=3,
                )
            )
        return result
