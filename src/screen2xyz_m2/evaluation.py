"""M2 controlled evaluation over a deterministic scripted OCR stream.

Scores the **parse -> stability -> retention decision** layer by feeding a
fixed sequence of raw-OCR frames (numeric, text, empty, ambiguous,
Unicode-minus, out-of-range, flicker) through the public parser and the
stability engine. It does NOT drive the journal/crop/export tier — that
storage-write path is covered separately by `tests_m2/test_journal_exports`
and the integration/acceptance harnesses. Deterministic and machine-scored;
retained under a new immutable evidence task id when accepted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import contracts as C
from .models import Observation, SourceConfig, new_source_id
from .parsing import RawBound, parse_for_source
from .stability import StabilityEngine

EVAL_TASK_ID = "S2XYZ-M2-EVAL-001"


@dataclass
class ScriptedFrame:
    label: str
    raw: dict[str, str]           # source_id -> raw OCR text ("" = empty)


def build_sources() -> list[SourceConfig]:
    return [
        SourceConfig(source_id="src-lon", display_name="Lon",
                     data_type="number", semantic_role="x",
                     numeric_range=(-180.0, 180.0), rect=(0, 0, 200, 30)),
        SourceConfig(source_id="src-lat", display_name="Lat",
                     data_type="number", semantic_role="y",
                     numeric_range=(-90.0, 90.0), rect=(0, 40, 200, 30)),
        SourceConfig(source_id="src-note", display_name="Note",
                     data_type="text", rect=(0, 80, 200, 30)),
    ]


def build_script() -> list[ScriptedFrame]:
    return [
        ScriptedFrame("seed", {"src-lon": "-123.654321", "src-lat": "49.1",
                               "src-note": "ready"}),
        ScriptedFrame("constant", {"src-lon": "-123.654321",
                                   "src-lat": "49.1", "src-note": "ready"}),
        ScriptedFrame("lon_change", {"src-lon": "-123.660000",
                                     "src-lat": "49.1",
                                     "src-note": "ready"}),
        ScriptedFrame("unicode_minus", {"src-lon": "−123.700000",
                                        "src-lat": "49.1",
                                        "src-note": "ready"}),
        ScriptedFrame("ambiguous_lat", {"src-lon": "-123.700000",
                                        "src-lat": "49.1 50.2",
                                        "src-note": "ready"}),
        ScriptedFrame("empty_lat", {"src-lon": "-123.700000",
                                    "src-lat": "", "src-note": "ready"}),
        ScriptedFrame("recover_lat", {"src-lon": "-123.700000",
                                      "src-lat": "49.1",
                                      "src-note": "ready"}),
        ScriptedFrame("out_of_range", {"src-lon": "999.0",
                                       "src-lat": "49.1",
                                       "src-note": "ready"}),
        ScriptedFrame("note_change", {"src-lon": "-123.700000",
                                      "src-lat": "49.1",
                                      "src-note": "=danger()"}),
    ]


def _observation(source: SourceConfig, raw: str, frame_id: str) -> Observation:
    obs = Observation(source_id=source.source_id, capture_status="OK",
                      pixel_sha256=f"{source.source_id}-{hash(raw) & 0xffff}",
                      ocr_executed=True)
    if raw == "":
        obs.ocr_status = "EMPTY_TEXT"
        obs.parse_status = "NOT_RUN"
    else:
        obs.ocr_status = "OK"
        bound = RawBound(raw, False, len(raw.encode("utf-8")))
        outcome = parse_for_source(bound, source.data_type,
                                   separator_mode=source.decimal_separator,
                                   numeric_range=source.numeric_range,
                                   precision_max=source.decimal_precision_max,
                                   line_part=source.line_part)
        obs.raw_text = raw
        obs.parse_status = outcome.parse_status
        obs.normalized_value = outcome.normalized_value
        obs.value_kind = outcome.value_kind
        obs.sign_normalized = outcome.sign_normalized
        obs.ocr_ref = frame_id
    obs.value_status = C.derive_value_status(
        obs.capture_status, obs.ocr_status, obs.parse_status,
        obs.stability_status)
    return obs


def run_evaluation() -> dict[str, Any]:
    sources = build_sources()
    engine = StabilityEngine(sources, confirmations=1, debounce_ms=0,
                             min_change_threshold=None,
                             retention_mode=C.RETENTION_CHANGED_AND_ERRORS)
    outcomes: list[dict[str, Any]] = []
    for index, frame in enumerate(build_script(), start=1):
        frame_id = f"f{index}"
        observations = {source.source_id:
                        _observation(source, frame.raw[source.source_id],
                                     frame_id)
                        for source in sources}
        decision = engine.process_tick(observations, frame_id, index * 1000.0,
                                       {})
        outcomes.append({
            "frame": frame.label,
            "event_status": decision.event_status,
            "changed": decision.changed_source_ids,
            "value_status": {sid: obs.value_status
                             for sid, obs in observations.items()},
            "sign_normalized": any(obs.sign_normalized
                                   for obs in observations.values()),
        })
    events = [o for o in outcomes if o["event_status"]]
    metrics = {
        "task_id": EVAL_TASK_ID,
        "frame_count": len(outcomes),
        "retained_event_count": len(events),
        "change_events": sum(1 for o in events
                             if o["event_status"] == "RETAINED_CHANGE"),
        "error_events": sum(1 for o in events
                            if o["event_status"] == "RETAINED_ERROR"),
        "unicode_minus_preserved_negative": any(
            o["frame"] == "unicode_minus" and o["sign_normalized"]
            for o in outcomes),
        "ambiguous_not_silently_resolved": any(
            o["frame"] == "ambiguous_lat"
            and o["value_status"]["src-lat"] == "AMBIGUOUS_MULTIPLE_NUMBERS"
            for o in outcomes),
        "empty_is_missing_not_error": all(
            o["value_status"]["src-lat"] == "MISSING_SOURCE_VALUE"
            for o in outcomes if o["frame"] == "empty_lat"),
        "out_of_range_flagged": any(
            o["frame"] == "out_of_range"
            and o["value_status"]["src-lon"] == "OUT_OF_RANGE"
            for o in outcomes),
        "constant_frame_no_event": all(
            o["event_status"] is None
            for o in outcomes if o["frame"] == "constant"),
        "note": ("Deterministic scripted OCR stream; not a real-world "
                 "accuracy claim. " + C.OUTPUT_CLASSIFICATION),
        "outcomes": outcomes,
    }
    metrics["all_expectations_met"] = all(
        metrics[key] for key in (
            "unicode_minus_preserved_negative",
            "ambiguous_not_silently_resolved", "empty_is_missing_not_error",
            "out_of_range_flagged", "constant_frame_no_event"))
    return metrics


def write_evidence(root: Path) -> Path:
    from .io_utils import atomic_write_json, write_manifest
    metrics = run_evaluation()
    evidence_dir = root / "runs" / "evidence" / EVAL_TASK_ID
    if evidence_dir.exists():
        raise FileExistsError(f"{evidence_dir} already exists")
    evidence_dir.mkdir(parents=True)
    atomic_write_json(evidence_dir / "m2_eval_metrics.json", metrics)
    write_manifest(evidence_dir, evidence_dir)
    return evidence_dir
