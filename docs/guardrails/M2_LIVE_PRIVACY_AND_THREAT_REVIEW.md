# M2-Live Privacy and Threat Review

Status: M2-000 planning. Extends (does not weaken) the baseline guardrails
and M1 privacy model. Scope: the live region watcher described in the
[product spec](../requirements/M2_LIVE_PRODUCT_SPEC.md).

## 1. Consent model

**Recurring (recorded) capture** requires, in order: explicit target
selection → explicit region drawing → mandatory preview confirmation →
explicit Start. Before Start, the only captures are single
`REGION_SNAPSHOT` and `PREVIEW` operations in their exact pre-ARM states,
each tied to an explicit click and visible 3–5 s countdown, displayed once and never
persisted or journaled. Recording state is visible whenever any
Screen2XYZ window is visible — including an **always-on-top mini
controller** showing REC/PAUSED, elapsed, Pause/Resume, Stop, and emergency
Stop. It is placed outside configured regions and remains usable while the
target application covers the main window. Esc (when a Screen2XYZ window
has focus), either Stop button, and closing the UI all end capture; the
worker process dies with the UI (stdin-close, parent-watch, job-object
hardening). No autostart, no service, no scheduled task, no background
residue. Cursor-position metadata is a visible per-session toggle, default
OFF; it
reads position only while RECORDING and never controls the pointer.

## 2. Data-use and target-trial authorization

M2-000 authorizes planning and sanitized one-shot gate tooling, not a
real-target run. Before S7 or any manual target acceptance, OD-M2-8/G-F must
record the source/controller, permission basis for capture/processing/local
storage, content classification, and confirmation that no access or capture
protection is bypassed. Only synthetic, owner-created, government-open, or
appropriately licensed non-confidential demonstration content is allowed.
Unknown rights or unexpected personal/client/employer/proprietary content
stops and quarantines the run outside Git. Target screenshots never enter
Git, PRs, issues, logs, or chat. S7 reviews default transient previews in an
in-process local viewer and deletes them on normal completion; a forced
termination may leave sensitive non-evidence files in the OS temporary
directory for owner-controlled cleanup. `--save` uses a unique ignored local
directory; only validated previews bound to trial/backend/verdict by the
no-overwrite sanitized `trial_record.json` and SHA-256 manifest form the raw
gate evidence record. An interrupted/incomplete directory is explicitly not a
complete record. These artifacts are never overwritten, committed, or shared.

## 3. Data retention

Only per-source crops of retained events (default mode) are written, under
ignored `.lab_work/m2_runs/<run_id>/`; the full frame lives in worker
memory for one tick and is never persisted in any mode. Retention modes,
disk caps, and full-disk behavior per spec M2-FR-062/063. Nothing under
`.lab_work/` is ever committed (repo sanitization + gitignore tests).
Candidate evidence is bounded to one bundle/source under every §0 PNG-payload,
canonical-metadata, and accounted-owned-byte per-source and aggregate cap, with
the data-contract §6b lifecycle. Raw target titles/process names are bounded
local metadata in profiles/session only; summaries/exports use a sanitized
user label by default and never retain a window inventory.

## 4. Threat table

