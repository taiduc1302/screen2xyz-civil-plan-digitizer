"""Monotonic non-overlapping scheduler (single outstanding tick)."""

from __future__ import annotations

import threading
import time
from typing import Callable


class TickScheduler:
    """Fires `on_tick` at monotonic deadlines; skips, never queues."""

    def __init__(self, interval_ms: int,
                 on_tick: Callable[[], None],
                 on_skip: Callable[[], None],
                 monotonic: Callable[[], float] = time.monotonic) -> None:
        self.interval_ms = interval_ms
        self._on_tick = on_tick
        self._on_skip = on_skip
        self._monotonic = monotonic
        self._running = threading.Event()
        self._stopped = threading.Event()
        self._in_flight = threading.Lock()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._running.set()
        self._stopped.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def pause(self) -> None:
        self._running.clear()

    def resume(self) -> None:
        self._running.set()

    def drain(self, timeout: float = 2.0) -> bool:
        """Wait up to `timeout` s for a currently in-flight tick to finish,
        WITHOUT stopping the loop thread itself (unlike stop()). A no-op if
        nothing is in-flight. Returns True if drained (nothing was in
        flight, or it finished within `timeout`), False if a tick was
        still in flight when `timeout` elapsed.

        Independent audit MAJOR: user_pause()/user_resume() issue their own
        direct worker request (PAUSE/RESUME) from the Tk main thread. If a
        tick is concurrently mid-CAPTURE on its own thread (holding both
        _in_flight and the WorkerClient's internal request lock), the
        losing side's request fails with WorkerError("PROTOCOL_ERROR",
        "overlapping worker request refused"), and user_pause() reacts to
        that by tearing the worker down - out from under the tick that was
        still using it. stop()/emergency_stop() already avoid this by
        draining before touching the controller; pause()/resume() must do
        the same. Calling this BEFORE the controller call (not pause()/
        stop(), which also block future dispatch) is what makes the
        ordering safe - PROVIDED the caller actually honors a False
        return and does not fall through to the controller call anyway
        (a second independent audit caught exactly that gap: a hardcoded
        timeout here that outran the real worker round-trip budget, with
        the True/False outcome previously discarded by every caller)."""

        if self._in_flight.acquire(timeout=max(0.0, timeout)):
            self._in_flight.release()
            return True
        return False

    def stop(self, drain_timeout: float = 5.0) -> None:
        """Stop dispatching and wait up to `drain_timeout` s for an in-flight
        tick to finish, so the caller has exclusive access afterward. Ticks run
        on their own threads, so the loop-thread join is fast; the drain is the
        real wait. Pass a small timeout on the emergency path to stay bounded —
        the caller then kills the worker, unblocking any still-running tick."""
        self._stopped.set()
        self._running.clear()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        # Drain: acquire the in-flight lock the running tick holds, then release.
        if self._in_flight.acquire(timeout=max(0.0, drain_timeout)):
            self._in_flight.release()

    def _run_tick(self) -> None:
        try:
            self._on_tick()
        finally:
            self._in_flight.release()

    def _loop(self) -> None:
        interval = self.interval_ms / 1000.0
        deadline = self._monotonic() + interval
        while not self._stopped.is_set():
            now = self._monotonic()
            if now < deadline:
                time.sleep(min(deadline - now, 0.02))
                continue
            missed = 0
            while deadline <= self._monotonic():
                deadline += interval
                missed += 1
            if not self._running.is_set():
                continue
            # The tick runs on its own thread and holds _in_flight for its full
            # duration; a deadline that arrives while it is still running finds
            # the lock held and is skipped (never queued). Each coalesced
            # missed deadline beyond the one we serve is also a skip.
            if self._in_flight.acquire(blocking=False):
                threading.Thread(target=self._run_tick, daemon=True).start()
                for _ in range(missed - 1):
                    self._on_skip()
            else:
                for _ in range(missed):
                    self._on_skip()
