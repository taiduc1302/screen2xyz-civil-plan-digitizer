from __future__ import annotations

import unittest

from screen2xyz_m2 import contracts as C
from screen2xyz_m2.models import Observation, SourceConfig, new_source_id
from screen2xyz_m2.stability import StabilityEngine


def source(sid: str = None, **kw) -> SourceConfig:
    return SourceConfig(source_id=sid or new_source_id(),
                        display_name=kw.pop("name", sid or "S"),
                        rect=(0, 0, 100, 20), **kw)


def ok_obs(sid: str, value: str, kind: str = "number",
           pixel: str = "h1") -> Observation:
    return Observation(source_id=sid, capture_status="OK",
                       ocr_status="OK", parse_status="OK",
                       stability_status="NOT_EVALUATED", value_status="OK",
                       normalized_value=value, value_kind=kind,
                       pixel_sha256=pixel, ocr_executed=True)


def err_obs(sid: str, value_status: str) -> Observation:
    return Observation(source_id=sid, capture_status="OK",
                       ocr_status="OK",
                       parse_status=value_status
                       if value_status in C.PARSE_STATUSES else "OK",
                       stability_status="NOT_EVALUATED",
                       value_status=value_status)


def engine(sources, mode=C.RETENTION_CHANGED_AND_ERRORS,
           confirmations=1, debounce=0, threshold=None) -> StabilityEngine:
    return StabilityEngine(sources, confirmations=confirmations,
                           debounce_ms=debounce,
                           min_change_threshold=threshold,
                           retention_mode=mode)


class FastModeTests(unittest.TestCase):
    def setUp(self):
        self.a = source(name="A")
        self.b = source(name="B")
        self.eng = engine([self.a, self.b])

    def tick(self, n, observations):
        return self.eng.process_tick(observations, f"f{n}", n * 1000.0, {})

    def test_seeding_is_not_a_change(self):
        decision = self.tick(1, {self.a.source_id: ok_obs(self.a.source_id, "1.0"),
                                 self.b.source_id: ok_obs(self.b.source_id, "2.0")})
        self.assertIsNone(decision.event_status)
        self.assertEqual(decision.stable_signature[self.a.source_id]
                         ["normalized_value"], "1.0")

    def test_change_after_seed_retains_once(self):
        self.tick(1, {self.a.source_id: ok_obs(self.a.source_id, "1.0"),
                      self.b.source_id: ok_obs(self.b.source_id, "2.0")})
        decision = self.tick(2, {self.a.source_id:
                                 ok_obs(self.a.source_id, "1.5"),
                                 self.b.source_id:
                                 ok_obs(self.b.source_id, "2.0")})
        self.assertEqual(decision.event_status, "RETAINED_CHANGE")
        self.assertEqual(decision.changed_source_ids, [self.a.source_id])
        decision3 = self.tick(3, {self.a.source_id:
                                  ok_obs(self.a.source_id, "1.5"),
                                  self.b.source_id:
                                  ok_obs(self.b.source_id, "2.0")})
        self.assertIsNone(decision3.event_status)

    def test_pending_source_never_appears_as_deletion(self):
        self.tick(1, {self.a.source_id: ok_obs(self.a.source_id, "1.0")})
        decision = self.tick(2, {self.a.source_id:
                                 ok_obs(self.a.source_id, "1.0"),
                                 self.b.source_id:
                                 err_obs(self.b.source_id,
                                         "MISSING_SOURCE_VALUE")})
        self.assertIsNone(decision.event_status)
        self.assertIn(self.a.source_id, decision.stable_signature)
        self.assertNotIn(self.b.source_id, decision.stable_signature)

    def test_error_transition_retains_once_and_repeat_does_not(self):
        self.tick(1, {self.a.source_id: ok_obs(self.a.source_id, "1.0")})
        decision = self.tick(2, {self.a.source_id:
                                 err_obs(self.a.source_id,
                                         "AMBIGUOUS_MULTIPLE_NUMBERS")})
        self.assertEqual(decision.event_status, "RETAINED_ERROR")
        repeat = self.tick(3, {self.a.source_id:
                               err_obs(self.a.source_id,
                                       "AMBIGUOUS_MULTIPLE_NUMBERS")})
        self.assertIsNone(repeat.event_status)

    def test_recovery_after_error_retains_even_same_value(self):
        self.tick(1, {self.a.source_id: ok_obs(self.a.source_id, "1.0")})
        self.tick(2, {self.a.source_id: err_obs(self.a.source_id,
                                                "OCR_FAILURE")})
        decision = self.tick(3, {self.a.source_id:
                                 ok_obs(self.a.source_id, "1.0")})
        self.assertEqual(decision.event_status, "RETAINED_CHANGE")
        self.assertIn("ERROR_RECOVERED", decision.retention_reason_codes)

    def test_missing_value_is_live_only(self):
        self.tick(1, {self.a.source_id: ok_obs(self.a.source_id, "1.0")})
        decision = self.tick(2, {self.a.source_id:
                                 err_obs(self.a.source_id,
                                         "MISSING_SOURCE_VALUE")})
        self.assertIsNone(decision.event_status)
        back = self.tick(3, {self.a.source_id:
                             ok_obs(self.a.source_id, "1.0")})
        self.assertIsNone(back.event_status)  # OK -> empty -> same OK: none

    def test_error_beats_change_in_same_tick(self):
        self.tick(1, {self.a.source_id: ok_obs(self.a.source_id, "1.0"),
                      self.b.source_id: ok_obs(self.b.source_id, "2.0")})
        decision = self.tick(2, {self.a.source_id:
                                 ok_obs(self.a.source_id, "9.9"),
                                 self.b.source_id:
                                 err_obs(self.b.source_id, "OUT_OF_RANGE")})
        self.assertEqual(decision.event_status, "RETAINED_ERROR")
        self.assertIn(self.a.source_id, decision.changed_source_ids)
        self.assertIn(self.b.source_id, decision.changed_source_ids)

    def test_min_change_threshold_suppresses_noise(self):
        a = source(name="T", min_change_threshold=0.5)
        eng = engine([a])
        eng.process_tick({a.source_id: ok_obs(a.source_id, "10.0")},
                         "f1", 0.0, {})
        small = eng.process_tick({a.source_id: ok_obs(a.source_id, "10.3")},
                                 "f2", 1000.0, {})
        self.assertIsNone(small.event_status)
        big = eng.process_tick({a.source_id: ok_obs(a.source_id, "10.9")},
                               "f3", 2000.0, {})
        self.assertEqual(big.event_status, "RETAINED_CHANGE")


