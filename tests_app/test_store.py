from __future__ import annotations

import tempfile
import unittest
import sqlite3
from pathlib import Path

from screen2xyz_app.capture import CapturedPoint
from screen2xyz_app.mapping import ChannelMapping, ChannelSource
from screen2xyz_app.store import SessionStore


class StoreTests(unittest.TestCase):
    def mapping(self):
        return ChannelMapping({
            "x": ChannelSource("screen_zone_ocr", (0, 0, 20, 20)),
            "y": ChannelSource("screen_zone_ocr", (20, 0, 20, 20)),
            "z": ChannelSource("plan_label_ocr"),
        })

    def point(self):
        return CapturedPoint(
            values={"x": 100.1, "y": 200.2, "z": 49.78, "description": "test"},
            source_methods={"x": "screen_zone_ocr", "y": "screen_zone_ocr", "z": "plan_label_ocr"},
            raw_texts={"x": "100.1", "y": "200.2", "z": "49.78"},
            confidences={"x": 0.9, "y": 0.8, "z": 0.95},
            created_utc="2026-01-01T00:00:00Z",
        )

    def test_journal_first_sqlite_round_trip_and_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            store = SessionStore(project)
            session_id = store.start_session(self.mapping(), session_id="session-test")
            point_id = store.append_point(session_id, self.point())
            self.assertEqual(point_id, 1)
            self.assertTrue((project / ".screen2xyz/journal/session-test/events.jsonl").is_file())
            self.assertEqual(store.points(session_id)[0]["z"], 49.78)
            store.close()
            reopened = SessionStore(project)
            self.assertEqual(reopened.replay_journals(), 0)
            self.assertEqual(len(reopened.points(session_id)), 1)
            reopened.close()

    def test_database_has_required_tables(self):
        with tempfile.TemporaryDirectory() as temporary:
            with SessionStore(Path(temporary)) as store:
                names = {row[0] for row in store.connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )}
                self.assertTrue(
                    {"sessions", "points", "point_audit", "session_audit"}.issubset(names)
                )

    def test_v26_not_null_z_schema_migrates_without_losing_points(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            store = SessionStore(project)
            session_id = store.start_session(self.mapping(), session_id="legacy-session")
            store.append_point(session_id, self.point())
            database = store.db_path
            store.close()
            connection = sqlite3.connect(database)
            connection.executescript(
                """
                ALTER TABLE points RENAME TO points_current;
                CREATE TABLE points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(id),
                    x REAL NOT NULL, y REAL NOT NULL, z REAL NOT NULL,
                    description TEXT, point_number TEXT,
                    source_method_x TEXT NOT NULL,
                    source_method_y TEXT NOT NULL,
                    source_method_z TEXT NOT NULL,
                    raw_text_x TEXT, raw_text_y TEXT, raw_text_z TEXT,
                    confidence_x REAL, confidence_y REAL, confidence_z REAL,
                    created_utc TEXT NOT NULL,
                    journal_event_id TEXT NOT NULL UNIQUE,
                    deleted_utc TEXT
                );
                INSERT INTO points (
                    id, session_id, x, y, z, description, point_number,
                    source_method_x, source_method_y, source_method_z,
                    raw_text_x, raw_text_y, raw_text_z,
                    confidence_x, confidence_y, confidence_z,
                    created_utc, journal_event_id, deleted_utc
                ) SELECT
                    id, session_id, x, y, z, description, point_number,
                    source_method_x, source_method_y, source_method_z,
                    raw_text_x, raw_text_y, raw_text_z,
                    confidence_x, confidence_y, confidence_z,
                    created_utc, journal_event_id, deleted_utc
                FROM points_current;
                DROP TABLE points_current;
                """
            )
            connection.close()

            migrated = SessionStore(project)
            try:
                columns = {
                    row[1]: row for row in migrated.connection.execute(
                        "PRAGMA table_info(points)"
                    )
                }
                self.assertEqual(columns["z"][3], 0)
                self.assertIn("capture_status", columns)
                row = migrated.points(session_id)[0]
                self.assertEqual(row["z"], 49.78)
                self.assertEqual(row["capture_status"], "COMPLETE")
            finally:
                migrated.close()

    def test_edit_and_soft_delete_are_audited(self):
        with tempfile.TemporaryDirectory() as temporary:
            with SessionStore(Path(temporary)) as store:
                session_id = store.start_session(self.mapping(), session_id="session-review")
                point_id = store.append_point(session_id, self.point())
                store.edit_point(session_id, point_id, {"z": 50.25, "description": "reviewed"})
                self.assertEqual(store.points(session_id)[0]["z"], 50.25)
                store.delete_point(session_id, point_id)
                self.assertEqual(store.points(session_id), [])
                self.assertEqual(len(store.points(session_id, include_deleted=True)), 1)
                events = store.audit_events(session_id)
                self.assertEqual([event["action"] for event in events], ["EDIT", "DELETE"])


if __name__ == "__main__":
    unittest.main()
