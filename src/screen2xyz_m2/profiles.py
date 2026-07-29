"""Profile persistence with environment-snapshot mismatch detection."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import contracts as C
from .models import SessionDefaults, SourceConfig, ValidationError, \
    validate_source_set
from .paths import new_profile_id, profile_root, resolve_under


@dataclass
class Profile:
    profile_id: str
    profile_display_name: str
    scope: dict[str, Any]
    sources: list[SourceConfig]
    defaults: SessionDefaults
    environment_snapshot: dict[str, Any]
    created_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc)
        .isoformat(timespec="seconds"))

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": C.SCHEMA_VERSION,
            "profile_id": self.profile_id,
            "profile_display_name": self.profile_display_name[:80],
            "created_utc": self.created_utc,
            "scope": self.scope,
            "sources": [source.to_json() for source in self.sources],
            "session_defaults": {
                "interval_ms": self.defaults.interval_ms,
                "retention_mode": self.defaults.retention_mode,
                "stability": {
                    "confirmations": self.defaults.confirmations,
                    "debounce_ms": self.defaults.debounce_ms,
                    "min_change_threshold":
                        self.defaults.min_change_threshold,
                },
                "cursor_metadata": self.defaults.cursor_metadata,
            },
            "environment_snapshot": self.environment_snapshot,
        }


def save_profile(profile: Profile) -> Path:
    validate_source_set(profile.sources)
    profile.defaults.validate()
    root = profile_root()
    root.mkdir(parents=True, exist_ok=True)
    path = resolve_under(root, f"{profile.profile_id}.json")
    data = (json.dumps(profile.to_json(), indent=2, sort_keys=True) + "\n") \
        .encode("utf-8")
    if len(data) > C.PROFILE_FILE_MAX_BYTES:
        raise ValidationError("profile exceeds the 256 KiB bound")
    path.write_bytes(data)
    return path


def load_profile(profile_id: str) -> Profile:
    path = resolve_under(profile_root(), f"{profile_id}.json")
    if path.stat().st_size > C.PROFILE_FILE_MAX_BYTES:
        raise ValidationError("profile exceeds the 256 KiB bound")
    value = json.loads(path.read_text(encoding="utf-8"))
    stability = (value.get("session_defaults") or {}).get("stability") or {}
    defaults = SessionDefaults(
        interval_ms=int((value.get("session_defaults") or {})
                        .get("interval_ms", C.INTERVAL_DEFAULT_MS)),
        retention_mode=(value.get("session_defaults") or {})
        .get("retention_mode", C.RETENTION_DEFAULT),
        confirmations=int(stability.get("confirmations")
                          or C.STABILITY_CONFIRMATIONS_DEFAULT),
        debounce_ms=int(stability.get("debounce_ms")
                        or C.DEBOUNCE_DEFAULT_MS),
        min_change_threshold=stability.get("min_change_threshold"),
        cursor_metadata=bool((value.get("session_defaults") or {})
                             .get("cursor_metadata", False)),
    )
    profile = Profile(
        profile_id=value["profile_id"],
        profile_display_name=value.get("profile_display_name", ""),
        scope=value.get("scope") or {},
        sources=[SourceConfig.from_json(item)
                 for item in value.get("sources", [])],
        defaults=defaults,
        environment_snapshot=value.get("environment_snapshot") or {},
        created_utc=value.get("created_utc", ""),
    )
    validate_source_set(profile.sources)
    defaults.validate()
    return profile


def new_profile(display_name: str, scope: dict[str, Any],
                sources: list[SourceConfig], defaults: SessionDefaults,
                environment_snapshot: dict[str, Any]) -> Profile:
    return Profile(new_profile_id(), display_name, scope, sources, defaults,
                   environment_snapshot)


def environment_mismatches(snapshot: dict[str, Any],
                           live: dict[str, Any]) -> list[str]:
    """Compare a stored snapshot with the live environment."""

    mismatches: list[str] = []
    for key in ("client_w", "client_h", "dpi"):
        old = (snapshot.get("window") or {}).get(key)
        new = (live.get("window") or {}).get(key)
        if old is not None and new is not None and old != new:
            mismatches.append(f"window.{key}: {old} -> {new}")
    if (snapshot.get("window") or {}).get("exists") is False:
        mismatches.append("window missing at snapshot time")
    old_monitors = snapshot.get("monitors")
    new_monitors = live.get("monitors")
    if old_monitors is not None and new_monitors is not None \
            and old_monitors != new_monitors:
        mismatches.append("monitor topology changed")
    old_backend = snapshot.get("backend")
    new_backend = live.get("backend")
    if old_backend and new_backend and old_backend != new_backend:
        mismatches.append(f"backend: {old_backend} -> {new_backend}")
    return mismatches