| # | Threat | Mitigation | Verification |
|---|---|---|---|
| TH-01 | Unintended screen capture (wrong region content) | Explicit REGION_SNAPSHOT for drawing; distinct PREVIEW shows exact crops; both one-frame/non-persistent; only selected retained crops leave worker memory | T-M2L-011/027/030, MA-2 |
| TH-02 | Wrong-window capture (HWND reuse, same-title windows) | HWND+PID binding; death ⇒ pause + explicit re-resolve; no title-based auto-rebind | T-M2L-035 |
| TH-03 | Hidden continued capture | Periodic CAPTURE only RECORDING; REGION_SNAPSHOT/PREVIEW only exact pre-ARM states; cross-launch recovery never restores RECORDING; full mini controller outside source regions; Esc/emergency/close ≤2 s | T-M2L-011/022/027/036/037, MA-4 |
| TH-04 | Orphan worker after UI death | stdin-close exit (measured <1 s), parent-PID WaitForExit watch, kill-on-close job object | T-M2L-037, S6 |
| TH-05 | Output/profile path traversal | Generated run/profile/source IDs; display names never paths; resolve-under ignored roots; all writes use atomic evidence utilities | T-M2L-001/012/019 |
| TH-06 | Malicious/oversized profile | 256 KiB file and bounded metadata, schema/bounds/closed-enum validation; never auto-arm | T-M2L-002/019 |
| TH-07 | Malformed/oversized worker message or hung worker | 96 MiB bounded reader; request+generation match; ordered kill/reap/drain/close/join; fail-closed restart/backoff; one outstanding request | T-M2L-020..024/039 |
| TH-08 | Unbounded disk usage | `changed_and_errors`; 200/500 MiB caps; live indicator; cap pauses; durable error is best-effort if journal remains writable | T-M2L-013/014, MA-5 |
| TH-09 | Crop data leakage into Git | Outputs under ignored `.lab_work/`; regression includes clean `git status`; sanitization scan | Regression suite |
| TH-10 | Personal paths/identity in artifacts | Run-relative paths only; bounded raw target identity stays in local profile/session; summaries contain only the §9 sanitized environment projection and exclude HWND/PID/raw title/process/device IDs/absolute paths; staged repository scan | T-M2L-015/019 + regression |
| TH-11 | Spreadsheet formula injection via OCR text | `formula_safe_display` on all text fields in CSV and display contexts | T-M2L-004/015, MA-7 |
| TH-12 | Stale value shown as fresh | Failures null current value; cached reads cite evidence frame; timeout invalidates worker generation; late messages discarded | T-M2L-009/020/021 |
| TH-13 | Journal/crop/checkpoint corruption | Atomic crop→final hash→journal flush/sync→checkpoint; journal wins; partial-tail/missing-crop/hash/divergence/orphan rules | T-M2L-012, MA-6 |
| TH-14 | Hostile/huge OCR text | Complete-code-point 4096-byte prefix, exact original length, explicit RAW_OCR_TRUNCATED, no parsing discarded suffix, normalized controls stripped | T-M2L-004 |
| TH-15 | Oversized images/messages | §0 region/frame/PNG/aggregate/JSON limits, runtime MaxImageDimension, fail closed before unbounded allocation | T-M2L-001/019/020/024/026 |
| TH-16 | Blank/protected content confused with missing text | Separate API capture, whole-frame/crop pixel health, OCR, parse and value fields; only five healthy-target near-uniform whole frames pause; EMPTY_TEXT/MISSING_SOURCE_VALUE never switches/pauses | T-M2L-005/033/039, MA-1 |
| TH-17 | Occluder/notification captured | S3 behavior is synthetic GDI-specific, not general immunity; S7 records only tested target/environment behavior; keep-visible warning until then; mini controller outside source regions | S3, S7, T-M2L-011/033, MA-3/4 |
| TH-18 | Config reuse after display change | Environment snapshot diff forces preview gate; topology/DPI change mid-run pauses | T-M2L-002/031 |
| TH-19 | Cursor metadata as movement surveillance | Default OFF visible toggle; only RECORDING when enabled; local run package only; never transmitted | T-M2L-017/018 |
| TH-20 | Worker reads beyond target (full-desktop frames) | Window scope captures the client area only; monitor scope is explicit user choice with its own warning | Code review + T-M2L-030 |
| TH-21 | Stabilized event claims missing/wrong evidence | First-candidate complete bundle with evidence_frame_id; every §0 PNG/metadata/accounted-byte cap; explicit replacement/rejection/timeout; no second capture or size-pressure eviction | T-M2L-009/026 |
| TH-22 | Unlicensed/confidential target trial | Blocking OD-M2-8/G-F permission record; authorized demo content only; default no-save; ignored local previews; stop/quarantine on surprise content | Gate review + MA-1 |

## 5. Explicit non-capabilities (future tests where marked)

No keylogging (no keyboard hooks; future T-M2L-018), no cursor control (no
SendInput/SetCursorPos; future T-M2L-018), no network (future T-M2L-018), no background service or
autostart, no full-screen persistence, no cloud upload, no live external-AI
calls. No checkmark is claimed before the M2 source and tests exist.

## 6. Residual risks

The documented-support boundary of unpackaged Windows.Media.Ocr use
(research O6) and undocumented capture semantics for hardware-accelerated
targets remain; both are tracked in the
[risk register](M2_LIVE_RISK_REGISTER.md) with S7/M2-001 as the gate.
