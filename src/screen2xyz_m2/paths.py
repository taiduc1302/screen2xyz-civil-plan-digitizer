"""Safe path handling for M2 runs and profiles."""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

from . import contracts as C


class UnsafePath(ValueError):
    """A path escaped its allowed root."""


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def run_root() -> Path:
    return repository_root() / C.RUN_ROOT_RELATIVE


def profile_root() -> Path:
    return repository_root() / C.PROFILE_ROOT_RELATIVE


def diagnostics_root() -> Path:
    return repository_root() / C.DIAGNOSTICS_ROOT_RELATIVE


_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"m2-{stamp}-{secrets.token_hex(3)}"


def new_profile_id() -> str:
    return f"profile-{secrets.token_hex(6)}"


def new_diagnostic_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"diag-{stamp}-{secrets.token_hex(3)}"


def resolve_under(root: Path, name: str) -> Path:
    """Join a generated id under a root, rejecting traversal."""

    if not _ID_RE.match(name):
        raise UnsafePath(f"unsafe path component {name!r}")
    candidate = (root / name).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise UnsafePath(f"{name!r} escapes {root}")
    return candidate
