"""Machine-readable rule-level scope coverage for the Claude takeoff pilot.

The first pilot keeps this ledger as append-only events in the existing agent
session decision log, so it adds no new persisted schema field and remains
backward compatible with already-created `.s2a.json` sessions.  A later
multi-sheet project can promote the same concept to first-class instance-level
scope records.

This ledger deliberately measures *coverage/accounting*, not correctness.  A
rule marked PROPOSED can still contain bad geometry or blocker flags; normal
QA remains authoritative for that.  The point is that a rule cannot disappear
silently from the agent's final pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .agent_session import AgentSessionError, AgentTakeoffSession
from .takeoff import RULES


UNSEARCHED = "UNSEARCHED"
PROPOSED = "PROPOSED"
WITHHELD = "WITHHELD"
NOT_PRESENT = "NOT_PRESENT"
NOT_APPLICABLE = "NOT_APPLICABLE"
SCOPE_STATUSES = frozenset(
    {UNSEARCHED, PROPOSED, WITHHELD, NOT_PRESENT, NOT_APPLICABLE}
)
ACCOUNTED_STATUSES = frozenset({PROPOSED, WITHHELD, NOT_PRESENT, NOT_APPLICABLE})


@dataclass(frozen=True)
class ScopeRuleState:
    rule_id: str
    status: str
    detail: str = ""
    at: str = ""
    source: str = ""

    @property
    def accounted(self) -> bool:
        return self.status in ACCOUNTED_STATUSES

    def to_dict(self) -> dict[str, Any]:
        rule = RULES[self.rule_id]
        return {
            "rule_id": self.rule_id,
            "display_name": rule.display_name,
            "geometry_kind": rule.geometry_kind,
            "summable": rule.summable,
            "status": self.status,
            "accounted": self.accounted,
            "detail": self.detail,
            "at": self.at,
            "source": self.source,
        }


def _proposal_events(session: AgentTakeoffSession) -> dict[str, ScopeRuleState]:
    """Return latest rule state by replaying append-only session decisions."""

    states = {
        rule_id: ScopeRuleState(rule_id=rule_id, status=UNSEARCHED)
        for rule_id in RULES
    }
    for event in session.decision_log:
        action = str(event.get("action", ""))
        rule_id = str(event.get("rule_id", ""))
        if rule_id not in RULES:
            continue
        if action in {"AI_TAKEOFF_PROPOSED", "MANUAL_TAKEOFF_PROPOSED"}:
            states[rule_id] = ScopeRuleState(
                rule_id=rule_id,
                status=PROPOSED,
                detail=f"Takeoff {event.get('takeoff_id', '')} exists for this rule.",
                at=str(event.get("at", "")),
                source=action,
            )
        elif action == "SCOPE_STATUS_SET":
            status = str(event.get("status", "")).upper()
            if status in SCOPE_STATUSES:
                states[rule_id] = ScopeRuleState(
                    rule_id=rule_id,
                    status=status,
                    detail=str(event.get("detail", "")),
                    at=str(event.get("at", "")),
                    source=action,
                )
    # A current retained measurement is stronger evidence of PROPOSED than a
    # stale NOT_PRESENT event accidentally left after an agent later created a
    # shape without appending an explicit ledger event.  The normal add path
    # already logs a proposal, but this closes the state against hand-edited
    # session files or old pilot records.
    by_rule: dict[str, list[str]] = {}
    for item in session.measurements:
        by_rule.setdefault(item.rule_id, []).append(item.id)
    for rule_id, ids in by_rule.items():
        current = states[rule_id]
        if current.status in {UNSEARCHED, NOT_PRESENT, NOT_APPLICABLE}:
            states[rule_id] = ScopeRuleState(
                rule_id=rule_id,
                status=PROPOSED,
                detail=f"Current takeoff(s): {', '.join(sorted(ids))}.",
                at=session.updated_at,
                source="CURRENT_MEASUREMENT",
            )
    return states


def scope_states(session: AgentTakeoffSession) -> list[ScopeRuleState]:
    states = _proposal_events(session)
    return [states[rule_id] for rule_id in RULES]


def set_scope_status(
    session: AgentTakeoffSession,
    *,
    rule_id: str,
    status: str,
    detail: str,
    now: str,
    actor: str = "agent",
) -> ScopeRuleState:
    if rule_id not in RULES:
        raise AgentSessionError(f"unknown civil takeoff rule: {rule_id}")
    cleaned = status.strip().upper()
    if cleaned not in {WITHHELD, NOT_PRESENT, NOT_APPLICABLE}:
        raise AgentSessionError(
            "explicit scope status must be WITHHELD, NOT_PRESENT, or NOT_APPLICABLE; "
            "PROPOSED is derived from an actual takeoff"
        )
    if not detail.strip():
        raise AgentSessionError("scope accounting detail/evidence is required")
    # Do not permit an agent to erase a real proposal by claiming the same rule
    # is absent/not-applicable.  A rule may be WITHHELD even when a partial or
    # blocked proposal exists, because that is a legitimate review state.
    has_rule_takeoff = any(item.rule_id == rule_id for item in session.measurements)
    if has_rule_takeoff and cleaned in {NOT_PRESENT, NOT_APPLICABLE}:
        raise AgentSessionError(
            f"{rule_id} already has current takeoff geometry; reject/remove that proposal "
            "before accounting the rule as absent/not applicable"
        )
    session.updated_at = now
    session.decision_log.append(
        {
            "at": now,
            "action": "SCOPE_STATUS_SET",
            "rule_id": rule_id,
            "status": cleaned,
            "detail": detail.strip(),
            "actor": actor,
        }
    )
    return ScopeRuleState(
        rule_id=rule_id,
        status=cleaned,
        detail=detail.strip(),
        at=now,
        source="SCOPE_STATUS_SET",
    )


def scope_summary(session: AgentTakeoffSession) -> dict[str, Any]:
    states = scope_states(session)
    unsearched = [item.rule_id for item in states if item.status == UNSEARCHED]
    withheld = [item.rule_id for item in states if item.status == WITHHELD]
    accounted = [item.rule_id for item in states if item.accounted]
    total = len(states)
    return {
        "rule_count": total,
        "accounted_count": len(accounted),
        "accounted_rate": 1.0 if total == 0 else len(accounted) / total,
        "unsearched_count": len(unsearched),
        "unsearched_rule_ids": unsearched,
        "withheld_count": len(withheld),
        "withheld_rule_ids": withheld,
        "ready_for_coverage_review": not unsearched,
        "states": [item.to_dict() for item in states],
        "note": (
            "Rule-level coverage guard only. Multiple instances/reaches of the same rule "
            "can still be missed and require visual estimator reconciliation."
        ),
    }
