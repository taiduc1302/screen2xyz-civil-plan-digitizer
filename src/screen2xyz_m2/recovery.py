"""Recover an unfinalized run from its canonical journal."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .exports import finalize_exports
from .journal import read_journal, verify_crops
from .models import SourceConfig


def recover_run(run_dir: Path) -> dict[str, Any]:
    """Rebuild exports from `events.jsonl`; the journal always wins."""

    session_path = run_dir / "session.json"
    if not session_path.is_file():
        raise FileNotFoundError(f"{run_dir} has no session.json")
    session = json.loads(session_path.read_text(encoding="utf-8"))
    events, warnings = read_journal(run_dir)
    warnings += verify_crops(run_dir, events)

    checkpoint_path = run_dir / "state_checkpoint.json"
    if checkpoint_path.is_file():
        try:
            checkpoint = json.loads(
                checkpoint_path.read_text(encoding="utf-8"))
            if checkpoint.get("last_event_seq", 0) > len(events):
                warnings.append("CHECKPOINT_DIVERGENCE")
        except (json.JSONDecodeError, OSError):
            warnings.append("CHECKPOINT_DIVERGENCE")

    sources = [SourceConfig.from_json(item)
               for item in session.get("sources", [])]
    counters = {"events": len(events), "recovered": True}
    summary = finalize_exports(run_dir, session, events, sources, counters,
                               recovered=True, warnings=sorted(set(warnings)))
    return {"events": len(events), "warnings": sorted(set(warnings)),
            "summary": summary}
