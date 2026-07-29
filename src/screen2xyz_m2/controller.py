"""Live-session controller: worker lifecycle policy, tick pipeline, pauses.

Owns the state machine, worker generations with the §0 failure counters and
0/1/5 s backoff, the cached-observation fill-forward, parsing/status
derivation, the stability engine, the journal, and every automatic-pause
threshold. The UI and the acceptance harness both drive this API; the
scheduler calls `tick()`.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import contracts as C
from .journal import DiskLimit, RunJournal, StorageFailure
from .models import (Observation, SessionDefaults, SourceConfig,
                     xyz_eligibility)
from .parsing import RawBound, parse_for_source
from .stability import StabilityEngine, TickDecision
from .statemachine import SessionStateMachine
from .paths import new_run_id, run_root
from .worker import WorkerClient, WorkerError, WorkerTimeout


@dataclass
class PauseState:
    reason: str
    detail: str = ""
    requires_repreview: bool = False
    requires_reresolve: bool = False


@dataclass
class TickResult:
    frame: dict[str, Any] | None
    observations: dict[str, Observation]
    decision: TickDecision | None
    event: dict[str, Any] | None
    pause: PauseState | None
    tick_ms: int
    skipped: bool = False


class LiveSessionController:
    def __init__(self, *, scope: dict[str, Any], backend: str,
                 sources: list[SourceConfig], defaults: SessionDefaults,
                 environment_snapshot: dict[str, Any],
                 session_id: str | None = None,
                 run_parent: Path | None = None,
                 worker_factory: Callable[..., WorkerClient] | None = None,
                 monotonic: Callable[[], float] = time.monotonic,
                 sleeper: Callable[[float], None] = time.sleep) -> None:
        from .models import validate_source_set
        # Defence in depth: no unvalidated source (incl. its filesystem-bound
        # source_id) can reach the journal even via a direct/tampered caller.
        # require_nonempty=False: Test capture / region_snapshot (Step 2) is
        # a full-frame probe that needs a target but no fields at all, and
        # Step 2 is deliberately usable before Step 3 "Add fields" - the
        # >=1-enabled-source bound is enforced later, at preview()/
        # confirm_preview_and_arm(), where a real field set actually matters.
        validate_source_set(sources, require_nonempty=False)
        self.machine = SessionStateMachine()
        self.scope = scope
        self.backend = backend
        self.sources = sources
        self.defaults = defaults
        self.environment_snapshot = environment_snapshot
        self.session_id = session_id or new_run_id()
        self._run_parent = run_parent or run_root()
        self._worker_factory = worker_factory or WorkerClient
        self._monotonic = monotonic
        self._sleep = sleeper
        self.worker: WorkerClient | None = None
        self.journal: RunJournal | None = None
        self.stability: StabilityEngine | None = None
        self.pause_state: PauseState | None = None
        self.setup_failures = 0
        self.recording_failures = 0
        self._recording_counter_initialized = False
        self._last_teardown_ms = 0.0
        self._minimized_streak = 0
        self._blank_streak = 0
        # A hard worker-reported frame capture failure (BACKEND_FAILURE,
        # REGION_OUT_OF_BOUNDS, PAYLOAD_TOO_LARGE - e.g. an oversize/spanned
        # window, or CopyFromScreen throwing on a locked desktop) arrives as
        # worker_status OK with a failed capture_status, so the WorkerError
        # failure-streak path never fires. Without this streak the session
        # would stay RECORDING and capture nothing forever (§18/§21).
        self._capture_fail_streak = 0
        self._offscreen_streak = 0
        self._last_ocr: dict[str, tuple[str, Observation]] = {}
        self._session_start_ms: float | None = None
        self.frame_seq = 0
        # The backend the CURRENTLY LIVE worker was actually spawned with
        # (independent audit BLOCKER): capture_worker_windows.ps1 latches
        # $script:Backend once at INIT and never re-reads it, so changing
        # the backend dropdown after a worker already exists silently did
        # nothing - ensure_worker()'s "reuse if alive" check never compared
        # the requested backend against what the live worker was actually
        # spawned with. Tracked separately from self.backend (the owner's
        # current *request*) so a mismatch forces a respawn.
        self._worker_backend: str | None = None
        # Requested backend may be 'auto'; effective_backend is whatever the
        # worker actually latched onto (None until the first successful
        # capture/probe). last_crop_bytes holds only the MOST RECENT crop PNG
        # per source (live thumbnails + diagnostic snapshot); it is never
        # accumulated into history and carries no extra retention meaning.
        self.effective_backend: str | None = None
        self.last_backend_probe: list[dict[str, Any]] | None = None
        self.last_crop_bytes: dict[str, bytes] = {}
        self.last_window_visibility: dict[str, Any] | None = None
        # skipped_since_last_event is incremented on the scheduler loop thread
        # (note_skipped_tick) while a tick runs on its own thread and resets it
        # on a retained event; guard the increment/read-reset with this lock so
        # a skip is never lost against a concurrent reset.
        self._skip_lock = threading.Lock()
        self.skipped_since_last_event = 0
        self.diagnostics: dict[str, Any] = {
            "worker_restarts": 0, "last_tick_ms": 0, "skipped_ticks": 0,
            "ocr_errors": 0, "capture_errors": 0, "export_errors": 0,
            "retained_events_attempted": 0,
            "last_capture_utc": None, "last_journal_write_utc": None,
            "last_live_csv_utc": None, "final_csv_utc": None}
        self.on_event: Callable[[dict[str, Any]], None] | None = None
        self.on_pause: Callable[[PauseState], None] | None = None

    # -- worker lifecycle policy -----------------------------------------

    def _request_timeout_ms(self) -> int:
        return max(2000, 2 * self.defaults.interval_ms)

    def drain_budget_s(self) -> float:
        """Upper bound, in seconds, that a single in-flight worker round
        trip may legitimately take. Callers that must wait one out before
        touching the controller (e.g. the UI's pause/resume handlers)
        should size their drain timeout from this, not a fixed constant -
        it scales with the user's configured interval the same way the
        worker's own request timeout does."""
        return self._request_timeout_ms() / 1000.0

    def _restore_state(self) -> str:
        state = self.machine.state
        if state in ("RECORDING", "PAUSED", "ARMED"):
            return state
        if state == "TARGET_SELECTED":
            return "TARGET_SELECTED"
        return "REGIONS_CONFIGURED"

    def _backoff_wait(self, failures: int) -> None:
        index = min(failures, len(C.RESTART_BACKOFF_MS) - 1)
        delay_ms = C.RESTART_BACKOFF_MS[index]
        elapsed = (self._monotonic() - self._last_teardown_ms) * 1000
        remaining = delay_ms - elapsed
        if remaining > 0:
            self._sleep(remaining / 1000.0)

    def _spawn_worker(self) -> None:
        self.worker = self._worker_factory(
            session_id=self.session_id, scope=self.scope,
            backend=self.backend,
            cursor_metadata=self.defaults.cursor_metadata)
        self.worker.start(
            restore_session_state=self._restore_state(),
            configuration_revision=self.machine.configuration_revision)
        self._worker_backend = self.backend

    def _teardown_worker(self) -> None:
        if self.worker is not None:
            self.worker.teardown()
            self.worker = None
        self._last_teardown_ms = self._monotonic()
        self.diagnostics["worker_restarts"] += 1

    def ensure_worker(self) -> None:
        """Setup-context spawn with the setup counter and interlock."""

        if self.worker is not None and self.worker.alive:
            if self._worker_backend == self.backend:
                return
            # The owner changed the backend dropdown since this worker was
            # spawned; the PowerShell worker latches its backend once at
            # INIT and never re-reads it, so reusing this worker would
            # silently keep using the OLD backend forever while the UI's
            # own explanatory text claims the new one is in effect. Force
            # a clean respawn so a backend change actually takes effect on
            # the very next Test capture/Preview.
            self._teardown_worker()
        if self.machine.setup_worker_blocked:
            raise WorkerError("UNAVAILABLE", "setup worker blocked")
        while True:
            try:
                self._backoff_wait(self.setup_failures)
                self._spawn_worker()
                return
            except WorkerError:
                self._teardown_worker()
                self.setup_failures += 1
                if self.setup_failures >= C.FAILURE_STREAK_LIMIT:
                    self.machine.setup_worker_blocked = True
                    raise WorkerError("UNAVAILABLE",
                                      "three consecutive setup failures")

    def retry_worker(self) -> None:
        """Explicit Retry after the setup interlock: INIT only."""

        self.machine.require("retry_worker")
        self._backoff_wait(self.setup_failures)
        try:
            self._spawn_worker()
        except WorkerError:
            self._teardown_worker()
            self.setup_failures += 1
            raise
        self.machine.setup_worker_blocked = False
        # counter resets only on the next successful setup/state request

    def _setup_request(self, command: str, payload: dict[str, Any],
                       timeout_ms: int | None = None) -> dict[str, Any]:
        self.ensure_worker()
        assert self.worker is not None
        try:
            reply = self.worker.request(
                command, payload,
                timeout_ms=timeout_ms or self._request_timeout_ms(),
                ui_session_state=self.machine.state,
                configuration_revision=self.machine.configuration_revision)
        except WorkerError:
            self._teardown_worker()
            self.setup_failures += 1
            if self.setup_failures >= C.FAILURE_STREAK_LIMIT:
                self.machine.setup_worker_blocked = True
            raise
        if reply.get("worker_status") != "OK":
            raise WorkerError(str(reply.get("worker_status")),
                              str(reply.get("error", "")))
        self.setup_failures = 0
        return reply

    # -- setup operations --------------------------------------------------

    def region_snapshot(self, probe_backend: bool = False) -> dict[str, Any]:
        self.machine.require("region_snapshot")
        reply = self._setup_request(
            "REGION_SNAPSHOT", {"probe_backend": probe_backend},
            timeout_ms=(C.BACKEND_PROBE_TIMEOUT_MS if probe_backend
                       else None))
        self._note_backend_reply(reply)
        return reply

    def test_capture(self) -> dict[str, Any]:
        """Explicit 'Test capture now' / 'Retest': forces a fresh Auto
        resolution (or a direct check of an explicit backend) and returns a
        full-frame classification the UI can render as PASS/WARNING/FAIL."""
        return self.region_snapshot(probe_backend=True)

    def _parsed_region_preview(self, source: SourceConfig,
                               raw: dict[str, Any]) -> dict[str, Any]:
        """Shared crop+OCR+parse enrichment for a single observation, used
        by both the full Step-4 preview and the picker's one-shot preview -
        so the setup table's retained preview always reflects a real parse,
        never a fabricated placeholder."""

        if raw.get("ocr_status") in ("OK", "EMPTY_TEXT"):
            bound = RawBound(raw.get("raw_text", "") or "",
                             bool(raw.get("raw_truncated")),
                             raw.get("raw_original_utf8_bytes"))
            outcome = parse_for_source(
                bound, source.data_type,
                separator_mode=source.decimal_separator,
                numeric_range=source.numeric_range,
                precision_max=source.decimal_precision_max,
                line_part=source.line_part)
            parse_status = outcome.parse_status
            normalized_value = outcome.normalized_value
        else:
            parse_status = "NOT_RUN"
            normalized_value = None
        if raw.get("ocr_status") == "EMPTY_TEXT":
            parse_status = "NOT_RUN"
            normalized_value = None
        return {**raw, "parse_status": parse_status,
               "normalized_value": normalized_value}

    def preview(self) -> dict[str, Any]:
        self.machine.require("preview")
        # Defence in depth: a real field set is required from here on (the
        # UI's own _preview() already checks this before it ever reaches a
        # controller, but a direct caller - a script, the scenario runner,
        # a future non-UI entry point - must never be able to preview or
        # arm zero fields just because construction-time validation was
        # relaxed to let Step 2 work before Step 3).
        from .models import validate_source_set
        validate_source_set(self.sources)
        enabled = [source for source in self.sources if source.enabled]
        payload = {"regions": [self._region_payload(source, preview=True)
                               for source in enabled],
                   "frame_seq": 0}
        reply = self._setup_request("PREVIEW", payload)
        self._note_backend_reply(reply)
        by_id = {source.source_id: source for source in enabled}
        parsed_observations = []
        for raw_obs in reply.get("observations", []):
            b64 = raw_obs.get("crop_png_b64")
            if b64:
                import base64
                self.last_crop_bytes[raw_obs["source_id"]] = \
                    base64.b64decode(b64)
            source = by_id.get(raw_obs.get("source_id"))
            parsed_observations.append(
                self._parsed_region_preview(source, raw_obs)
                if source is not None else raw_obs)
        return {**reply, "observations": parsed_observations}

    def preview_single_region(self, source: SourceConfig) -> dict[str, Any]:
        """One-shot crop+OCR+parse preview for exactly one field's region -
        used by the region-selection picker to show a live readout right
        after a drag, without needing a full multi-field preview first.
        Never mutates self.sources or the stability engine; `source` may be
        a temporary, not-yet-confirmed copy."""

        self.machine.require("preview")
        payload = {"regions": [self._region_payload(source, preview=True)],
                  "frame_seq": 0}
        reply = self._setup_request("PREVIEW", payload)
        self._note_backend_reply(reply)
        obs_list = reply.get("observations") or []
        region_preview = (self._parsed_region_preview(source, obs_list[0])
                          if obs_list else None)
        return {**reply, "region_preview": region_preview}

    def _note_backend_reply(self, reply: dict[str, Any]) -> None:
        effective = reply.get("effective_backend")
        if effective:
            self.effective_backend = effective
        probe = reply.get("backend_probe")
        if probe is not None:
            self.last_backend_probe = probe

    def confirm_preview_and_arm(self) -> None:
        self.machine.require("confirm_preview")
        # Defence in depth (see preview()): never arm on zero fields.
        from .models import validate_source_set
        validate_source_set(self.sources)
        self._setup_request("ARM", {})
        self.machine.confirm_preview()

    def start_recording(self) -> None:
        self.machine.require("start_recording")
        self._setup_request("RECORD_START", {})
        self.machine.start_recording()
        if not self._recording_counter_initialized:
            self.recording_failures = 0
            self._recording_counter_initialized = True
        if self.journal is None:
            self.journal = RunJournal(self._run_parent / self.session_id)
            self.journal.write_session(self.session_json())
        if self.stability is None:
            self.stability = StabilityEngine(
                self.sources,
                confirmations=self.defaults.confirmations,
                debounce_ms=self.defaults.debounce_ms,
                min_change_threshold=self.defaults.min_change_threshold,
                retention_mode=self.defaults.retention_mode)
        if self._session_start_ms is None:
            self._session_start_ms = self._monotonic()
        self.pause_state = None

    def session_json(self) -> dict[str, Any]:
        return {
            "schema_version": C.SCHEMA_VERSION,
            "session_id": self.session_id,
            "scope": {key: value for key, value in self.scope.items()
                      if key != "title"} | {
                "title_recorded": bool(self.scope.get("title"))},
            "locked_backend": {
                # "name" is kept for exports.py's summary (the backend that
                # actually captured the session); requested/effective make
                # the Auto resolution explicit for anything reading the
                # full session record.
                "name": self.effective_backend or self.backend,
                "requested": self.backend,
                "effective": self.effective_backend,
                "reason": ("auto: resolved from a real capture+classify "
                          "probe, falls back to CopyFromScreen when "
                          "PrintWindow is unusable"
                          if self.backend == C.BACKEND_AUTO else
                          "explicit owner choice")},
            "interval_ms": self.defaults.interval_ms,
            "retention_mode": self.defaults.retention_mode,
            "stability_defaults": {
                "confirmations": self.defaults.confirmations,
                "debounce_ms": self.defaults.debounce_ms,
                "min_change_threshold": self.defaults.min_change_threshold},
            "cursor_metadata": self.defaults.cursor_metadata,
            "sources": [source.to_json() for source in self.sources],
            "environment_snapshot": self.environment_snapshot,
            "configuration_revision": self.machine.configuration_revision,
            "xyz_eligibility": xyz_eligibility(self.sources),
        }

    def _region_payload(self, source: SourceConfig,
                        preview: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source_id": source.source_id,
            "rect": {"x": source.rect[0], "y": source.rect[1],
                     "w": source.rect[2], "h": source.rect[3]},
            "upscale": source.upscale_factor,
        }
        if not preview:
            prior = self._last_ocr.get(source.source_id)
            payload["prev_pixel_sha256"] = prior[0] if prior else None
        return payload

    # -- recording tick ----------------------------------------------------

    def tick(self) -> TickResult:
        if self.machine.state != "RECORDING":
            return TickResult(None, {}, None, None, self.pause_state, 0,
                              skipped=True)
        started = self._monotonic()
        self.frame_seq += 1
        if self.journal:
            self.journal.frame_seq = self.frame_seq
            self.journal.counters["ticks"] += 1
        payload = {"frame_seq": self.frame_seq,
                   "regions": [self._region_payload(source)
                               for source in self.sources if source.enabled]}
        try:
            assert self.worker is not None
            reply = self.worker.request(
                "CAPTURE", payload,
                timeout_ms=self._request_timeout_ms(),
                ui_session_state="RECORDING",
                configuration_revision=self.machine.configuration_revision)
        except WorkerError as exc:
            return self._recording_failure(exc, started)
        if reply.get("worker_status") != "OK":
            return self._recording_failure(
                WorkerError(str(reply.get("worker_status")),
                            str(reply.get("error", ""))), started)
        self.recording_failures = 0
        return self._process_reply(reply, started)

    def _recording_failure(self, exc: WorkerError,
                           started: float) -> TickResult:
        self.recording_failures += 1
        self.diagnostics["capture_errors"] += 1
        self._teardown_worker()
        # A transient capture/OCR failure discards any pending candidate
        # bundle (contracts §6b) even when it does not escalate to a pause.
        if self.stability is not None:
            self.stability.discard_all_candidates()
        observations = self._all_failure_observations("BACKEND_FAILURE",
                                                      exc.worker_status)
        event = self._journal_failure_event(exc, observations)
        pause: PauseState | None = None
        if self.recording_failures >= C.FAILURE_STREAK_LIMIT:
            pause = PauseState("WORKER_FAILURE_STREAK", exc.detail)
            self._enter_pause(pause)
        else:
            try:
                self._backoff_wait(self.recording_failures - 1)
                self._spawn_worker()
            except WorkerError:
                # start() tears itself down on failure, but ensure no
                # half-initialized worker is left referenced.
                self._teardown_worker()
                self.recording_failures += 1
                pause = PauseState("WORKER_FAILURE_STREAK",
                                   "restart INIT failed")
                self._enter_pause(pause)
        tick_ms = int((self._monotonic() - started) * 1000)
        self.diagnostics["last_tick_ms"] = tick_ms
        return TickResult(None, observations, None, event, pause, tick_ms)

    def _all_failure_observations(
            self, capture_status: str,
            worker_status: str) -> dict[str, Observation]:
        observations: dict[str, Observation] = {}
        for source in self.sources:
            if not source.enabled:
                continue
            obs = Observation(source_id=source.source_id,
                              capture_status=capture_status,
                              ocr_status="NOT_RUN_CAPTURE_FAILED",
                              parse_status="NOT_RUN",
                              stability_status="NOT_EVALUATED")
            obs.value_status = C.derive_value_status(
                obs.capture_status, obs.ocr_status, obs.parse_status,
                obs.stability_status, worker_status=worker_status)
            observations[source.source_id] = obs
        return observations

    def _journal_failure_event(
            self, exc: WorkerError,
            observations: dict[str, Observation]) -> dict[str, Any] | None:
        if self.journal is None or self.stability is None:
            return None
        transitions = []
        for sid, obs in observations.items():
            if self.stability.stable_status_of(sid) != obs.value_status:
                transitions.append(sid)
        if not transitions or self.defaults.retention_mode == \
                C.RETENTION_CHANGED_ONLY:
            return None
        self.diagnostics["retained_events_attempted"] += 1
        # Snapshot before advancing the error transition so a failed durable
        # write rolls it back and the error event is re-detected next tick
        # (§9). The skip count is peeked, not consumed, until the write
        # succeeds (§24).
        stability_snapshot = self.stability.snapshot_state()
        for sid in transitions:
            state = self.stability._state[sid]
            state.stable_status = observations[sid].value_status
            state.retained_error_active = True
        skipped = self._peek_skipped_since_last()
        event = {
            "session_id": self.session_id,
            "event_status": "RETAINED_ERROR",
            "worker_status": exc.worker_status,
            "frame": None,
            "scheduler_context": {
                "monotonic_offset_ms": self._offset_ms(),
                "worker_status": exc.worker_status,
                "reason": exc.detail[:200]},
            "observations": [obs.to_json()
                             for obs in observations.values()],
            "stable_signature": self.stability.signature(),
            "changed_source_ids": sorted(transitions),
            "retention_reason_codes": ["ERROR_TRANSITION"],
            "evidence": {},
            "skipped_ticks_since_last": skipped,
        }
        try:
            written = self.journal.append_event(
                event, {}, self.defaults.retention_mode)
        except StorageFailure as failure:
            self.stability.restore_state(stability_snapshot)
            self._storage_pause(failure)
            return None
        self._consume_skipped_since_last(skipped)
        written = self._after_journal_write(written)
        if self.on_event:
            self.on_event(written)
        return written

    def _after_journal_write(self, written: dict[str, Any]) -> dict[str, Any]:
        """§2 truthful persistence: journal success is already final by the
        time this runs (append_event fsynced it); this only regenerates the
        best-effort live CSV snapshot and records its own success/failure
        separately, so a snapshot failure can never be mis-shown as a lost
        or unpersisted event."""

        from datetime import datetime, timezone
        assert self.journal is not None
        self.diagnostics["last_journal_write_utc"] = \
            datetime.now(timezone.utc).isoformat()
        # Incremental O(1) append of just this event's rows (§10) - not an
        # O(n) full regeneration of the whole file every event, which was
        # O(n^2) over a session and blew the tick budget on long/high-rate
        # runs. finalize() still regenerates the authoritative CSV from the
        # canonical journal.
        snapshot = self.journal.append_live_row(
            written, self.sources, self.defaults.cursor_metadata)
        if snapshot["ok"]:
            self.diagnostics["last_live_csv_utc"] = \
                self.journal.last_live_snapshot_utc
        else:
            self.diagnostics["export_errors"] += 1
            self.journal.log_error(
                f"live CSV snapshot write failed: {snapshot['error']}")
        return {**written, "live_csv_snapshot": snapshot}

    def _offset_ms(self) -> int:
        if self._session_start_ms is None:
            return 0
        return int((self._monotonic() - self._session_start_ms) * 1000)

    def _process_reply(self, reply: dict[str, Any],
                       started: float) -> TickResult:
        window = reply.get("window") or {}
        frame_capture_status = reply.get("capture_status", "OK")
        frame_id = f"{self.session_id}-f{self.frame_seq}"
        self._note_backend_reply(reply)
        frame = {
            "frame_id": frame_id,
            "frame_seq": self.frame_seq,
            "capture_utc": reply.get("capture_utc", ""),
            "monotonic_offset_ms": self._offset_ms(),
            "window": window,
            "capture_status": frame_capture_status,
            "frame_content_status": reply.get("frame_content_status",
                                              "NOT_EVALUATED"),
            "cursor": reply.get("cursor"),
            "effective_backend": self.effective_backend,
            "timings": {**(reply.get("timings") or {}),
                        "tick_ms": 0},
        }

        pause: PauseState | None = None
        if frame_capture_status == "TARGET_UNAVAILABLE":
            pause = PauseState("TARGET_UNAVAILABLE", requires_reresolve=True)
            self.diagnostics["capture_errors"] += 1
        elif frame_capture_status == "TARGET_MINIMIZED":
            self._minimized_streak += 1
            self.diagnostics["capture_errors"] += 1
            if self._minimized_streak >= C.PAUSE_MINIMIZED_TICKS:
                pause = PauseState("TARGET_MINIMIZED_STREAK")
        else:
            self._minimized_streak = 0
        if frame_capture_status == "OK":
            from datetime import datetime, timezone
            self.diagnostics["last_capture_utc"] = \
                datetime.now(timezone.utc).isoformat()
            expected_w = (self.environment_snapshot.get("window") or {}) \
                .get("client_w")
            expected_h = (self.environment_snapshot.get("window") or {}) \
                .get("client_h")
            if expected_w and (window.get("client_w") != expected_w
                               or window.get("client_h") != expected_h):
                pause = PauseState("DISPLAY_INVALIDATED",
                                   "client size changed",
                                   requires_repreview=True)
            elif (self.environment_snapshot.get("window") or {}).get("dpi") \
                    and window.get("dpi") != \
                    (self.environment_snapshot.get("window") or {}) \
                    .get("dpi"):
                pause = PauseState("DISPLAY_INVALIDATED", "DPI changed",
                                   requires_repreview=True)
            if reply.get("frame_content_status", "") \
                    .startswith("NEAR_UNIFORM") and window.get("exists"):
                self._blank_streak += 1
                if self._blank_streak >= C.PAUSE_BLANK_FRAME_TICKS \
                        and pause is None:
                    pause = PauseState("BACKEND_BLANK_STREAK")
            else:
                self._blank_streak = 0
            self._capture_fail_streak = 0
            # §8: under CopyFromScreen a window dragged partly off the
            # virtual screen silently reads black/adjacent-monitor pixels for
            # the off-screen part, and neither the size/DPI check above nor
            # occlusion detection catches a pure move. Recompute containment
            # each tick from the live origin the worker reports and pause on
            # a streak so those regions never masquerade as good readings.
            if pause is None and self.effective_backend == \
                    C.BACKEND_COPYFROMSCREEN and self.scope.get("type") == \
                    "window" and window.get("origin_x") is not None:
                from .targets import window_visibility
                vis = window_visibility(
                    window.get("client_w", 0), window.get("client_h", 0),
                    window.get("origin_x", 0), window.get("origin_y", 0),
                    self.environment_snapshot.get("virtual_screen") or {})
                self.last_window_visibility = vis
                if not vis["fully_visible"]:
                    self._offscreen_streak += 1
                    if self._offscreen_streak >= C.PAUSE_BLANK_FRAME_TICKS:
                        pause = PauseState("DISPLAY_INVALIDATED",
                                          "window moved partly off-screen",
                                          requires_repreview=True)
                else:
                    self._offscreen_streak = 0
        elif frame_capture_status not in ("TARGET_UNAVAILABLE",
                                          "TARGET_MINIMIZED"):
            # REGION_OUT_OF_BOUNDS / BACKEND_FAILURE / PAYLOAD_TOO_LARGE /
            # DISPLAY_INVALIDATED reported directly by the worker: a hard
            # capture failure. Escalate to a pause on a streak so a session
            # that can no longer capture (oversize window, locked desktop,
            # GDI failure) stops loudly instead of silently recording nothing
            # forever (§18/§21).
            self.diagnostics["capture_errors"] += 1
            self._capture_fail_streak += 1
            if self._capture_fail_streak >= C.PAUSE_BLANK_FRAME_TICKS \
                    and pause is None:
                pause = PauseState("BACKEND_BLANK_STREAK",
                                  f"capture failed: {frame_capture_status}")

        observations = self._build_observations(reply, frame_id)
        decision: TickDecision | None = None
        event: dict[str, Any] | None = None
        # §20: a DISPLAY_INVALIDATED frame (client size/DPI changed this
        # tick) has region rects indexed against the OLD geometry, so its
        # observations may read shifted/wrong pixels. Do not run stability or
        # journal a RETAINED_CHANGE for it - drop this frame's candidates and
        # pause instead, exactly like a capture failure.
        display_invalidated = pause is not None and \
            pause.reason == "DISPLAY_INVALIDATED"
        if display_invalidated and self.stability is not None:
            self.stability.discard_all_candidates()
        if self.stability is not None and not display_invalidated:
            crop_bytes = self._crop_bytes(reply)
            if crop_bytes:
                self.last_crop_bytes.update(crop_bytes)
            # Snapshot the committed stability state BEFORE process_tick so a
            # journal-write failure can roll the in-memory transition back
            # (§9): the change is then re-detected and re-journaled on the
            # next tick instead of being silently lost past the source of
            # truth.
            stability_snapshot = self.stability.snapshot_state()
            try:
                decision = self.stability.process_tick(
                    observations, frame_id, self._monotonic() * 1000,
                    crop_bytes)
            except BufferError:
                pause = PauseState("EVIDENCE_BUFFER_LIMIT")
                decision = None
                self.stability.restore_state(stability_snapshot)
            if decision and decision.event_status and self.journal:
                self.diagnostics["retained_events_attempted"] += 1
                event = self._write_event(frame, observations, decision)
                if event is None:
                    # The durable journal append failed (a storage pause was
                    # entered). Roll back the committed stable transition so
                    # it is re-detected and re-journaled after resume.
                    self.stability.restore_state(stability_snapshot)
        tick_ms = int((self._monotonic() - started) * 1000)
        frame["timings"]["tick_ms"] = tick_ms
        self.diagnostics["last_tick_ms"] = tick_ms
        self.diagnostics["ocr_errors"] += sum(
            1 for obs in observations.values()
            if obs.ocr_status == "ENGINE_FAILURE")
        if self.journal:
            self.journal.counters["ocr_errors"] = \
                self.diagnostics["ocr_errors"]
            _, warn, stop = self.journal.disk_status()
            if stop and pause is None:
                # Independent audit finding (adjacent to the DiskLimit-
                # exception fix in _write_event): this proactive per-tick
                # check paused directly with no journal.log_error call,
                # unlike every exception-driven storage-failure pause -
                # a session hitting the disk limit this way left no
                # errors.log trace of why it stopped.
                self.journal.log_error(
                    "DISK_LIMIT: disk usage reached the hard stop "
                    "threshold (proactive per-tick check)")
                pause = PauseState("DISK_LIMIT")
        if pause is not None:
            self._enter_pause(pause)
        return TickResult(frame, observations, decision, event, pause,
                          tick_ms)

    def _build_observations(self, reply: dict[str, Any],
                            frame_id: str) -> dict[str, Observation]:
        observations: dict[str, Observation] = {}
        config = {source.source_id: source for source in self.sources
                  if source.enabled}
        for raw_obs in reply.get("observations", []):
            sid = raw_obs.get("source_id")
            source = config.get(sid)
            if source is None:
                continue
            obs = Observation(
                source_id=sid,
                capture_status=raw_obs.get("capture_status", "OK"),
                crop_content_status=raw_obs.get("crop_content_status",
                                                "NOT_EVALUATED"),
                ocr_status=raw_obs.get("ocr_status",
                                       "NOT_RUN_CAPTURE_FAILED"),
                raw_text=raw_obs.get("raw_text", "") or "",
                raw_truncated=bool(raw_obs.get("raw_truncated")),
                raw_original_utf8_bytes=raw_obs.get(
                    "raw_original_utf8_bytes"),
                warning_codes=tuple(raw_obs.get("warning_codes") or ()),
                pixel_sha256=raw_obs.get("pixel_sha256"),
                crop_w=int(raw_obs.get("crop_w") or 0),
                crop_h=int(raw_obs.get("crop_h") or 0),
                ocr_executed=bool(raw_obs.get("ocr_executed")),
                confirmation=raw_obs.get("confirmation", "new_ocr"),
                ocr_ms=int(raw_obs.get("ocr_ms") or 0),
            )
            if obs.confirmation == "pixel_hash_cached":
                prior = self._last_ocr.get(sid)
                if prior and prior[0] == obs.pixel_sha256:
                    cached_from = prior[1]
                    obs.raw_text = ""
                    obs.parse_status = cached_from.parse_status
                    obs.normalized_value = cached_from.normalized_value
                    obs.value_kind = cached_from.value_kind
                    obs.ocr_ref = cached_from.ocr_ref
                    obs.value_status = cached_from.value_status
                    obs.stability_status = "CONFIRMED"
                    # Adversarial review finding (2026-07-21): every other
                    # parse-derived field above is copied from the fresh
                    # observation this pixel hash was first confirmed
                    # against - warning_codes was the one silent exception,
                    # so a DEGREE_GLYPH_RECOVERED-labelled value (or any
                    # other warned value) journaled as a bare, unlabelled
                    # OK on every subsequent cached tick. Copied for the
                    # same reason every sibling field already is.
                    obs.warning_codes = cached_from.warning_codes
                    observations[sid] = obs
                    continue
                obs.ocr_status = "NOT_RUN_CAPTURE_FAILED"
                obs.parse_status = "NOT_RUN"
            elif obs.ocr_status in ("OK", "EMPTY_TEXT"):
                bound = RawBound(obs.raw_text, obs.raw_truncated,
                                 obs.raw_original_utf8_bytes)
                outcome = parse_for_source(
                    bound, source.data_type,
                    separator_mode=source.decimal_separator,
                    numeric_range=source.numeric_range,
                    precision_max=source.decimal_precision_max,
                    line_part=source.line_part)
                obs.parse_status = outcome.parse_status
                obs.normalized_value = outcome.normalized_value
                obs.value_kind = outcome.value_kind
                obs.sign_normalized = outcome.sign_normalized
                obs.warning_codes = tuple(set(obs.warning_codes)
                                          | set(outcome.warning_codes))
                if obs.ocr_status == "EMPTY_TEXT":
                    obs.parse_status = "NOT_RUN"
                    obs.normalized_value = None
                obs.ocr_ref = frame_id
                self._last_ocr[sid] = (obs.pixel_sha256 or "", obs)
            else:
                obs.parse_status = "NOT_RUN"
            obs.value_status = C.derive_value_status(
                obs.capture_status, obs.ocr_status, obs.parse_status,
                obs.stability_status)
            observations[sid] = obs
        return observations

    def _crop_bytes(self, reply: dict[str, Any]) -> dict[str, bytes]:
        import base64
        crops: dict[str, bytes] = {}
        for raw_obs in reply.get("observations", []):
            b64 = raw_obs.get("crop_png_b64")
            if b64:
                crops[raw_obs["source_id"]] = base64.b64decode(b64)
        return crops

    def _write_event(self, frame: dict[str, Any],
                     observations: dict[str, Observation],
                     decision: TickDecision) -> dict[str, Any] | None:
        assert self.journal is not None
        event = {
            "session_id": self.session_id,
            "event_status": decision.event_status,
            "worker_status": "OK",
            "frame": frame,
            "scheduler_context": None,
            "observations": [obs.to_json()
                             for obs in observations.values()],
            "stable_signature": decision.stable_signature,
            "changed_source_ids": decision.changed_source_ids,
            "retention_reason_codes": decision.retention_reason_codes,
            "evidence": decision.evidence,
            "skipped_ticks_since_last": self._peek_skipped_since_last(),
        }
        try:
            written = self.journal.append_event(
                event, decision.crops_to_save, self.defaults.retention_mode)
        except DiskLimit as failure:
            # Independent audit MINOR: DiskLimit is a StorageFailure
            # subclass but was caught by its own more-specific branch,
            # which paused directly without the journal.log_error(...)
            # call _storage_pause makes for every other storage failure -
            # DiskLimit is a valid StorageFailure so this is a safe,
            # drop-in fix, not a behavior change to the pause itself.
            self._storage_pause(failure)
            return None
        except StorageFailure as failure:
            self._storage_pause(failure)
            return None
        self._consume_skipped_since_last(event["skipped_ticks_since_last"])
        written = self._after_journal_write(written)
        if self.on_event:
            self.on_event(written)
        return written

    def _storage_pause(self, failure: StorageFailure) -> None:
        pause = PauseState(failure.reason, str(failure))
        if self.journal:
            self.journal.log_error(str(failure))
        self._enter_pause(pause)

    def _enter_pause(self, pause: PauseState) -> None:
        if self.machine.state == "RECORDING":
            self.machine.pause()
        self.pause_state = pause
        if self.stability:
            self.stability.discard_all_candidates()
        if self.on_pause:
            self.on_pause(pause)

    # -- user actions ------------------------------------------------------

    def note_skipped_tick(self) -> None:
        with self._skip_lock:
            self.skipped_since_last_event += 1
        self.diagnostics["skipped_ticks"] += 1
        if self.journal:
            self.journal.counters["skipped"] += 1

    def _peek_skipped_since_last(self) -> int:
        """Read the skip counter WITHOUT resetting it (§24). The value is
        embedded in the event dict, but the counter is only decremented via
        _consume_skipped_since_last after the event durably journals - so a
        failed append never discards the accumulated skip count (which would
        make the next journaled event under-report skipped ticks and break
        the tick<->event correspondence)."""
        with self._skip_lock:
            return self.skipped_since_last_event

    def _consume_skipped_since_last(self, count: int) -> None:
        """Subtract the exact count that was durably journaled (not reset to
        0), preserving any ticks skipped between the peek and the write."""
        with self._skip_lock:
            self.skipped_since_last_event = max(
                0, self.skipped_since_last_event - count)

    def user_pause(self) -> None:
        self.machine.require("pause")
        try:
            assert self.worker is not None
            self.worker.request("PAUSE", {},
                                timeout_ms=self._request_timeout_ms(),
                                ui_session_state="RECORDING",
                                configuration_revision=
                                self.machine.configuration_revision)
        except WorkerError:
            self.recording_failures += 1
            self._teardown_worker()
        self.machine.pause()
        self.pause_state = PauseState("USER_REQUEST")

    def user_resume(self) -> None:
        self.machine.require("resume")
        pause = self.pause_state
        if pause and (pause.requires_repreview or pause.requires_reresolve):
            raise WorkerError("PROTOCOL_ERROR",
                              "this pause requires reconfiguration")
        if self.worker is None or not self.worker.alive:
            self._backoff_wait(self.recording_failures)
            try:
                self._spawn_worker()
            except WorkerError:
                self._teardown_worker()
                self.recording_failures += 1
                raise
        try:
            self.worker.request("RESUME", {},
                                timeout_ms=self._request_timeout_ms(),
                                ui_session_state="PAUSED",
                                configuration_revision=
                                self.machine.configuration_revision)
        except WorkerError:
            self.recording_failures += 1
            self._teardown_worker()
            raise
        self.machine.resume()
        self.pause_state = None

    def stop(self) -> dict[str, Any]:
        self.machine.require("stop")
        recording = self.machine.state in ("RECORDING", "PAUSED")
        if self.worker is not None and self.worker.alive and recording:
            try:
                self.worker.request("STOP", {},
                                    timeout_ms=C.GRACEFUL_SHUTDOWN_MS,
                                    ui_session_state=self.machine.state,
                                    configuration_revision=
                                    self.machine.configuration_revision)
            except WorkerError:
                pass
        self.machine.stop()
        if self.worker is not None:
            self.worker.graceful_shutdown(
                self.machine.state, self.machine.configuration_revision)
            self.worker = None
        return self.finalize() if recording else {}

    def emergency_stop(self) -> dict[str, Any]:
        self.machine.require("emergency_stop")
        recording = self.machine.state in ("RECORDING", "PAUSED")
        # Hard ≤2 s bound (contracts §0): kill within the emergency budget,
        # abandoning reader joins rather than blocking past it.
        budget = C.EMERGENCY_STOP_MS / 1000.0
        if recording:
            self.machine.stop()
        else:
            self.machine.reconfigure()
            if self.worker:
                self.worker.teardown(deadline_s=budget)
                self.worker = None
            return {}
        if self.worker is not None:
            self.worker.teardown(deadline_s=budget)
            self.worker = None
        return self.finalize() if recording else {}

    def finalize(self) -> dict[str, Any]:
        from .exports import finalize_exports
        from .journal import read_journal, verify_crops
        if self.journal is None:
            self.machine.finalized()
            return {}
        self.journal.maybe_checkpoint(
            self.stability.signature() if self.stability else {}, force=True)
        events, warnings = read_journal(self.journal.run_dir)
        warnings += verify_crops(self.journal.run_dir, events)
        counters = {**self.journal.counters,
                    "disk_bytes": self.journal.disk_bytes}
        summary = finalize_exports(
            self.journal.run_dir, self.session_json(), events, self.sources,
            counters, recovered=False, warnings=sorted(set(warnings)))
        from datetime import datetime, timezone
        self.diagnostics["final_csv_utc"] = \
            datetime.now(timezone.utc).isoformat()
        summary["final_csv_utc"] = self.diagnostics["final_csv_utc"]
        summary["live_csv_snapshot_row_count"] = \
            self.journal.live_snapshot_row_count
        self.machine.finalized()
        return summary

    # -- manual diagnostic snapshot ----------------------------------------

    def diagnostic_snapshot(self, out_root: Path | None = None) -> dict[str, Any]:
        """Write the most recent per-source crops (whatever preview/tick has
        produced so far) to an explicit, ignored local folder, plus a small
        sanitized metadata file. Never includes the raw window title/path,
        never uploads anything. Returns {"dir", "source_count"}; an empty
        last_crop_bytes yields source_count 0 with no directory written."""

        if not self.last_crop_bytes:
            return {"dir": None, "source_count": 0,
                    "note": "no capture yet - run Test capture, Preview, "
                            "or start recording first"}
        import json
        from datetime import datetime, timezone
        from .paths import diagnostics_root, new_diagnostic_id, resolve_under
        root = out_root or diagnostics_root()
        root.mkdir(parents=True, exist_ok=True)
        snap_dir = resolve_under(root, new_diagnostic_id())
        snap_dir.mkdir(parents=True, exist_ok=False)
        names = {s.source_id: s.display_name for s in self.sources}
        written = []
        for source_id, png_bytes in self.last_crop_bytes.items():
            if len(png_bytes) > C.CROP_PNG_MAX_BYTES:
                continue
            (snap_dir / f"{source_id}.png").write_bytes(png_bytes)
            written.append({"source_id": source_id,
                            "display_name": names.get(source_id, source_id),
                            "bytes": len(png_bytes)})
        meta = {
            "schema_version": C.SCHEMA_VERSION,
            "captured_utc": datetime.now(timezone.utc).isoformat(),
            "session_state": self.machine.state,
            "requested_backend": self.backend,
            "effective_backend": self.effective_backend,
            "crops": written,
        }
        (snap_dir / "meta.json").write_text(
            json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")
        return {"dir": str(snap_dir), "source_count": len(written)}
