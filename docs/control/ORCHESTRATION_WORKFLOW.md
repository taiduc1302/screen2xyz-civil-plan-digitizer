# Parent-Agent Orchestration Workflow

GitHub and the repository are the shared project state. Each task uses one parent Codex agent, read-only specialized subagents, one task-specific branch, and one consolidated report. The parent agent is the only file writer during a run. Parallel write-heavy work is prohibited unless a later approved decision changes this rule.

## Required workflow

1. The parent agent reads the repository before every run, beginning with `PROJECT_STATE.md`, `NEXT_ACTION.md`, the current Master Index, Decision Log, and applicable source-of-truth documents.
2. The parent agent checks the current lifecycle gate, recorded authorization, task scope, and prohibited work.
3. The parent agent delegates suitable independent read-heavy analysis to specialized read-only subagents.
4. Subagents return evidence summaries and do not modify files, Git refs, remotes, or external state.
5. The parent agent waits for all subagents, reconciles their results, and resolves conflicts using the approved source-of-truth hierarchy.
6. The parent agent performs all and only the authorized file changes on one task-specific branch.
7. The parent agent runs the task's required validation and records actual results without invention.
8. An independent reviewer subagent reviews the complete resulting diff for scope, governance, safety, evidence, and regression issues.
9. The parent agent corrects verified issues only when the current task authorizes those corrections; otherwise it reports the blocker.
10. The parent agent creates one consolidated run report containing actions, evidence, validation, limitations, and the next action.
11. The parent agent updates `PROJECT_STATE.md` and `NEXT_ACTION.md` to reflect the accepted state without claiming unaccepted work complete.
12. The parent agent commits and pushes the task-specific branch after validation succeeds or documented source-preservation exceptions are accepted.
13. The parent agent opens or updates one pull request and does not merge it without explicit authorization.
14. The parent agent reports to the user only the outcome category, verification result, failure or incompleteness, genuine decision requirement, and exactly one next action.

## Owner communication outcomes

The user-facing outcome must use only the information needed to communicate one or more of these states:

- completed;
- verified;
- failed or incomplete;
- decision required;
- next action.
