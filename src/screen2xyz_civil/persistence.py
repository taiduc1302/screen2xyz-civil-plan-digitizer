"""Atomic project save/reopen with explicit schema migration."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from screen2xyz_lab.evidence import atomic_write_json, sha256_file

from . import contracts as C
from .models import CivilModelError, CivilProject


class ProjectPersistenceError(RuntimeError):
    """Project state cannot be safely read, migrated, or written."""


def migrate_project_dict(value: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(value)
    version = str(migrated.get("schema_version", "0.9"))
    if version == C.SCHEMA_VERSION:
        return migrated
    if version == "0.9":
        migrated["schema_version"] = C.SCHEMA_VERSION
        if "points" in migrated and "point_candidates" not in migrated:
            migrated["point_candidates"] = migrated.pop("points")
        migrated.setdefault("calibration_history", [])
        migrated.setdefault("export_history", [])
        migrated.setdefault("decision_log", [])
        migrated.setdefault("exports_stale", True)
        migrated.setdefault("no_cross_lines", [])
        migrated.setdefault("disabled_triangles", [])
        migrated.setdefault(
            "feature_flags", {"preliminary_surface": False, "landxml": False}
        )
        return migrated
    raise ProjectPersistenceError(f"unsupported project schema: {version}")


def save_project(
    project: CivilProject, path: Path, *, replace: bool = True
) -> dict[str, str]:
    target = path.expanduser().resolve()
    if target.suffixes[-2:] != [".s2c", ".json"]:
        raise ProjectPersistenceError(
            f"project file must end with {C.PROJECT_FILE_SUFFIX}"
        )
    try:
        atomic_write_json(target, project.to_dict(), replace=replace)
        return {"path": str(target), "sha256": sha256_file(target)}
    except (OSError, CivilModelError, ValueError) as exc:
        raise ProjectPersistenceError("project save failed") from exc


def load_project(path: Path) -> CivilProject:
    target = path.expanduser().resolve()
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ProjectPersistenceError("project root must be a JSON object")
        return CivilProject.from_dict(migrate_project_dict(value))
    except ProjectPersistenceError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, CivilModelError, KeyError, TypeError) as exc:
        raise ProjectPersistenceError("project load failed") from exc
