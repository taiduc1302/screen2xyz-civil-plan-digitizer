"""Stability engine and retention decision (data contracts §6a/§6b).

Three tiers: provisional observation (every tick) -> per-source stable
state (after confirmations/debounce/threshold) -> retained event decided by
the closed precedence. Cached (pixel-hash) confirmations never count as new
readings; failures never inherit prior values.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from . import contracts as C
from .models import Observation, SourceConfig


@dataclass
class _Candidate:
    value: str | None
    kind: str
    value_status: str
    first_frame_id: str
    first_observation: Observation
    first_crop_png: bytes | None
    first_seen_ms: float
    count: int = 1


@dataclass
class _SourceState:
    seeded: bool = False
    stable_value: str | None = None
    stable_kind: str = "number"
    stable_status: str | None = None      # value_status of the stable state
    retained_error_active: bool = False
    last_retained_error: str | None = None  # last error value_status retained
    pre_error_value: str | None = None    # stable value before the error run
    pre_error_kind: str = "number"
    candidate: _Candidate | None = None


@dataclass
class TickDecision:
    event_status: str | None              # RETAINED_* or None
    changed_source_ids: list[str] = field(default_factory=list)
    retention_reason_codes: list[str] = field(default_factory=list)
    stable_signature: dict[str, dict[str, Any]] = field(default_factory=dict)
    evidence: dict[str, dict[str, Any]] = field(default_factory=dict)
    crops_to_save: dict[str, bytes] = field(default_factory=dict)


class StabilityEngine:
    def __init__(self, sources: list[SourceConfig], *,
                 confirmations: int, debounce_ms: int,
                 min_change_threshold: float | None,
                 retention_mode: str) -> None:
        self.retention_mode = retention_mode
        self._config: dict[str, SourceConfig] = {
            source.source_id: source for source in sources if source.enabled}
        self._defaults = (confirmations, debounce_ms, min_change_threshold)
        self._state: dict[str, _SourceState] = {
            sid: _SourceState() for sid in self._config}
        # Bounded first-candidate evidence buffer accounting (contracts §6b).
        self._evidence_bytes = 0

    # -- helpers ----------------------------------------------------------

    def _confirmations(self, sid: str) -> int:
        override = self._config[sid].confirmations
        return override if override is not None else self._defaults[0]

    def _debounce(self, sid: str) -> int:
        override = self._config[sid].debounce_ms
        return override if override is not None else self._defaults[1]

    def _threshold(self, sid: str) -> float | None:
        override = self._config[sid].min_change_threshold
        return override if override is not None else self._defaults[2]

    def _below_threshold(self, sid: str, old: str | None,
                         new: str | None) -> bool:
        threshold = self._threshold(sid)
        if threshold is None or old is None or new is None:
            return False
        try:
            return abs(float(new) - float(old)) < threshold
        except ValueError:
            return False

    def signature(self) -> dict[str, dict[str, Any]]:
        return {sid: {"value_kind": state.stable_kind,
                      "normalized_value": state.stable_value}
                for sid, state in self._state.items() if state.seeded}

    def stable_status_of(self, sid: str) -> str | None:
        return self._state[sid].stable_status

    # -- transactional snapshot/restore (durable-journal contingency) -----

    def snapshot_state(self) -> tuple[dict[str, "_SourceState"], int]:
        """Deep-copy the committed per-source state and evidence accounting.
        The caller snapshots BEFORE process_tick and restore()s if the
        resulting event fails to durably journal, so an in-memory stable
        transition is never advanced past a change the source-of-truth
        journal never recorded (which would make the change undetectable on
        the next tick and silently lose it)."""

        return (copy.deepcopy(self._state), self._evidence_bytes)

    def restore_state(self,
                      snapshot: tuple[dict[str, "_SourceState"], int]) -> None:
        self._state, self._evidence_bytes = snapshot[0], snapshot[1]

    # -- main entry -------------------------------------------------------

    def process_tick(self, observations: dict[str, Observation],
                     frame_id: str, monotonic_ms: float,
                     crop_bytes: dict[str, bytes]) -> TickDecision:
        changed: list[str] = []
        reasons: list[str] = []
        error_transitions: list[str] = []
        recoveries: list[str] = []
        evidence: dict[str, dict[str, Any]] = {}
        crops: dict[str, bytes] = {}

        recovery_changed: dict[str, bool] = {}
        for sid, obs in observations.items():
            if sid not in self._state:
                continue
            state = self._state[sid]
            status = obs.value_status

            if status == "OK":
                same_as_stable = (state.seeded
                                  and state.stable_value == obs.normalized_value
                                  and state.stable_kind == obs.value_kind
                                  and state.stable_status == "OK")
                if same_as_stable and not state.retained_error_active:
                    self._release_candidate(state)
                    obs.stability_status = "CONFIRMED"
                    continue
                if self._below_threshold(sid, state.stable_value,
                                         obs.normalized_value) \
                        and state.seeded and not state.retained_error_active:
                    obs.stability_status = "CONFIRMED"
                    self._release_candidate(state)
                    continue
                candidate_matches = (
                    state.candidate is not None
                    and state.candidate.value == obs.normalized_value
                    and state.candidate.kind == obs.value_kind)
                if candidate_matches:
                    state.candidate.count += 1
                else:
                    replaced = (state.candidate is not None
                                and self._confirmations(sid) > 1)
                    self._release_candidate(state)
                    state.candidate = _Candidate(
                        value=obs.normalized_value, kind=obs.value_kind,
                        value_status="OK", first_frame_id=frame_id,
                        first_observation=obs,
                        first_crop_png=self._own_crop(crop_bytes.get(sid)),
                        first_seen_ms=monotonic_ms)
                    if replaced:
                        # a pending candidate failed to repeat -> the new,
                        # not-yet-confirmed reading is surfaced as unstable
                        obs.stability_status = "REJECTED"
                        obs.value_status = C.derive_value_status(
                            obs.capture_status, obs.ocr_status,
                            obs.parse_status, "REJECTED")
                        obs.warning_codes = tuple(
                            set(obs.warning_codes) | {"CANDIDATE_REPLACED"})
                        continue
                needed = self._confirmations(sid)
                debounce = self._debounce(sid)
                candidate = state.candidate
                confirmed = (candidate.count >= needed
                             and (monotonic_ms - candidate.first_seen_ms)
                             >= debounce)
                if not confirmed:
                    obs.stability_status = "PENDING_CONFIRMATION"
                    continue
                obs.stability_status = ("IMMEDIATE" if needed == 1
                                        else "CONFIRMED")
                was_error = state.retained_error_active
                pre_error_value = state.pre_error_value
                pre_error_kind = state.pre_error_kind
                seeding = not state.seeded
                value_before = state.stable_value
                kind_before = state.stable_kind
                state.seeded = True
                state.stable_value = candidate.value
                state.stable_kind = candidate.kind
                state.stable_status = "OK"
                if was_error:
                    state.retained_error_active = False
                    state.last_retained_error = None
                    value_moved = (candidate.value != pre_error_value
                                   or candidate.kind != pre_error_kind)
                    recoveries.append(sid)
                    recovery_changed[sid] = value_moved
                    evidence[sid] = self._evidence_record(candidate, obs)
                    self._stash_crop(sid, candidate, crops)
                elif not seeding and (value_before != candidate.value
                                      or kind_before != candidate.kind):
                    changed.append(sid)
                    evidence[sid] = self._evidence_record(candidate, obs)
                    self._stash_crop(sid, candidate, crops)
                self._release_candidate(state, keep=False)
                continue

            # non-OK observation ------------------------------------------
            self._release_candidate(state)
            if status in ("MISSING_SOURCE_VALUE", "UNSTABLE_READING"):
                # live/diagnostic only; never mutates the stable signature
                continue
            if status in C.RETAINABLE_ERROR_VALUE_STATUSES:
                # Remember the last stable value before the FIRST error so a
                # later recovery can tell whether the value actually moved.
                if not state.retained_error_active:
                    state.pre_error_value = state.stable_value
                    state.pre_error_kind = state.stable_kind
                # Retain a transition on entry into a retainable error AND on a
                # transition to a DIFFERENT retainable error type (data
                # contracts §6a); an identical repeated error retains nothing.
                if state.last_retained_error != status:
                    state.stable_status = status
                    state.retained_error_active = True
                    state.last_retained_error = status
                    error_transitions.append(sid)
                    evidence[sid] = {
                        "evidence_frame_id": frame_id,
                        "raw_text": obs.raw_text,
                        "raw_truncated": obs.raw_truncated,
                        "raw_original_utf8_bytes":
                            obs.raw_original_utf8_bytes,
                        "warning_codes": list(obs.warning_codes),
                        "parse_status": obs.parse_status,
                        "normalized_value": None,
                        "value_kind": obs.value_kind,
                        "pixel_sha256": obs.pixel_sha256,
                    }
                    if sid in crop_bytes:
                        crops[sid] = crop_bytes[sid]

        decision = TickDecision(event_status=None,
                                stable_signature=self.signature(),
                                evidence=evidence, crops_to_save=crops)
        mode = self.retention_mode
        error_eligible = mode in (C.RETENTION_CHANGED_AND_ERRORS,
                                  C.RETENTION_EVERY_TICK,
                                  C.RETENTION_VALUES_ONLY)
        if error_transitions and error_eligible:
            decision.event_status = "RETAINED_ERROR"
            decision.changed_source_ids = sorted(set(changed)
                                                 | set(error_transitions))
            decision.retention_reason_codes = ["ERROR_TRANSITION"]
            if changed:
                decision.retention_reason_codes.append("STABLE_CHANGE")
            return decision
        change_sources = list(changed)
        reason_codes: list[str] = []
        if changed:
            reason_codes.append("STABLE_CHANGE")
        if recoveries:
            if mode == C.RETENTION_CHANGED_ONLY:
                # changed_only did not retain the error, so a same-value
                # recovery is not an event — but a recovery to a DIFFERENT
                # value is a genuine change and must be retained.
                recovered_changed = [sid for sid in recoveries
                                     if recovery_changed.get(sid)]
                change_sources.extend(recovered_changed)
                if recovered_changed and "STABLE_CHANGE" not in reason_codes:
                    reason_codes.append("STABLE_CHANGE")
            else:
                change_sources.extend(recoveries)
                reason_codes.append("ERROR_RECOVERED")
        if change_sources:
            decision.event_status = "RETAINED_CHANGE"
            decision.changed_source_ids = sorted(set(change_sources))
            decision.retention_reason_codes = reason_codes or ["STABLE_CHANGE"]
            return decision
        if mode == C.RETENTION_EVERY_TICK:
            decision.event_status = "RETAINED_DIAGNOSTIC"
            decision.retention_reason_codes = ["DIAGNOSTIC_TICK"]
            return decision
        decision.crops_to_save = {}
        decision.evidence = {}
        return decision

    # -- evidence buffer (contracts §6b) ----------------------------------

    def _own_crop(self, png: bytes | None) -> bytes | None:
        if png is None:
            return None
        if len(png) > C.CROP_PNG_MAX_BYTES:
            raise BufferError("EVIDENCE_BUFFER_LIMIT")
        if self._evidence_bytes + len(png) > C.AGGREGATE_CROP_MAX_BYTES:
            raise BufferError("EVIDENCE_BUFFER_LIMIT")
        self._evidence_bytes += len(png)
        return png

    def _release_candidate(self, state: _SourceState,
                           keep: bool = False) -> None:
        candidate = state.candidate
        if candidate is not None and candidate.first_crop_png is not None:
            self._evidence_bytes -= len(candidate.first_crop_png)
        if not keep:
            state.candidate = None

    def discard_all_candidates(self) -> None:
        for state in self._state.values():
            self._release_candidate(state)

    def _evidence_record(self, candidate: _Candidate,
                         current: Observation) -> dict[str, Any]:
        first = candidate.first_observation
        return {
            "evidence_frame_id": candidate.first_frame_id,
            "raw_text": first.raw_text,
            "raw_truncated": first.raw_truncated,
            "raw_original_utf8_bytes": first.raw_original_utf8_bytes,
            "warning_codes": list(first.warning_codes),
            "parse_status": first.parse_status,
            "normalized_value": candidate.value,
            "value_kind": candidate.kind,
            "pixel_sha256": first.pixel_sha256,
        }

    def _stash_crop(self, sid: str, candidate: _Candidate,
                    crops: dict[str, bytes]) -> None:
        if candidate.first_crop_png is not None:
            crops[sid] = candidate.first_crop_png
