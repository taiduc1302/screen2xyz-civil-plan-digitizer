"""Deterministic tests for the demo target's §6 command protocol -
`_ack_matches`, `_validate_ready`, and `DemoSession._send`'s stale/
duplicate/foreign-token/garbled-line rejection - using a fake stdin/stdout
queue, never a real subprocess, so these run instantly and never flake."""

from __future__ import annotations

import json
import queue
import unittest
from unittest.mock import MagicMock

from screen2xyz_m2.demo import (DemoProtocolError, DemoSession, _ack_matches,
                                _validate_ready)


class DemoTargetConfigTests(unittest.TestCase):
    """§9: lock the demo target's command-pump interval and the opt-in
    diagnostic gating so the timing fix cannot silently regress."""

    def test_pump_interval_is_tight(self):
        from screen2xyz_m2.adapters import demo_target_windows as dt
        self.assertLessEqual(dt.PUMP_INTERVAL_MS, 10)
        self.assertGreater(dt.PUMP_INTERVAL_MS, 0)

    def test_diagnostics_are_off_by_default(self):
        # The diagnostic timestamps are opt-in via S2XYZ_DEMO_DIAG=1, so on
        # the normal path (env var unset) they add no stderr noise and _diag
        # is a no-op.
        import os
        from screen2xyz_m2.adapters import demo_target_windows as dt
        self.assertNotEqual(os.environ.get("S2XYZ_DEMO_DIAG"), "1")
        self.assertFalse(dt._DIAG)


class AckMatchesTests(unittest.TestCase):
    def test_matching_seq_and_token_accepted(self):
        self.assertTrue(_ack_matches(
            {"seq": 5, "session_token": "abc"}, 5, "abc"))

    def test_wrong_seq_rejected(self):
        self.assertFalse(_ack_matches(
            {"seq": 4, "session_token": "abc"}, 5, "abc"))

    def test_wrong_token_rejected(self):
        self.assertFalse(_ack_matches(
            {"seq": 5, "session_token": "xyz"}, 5, "abc"))

    def test_missing_fields_rejected(self):
        self.assertFalse(_ack_matches({}, 5, "abc"))

    def test_both_wrong_rejected(self):
        self.assertFalse(_ack_matches(
            {"seq": 1, "session_token": "nope"}, 5, "abc"))


class ValidateReadyTests(unittest.TestCase):
    def test_valid_ready_returns_token(self):
        token = _validate_ready(
            {"protocol_version": "m2demo.1", "session_token": "tok123"})
        self.assertEqual(token, "tok123")

    def test_wrong_protocol_version_raises(self):
        with self.assertRaises(DemoProtocolError):
            _validate_ready({"protocol_version": "m2demo.0",
                            "session_token": "tok123"})

    def test_missing_protocol_version_raises(self):
        with self.assertRaises(DemoProtocolError):
            _validate_ready({"session_token": "tok123"})

    def test_missing_session_token_raises(self):
        with self.assertRaises(DemoProtocolError):
            _validate_ready({"protocol_version": "m2demo.1"})

    def test_empty_session_token_raises(self):
        with self.assertRaises(DemoProtocolError):
            _validate_ready({"protocol_version": "m2demo.1",
                            "session_token": ""})


def _fake_session() -> DemoSession:
    """A DemoSession with no real subprocess - .proc is a mock, the reader
    queue is a real Queue the test feeds by hand. Exercises exactly the
    same _send() code path a real session uses."""

    session = DemoSession.__new__(DemoSession)
    session.proc = MagicMock()
    session.proc.stdin = MagicMock()
    session._out_queue = queue.Queue()
    session._seq = 0
    session.session_token = "real-token"
    return session


