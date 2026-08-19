"""Project-local SQLite sessions with journal-first crash recovery."""

from __future__ import annotations

import json
import secrets
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from screen2xyz_m2.journal import RunJournal, read_journal

from . import __version__
from .capture import CapturedPoint
from .mapping import ChannelMapping


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class SessionStore:
    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir.expanduser().resolve()
        self.root = self.project_dir / ".screen2xyz"
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "screen2xyz.sqlite3"
        self.journal_root = self.root / "journal"
        self.journal_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._create_schema()
        self._journals: dict[str, RunJournal] = {}
        self.replay_journals()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_utc TEXT NOT NULL,
                mapping_json TEXT NOT NULL,
                calibration_json TEXT,
                app_version TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                x REAL NOT NULL,
                y REAL NOT NULL,
                z REAL,
                description TEXT,
                point_number TEXT,
                source_method_x TEXT NOT NULL,
                source_method_y TEXT NOT NULL,
                source_method_z TEXT NOT NULL,
                raw_text_x TEXT,
                raw_text_y TEXT,
                raw_text_z TEXT,
                confidence_x REAL,
                confidence_y REAL,
                confidence_z REAL,
                capture_status TEXT NOT NULL DEFAULT 'COMPLETE',
                created_utc TEXT NOT NULL,
                journal_event_id TEXT NOT NULL UNIQUE,
                deleted_utc TEXT
            );
            CREATE TABLE IF NOT EXISTS point_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                point_id INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                action TEXT NOT NULL,
                before_json TEXT NOT NULL,
                after_json TEXT,
                created_utc TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS session_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                action TEXT NOT NULL,
                before_json TEXT NOT NULL,
                after_json TEXT NOT NULL,
                created_utc TEXT NOT NULL
            );
            """
        )
        columns = {
            row[1] for row in self.connection.execute("PRAGMA table_info(points)")
        }
        if "deleted_utc" not in columns:
            self.connection.execute("ALTER TABLE points ADD COLUMN deleted_utc TEXT")
        if "capture_status" not in columns:
            self.connection.execute(
                "ALTER TABLE points ADD COLUMN capture_status TEXT NOT NULL DEFAULT 'COMPLETE'"
            )
        self.connection.commit()
        z_column = next(
            row for row in self.connection.execute("PRAGMA table_info(points)")
            if row[1] == "z"
        )
        if bool(z_column[3]):
            self._make_z_nullable()

    def _make_z_nullable(self) -> None:
        """Migrate v2.6 databases so an explicitly partial row can store NULL Z."""
        self.connection.executescript(
            """
            PRAGMA foreign_keys = OFF;
            BEGIN;
            CREATE TABLE points_v27 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                x REAL NOT NULL,
                y REAL NOT NULL,
                z REAL,
                description TEXT,
                point_number TEXT,
                source_method_x TEXT NOT NULL,
                source_method_y TEXT NOT NULL,
                source_method_z TEXT NOT NULL,
                raw_text_x TEXT,
                raw_text_y TEXT,
                raw_text_z TEXT,
                confidence_x REAL,
                confidence_y REAL,
                confidence_z REAL,
                capture_status TEXT NOT NULL DEFAULT 'COMPLETE',
                created_utc TEXT NOT NULL,
                journal_event_id TEXT NOT NULL UNIQUE,
                deleted_utc TEXT
            );
            INSERT INTO points_v27 (
                id, session_id, x, y, z, description, point_number,
                source_method_x, source_method_y, source_method_z,
                raw_text_x, raw_text_y, raw_text_z,
                confidence_x, confidence_y, confidence_z, capture_status,
                created_utc, journal_event_id, deleted_utc
            ) SELECT
                id, session_id, x, y, z, description, point_number,
                source_method_x, source_method_y, source_method_z,
                raw_text_x, raw_text_y, raw_text_z,
                confidence_x, confidence_y, confidence_z, capture_status,
                created_utc, journal_event_id, deleted_utc
            FROM points;
            DROP TABLE points;
            ALTER TABLE points_v27 RENAME TO points;
            COMMIT;
            PRAGMA foreign_keys = ON;
            """
        )

    def start_session(
        self,
        mapping: ChannelMapping,
        *,
        calibration: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> str:
        mapping.validate()
        session_id = session_id or f"session-{secrets.token_hex(8)}"
        created = _utc_now()
        mapping_json = json.dumps(mapping.to_json(), sort_keys=True)
        calibration_json = None if calibration is None else json.dumps(calibration, sort_keys=True)
        self.connection.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
            (session_id, created, mapping_json, calibration_json, __version__),
        )
        self.connection.commit()
        journal = RunJournal(self.journal_root / session_id)
        journal.write_session({
            "schema_version": "2.0",
            "session_id": session_id,
            "created_utc": created,
            "mapping": mapping.to_json(),
            "calibration": calibration,
            "app_version": __version__,
        })
        self._journals[session_id] = journal
        return session_id

    @staticmethod
    def _point_payload(point: CapturedPoint) -> dict[str, Any]:
        return {
            "values": point.values,
            "source_methods": point.source_methods,
            "raw_texts": point.raw_texts,
            "confidences": point.confidences,
            "capture_status": point.capture_status,
            "created_utc": point.created_utc,
        }

    def append_point(self, session_id: str, point: CapturedPoint) -> int:
        with self._lock:
            journal = self._journals.get(session_id)
            if journal is None:
                raise ValueError("session is not active in this process")
            event = journal.append_event(
                {
                    "session_id": session_id,
                    "event_status": "RETAINED_CHANGE",
                    "timestamp_utc": point.created_utc,
                    "point": self._point_payload(point),
                    "observations": [],
                },
                crops={},
                retention_mode="values_only",
            )
            return self._insert_event(event)

    def _insert_event(self, event: dict[str, Any]) -> int:
        point = event["point"]
        values = point["values"]
        methods = point["source_methods"]
        raw = point["raw_texts"]
        confidence = point["confidences"]
        cursor = self.connection.execute(
            """
            INSERT OR IGNORE INTO points (
                session_id, x, y, z, description, point_number,
                source_method_x, source_method_y, source_method_z,
                raw_text_x, raw_text_y, raw_text_z,
                confidence_x, confidence_y, confidence_z,
                capture_status, created_utc, journal_event_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["session_id"], float(values["x"]), float(values["y"]),
                None if values["z"] is None else float(values["z"]),
                values.get("description"), values.get("point_number"),
                methods["x"], methods["y"], methods["z"],
                raw.get("x"), raw.get("y"), raw.get("z"),
                confidence.get("x"), confidence.get("y"), confidence.get("z"),
                point.get("capture_status", "COMPLETE"),
                point["created_utc"], event["event_id"],
            ),
        )
        self.connection.commit()
        if cursor.lastrowid:
            return int(cursor.lastrowid)
        existing = self.connection.execute(
            "SELECT id FROM points WHERE journal_event_id = ?", (event["event_id"],)
        ).fetchone()
        return int(existing["id"])

    def replay_journals(self) -> int:
        replayed = 0
        for directory in sorted(self.journal_root.iterdir()):
            if not directory.is_dir() or not (directory / "events.jsonl").exists():
                continue
            events, _warnings = read_journal(directory)
            for event in events:
                if "point" not in event:
                    continue
                before = self.connection.total_changes
                self._insert_event(event)
                replayed += self.connection.total_changes - before
        return replayed

    def points(
        self, session_id: str, *, include_deleted: bool = False
    ) -> list[sqlite3.Row]:
        deleted_clause = "" if include_deleted else " AND deleted_utc IS NULL"
        with self._lock:
            return list(self.connection.execute(
                "SELECT * FROM points WHERE session_id = ?" + deleted_clause + " ORDER BY id",
                (session_id,),
            ))

    def edit_point(self, session_id: str, point_id: int, changes: dict[str, Any]) -> None:
        allowed = {"x", "y", "z", "description", "point_number"}
        unknown = set(changes) - allowed
        if unknown or not changes:
            raise ValueError(f"unsupported point edits: {sorted(unknown)}")
        with self._lock:
            before = self.connection.execute(
                "SELECT * FROM points WHERE id = ? AND session_id = ? AND deleted_utc IS NULL",
                (point_id, session_id),
            ).fetchone()
            if before is None:
                raise KeyError(point_id)
            normalized = dict(changes)
            for name in ("x", "y", "z"):
                if name in normalized:
                    normalized[name] = (
                        None if normalized[name] is None else float(normalized[name])
                    )
            if "z" in normalized:
                normalized["capture_status"] = (
                    "PARTIAL_MISSING_Z" if normalized["z"] is None else "COMPLETE"
                )
            assignments = ", ".join(f"{name} = ?" for name in sorted(normalized))
            values = [normalized[name] for name in sorted(normalized)]
            now = _utc_now()
            with self.connection:
                self.connection.execute(
                    f"UPDATE points SET {assignments} WHERE id = ? AND session_id = ?",
                    (*values, point_id, session_id),
                )
                after = self.connection.execute(
                    "SELECT * FROM points WHERE id = ?", (point_id,)
                ).fetchone()
                self.connection.execute(
                """
                INSERT INTO point_audit
                    (point_id, session_id, action, before_json, after_json, created_utc)
                VALUES (?, ?, 'EDIT', ?, ?, ?)
                """,
                    (
                        point_id,
                        session_id,
                        json.dumps(dict(before), sort_keys=True),
                        json.dumps(dict(after), sort_keys=True),
                        now,
                    ),
                )

    def delete_point(self, session_id: str, point_id: int) -> None:
        with self._lock:
            before = self.connection.execute(
                "SELECT * FROM points WHERE id = ? AND session_id = ? AND deleted_utc IS NULL",
                (point_id, session_id),
            ).fetchone()
            if before is None:
                raise KeyError(point_id)
            now = _utc_now()
            with self.connection:
                self.connection.execute(
                    "UPDATE points SET deleted_utc = ? WHERE id = ? AND session_id = ?",
                    (now, point_id, session_id),
                )
                self.connection.execute(
                """
                INSERT INTO point_audit
                    (point_id, session_id, action, before_json, after_json, created_utc)
                VALUES (?, ?, 'DELETE', ?, NULL, ?)
                """,
                    (point_id, session_id, json.dumps(dict(before), sort_keys=True), now),
                )

    def audit_events(self, session_id: str) -> list[sqlite3.Row]:
        with self._lock:
            return list(self.connection.execute(
                "SELECT * FROM point_audit WHERE session_id = ? ORDER BY id",
                (session_id,),
            ))

    def update_session_mapping(
        self, session_id: str, mapping: ChannelMapping
    ) -> None:
        mapping.validate()
        after = json.dumps(mapping.to_json(), sort_keys=True)
        with self._lock:
            row = self.session(session_id)
            before = row["mapping_json"]
            with self.connection:
                self.connection.execute(
                    "UPDATE sessions SET mapping_json = ? WHERE id = ?",
                    (after, session_id),
                )
                self.connection.execute(
                    """
                    INSERT INTO session_audit
                        (session_id, action, before_json, after_json, created_utc)
                    VALUES (?, 'RECONFIGURE_ZONES', ?, ?, ?)
                    """,
                    (session_id, before, after, _utc_now()),
                )

    def session_audit_events(self, session_id: str) -> list[sqlite3.Row]:
        with self._lock:
            return list(self.connection.execute(
                "SELECT * FROM session_audit WHERE session_id = ? ORDER BY id",
                (session_id,),
            ))

    def session(self, session_id: str) -> sqlite3.Row:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        if row is None:
            raise KeyError(session_id)
        return row

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "SessionStore":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
