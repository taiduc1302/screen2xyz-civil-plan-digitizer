"""Crash-safe run journal: crops -> events.jsonl -> checkpoint (§6c order)."""

from __future__ import annotations

import csv as _csv
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from . import contracts as C

_SOURCE_ID_RE = re.compile(r"^src-[a-z0-9-]+$")


class StorageFailure(RuntimeError):
    """Crop or journal write failed; caller pauses the session."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason = reason


class DiskLimit(StorageFailure):
    def __init__(self, used: int, limit: int) -> None:
        super().__init__("DISK_LIMIT", f"{used} of {limit} bytes")
        self.used = used


class RunJournal:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.events_path = run_dir / "events.jsonl"
        self.checkpoint_path = run_dir / "state_checkpoint.json"
        self.errors_path = run_dir / "errors.log"
        self.event_seq = 0
        self.frame_seq = 0
        self.disk_bytes = 0
        self.counters = {"ticks": 0, "skipped": 0, "ocr_errors": 0,
                         "events": 0}
        self._hash_to_artifact: dict[str, str] = {}
        self._last_checkpoint = 0.0
        # In-memory mirror of every successfully journaled event this run,
        # fed only by append_event - never a re-read of events.jsonl - so the
        # live CSV snapshot can be regenerated after each event without a
        # per-tick disk re-scan (§2: "never a full-CSV-reread per tick").
        self.live_events: list[dict[str, Any]] = []
        self.live_snapshot_row_count = 0
        self.last_live_snapshot_utc: str | None = None
        self.last_live_snapshot_error: str | None = None
        # Incremental-append live-snapshot state (§10: O(1) per event, not a
        # full O(n) regeneration every event). Headers are written once on
        # the first appended row; the axis mapping is fixed for the session.
        self._live_initialized = False
        self._live_axis_ids: tuple[str, str, str] | None = None
        run_dir.mkdir(parents=True, exist_ok=False)

    # -- session ----------------------------------------------------------

    def write_session(self, session: dict[str, Any]) -> None:
        data = (json.dumps(session, indent=2, sort_keys=True) + "\n") \
            .encode("utf-8")
        (self.run_dir / "session.json").write_bytes(data)
        self.disk_bytes += len(data)

    def log_error(self, text: str) -> None:
        try:
            with self.errors_path.open("a", encoding="utf-8") as handle:
                handle.write(text.rstrip() + "\n")
        except OSError:
            pass

    # -- crops ------------------------------------------------------------

    def _write_crop(self, event_seq: int, source_id: str,
                    png: bytes) -> tuple[str, str]:
        if not _SOURCE_ID_RE.match(source_id):
            raise StorageFailure("CROP_WRITE_FAILURE",
                                 f"unsafe source_id {source_id!r}")
        relative = C.CROP_PATH_TEMPLATE.format(event_seq=event_seq,
                                               source_id=source_id)
        final = (self.run_dir / relative).resolve()
        if not final.is_relative_to(self.run_dir.resolve()):
            raise StorageFailure("CROP_WRITE_FAILURE",
                                 "crop path escapes run directory")
        final.parent.mkdir(parents=True, exist_ok=True)
        temporary = final.with_name(final.name + ".tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(png)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, final)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise StorageFailure("CROP_WRITE_FAILURE", str(exc)) from exc
        artifact_hash = hashlib.sha256(png).hexdigest()
        self.disk_bytes += len(png)
        return relative, artifact_hash

    # -- events -----------------------------------------------------------

    def append_event(self, event: dict[str, Any],
                     crops: dict[str, bytes],
                     retention_mode: str) -> dict[str, Any]:
        """Write crops first, then the referencing journal line (§6c)."""

        if self.disk_bytes >= C.DISK_STOP_BYTES:
            raise DiskLimit(self.disk_bytes, C.DISK_STOP_BYTES)
        # Compute the next sequence number into a LOCAL and only commit it to
        # self.event_seq AFTER the journal line is durably fsynced (below).
        # A transient crop/journal I/O failure here must NOT advance the
        # counter: otherwise the failed number is skipped, the (resumable)
        # storage-failure pause lets the run continue, the next event writes
        # a discontiguous seq, and read_journal's strict-contiguity check
        # then raises JOURNAL_SEQUENCE_BREAK on Stop/recover - permanently
        # corrupting the run this pause/resume mechanism exists to survive.
        event_seq = self.event_seq + 1
        crops_saved: dict[str, Any] = {}
        write_pngs = retention_mode != C.RETENTION_VALUES_ONLY
        for source_id, png in crops.items():
            pixel_hash = None
            for obs in event.get("observations", []):
                if obs.get("source_id") == source_id:
                    pixel_hash = obs.get("pixel_sha256")
            if not write_pngs:
                crops_saved[source_id] = None
                continue
            if pixel_hash and pixel_hash in self._hash_to_artifact \
                    and event.get("event_status") == "RETAINED_DIAGNOSTIC":
                prior = self._hash_to_artifact[pixel_hash]
                crops_saved[source_id] = {"path": prior,
                                          "pixel_sha256": pixel_hash,
                                          "crop_artifact_sha256": None,
                                          "reference": True}
                continue
            relative, artifact = self._write_crop(event_seq, source_id, png)
            crops_saved[source_id] = {"path": relative,
                                      "pixel_sha256": pixel_hash,
                                      "crop_artifact_sha256": artifact,
                                      "reference": False}
            if pixel_hash:
                self._hash_to_artifact[pixel_hash] = relative
        event = {**event,
                 "schema_version": C.SCHEMA_VERSION,
                 "event_seq": event_seq,
                 "event_id": f"{event.get('session_id', 'run')}-e{event_seq}",
                 "crops_saved": crops_saved,
                 "retention_mode": retention_mode}
        line = json.dumps(event, sort_keys=True, ensure_ascii=False)
        try:
            with self.events_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            raise StorageFailure("CROP_WRITE_FAILURE",
                                 f"journal append: {exc}") from exc
        # Durable now: commit the sequence number and all derived counters.
        self.event_seq = event_seq
        self.disk_bytes += len(line) + 1
        self.counters["events"] += 1
        self.live_events.append(event)
        self.maybe_checkpoint(event["stable_signature"]
                              if "stable_signature" in event else {})
        return event

    # -- live CSV snapshot (§2: durable journal is truth; this is a best-
    # effort, atomically-replaced convenience view of it) -------------------

    def _atomic_replace(self, path: Path, data: bytes) -> None:
        temporary = path.with_name(path.name + ".tmp")
        with temporary.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)

    # The exact exception boundary for write_live_snapshot's "never crash
    # recording" contract (§11). These are the failure modes an export
    # serialization + atomic file write can legitimately raise: I/O errors,
    # a malformed/unexpected event shape (Value/Type/Key/csv/Unicode), and
    # out-of-memory while materializing a large CSV. Anything OUTSIDE this
    # set (e.g. an AttributeError from a genuine programmer defect) is NOT
    # swallowed, so real bugs still surface loudly.
    _SNAPSHOT_EXPECTED_ERRORS = (
        OSError, ValueError, TypeError, KeyError, IndexError,
        UnicodeError, MemoryError, _csv.Error,
    )

    def write_live_snapshot(self, sources: list[Any],
                            cursor_metadata: bool) -> dict[str, Any]:
        """Regenerate events_wide.live.csv / observations_long.live.csv /
        points.live.xyz from every event journaled so far, via temp file +
        flush + fsync + atomic replace. Never raises for any EXPECTED
        serialization/export failure (see _SNAPSHOT_EXPECTED_ERRORS): a
        failure here must never lose the already-journaled event or crash
        the recording session (§2/§11) - the caller inspects the returned
        dict instead. Unexpected exceptions (real defects) still propagate."""

        from .exports import long_csv, wide_csv, xyz_export
        from datetime import datetime, timezone
        try:
            wide = wide_csv(self.live_events, sources, cursor_metadata)
            self._atomic_replace(self.run_dir / "events_wide.live.csv", wide)
            long_ = long_csv(self.live_events, sources)
            self._atomic_replace(
                self.run_dir / "observations_long.live.csv", long_)
            xyz_bytes, _ = xyz_export(self.live_events, sources)
            if xyz_bytes is not None:
                self._atomic_replace(self.run_dir / "points.live.xyz",
                                     xyz_bytes)
            self.live_snapshot_row_count = len(self.live_events)
            self.last_live_snapshot_error = None
            self.last_live_snapshot_utc = \
                datetime.now(timezone.utc).isoformat()
            return {"ok": True, "row_count": self.live_snapshot_row_count,
                    "error": None}
        except self._SNAPSHOT_EXPECTED_ERRORS as exc:
            detail = f"{type(exc).__name__}: {exc}"
            self.last_live_snapshot_error = detail
            return {"ok": False, "row_count": self.live_snapshot_row_count,
                    "error": detail}

    def _append_bytes(self, path: Path, data: bytes) -> None:
        with path.open("ab") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())

    def append_live_row(self, event: dict[str, Any], sources: list[Any],
                        cursor_metadata: bool) -> dict[str, Any]:
        """Append ONE just-journaled event's rows to the live CSV/XYZ
        previews in O(1) (§10) - byte-identical to what a full regeneration
        would produce, proven by test. The live files are a best-effort
        preview; events.jsonl remains the crash-safe source of truth and
        finalize() regenerates the authoritative CSV from it, so a partial
        last appended line after a crash is acceptable. Never raises for an
        expected export failure - returns {"ok", "row_count", "error"} the
        same way write_live_snapshot does, so the caller can show the live-
        CSV state truthfully without ever losing the journaled event."""

        from .exports import (csv_header_bytes, csv_row_bytes,
                              LONG_CSV_HEADER, long_csv_rows,
                              wide_csv_header, wide_csv_row, xyz_axis_ids,
                              xyz_line_for_event)
        from datetime import datetime, timezone
        wide_path = self.run_dir / "events_wide.live.csv"
        long_path = self.run_dir / "observations_long.live.csv"
        xyz_path = self.run_dir / "points.live.xyz"
        try:
            if not self._live_initialized:
                self._append_bytes(
                    wide_path, csv_header_bytes(
                        wide_csv_header(sources, cursor_metadata)))
                self._append_bytes(
                    long_path, csv_header_bytes(LONG_CSV_HEADER))
                self._live_axis_ids = xyz_axis_ids(sources)
                self._live_initialized = True
            wide_header = wide_csv_header(sources, cursor_metadata)
            self._append_bytes(wide_path, csv_row_bytes(
                wide_csv_row(event, sources, cursor_metadata), wide_header))
            long_data = b"".join(
                csv_row_bytes(row, LONG_CSV_HEADER)
                for row in long_csv_rows(event, sources))
            if long_data:
                self._append_bytes(long_path, long_data)
            if self._live_axis_ids is not None:
                line = xyz_line_for_event(event, self._live_axis_ids)
                if line is not None:
                    self._append_bytes(xyz_path,
                                      (line + "\n").encode("utf-8"))
            self.live_snapshot_row_count += 1
            self.last_live_snapshot_error = None
            self.last_live_snapshot_utc = \
                datetime.now(timezone.utc).isoformat()
            return {"ok": True, "row_count": self.live_snapshot_row_count,
                    "error": None}
        except self._SNAPSHOT_EXPECTED_ERRORS as exc:
            detail = f"{type(exc).__name__}: {exc}"
            self.last_live_snapshot_error = detail
            return {"ok": False, "row_count": self.live_snapshot_row_count,
                    "error": detail}

    # -- checkpoint (only after the journal state it reflects) -------------

    def maybe_checkpoint(self, stable_signature: dict[str, Any],
                         force: bool = False) -> None:
        now = time.monotonic()
        if not force and (now - self._last_checkpoint) * 1000 \
                < C.CHECKPOINT_INTERVAL_MS:
            return
        self._last_checkpoint = now
        payload = {"schema_version": C.SCHEMA_VERSION,
                   "last_event_seq": self.event_seq,
                   "last_frame_seq": self.frame_seq,
                   "stable_signature": stable_signature,
                   "counters": {**self.counters,
                                "disk_bytes": self.disk_bytes}}
        temporary = self.checkpoint_path.with_name("state_checkpoint.tmp")
        try:
            with temporary.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.checkpoint_path)
        except OSError:
            temporary.unlink(missing_ok=True)

    def disk_status(self) -> tuple[int, bool, bool]:
        return (self.disk_bytes,
                self.disk_bytes >= C.DISK_WARN_BYTES,
                self.disk_bytes >= C.DISK_STOP_BYTES)


def read_journal(run_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Tolerant canonical read: warn on the unterminated final line only."""

    warnings: list[str] = []
    events: list[dict[str, Any]] = []
    path = run_dir / "events.jsonl"
    if not path.exists():
        return events, ["JOURNAL_MISSING"]
    raw = path.read_bytes()
    lines = raw.split(b"\n")
    trailing_complete = raw.endswith(b"\n")
    # Index of the last non-empty split segment, computed ONCE (was an
    # O(n^2) per-iteration list rebuild on the hot finalize/recover path).
    last_nonempty_index = -1
    for i in range(len(lines) - 1, -1, -1):
        if lines[i]:
            last_nonempty_index = i
            break
    for index, line in enumerate(lines):
        if not line:
            continue
        is_last = index == last_nonempty_index and not trailing_complete
        try:
            event = json.loads(line.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            if is_last:
                warnings.append("PARTIAL_FINAL_LINE")
                break
            raise StorageFailure("MALFORMED_JOURNAL_LINE",
                                 f"line {index + 1}")
        expected = len(events) + 1
        if event.get("event_seq") != expected:
            raise StorageFailure("JOURNAL_SEQUENCE_BREAK",
                                 f"line {index + 1}: "
                                 f"{event.get('event_seq')} != {expected}")
        events.append(event)
    return events, warnings


def verify_crops(run_dir: Path,
                 events: list[dict[str, Any]]) -> list[str]:
    """Null missing/mismatched crop references; report; never crash."""

    warnings: list[str] = []
    referenced: set[str] = set()
    for event in events:
        for source_id, ref in (event.get("crops_saved") or {}).items():
            if not ref or ref.get("reference"):
                if ref:
                    referenced.add(ref.get("path", ""))
                continue
            referenced.add(ref["path"])
            crop_path = run_dir / ref["path"]
            if not crop_path.is_file():
                warnings.append(f"MISSING_CROP:{ref['path']}")
                event["crops_saved"][source_id] = None
                continue
            digest = hashlib.sha256(crop_path.read_bytes()).hexdigest()
            if ref.get("crop_artifact_sha256") \
                    and digest != ref["crop_artifact_sha256"]:
                warnings.append(f"CROP_HASH_MISMATCH:{ref['path']}")
                event["crops_saved"][source_id] = None
    crops_root = run_dir / "crops"
    if crops_root.exists():
        for crop in crops_root.rglob("*.png"):
            relative = crop.relative_to(run_dir).as_posix()
            if relative not in referenced:
                warnings.append(f"ORPHAN_CROP:{relative}")
    return warnings
