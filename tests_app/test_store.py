from __future__ import annotations

import tempfile
import unittest
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
                self.assertTrue({"sessions", "points"}.issubset(names))


if __name__ == "__main__":
    unittest.main()
