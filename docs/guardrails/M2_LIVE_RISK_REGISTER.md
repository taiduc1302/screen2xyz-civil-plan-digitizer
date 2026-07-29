# M2-Live Risk Register

Status: M2-000 planning. Severity/likelihood: H/M/L. "Owner" column marks
risks needing an owner decision (cross-ref
[owner decisions](../control/M2_LIVE_OWNER_DECISIONS.md)).

| ID | Risk | Sev | Lik | Detection | Mitigation | Fallback | Owner |
|---|---|---|---|---|---|---|---|
| RSK-M2-01 | Intended target is hardware-accelerated → PW_CLIENTONLY blank | H | M | Authorized S7 one-shot gate; whole-frame health + visual check | Lock target-tested CopyFromScreen with keep-visible warning | WGC via C# helper | OD-M2-2 |
| RSK-M2-02 | Intended target is capture-protected → blank under both | H | L | Authorized S7 | Do not bypass; document and stop | Reconsider direction for that target | OD-M2-2/8 |
| RSK-M2-03 | OCR misreads small/anti-aliased digits (O/0, I/1) at 1× scale | M | M | Preview OCR; MA-3 crop checks | Per-source upscale 1–4 within runtime bounds; no glyph substitution; retained evidence | Stabilized mode; narrow region | — |
| RSK-M2-04 | OCR flicker floods history in confirmations=1 | M | M | Event-rate counter; MA-3 | min_change_threshold or confirmations=2; deterministic retention precedence; bounded first-candidate evidence | Audit crops/causal fields | OD-M2-4 |
| RSK-M2-05 | Mixed-DPI (≠100%) coordinate mismatch — untested on this machine | H | M (if owner changes scaling/monitors) | Environment snapshot diff; preview gate misalignment visible | **PMv2 in both processes — the worker sets it in its bootstrap and reports it in INIT (all coordinate calls run in the worker)** + client-relative rects + per-tick origin re-query; re-run S5 at ≠100% before trusting | Pause + re-preview on any DPI/client-size change | — |
| RSK-M2-06 | PS 5.1 worker fragility (encoding, Add-Type quirks) over long sessions | M | L | S2/S4 measured clean; 30-min soak MA-5 | UTF-8 forced both ends; restart-with-backoff; journal unaffected by worker death | Option B compiled C# helper, same protocol | — |
| RSK-M2-07 | PrintWindow blocks indefinitely on a hung target | M | L | Request timeout | Invalidate generation; kill/reap; drain/close/join; fresh INIT only after teardown; no overlapping request | Backend fallback after explicit preview | — |
| RSK-M2-08 | Journal/crop/checkpoint corruption on crash or disk-full | M | L | recovery warnings; manifest | Crop→artifact hash→journal sync→checkpoint; journal wins; missing-crop/divergence/orphan rules | Fail closed on malformed complete journal line | — |
| RSK-M2-09 | Windows.Media.Ocr documented support requires package identity (unpackaged use is outside the stated envelope) | M | L (works today, proven by sealed baseline) | Research O6; runtime engine-null check | Record as support-boundary limitation in docs; no behavioral dependence on undocumented features beyond this | MSIX packaging later; or OCR via a packaged helper | noted |
| RSK-M2-10 | Tk snapshot-based region drawing confuses the user (expects live overlay) | M | M | UX approval gate; MA-8 | Wireframes reviewed before build; re-preview loop is cheap | Add live overlay in M3 if requested | OD-M2-6 |
| RSK-M2-15 | **Hover-dependent fields** blank while user interacts with Screen2XYZ | H | M | UX checklist; S7 present/absent trials | Explicit 3–5 s countdown then exactly one REGION_SNAPSHOT/PREVIEW; empty OCR never switches/pauses | If owner rejects workflow, reconsider setup trigger in a later approved plan | OD-M2-6 |
| RSK-M2-11 | 1 s cadence insufficient (values change faster than sampling) | M | M | Owner observation in MA-3 | Interval configurable to 250 ms (tick budget measured 24 ms); document Nyquist-style limitation honestly | Faster interval milestone with WGC frame-driven capture | OD-M2-4 |
| RSK-M2-12 | Sandbox-affected spike environment (window enumeration filtered) hid a real defect | L | L | S7 runs on a normal desktop session | Enumeration/pickers re-verified in M2-001 on the owner's session | Adjust picker to alternative enumeration | — |
| RSK-M2-13 | Scope creep toward background monitoring | H | L | Guardrails; PR review | Prohibited-capability source scans; consent model frozen in spec | — | — |
| RSK-M2-14 | Disk exhaustion in every-tick diagnostic mode | M | M | Live disk indicator; warn/stop caps | Mode is opt-in, capped, and labelled diagnostic | values_only mode | OD-M2-3 |
| RSK-M2-16 | Target trial uses content without capture/data rights or exposes confidential material | H | M | OD-M2-8/G-F record before S7/MA | Authorized non-confidential demo content only; default no-save; ignored local preview; stop/quarantine | Do not execute trial | OD-M2-8 |
| RSK-M2-17 | Stabilized event loses or misattributes raw/crop evidence | H | L | T-M2L-009/026 | Complete first-candidate bundle; evidence_frame_id; all §0 PNG-payload, canonical-metadata, and accounted-owned-byte caps; explicit lifecycle; no second capture | Pause on buffer cap/write failure | — |
| RSK-M2-18 | Full-frame/eight-crop JSON line exhausts memory or blocks pipes | H | L | Boundary tests | 64 MiB image/aggregate and 96 MiB line caps; bounded reader; fail-closed worker generation | Reduce crop/frame size after explicit reconfiguration | — |
| RSK-M2-19 | Always-on-top controller covers a CopyFromScreen source | H | L | Pre-start intersection check; MA-4 | Auto-place outside region union; require relocation if no safe corner | Window backend or different layout | OD-M2-6 |
| RSK-M2-20 | Worker state restoration resumes capture without live consent | H | L | T-M2L-022/024/027; visible REC state | Restore RECORDING/PAUSED only inside the same live UI process and session/revision after explicit Start; validate INIT echo; app relaunch always starts non-recording | Fail closed to PAUSED/REGIONS_CONFIGURED | — |

Top blocking risks before implementation: **RSK-M2-16 must be resolved
before S7; RSK-M2-01/02 are then evaluated by the target-specific S7 trial
(M2-001). S7 does not prove general backend compatibility or occlusion
immunity.**
