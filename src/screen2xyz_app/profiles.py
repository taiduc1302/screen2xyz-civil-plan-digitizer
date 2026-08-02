"""Named JSON mapping profiles stored inside a project directory."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .mapping import ChannelMapping

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,79}$")


class MappingProfileStore:
    def __init__(self, project_dir: Path) -> None:
        self.root = project_dir.resolve() / ".screen2xyz" / "profiles"

    @staticmethod
    def _file_name(name: str) -> str:
        if not _SAFE_NAME.fullmatch(name):
            raise ValueError("profile name must be 1-80 plain filename characters")
        return re.sub(r"[ .]+", "-", name.strip()).lower() + ".json"

    def save(self, name: str, mapping: ChannelMapping) -> Path:
        payload = {"name": name, **mapping.to_json()}
        encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        if len(encoded) > 256 * 1024:
            raise ValueError("profile exceeds 256 KiB")
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / self._file_name(name)
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(path)
        return path

    def load(self, name: str) -> ChannelMapping:
        path = self.root / self._file_name(name)
        if path.stat().st_size > 256 * 1024:
            raise ValueError("profile exceeds 256 KiB")
        return ChannelMapping.from_json(json.loads(path.read_text(encoding="utf-8")))

    def names(self) -> list[str]:
        if not self.root.exists():
            return []
        names: list[str] = []
        for path in sorted(self.root.glob("*.json")):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                names.append(str(value["name"]))
            except (OSError, KeyError, ValueError, json.JSONDecodeError):
                continue
        return names

