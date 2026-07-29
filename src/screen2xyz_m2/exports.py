"""Deterministic exports, sanitized summary, strict XYZ gate, manifest."""

from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
from typing import Any

from screen2xyz_lab.evidence import write_manifest
from screen2xyz_lab.exporters import csv_bytes, formula_safe_display

from . import contracts as C
from .models import SourceConfig, xyz_eligibility


def _source_order(sources: list[SourceConfig]) -> list[SourceConfig]:
    return [source for source in sources if source.enabled]


def csv_header_bytes(header: tuple[str, ...]) -> bytes:
    """Just the CSV header line (with the trailing \\r\\n), byte-identical to
    the first line csv_bytes() writes - used to initialize an incrementally
    appended live CSV file."""
    return csv_bytes([], header)


def csv_row_bytes(row: dict[str, Any], header: tuple[str, ...]) -> bytes:
    """A single CSV data row (no header), byte-identical to the row
    csv_bytes() would write for it - used to append one event's row(s) to a
    live CSV without regenerating the whole file (§10 O(1) per event)."""
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output, fieldnames=header, lineterminator="\r\n",
        quoting=csv.QUOTE_MINIMAL, extrasaction="raise")
    writer.writerow({key: row.get(key, "") for key in header})
    return output.getvalue().encode("utf-8")


def wide_csv_header(sources: list[SourceConfig],
                    cursor_metadata: bool) -> tuple[str, ...]:
    header = ["event_seq", "event_id", "event_status", "capture_utc",
              "monotonic_offset_ms"]
    if cursor_metadata:
        header += ["cursor_screen_x", "cursor_screen_y"]
    for source in _source_order(sources):
        # Header cells embed the user-controlled display name; escape it so a
        # name like "=cmd" cannot execute when the CSV is opened.
        safe_name = formula_safe_display(source.display_name)
        header += [f"{safe_name} [value]",
                   f"{safe_name} [value_status]"]
    return tuple(header)


def wide_csv_row(event: dict[str, Any], sources: list[SourceConfig],
                 cursor_metadata: bool) -> dict[str, Any]:
    """One event's wide-CSV row, exactly as `wide_csv` would write it - the
    live UI feed's 'Saved CSV rows' view calls this directly on a single
    just-persisted event so what it shows is byte-for-byte what finalize()
    will later write, never a reimplementation of the shaping rules."""

    frame = event.get("frame") or {}
    context = event.get("scheduler_context") or {}
    row: dict[str, Any] = {
        "event_seq": event["event_seq"],
        "event_id": event["event_id"],
        "event_status": event["event_status"],
        "capture_utc": frame.get("capture_utc", ""),
        "monotonic_offset_ms": frame.get("monotonic_offset_ms",
                                         context.get(
                                             "monotonic_offset_ms", "")),
    }
    if cursor_metadata:
        cursor = frame.get("cursor") or {}
        row["cursor_screen_x"] = cursor.get("screen_x", "")
        row["cursor_screen_y"] = cursor.get("screen_y", "")
    observations = {obs["source_id"]: obs
                    for obs in event.get("observations", [])}
    for source in _source_order(sources):
        safe_name = formula_safe_display(source.display_name)
        obs = observations.get(source.source_id, {})
        value = obs.get("normalized_value")
        display = "" if value is None else str(value)
        if obs.get("value_kind") == "text":
            display = formula_safe_display(display)
        row[f"{safe_name} [value]"] = display
        row[f"{safe_name} [value_status]"] = obs.get("value_status", "")
    return row


def wide_csv(events: list[dict[str, Any]], sources: list[SourceConfig],
             cursor_metadata: bool) -> bytes:
    header = wide_csv_header(sources, cursor_metadata)
    rows = [wide_csv_row(event, sources, cursor_metadata)
            for event in events]
    return csv_bytes(rows, header)


LONG_CSV_HEADER = ("event_seq", "capture_utc", "worker_status", "source_id",
                   "display_name", "value_kind", "capture_status",
                   "ocr_status", "parse_status", "stability_status",
                   "value_status", "raw_text_display", "normalized_value",
                   "warning_codes", "ocr_executed", "confirmation",
                   "evidence_frame_id", "crop_path")


def long_csv_header(sources: list[SourceConfig]) -> tuple[str, ...]:
    return LONG_CSV_HEADER


