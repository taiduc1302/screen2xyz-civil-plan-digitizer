"""Deterministic scheduler tests (W1 / M2-FR-041 regression)."""

from __future__ import annotations

import threading
import time
import unittest

from screen2xyz_m2.scheduler import TickScheduler


class SchedulerTests(unittest.TestCase):
    def test_slow_tick_is_skipped_not_queued(self):
        ticks = {"count": 0}
        skips = {"count": 0}
        release = threading.Event()

        def on_tick():
            ticks["count"] += 1
            release.wait(timeout=5)   # hold the in-flight lock

        def on_skip():
            skips["count"] += 1

        scheduler = TickScheduler(50, on_tick=on_tick, on_skip=on_skip)
        scheduler.start()
        # While the first tick holds the in-flight lock, no other tick may run
        # (single outstanding). Every deadline that arrives during that window
        # is skipped, never queued into a later burst.
        time.sleep(0.35)   # ~6 deadlines pass while the first tick blocks
        self.assertEqual(ticks["count"], 1)
        self.assertGreaterEqual(skips["count"], 1)
        release.set()      # let the in-flight tick finish so stop() drains fast
        scheduler.stop()

    def test_stop_drains_in_flight_tick(self):
        entered = threading.Event()
        release = threading.Event()
        finished = {"done": False}

        def on_tick():
            entered.set()
            release.wait(timeout=5)
            finished["done"] = True

        scheduler = TickScheduler(20, on_tick=on_tick, on_skip=lambda: None)
        scheduler.start()
        self.assertTrue(entered.wait(timeout=2))  # a tick is in flight
        returned = {"stop": False}

        def stopper():
            scheduler.stop(drain_timeout=5.0)
            returned["stop"] = True

        thread = threading.Thread(target=stopper)
        thread.start()
        time.sleep(0.2)
        # stop() must block until the in-flight tick drains, so the caller
        # (controller.stop) never runs concurrently with a live capture.
        self.assertFalse(returned["stop"])
        self.assertFalse(finished["done"])
        release.set()
        thread.join(timeout=5)
        self.assertTrue(returned["stop"])
        self.assertTrue(finished["done"])

    def test_drain_waits_for_in_flight_tick_without_stopping_the_loop(self):
        """Independent audit MAJOR: user_pause()/user_resume() used to
        touch the controller/worker directly with no synchronization
        against a concurrently in-flight tick (which holds the worker's
        own request lock for the whole tick) - the loser's WorkerError
        made user_pause() tear the worker down out from under the still-
        running tick. drain() lets a caller wait out any in-flight tick
        WITHOUT stopping the scheduler loop itself (unlike stop()), so
        pause()+drain() can safely precede a direct controller call while
        still leaving the scheduler resumable."""

        entered = threading.Event()
        release = threading.Event()
        finished = {"done": False}
        call_count = {"n": 0}

        def on_tick():
            call_count["n"] += 1
            if call_count["n"] == 1:
                entered.set()
                release.wait(timeout=5)
                finished["done"] = True

        scheduler = TickScheduler(20, on_tick=on_tick, on_skip=lambda: None)
        scheduler.start()
        self.assertTrue(entered.wait(timeout=2))  # first tick is in flight
        scheduler.pause()  # stop future dispatch, mirroring _pause()'s order
        returned = {"drained": False}

        def drainer():
            scheduler.drain(timeout=5.0)
            returned["drained"] = True

        thread = threading.Thread(target=drainer)
        thread.start()
        time.sleep(0.2)
        # drain() must block until the in-flight tick finishes, exactly
        # like stop()'s drain step - a caller must never proceed while a
        # tick is still using the worker.
        self.assertFalse(returned["drained"])
        self.assertFalse(finished["done"])
        release.set()
        thread.join(timeout=5)
        self.assertTrue(returned["drained"])
        self.assertTrue(finished["done"])
        # Unlike stop(), the loop thread must still be alive and resumable.
        self.assertIsNotNone(scheduler._thread)
        scheduler.resume()
        time.sleep(0.1)
        self.assertGreaterEqual(call_count["n"], 2)  # a new tick fired
        scheduler.stop()

    def test_pause_resume_gate_ticks(self):
        ticks = {"count": 0}
        scheduler = TickScheduler(30, on_tick=lambda: ticks.__setitem__(
            "count", ticks["count"] + 1), on_skip=lambda: None)
        scheduler.start()
        time.sleep(0.15)
        scheduler.pause()
        # A tick dispatched just before pause may still be draining. A
        # fixed grace sleep here previously raced under CI scheduler
        # jitter: a stalled test thread could let genuinely more ticks
        # land inside that same guessed window (observed as a real CI
        # flake, "5 != 4", unrelated to any product code - the assertion
        # was timing-brittle). Wait for the count to actually go quiet
        # instead of guessing a duration, so the snapshot is never taken
        # mid-flight regardless of how slow the runner is.
        paused_count = self._wait_for_quiet(ticks, key="count")
        time.sleep(0.15)
        self.assertEqual(ticks["count"], paused_count)  # no ticks while paused
        scheduler.resume()
        time.sleep(0.15)
        scheduler.stop()
        self.assertGreater(ticks["count"], paused_count)

    @staticmethod
    def _wait_for_quiet(counter: dict, key: str, quiet_polls: int = 3,
                        poll_s: float = 0.02, max_wait_s: float = 2.0):
        """Poll `counter[key]` until it holds the same value for
        `quiet_polls` consecutive polls, then return that value. Used in
        place of a fixed grace sleep for tests observing a background
        thread's tick count - robust to CI scheduling jitter that a
        constant-duration sleep is not."""
        deadline = time.monotonic() + max_wait_s
        stable_since = counter[key]
        stable_count = 0
        while time.monotonic() < deadline:
            time.sleep(poll_s)
            current = counter[key]
            if current == stable_since:
                stable_count += 1
                if stable_count >= quiet_polls:
                    return current
            else:
                stable_since = current
                stable_count = 0
        return counter[key]