class StabilizedModeTests(unittest.TestCase):
    def setUp(self):
        self.a = source(name="A")
        self.eng = engine([self.a], confirmations=2)

    def tick(self, n, value=None, obs=None, crops=None):
        observation = obs or ok_obs(self.a.source_id, value)
        return self.eng.process_tick({self.a.source_id: observation},
                                     f"f{n}", n * 1000.0, crops or {})

    def test_single_tick_flicker_suppressed(self):
        self.tick(1, "1.0")
        self.tick(2, "1.0")           # seeds after 2 confirmations
        flicker = self.tick(3, "9.9")
        self.assertIsNone(flicker.event_status)
        back = self.tick(4, "1.0")
        self.assertIsNone(back.event_status)
        again = self.tick(5, "1.0")
        self.assertIsNone(again.event_status)

    def test_confirmed_change_retains_with_first_candidate_evidence(self):
        self.tick(1, "1.0")
        self.tick(2, "1.0")
        crops = {self.a.source_id: b"PNG1"}
        first = self.eng.process_tick(
            {self.a.source_id: ok_obs(self.a.source_id, "2.0",
                                      pixel="h2")},
            "f3", 3000.0, crops)
        self.assertIsNone(first.event_status)
        confirm = self.eng.process_tick(
            {self.a.source_id: ok_obs(self.a.source_id, "2.0",
                                      pixel="h2")},
            "f4", 4000.0, {})
        self.assertEqual(confirm.event_status, "RETAINED_CHANGE")
        evidence = confirm.evidence[self.a.source_id]
        self.assertEqual(evidence["evidence_frame_id"], "f3")
        self.assertEqual(confirm.crops_to_save[self.a.source_id], b"PNG1")

    def test_evidence_buffer_cap_raises(self):
        big = b"x" * (C.CROP_PNG_MAX_BYTES + 1)
        with self.assertRaises(BufferError):
            self.eng.process_tick(
                {self.a.source_id: ok_obs(self.a.source_id, "3.0",
                                          pixel="h3")},
                "f9", 9000.0, {self.a.source_id: big})


class RetentionModeTests(unittest.TestCase):
    def setUp(self):
        self.a = source(name="A")

    def run_sequence(self, mode):
        eng = engine([self.a], mode=mode)
        outcomes = []
        outcomes.append(eng.process_tick(
            {self.a.source_id: ok_obs(self.a.source_id, "1.0")},
            "f1", 0.0, {}))
        outcomes.append(eng.process_tick(
            {self.a.source_id: err_obs(self.a.source_id, "OCR_FAILURE")},
            "f2", 1000.0, {}))
        outcomes.append(eng.process_tick(
            {self.a.source_id: ok_obs(self.a.source_id, "1.0")},
            "f3", 2000.0, {}))
        outcomes.append(eng.process_tick(
            {self.a.source_id: ok_obs(self.a.source_id, "1.0")},
            "f4", 3000.0, {}))
        return [d.event_status for d in outcomes]

    def test_changed_and_errors(self):
        self.assertEqual(self.run_sequence(C.RETENTION_CHANGED_AND_ERRORS),
                         [None, "RETAINED_ERROR", "RETAINED_CHANGE", None])

    def test_changed_only_suppresses_errors_and_same_value_recovery(self):
        self.assertEqual(self.run_sequence(C.RETENTION_CHANGED_ONLY),
                         [None, None, None, None])

    def test_every_tick_diagnostic(self):
        outcomes = self.run_sequence(C.RETENTION_EVERY_TICK)
        self.assertEqual(outcomes[0], "RETAINED_DIAGNOSTIC")
        self.assertEqual(outcomes[1], "RETAINED_ERROR")
        self.assertEqual(outcomes[2], "RETAINED_CHANGE")
        self.assertEqual(outcomes[3], "RETAINED_DIAGNOSTIC")

    def test_values_only_retains_events(self):
        self.assertEqual(self.run_sequence(C.RETENTION_VALUES_ONLY),
                         [None, "RETAINED_ERROR", "RETAINED_CHANGE", None])