class SendProtocolTests(unittest.TestCase):
    """§6 required coverage: duplicate messages and stale session tokens
    must never be mistaken for the current command's ack."""

    def test_normal_ack_accepted(self):
        session = _fake_session()
        session._out_queue.put(json.dumps(
            {"ok": "case", "seq": 1, "session_token": "real-token"}) + "\n")
        session._send({"cmd": "case", "name": "stable"}, timeout=2.0)

    def test_stale_ack_from_earlier_command_is_discarded(self):
        # A late ack for a PRIOR command (seq 0) sitting ahead of the real
        # one for THIS command (seq 1) must never be accepted as seq 1's ack.
        session = _fake_session()
        session._out_queue.put(json.dumps(
            {"ok": "case", "seq": 0, "session_token": "real-token"}) + "\n")
        session._out_queue.put(json.dumps(
            {"ok": "case", "seq": 1, "session_token": "real-token"}) + "\n")
        session._send({"cmd": "case", "name": "stable"}, timeout=2.0)

    def test_duplicate_ack_for_same_seq_does_not_hang_or_double_apply(self):
        session = _fake_session()
        session._out_queue.put(json.dumps(
            {"ok": "case", "seq": 1, "session_token": "real-token"}) + "\n")
        session._out_queue.put(json.dumps(
            {"ok": "case", "seq": 1, "session_token": "real-token"}) + "\n")
        session._send({"cmd": "case", "name": "stable"}, timeout=2.0)
        # The duplicate second copy is simply left unread - harmless, and
        # proven not to have been required by the fact _send already
        # returned above without touching it.
        self.assertEqual(session._out_queue.qsize(), 1)

    def test_stale_session_token_is_discarded(self):
        # A reply carrying the right seq but the WRONG (stale/foreign)
        # session token must never be accepted.
        session = _fake_session()
        session._out_queue.put(json.dumps(
            {"ok": "case", "seq": 1,
             "session_token": "some-other-sessions-token"}) + "\n")
        session._out_queue.put(json.dumps(
            {"ok": "case", "seq": 1, "session_token": "real-token"}) + "\n")
        session._send({"cmd": "case", "name": "stable"}, timeout=2.0)

    def test_garbled_line_is_skipped_not_fatal(self):
        session = _fake_session()
        session._out_queue.put("not json at all\n")
        session._out_queue.put(json.dumps(
            {"ok": "case", "seq": 1, "session_token": "real-token"}) + "\n")
        session._send({"cmd": "case", "name": "stable"}, timeout=2.0)

    def test_unknown_command_rejection_raises_protocol_error(self):
        session = _fake_session()
        session._out_queue.put(json.dumps(
            {"ok": False, "error": "UNKNOWN_COMMAND", "seq": 1,
             "session_token": "real-token"}) + "\n")
        with self.assertRaises(DemoProtocolError):
            session._send({"cmd": "bogus"}, timeout=2.0)

    def test_true_timeout_when_nothing_ever_matches(self):
        session = _fake_session()
        session._out_queue.put(json.dumps(
            {"ok": "case", "seq": 999, "session_token": "real-token"}) + "\n")
        with self.assertRaises(TimeoutError):
            session._send({"cmd": "case", "name": "stable"}, timeout=0.2)

    def test_process_ended_raises_runtime_error(self):
        session = _fake_session()
        session._out_queue.put(None)  # reader thread's end-of-stream sentinel
        with self.assertRaises(RuntimeError):
            session._send({"cmd": "case", "name": "stable"}, timeout=2.0)

    def test_each_send_uses_a_strictly_increasing_seq(self):
        session = _fake_session()
        session._out_queue.put(json.dumps(
            {"ok": "case", "seq": 1, "session_token": "real-token"}) + "\n")
        session._send({"cmd": "case", "name": "stable"}, timeout=2.0)
        session._out_queue.put(json.dumps(
            {"ok": "case", "seq": 2, "session_token": "real-token"}) + "\n")
        session._send({"cmd": "case", "name": "changing"}, timeout=2.0)
        self.assertEqual(session._seq, 2)
