"""Session state machine and legal-action enforcement (UX §3)."""

from __future__ import annotations

from . import contracts as C


class IllegalAction(RuntimeError):
    """Action not legal in the current session state."""


# action -> states in which it is legal (before interlock filtering)
_LEGAL: dict[str, frozenset[str]] = {
    "select_target": frozenset({"IDLE", "TARGET_SELECTED",
                                "REGIONS_CONFIGURED", "ARMED", "PAUSED",
                                "FINALIZED"}),
    "edit_sources": frozenset({"TARGET_SELECTED", "REGIONS_CONFIGURED",
                               "ARMED"}),
    "region_snapshot": frozenset({"TARGET_SELECTED", "REGIONS_CONFIGURED"}),
    "save_profile": frozenset({"IDLE", "TARGET_SELECTED",
                               "REGIONS_CONFIGURED", "ARMED", "FINALIZED"}),
    "load_profile": frozenset({"IDLE", "TARGET_SELECTED",
                               "REGIONS_CONFIGURED", "ARMED", "FINALIZED"}),
    "preview": frozenset({"REGIONS_CONFIGURED"}),
    "confirm_preview": frozenset({"REGIONS_CONFIGURED"}),
    "start_recording": frozenset({"ARMED"}),
    "pause": frozenset({"RECORDING"}),
    "resume": frozenset({"PAUSED"}),
    "reconfigure": frozenset({"ARMED", "PAUSED"}),
    "stop": frozenset({"ARMED", "RECORDING", "PAUSED"}),
    "emergency_stop": frozenset({"ARMED", "RECORDING", "PAUSED"}),
    "export": frozenset({"FINALIZED"}),
    "retry_worker": frozenset({"TARGET_SELECTED", "REGIONS_CONFIGURED",
                               "ARMED"}),
    "close": frozenset(C.SESSION_STATES),
}

_WORKER_DEPENDENT = frozenset({
    "region_snapshot", "preview", "confirm_preview", "start_recording",
})


class SessionStateMachine:
    def __init__(self) -> None:
        self.state = "IDLE"
        self.setup_worker_blocked = False
        self.preview_confirmed_revision: int | None = None
        self.configuration_revision = 0

    def is_legal(self, action: str) -> bool:
        states = _LEGAL.get(action)
        if states is None or self.state not in states:
            return False
        if self.setup_worker_blocked and action in _WORKER_DEPENDENT:
            return False
        if action == "retry_worker" and not self.setup_worker_blocked:
            return False
        return True

    def require(self, action: str) -> None:
        if not self.is_legal(action):
            raise IllegalAction(
                f"action {action!r} is not legal in state {self.state}"
                + (" (worker blocked)" if self.setup_worker_blocked else ""))

    # -- transitions ------------------------------------------------------

    def _bump_revision(self) -> None:
        self.configuration_revision += 1
        self.preview_confirmed_revision = None

    def select_target(self) -> None:
        self.require("select_target")
        if self.state in ("ARMED", "PAUSED"):
            self.state = "TARGET_SELECTED"
        elif self.state in ("IDLE", "FINALIZED"):
            self.state = "TARGET_SELECTED"
        self._bump_revision()

    def sources_configured(self) -> None:
        self.require("edit_sources")
        if self.state == "ARMED":
            self.state = "REGIONS_CONFIGURED"
        elif self.state == "TARGET_SELECTED":
            self.state = "REGIONS_CONFIGURED"
        self._bump_revision()

    def confirm_preview(self) -> None:
        self.require("confirm_preview")
        self.preview_confirmed_revision = self.configuration_revision
        self.state = "ARMED"

    def start_recording(self) -> None:
        self.require("start_recording")
        if self.preview_confirmed_revision != self.configuration_revision:
            raise IllegalAction("preview is stale; re-preview before Start")
        self.state = "RECORDING"

    def pause(self) -> None:
        self.require("pause")
        self.state = "PAUSED"

    def resume(self) -> None:
        self.require("resume")
        self.state = "RECORDING"

    def reconfigure(self) -> None:
        self.require("reconfigure")
        self.state = "REGIONS_CONFIGURED"
        self._bump_revision()

    def stop(self) -> None:
        self.require("stop")
        self.state = "STOPPING" if self.state in ("RECORDING", "PAUSED") \
            else "REGIONS_CONFIGURED"

    def finalized(self) -> None:
        if self.state != "STOPPING":
            raise IllegalAction("finalize only from STOPPING")
        self.state = "FINALIZED"