def long_csv_rows(event: dict[str, Any],
                  sources: list[SourceConfig]) -> list[dict[str, Any]]:
    """The observations_long rows for exactly ONE event - the per-event
    unit the live snapshot appends incrementally (§10 O(1) per event)
    instead of regenerating the whole file. Byte-identical to what
    long_csv() would emit for this event."""

    names = {source.source_id: source.display_name for source in sources}
    frame = event.get("frame") or {}
    crops = event.get("crops_saved") or {}
    evidence = event.get("evidence") or {}
    rows = []
    for obs in event.get("observations", []):
        sid = obs["source_id"]
        crop_ref = crops.get(sid) or {}
        # Independent audit MINOR: coerce to str the same way wide_csv_row
        # already does (line 85) before formula_safe_display, which calls
        # .replace()/.startswith() directly and would raise AttributeError
        # on a non-str value. Not reachable via any current legitimate data
        # path (every text-kind normalized_value is already str|None), but
        # this keeps the two row-builders' defensiveness consistent.
        value = obs.get("normalized_value")
        normalized = "" if value is None else str(value)
        if obs.get("value_kind") == "text":
            normalized = formula_safe_display(normalized)
        rows.append({
            "event_seq": event["event_seq"],
            "capture_utc": frame.get("capture_utc", ""),
            "worker_status": event.get("worker_status", "OK"),
            "source_id": sid,
            "display_name": formula_safe_display(names.get(sid, sid)),
            "value_kind": obs.get("value_kind", ""),
            "capture_status": obs.get("capture_status", ""),
            "ocr_status": obs.get("ocr_status", ""),
            "parse_status": obs.get("parse_status", ""),
            "stability_status": obs.get("stability_status", ""),
            "value_status": obs.get("value_status", ""),
            "raw_text_display":
                formula_safe_display(obs.get("raw_text", "") or ""),
            "normalized_value": normalized,
            # Adversarial review finding (2026-07-21): a value that
            # survived only because of an audit-flagged recovery (e.g.
            # DEGREE_GLYPH_RECOVERED) was indistinguishable in every
            # export from a cleanly-read one - present in the journal's
            # own raw Observation, silently dropped here. This is the one
            # place the full session's own promise ("always labelled,
            # never silent") is actually kept end to end.
            "warning_codes": ";".join(obs.get("warning_codes") or ()),
            "ocr_executed": str(bool(obs.get("ocr_executed"))).lower(),
            "confirmation": obs.get("confirmation", ""),
            "evidence_frame_id":
                (evidence.get(sid) or {}).get("evidence_frame_id", ""),
            "crop_path": (crop_ref or {}).get("path", "") or "",
        })
    return rows


def long_csv(events: list[dict[str, Any]],
             sources: list[SourceConfig]) -> bytes:
    rows = []
    for event in events:
        rows.extend(long_csv_rows(event, sources))
    return csv_bytes(rows, LONG_CSV_HEADER)


def xyz_axis_ids(sources: list[SourceConfig]) -> tuple[str, str, str] | None:
    """The (x, y, z) source ids if the source set is XYZ-eligible, else
    None - the fixed-per-session axis mapping the live XYZ append uses."""

    eligibility = xyz_eligibility(sources)
    if not eligibility["eligible"]:
        return None
    return (eligibility["x_source_id"], eligibility["y_source_id"],
            eligibility["z_source_id"])


def xyz_line_for_event(event: dict[str, Any],
                       axis_ids: tuple[str, str, str]) -> str | None:
    """The single XYZ point line for one event, or None if it is not an
    eligible RETAINED_CHANGE with all three axes OK - the per-event unit the
    live XYZ append uses. Matches xyz_export()'s per-event logic exactly."""

    if event.get("event_status") != "RETAINED_CHANGE":
        return None
    observations = {obs["source_id"]: obs
                    for obs in event.get("observations", [])}
    values = []
    for sid in axis_ids:
        obs = observations.get(sid) or {}
        if obs.get("value_status") != "OK" \
                or obs.get("value_kind") != "number" \
                or obs.get("normalized_value") is None \
                or obs.get("stability_status") not in ("IMMEDIATE",
                                                       "CONFIRMED"):
            return None
        values.append(str(obs["normalized_value"]))
    return " ".join(values)


def xyz_export(events: list[dict[str, Any]],
               sources: list[SourceConfig]) -> tuple[bytes | None,
                                                     dict[str, Any]]:
    eligibility = xyz_eligibility(sources)
    metadata: dict[str, Any] = {
        "schema_version": C.SCHEMA_VERSION,
        "eligible": eligibility["eligible"],
        "reason": eligibility["reason"],
        "coordinate_reference": C.COORDINATE_REFERENCE,
        "output_classification": C.OUTPUT_CLASSIFICATION,
        "row_count": 0,
        "excluded_event_count": 0,
    }
    if not eligibility["eligible"]:
        return None, metadata
    axis_ids = (eligibility["x_source_id"], eligibility["y_source_id"],
                eligibility["z_source_id"])
    names = {source.source_id: source.display_name for source in sources}
    metadata["axis_order"] = [names[sid] for sid in axis_ids]
    lines: list[str] = []
    excluded = 0
    for event in events:
        if event.get("event_status") != "RETAINED_CHANGE":
            continue
        line = xyz_line_for_event(event, axis_ids)
        if line is not None:
            lines.append(line)
        else:
            excluded += 1
    metadata["row_count"] = len(lines)
    metadata["excluded_event_count"] = excluded
    payload = ("\n".join(lines) + "\n") if lines else ""
    return payload.encode("utf-8"), metadata


