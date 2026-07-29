# M2-Live Owner Decisions

Status: OD-M2-1, OD-M2-3, OD-M2-4, OD-M2-5, OD-M2-6, OD-M2-7 recorded
2026-07-18 by explicit owner authorization in chat (Claude Code session,
model claude-sonnet-5). OD-M2-2 is a decision **rule**, not yet a decision:
the actual backend selection remains blocked on the real S7 trial. OD-M2-8
records the authorized/prohibited scope, but the specific narrow
per-session confirmation ("does the currently displayed target contain
only authorized, non-confidential content?") must still be asked and
answered **immediately before** the S7 run and before every later
real-target manual-acceptance session — recording the scope here does not
substitute for that live confirmation. Technical constants and enums
remain centralized in
[`M2_LIVE_DATA_CONTRACTS.md` §0](../requirements/M2_LIVE_DATA_CONTRACTS.md).

| ID | Decision | Status |
|---|---|---|
| OD-M2-1 | **Approved 2026-07-18.** MVP scope: Windows 11 local desktop app; one selected target window as primary scope, one selected monitor as fallback; 1–8 enabled sources; dynamic names; types `number`/`text`/`auto`; optional roles `x`/`y`/`z`/`metadata`/`none`; local-only, no network dependency, no service-specific scraping preset, no pointer control, no hidden/background recording; M1 remains a separate available mode. | **Closed** |
| OD-M2-2 | Backend/scope response to the S7 trial: decision **rule** recorded 2026-07-18 — prefer `printwindow_clientonly` only if the `present` trial shows the target/value correctly with valid geometry/DPI and a usable visual result; the `occluded` trial determines only target-specific behavior and is never generalized; use `copyfromscreen` if it is the reliable backend, with a persistent "keep target visible" warning; if both MVP backends are unusable, stop before the worker milestone and produce a focused Windows Graphics Capture / C# fallback plan instead; `PW_RENDERFULLCONTENT` is never a production dependency. **G-E-SYNTHETIC executed 2026-07-18: 6/6 automated trials passed; synthetic-target provisional backend = `printwindow_clientonly` (fallback `copyfromscreen`), per research doc S7-SYNTHETIC section.** | **Synthetic-provisional backend recorded; final real-target confirmation at G-E-REAL** |
| OD-M2-3 | **Approved 2026-07-18.** Retention default `changed_and_errors`; warning 200 MiB, hard stop 500 MiB per session; full frames never persisted in any mode; only required retained-event crops persisted; `values_only`/`changed_only`/`every_tick_diagnostic` remain available as explicit options. | **Closed** |
| OD-M2-4 | **Approved 2026-07-18.** Interval default 1000 ms (configurable 250–10000 ms); `stability_confirmations = 1` default; `debounce_ms = 0` default; `min_change_threshold = null` default; per-source overrides allowed; stabilized mode (≥2 confirmations) available but not default. | **Closed** |
| OD-M2-5 | **Approved 2026-07-18.** Optional cursor-position metadata remains implemented; default **OFF**; visible per-session opt-in; collected only during active RECORDING; never controls the pointer. | **Closed** |
| OD-M2-6 | **Approved 2026-07-18.** The documented user journey (target/monitor selection; 1–8 sources; countdown-snapshot region drawing; mandatory synchronized preview; Confirm Preview → ARM; explicit Start; live grid updated every tick; retained-event history; visible REC state; always-on-top mini controller placed outside configured regions; Pause/Resume; normal Stop; Emergency Stop; finalized exports; recovery workflow) is approved as the implementation baseline. This approval does not waive later usability testing (MA-8); if the implemented UI materially differs from the documented flow, implementation must stop and report the difference before continuing. | **Closed — hard gate G-D green** |
| OD-M2-7 | **Approved 2026-07-18.** Roadmap milestones M2-002 through M2-011; milestone-scoped commits; implementation branch `feat/m2-live-region-watch-impl`; a Draft implementation PR; no final merge without explicit owner confirmation after acceptance; source-agnostic implementation only; prior baseline/M1 evidence remains immutable; no public release or licence change in this task. | **Closed** (implementation itself remains additionally gated on G-E/G-F per the hard-gate sequence below) |
| OD-M2-8 | Capture/data-use permission scope **recorded 2026-07-18**. Authorized: local testing on the owner's machine; synthetic, owner-created, government-open, or appropriately licensed non-confidential demonstration content; the tracked S7 one-shot trials; synthetic integration targets; local ignored outputs under `.lab_work/`. **Not authorized**: confidential employer/client information; credentials; personal/private third-party data; protected content; bypassing access controls or capture protections; uploading real screenshots to GitHub, PRs, issues, chat, or any external service. | **Scope recorded; live per-session confirmation still required before each real-target capture (see status note above)** |

| OD-M2-9 | **Approved 2026-07-18 (owner governance change, maximum-autonomy continuation).** Gate G-E is split: **G-E-SYNTHETIC** — a fully automated compatibility gate against a deterministic, non-confidential synthetic target with machine-readable oracles (no human visual judgment); passing it authorizes beginning and completing implementation, synthetic integration testing, and a Draft implementation PR, and (together with G-D/G-G and the recorded OD-M2-8 scope) authorizes merging planning PR #4. **G-E-REAL** — the owner-machine real-target compatibility validation; it remains mandatory before any claim that the application supports the intended real target and before the final implementation-PR merge, but it no longer blocks coding, synthetic integration, or the Draft implementation PR. The owner-run S7 script is preserved for G-E-REAL; a consolidated `validate-real-target` command will be prepared so the owner pauses only once near the end. The G-F live per-session confirmation applies to **real, non-synthetic** capture only; synthetic self-generated targets are covered by the recorded OD-M2-8 scope. | **Closed (governance rule); G-E-SYNTHETIC to be executed and recorded; G-E-REAL pending owner-machine validation** |

Decision order: OD-M2-1/3/4/5/6/7 close G-D and G-G. OD-M2-9 replaces the
single-G-E sequencing: implementation and the PR #4 merge are authorized
after **G-E-SYNTHETIC** passes on recorded automated evidence, while
**G-E-REAL** (real-target validation and the live G-F confirmation for real
content) remains mandatory before the final implementation-PR merge and
before any real-target support claim. The OD-M2-2 backend rule now selects a
**synthetic-target provisional** backend from G-E-SYNTHETIC; the final
backend confirmation for the intended real target happens at G-E-REAL.
G-E-REAL must never be marked passed without actual owner-machine execution.