def sanitized_summary(session: dict[str, Any],
                      events: list[dict[str, Any]],
                      counters: dict[str, Any],
                      *, recovered: bool,
                      warnings: list[str]) -> dict[str, Any]:
    environment = session.get("environment_snapshot") or {}
    window = dict(environment.get("window") or {})
    window.pop("title", None)
    monitors = [{"index": index, "x": m.get("x"), "y": m.get("y"),
                 "w": m.get("w"), "h": m.get("h")}
                for index, m in enumerate(environment.get("monitors") or [])]
    return {
        "schema_version": C.SCHEMA_VERSION,
        "session_label": "Selected target",
        "recovered": recovered,
        "event_count": len(events),
        "counters": counters,
        "retention_mode": session.get("retention_mode"),
        "backend": (session.get("locked_backend") or {}).get("name"),
        "interval_ms": session.get("interval_ms"),
        "cursor_metadata": session.get("cursor_metadata", False),
        "sanitized_environment_snapshot": {
            "scope_type": (session.get("scope") or {}).get("type"),
            "window": {key: window.get(key) for key in
                       ("client_w", "client_h", "dpi")},
            "monitors": monitors,
            "virtual_screen": environment.get("virtual_screen"),
        },
        "warnings": warnings,
        "output_classification": C.OUTPUT_CLASSIFICATION,
    }


def _atomic_write(path: Path, data: bytes) -> None:
    """Same temp-file + fsync + os.replace pattern as the journal's crop and
    checkpoint writers, so a crash mid-finalize never leaves a half-written
    official export file."""

    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _csv_data_row_count(data: bytes) -> int:
    """Parse the CSV back (not a newline count, which quoted embedded
    newlines would miscount) and return the row count excluding the header -
    the real verification that finalize_exports actually wrote one row per
    journal event, not merely that it intended to (§5, §12)."""

    if not data:
        return 0
    reader = csv.reader(io.StringIO(data.decode("utf-8")))
    rows = list(reader)
    return max(0, len(rows) - 1)


def finalize_exports(run_dir: Path, session: dict[str, Any],
                     events: list[dict[str, Any]],
                     sources: list[SourceConfig],
                     counters: dict[str, Any], *,
                     recovered: bool = False,
                     warnings: list[str] | None = None) -> dict[str, Any]:
    warnings = list(warnings or [])
    cursor = bool(session.get("cursor_metadata"))
    wide_bytes = wide_csv(events, sources, cursor)
    _atomic_write(run_dir / "events_wide.csv", wide_bytes)
    _atomic_write(run_dir / "observations_long.csv",
                 long_csv(events, sources))
    xyz_bytes_payload, xyz_meta = xyz_export(events, sources)
    if xyz_bytes_payload is not None:
        _atomic_write(run_dir / "points.xyz", xyz_bytes_payload)
    (run_dir / "points_xyz_metadata.json").write_text(
        json.dumps(xyz_meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    # Verify the official wide CSV actually contains one row per event
    # written to the canonical journal (§5 "verify official row counts
    # against the canonical journal"). Read the bytes BACK FROM DISK rather
    # than re-parsing the in-memory buffer we just generated - otherwise the
    # check is a tautology (wide_csv always emits one row per event) that
    # cannot catch a truncated/partial on-disk write or post-write
    # corruption, which is exactly what a durability verification must
    # detect. A mismatch is never hidden - it is recorded as a warning and
    # in the summary, never silently dropped.
    try:
        on_disk = (run_dir / "events_wide.csv").read_bytes()
    except OSError as exc:
        on_disk = b""
        warnings.append(f"FINAL_CSV_UNREADABLE: {exc}")
    final_csv_row_count = _csv_data_row_count(on_disk)
    row_count_verified = final_csv_row_count == len(events)
    if not row_count_verified:
        warnings.append(
            f"FINAL_CSV_ROW_COUNT_MISMATCH: {final_csv_row_count} CSV rows "
            f"vs {len(events)} journal events")
    summary = sanitized_summary(session, events, counters,
                                recovered=recovered, warnings=warnings)
    summary["final_csv_row_count"] = final_csv_row_count
    summary["final_csv_row_count_verified"] = row_count_verified
    # Surface the XYZ outcome in the summary so the Finalized screen can tell
    # the owner plainly whether their point cloud was produced (and why not)
    # - previously the only signal was the separate points_xyz_metadata.json
    # the owner had to go hunting for.
    summary["xyz"] = {
        "eligible": xyz_meta["eligible"],
        "reason": xyz_meta["reason"],
        "written": xyz_bytes_payload is not None,
        "row_count": xyz_meta.get("row_count", 0),
        "excluded_event_count": xyz_meta.get("excluded_event_count", 0),
    }
    (run_dir / "run_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    write_manifest(run_dir, run_dir, replace=True)
    return summary
