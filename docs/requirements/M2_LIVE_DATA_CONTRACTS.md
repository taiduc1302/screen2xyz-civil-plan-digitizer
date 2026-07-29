# M2-Live Data Contracts

Status: M2-000 planning. All schemas carry `schema_version: "m2.1"`;
consumers must reject unknown major versions and ignore unknown fields
within a major version. JSON everywhere; UTF-8; timestamps are UTC ISO-8601
plus a monotonic offset in ms from session start (ordering authority).

## 0. Authoritative constants and enums

This section is the single source of truth for cross-document constants.
Other M2-Live documents may explain a value, but must not redefine it.
Every value remains a planning recommendation until the applicable owner
decision is recorded.

| Concern | Authoritative value |
|---|---|
| Planning task / branch | `M2-000` / `plan/m2-live-region-watch` |
| Future implementation branch | `feat/m2-live-region-watch-impl` (must not be created before the owner gates) |
| Schema / worker protocol | `m2.1` / `m2w.1` |
| Worker commands | `INIT`, `REGION_SNAPSHOT`, `PREVIEW`, `ARM`, `DISARM`, `RECORD_START`, `CAPTURE`, `PAUSE`, `RESUME`, `HEALTH`, `STOP`, `SHUTDOWN` |
| Backend identifiers | `printwindow_clientonly`, `copyfromscreen`; future seam `windows_graphics_capture` |
| Source count | 1-8 enabled sources; acceptance demonstrates at least 3 |
| Source region | minimum 8x8 physical px; maximum 2000x800 physical px; fully inside scope |
| Client-frame bound | maximum 8192x8192 physical px and within the worker-reported OCR/runtime limit |
| Upscaling | integer 1-4; every resulting dimension must remain within the runtime `MaxImageDimension` |
| Source/display text | display name <=80 UTF-8 bytes; notes <=512; target title/process fields <=512 each |
| Raw OCR | longest complete-code-point UTF-8 prefix <=4096 bytes; truncation is explicit and never parsed as complete input |
| PNG/protocol bounds | crop PNG <=8 MiB decoded; all changed crop PNGs <=64 MiB decoded per response; setup full-frame PNG <=64 MiB; JSON line <=96 MiB with a bounded reader |
| Candidate evidence buffer | one bundle/source; PNG payload <=8 MiB/source and <=64 MiB total; canonical UTF-8 metadata <=16 KiB/source and <=128 KiB total; accounted owned bytes <=8 MiB + 16 KiB/source and <=64 MiB + 128 KiB total; no size-pressure eviction |
| Setup countdown | default 3 s; allowed integer range 3-5 s |
| Capture interval | default 1000 ms; range 250-10000 ms |
| Request timeout | `max(2000 ms, 2 * interval_ms)` |
| Health / graceful shutdown | 1000 ms / 2000 ms; emergency stop hard bound <=2000 ms independent of interval |
| Restart backoff | delays 0, 1000, then 5000 ms for failure 3 and every later failure (saturating), between teardown and the next automatic or explicit-Retry generation spawn for the context-specific counter below |
| Setup-state failure context | Any request issued while UI state is `TARGET_SELECTED`, `REGIONS_CONFIGURED`, or `ARMED`—including post-recording disarm/re-preview repair—uses the setup counter and leaves that setup state unchanged. Failures 1-2 automatically spawn/INIT after backoff. At count >=3, no replacement is spawned: set `setup_worker_blocked=true` and `worker_status=UNAVAILABLE`, disable every worker-dependent action, and require **Retry worker**. Retry waits any remainder of the saturated 5000 ms measured from teardown, spawns a fresh generation, and sends only INIT—never the failed command. Successful INIT clears the flag but not the counter; the next successful post-INIT setup/state request resets it. Failed Retry INIT increments the counter and remains blocked. |
| Recording-state failure context | Requests issued in `RECORDING` or `PAUSED` use the recording counter. The first successful `RECORD_START` in a run initializes it at zero; later `DISARM`/repair/`RECORD_START` cycles in that same live run preserve it. Every recording worker/capture failure count >=3 auto-pauses; Resume and re-arm/re-start do not reset it, and only a successful `CAPTURE` resets it. |
| State-command timeout | A timed-out `PAUSE` resolves the latched user intent to UI `PAUSED` before teardown and replacement INIT restores PAUSED. A timed-out `RESUME` remains PAUSED and requires another explicit Resume. Both increment the recording failure counter. `STOP`, `SHUTDOWN`, UI close, and Emergency Stop are terminal: they bypass both failure counters/backoff and never spawn a replacement. |
| Recording automatic-pause thresholds | target closed/identity invalid: 1; minimized: 5 consecutive recording ticks; whole-frame near-uniform: 5 recording ticks; worker/capture failures after successful `RECORD_START`: 3; display/client/DPI invalidation: immediate. Before recording, target/display invalidation returns to or remains in the applicable setup state and requires repair/re-preview; it never creates a PAUSED recording. |
| Pixel-health heuristic | sample at most a 40x40 grid; near-uniform when luma range <=3.0; dark when mean <=5.0; light when mean >=250.0; otherwise near-uniform-other |
| Stability | confirmations default 1, range 1-5; debounce default 0 ms, range 0-5000 ms |
| Candidate timeout | `max(10000 ms, confirmations * interval_ms + debounce_ms + request_timeout_ms)` |
| Retention modes | `changed_and_errors` (default), `changed_only`, `every_tick_diagnostic`, `values_only` |
| Checkpoint | every 15000 ms, after any journal append it reflects |
| Disk thresholds | warning 200 MiB; hard stop 500 MiB per session (pending OD-M2-3) |
| Cursor metadata | optional and visible; default `false` pending OD-M2-5 |
| Profile / run roots | ignored `.lab_work/m2_profiles/` and `.lab_work/m2_runs/<run_id>/` |
| Crop path | `crops/<event_seq>/<source_id>.png` |
| Milestones / test namespaces | `M2-000`..`M2-011`; `T-M2L-*`; `MA-1`..`MA-8` |

`PW_RENDERFULLCONTENT` is not a backend identifier and must never be a
production dependency. Decimal MB is not used for the disk or memory caps;
the values above are binary MiB.

Closed enums (defined here once):

| Field | Values |
|---|---|
| `session_state` | `IDLE`, `TARGET_SELECTED`, `REGIONS_CONFIGURED`, `ARMED`, `RECORDING`, `PAUSED`, `STOPPING`, `FINALIZED` |
| `worker_mode` | `SETUP`, `PREVIEWED`, `ARMED`, `RECORDING`, `PAUSED`, `STOPPED` |
| `worker_status` | `OK`, `PROTOCOL_ERROR`, `REQUEST_TIMEOUT`, `PROCESS_EXITED`, `RESTARTING`, `UNAVAILABLE` |
| `setup_worker_blocked` | `false`, `true`; UI-only orthogonal interlock, permitted only in `TARGET_SELECTED`, `REGIONS_CONFIGURED`, or `ARMED`, including same-run repair; not a worker mode or session state |
| `capture_status` | `OK`, `TARGET_UNAVAILABLE`, `TARGET_MINIMIZED`, `REGION_OUT_OF_BOUNDS`, `BACKEND_FAILURE`, `PAYLOAD_TOO_LARGE`, `DISPLAY_INVALIDATED` |
| `frame_content_status` / `crop_content_status` | `CONTENT_DETECTED`, `NEAR_UNIFORM_DARK`, `NEAR_UNIFORM_LIGHT`, `NEAR_UNIFORM_OTHER`, `NOT_EVALUATED` |
| `ocr_status` | `OK`, `EMPTY_TEXT`, `ENGINE_FAILURE`, `NOT_RUN_UNCHANGED`, `NOT_RUN_CAPTURE_FAILED` |
| `parse_status` | `OK`, `NOT_APPLICABLE`, `NOT_RUN`, `NO_NUMBER`, `AMBIGUOUS_MULTIPLE_NUMBERS`, `MALFORMED_NUMBER`, `OUT_OF_RANGE`, `INPUT_TRUNCATED` |
| `stability_status` | `IMMEDIATE`, `PENDING_CONFIRMATION`, `CONFIRMED`, `REJECTED`, `NOT_EVALUATED` |
| `value_status` | `OK`, `MISSING_SOURCE_VALUE`, `OCR_FAILURE`, `NO_NUMBER`, `AMBIGUOUS_MULTIPLE_NUMBERS`, `MALFORMED_NUMBER`, `OUT_OF_RANGE`, `INPUT_TRUNCATED`, `UNSTABLE_READING`, `SOURCE_NOT_VISIBLE`, `TARGET_UNAVAILABLE`, `CAPTURE_FAILURE` |
| `event_status` | `RETAINED_CHANGE`, `RETAINED_ERROR`, `RETAINED_DIAGNOSTIC` |
| `pause_reason` | `USER_REQUEST`, `TARGET_UNAVAILABLE`, `TARGET_MINIMIZED_STREAK`, `DISPLAY_INVALIDATED`, `BACKEND_BLANK_STREAK`, `WORKER_FAILURE_STREAK`, `DISK_LIMIT`, `CROP_WRITE_FAILURE`, `EVIDENCE_BUFFER_LIMIT`, `MANUAL_RECONFIGURATION` |

No schema field is named only `status`. `value_status` is a derived,
user-facing summary; the causal fields remain independently available.
`normalized_value` is governed by `parse_status`, not by
`stability_status`, so the live grid can show a provisional parsed value
without presenting it as stable.

## 1. Source configuration (`sources` inside session/profile)

```json
{
  "schema_version": "m2.1",
  "source_id": "src-1",
  "display_name": "Longitude",
  "enabled": true,
  "data_type": "number",            // "number" | "text" | "auto"
  "semantic_role": "x",             // "x" | "y" | "z" | "metadata" | "none"
  "unit": "deg",                    // optional, free text, export metadata only
  "numeric_range": {"min": -180.0, "max": 180.0},   // optional, number mode
  "decimal_precision_max": 6,       // optional; exceeding => MALFORMED_NUMBER
  "decimal_separator": "point",     // "point" | "comma" | "auto"
  "rect": {"x": 812, "y": 64, "w": 180, "h": 28},   // physical px, coordinate_basis space
  "coordinate_basis": "client_area",// "client_area" | "monitor"
  "ocr_language": "en-US",
  "preprocess": {"upscale_factor": 1},              // 1..4; bounded by MaxImageDimension
  "stability": {"confirmations": null, "min_change_threshold": null, "debounce_ms": null},
  "notes": ""
}
```

MVP fields: all above. Deferred (documented, not implemented): per-source
OCR language ≠ session language, locale-mode auto-detection beyond
point/comma, regex extraction patterns.

Validation rules: `display_name` unique and non-empty; rect ≥8×8 px,
≤2000×800 px, fully inside the scope bounds; at most one enabled source
per x/y/z role (assigning a taken role prompts move-or-cancel); **x/y/z
roles are assignable only to `data_type: "number"` sources** (auto/text
refused — XYZ requires a fixed numeric kind); `min_change_threshold` only
valid for number mode; `preprocess.upscale_factor` 1..4; null stability
values inherit session defaults. Source IDs are generated (`src-[a-z0-9-]+`)
and never derived from display text. All sizes and ranges are the §0
constants; validation occurs both when a profile is loaded and immediately
before any worker request.

## 2. Profile (`.lab_work/m2_profiles/<profile_id>.json`)

`{schema_version, profile_id, profile_display_name, created_utc, scope, sources[],
session_defaults{interval_ms, retention_mode, stability{...},
cursor_metadata}, environment_snapshot}` where `environment_snapshot` =
`{window:{title, process_name, client_w, client_h, dpi}, monitors:[{device,
x, y, w, h, dpi}], virtual_screen:{x, y, w, h}, backend, captured_utc}`.
Loading a profile compares the live environment to the snapshot; any
mismatch (missing window, different client size, DPI, topology) forces the
preview gate with a shown diff (M2-FR-031). A profile never auto-selects a
window by title alone — the user confirms the resolved HWND.

`profile_id` is generated and allowlisted; the display name is data, never
a path component. Writes resolve under the ignored profile root and reject
path traversal. Profile files are size-bounded to 256 KiB. Window titles
and process names are local potentially sensitive metadata: control
characters are removed, the UTF-8 bounds in §0 apply, and raw identity is
not copied into retained evaluation evidence, PR text, or public output.

## 3. Session (`session.json`, written at ARMED)

`{schema_version, session_id, run_dir_name, created_utc, app_version,
git_commit, scope{type:"window"|"monitor", hwnd, pid, title, monitor_id},
locked_backend{name:"printwindow_clientonly"|"copyfromscreen", reason},
interval_ms, retention_mode, stability_defaults, cursor_metadata:bool,
sources[], environment_snapshot, configuration_revision,
xyz_eligibility{eligible:bool,
x_source_id?, y_source_id?, z_source_id?, reason}}`.

## 4. Frame (embedded in worker responses and events)

`{frame_id: "<session_id>-f<seq>", frame_seq, capture_utc,
monotonic_offset_ms, window:{exists, iconic, client_w, client_h, origin_x,
origin_y, dpi}, capture_status, frame_content_status,
cursor?:{screen_x, screen_y, client_x, client_y},
timings:{capture_ms, ocr_ms_total, tick_ms}}`. One frame per tick,
produced by exactly one capture call; all observations of a tick reference
exactly this frame. `monotonic_offset_ms` and `tick_ms` are stamped by the
**Python scheduler** (sole monotonic authority); the worker supplies only
`capture_utc`, window/cursor data, and the two duration fields. Cursor is
omitted when the metadata toggle is off.

**Frameless events:** when a tick fails without a worker response (request
timeout or worker crash/restart), the event's `frame` is `null` and a
`scheduler_context: {monotonic_offset_ms, worker_status, reason}` object
carries timing and cause. Every observation has
`capture_status:"BACKEND_FAILURE"`, `ocr_status:"NOT_RUN_CAPTURE_FAILED"`,
`parse_status:"NOT_RUN"`, `stability_status:"NOT_EVALUATED"`, and
`value_status:"CAPTURE_FAILURE"`; normalized values and crop fields are
null. A storage failure is different: it is shown as a non-durable critical
UI state and appended as a best-effort `RETAINED_ERROR` only if the journal
itself remains writable. The design never promises a durable error event on
failed storage.

## 5. Observation (per source, per tick)

```json
{
  "source_id": "src-1",
  "capture_status": "OK",
  "crop_content_status": "CONTENT_DETECTED",
  "ocr_status": "OK",
  "parse_status": "OK",
  "stability_status": "IMMEDIATE",
  "value_status": "OK",
  "raw_text": "-123.654321",
  "raw_truncated": false,
  "raw_original_utf8_bytes": 11,
  "warning_codes": [],
  "normalized_value": "-123.654321",
  "value_kind": "number",
  "pixel_sha256": "…",
  "crop_w": 180, "crop_h": 28,
  "ocr_executed": true,
  "confirmation": "new_ocr",
  "ocr_ms": 5,
  "ocr_ref": null,
  "evidence": null
}
```

The closed enums are defined only in §0. Their causal mapping is:

| Condition | Causal fields | Derived `value_status` |
|---|---|---|
| Successful capture, OCR and parse | `capture_status=OK`, `ocr_status=OK`, `parse_status=OK` | `OK` (regardless of pending stability) |
| OCR returned no text | `ocr_status=EMPTY_TEXT`, `parse_status=NOT_RUN` | `MISSING_SOURCE_VALUE` |
| OCR engine failed | `ocr_status=ENGINE_FAILURE`, `parse_status=NOT_RUN` | `OCR_FAILURE` |
| Number parsing failed | `parse_status` carries the exact parser outcome | same exact parser outcome |
| Raw input exceeded its bound | `parse_status=INPUT_TRUNCATED`, `warning_codes` includes `RAW_OCR_TRUNCATED` | `INPUT_TRUNCATED` |
| Candidate did not stabilize | causal capture/OCR/parse fields remain intact; `stability_status=REJECTED` | `UNSTABLE_READING` |
| Region is outside the live scope | `capture_status=REGION_OUT_OF_BOUNDS` | `SOURCE_NOT_VISIBLE` |
| Target is gone/minimized | `capture_status=TARGET_UNAVAILABLE` or `TARGET_MINIMIZED` | `TARGET_UNAVAILABLE` |
| Worker/backend/transport failed | non-OK `worker_status` or `capture_status=BACKEND_FAILURE` | `CAPTURE_FAILURE` |

`normalized_value` is present when parsing produced a value, including a
provisional value whose `stability_status` is `PENDING_CONFIRMATION` or
`REJECTED`. It is null for capture, OCR, parse, or truncation failure. A
previous value is never substituted for a failed current read. Skipped
ticks have no observation and are counted only in
`skipped_ticks_since_last` and diagnostics.

**Raw bound.** `raw_text` is the verbatim OCR string if its UTF-8 encoding
is at most 4096 bytes. When longer, it is the longest prefix ending at a
complete UTF-8 code point and not exceeding 4096 bytes;
`raw_truncated:true`, `raw_original_utf8_bytes:<exact length>`, and warning
`RAW_OCR_TRUNCATED` are mandatory. Truncation is never silent and the
discarded suffix is never used to create a parsed/normalized value:
`parse_status=INPUT_TRUNCATED` and `normalized_value=null`. When OCR did
not execute, `raw_text:""`, `raw_original_utf8_bytes:null`.

**Cached observations.** `confirmation:"pixel_hash_cached"` requires
`ocr_executed:false`, `ocr_status:"NOT_RUN_UNCHANGED"`, and `ocr_ref`
naming the earlier frame whose identical `pixel_sha256` was OCRed. It
carries the prior parse outcome and normalized value explicitly, but is
never labelled fresh OCR. A retained event that depends on the cached
confirmation embeds the self-contained candidate `evidence` bundle
defined below, so recovery never relies on an unjournaled provisional
frame.

### Parsing (public `screen2xyz_m2` parser — no baseline private imports)

**NUMBER mode:** strip surrounding whitespace; candidate = maximal substrings matching
a signed decimal with optional thousands separators and unit suffix
(configured separator mode; `auto` accepts either but a mixed string like
`1,234.5` resolves comma-as-thousands only when both present and pattern is
unambiguous, else `MALFORMED_NUMBER`). **Closed sign policy:** ASCII `+`
and `-` are accepted only when directly adjacent to the first digit. The
minus variants U+2212, U+2010, U+2011, U+2012, U+2013, U+2014, U+FE63,
and U+FF0D are accepted only in that same position and normalized to ASCII
`-`; record `sign_normalized:true` and `original_sign_code_point`. Any
whitespace between a sign and its digit is rejected as
`MALFORMED_NUMBER`. Before candidate extraction, any other code point of
Unicode category `Pd`, or whose Unicode name contains `MINUS` or `PLUS`
(case-insensitive), is treated as a disallowed sign when immediately followed
by a digit or by whitespace then a digit. The entire numeric parse is
`MALFORMED_NUMBER`—the glyph is never treated as a boundary that allows the
following digits to become positive. The same whitespace rule applies to an
allowed sign. This Unicode-category/name rule is the closed rejection
algorithm; it does not guess glyph intent. Zero candidates → `NO_NUMBER` (`EMPTY_TEXT` is an OCR
outcome, not a parser result). **More than one candidate →
`AMBIGUOUS_MULTIPLE_NUMBERS`, never auto-picked** — note this makes
station notation (`0+250.00`) and space-grouped numbers (`1 234.56`)
unsupported as numeric in MVP (documented; use text type; per-source
extraction patterns are a deferred feature). Glyph confusables (O/0,
I/l/1) are **report-only**: no substitution is ever applied; a letter
inside digits ⇒ `MALFORMED_NUMBER`. Range check ⇒ `OUT_OF_RANGE`;
precision check ⇒ `MALFORMED_NUMBER`. Canonical form: `-?d+(.d+)?` with
point separator, no thousands separators, precision preserved as read.

**TEXT mode:** bounded raw preserved; normalized = whitespace-collapsed, control
characters removed, formula-safe escaping applied at export time (reuse
`formula_safe_display`). Empty OCR leaves parsing `NOT_RUN` and derives
`MISSING_SOURCE_VALUE`. Truncated input is not normalized as complete text.

**AUTO mode (conservative):** resolves to number iff exactly one numeric
candidate exists AND non-numeric residue is only whitespace/punctuation;
otherwise resolves to text. Auto never guesses among multiple numbers.

## 6. Retained event (`events.jsonl`, one JSON object per line)

`{schema_version, event_seq, event_id: "<session_id>-e<seq>", event_status,
worker_status, frame:{...}|null, scheduler_context:{monotonic_offset_ms, worker_status,
reason}|null, observations:[...], stable_signature:{<source_id>:
{value_kind, normalized_value}}, changed_source_ids:[...],
retention_reason_codes:[...], crops_saved:{<source_id>:
{path, pixel_sha256, crop_artifact_sha256, evidence_frame_id}|null},
skipped_ticks_since_last, retention_mode}`.

For a retained event, each observation has an `evidence` object when OCR
or crop evidence contributed to the decision:

`{evidence_frame_id, raw_text, raw_truncated,
raw_original_utf8_bytes, warning_codes, parse_status, normalized_value,
value_kind, pixel_sha256, crop_path|null, crop_artifact_sha256|null}`.

That object is self-contained. A cached confirmation can therefore retain
the raw OCR and first-candidate crop even when the evidence frame itself
was provisional and never journaled. The event `frame` remains the single
confirmation/current tick shared by every observation; evidence frame IDs
are provenance links, not alternate observation frames.

### 6a. Retention decision and precedence (single source of truth)

Retention maintains a per-source **stable comparator** plus a `baseline_seeded`
bit. On the first stable OK observation for a source, it seeds that source's
comparator without creating a change event. Sources seed independently: an
unseeded, pending, missing, unstable, or failed source is never represented as
deletion of another source and cannot make the map differ spuriously. On later
ticks, only a stable OK value for an already-seeded source is compared; a real
change updates that source in the post-decision comparator. If an event also
contains another source's first stable value, that source is seeded but omitted
from `changed_source_ids`.

The event's `stable_signature` is the complete post-decision historical
comparator for all seeded sources, not a current-observation view. Non-OK or
pending observations leave their source entry unchanged. The UI must use
`observations` for current values and never substitute a comparator value into
a failed current observation. A source whose first stable OK follows a
previously retained error both seeds and emits the one required
`ERROR_RECOVERED` event; `changed_only`, which did not retain that error, only
seeds it. Retention then uses this precedence:

| Priority | Condition | Result |
|---:|---|---|
| 1 | Any source transitions into a retainable error and mode is `changed_and_errors`, `every_tick_diagnostic`, or `values_only` | `event_status=RETAINED_ERROR` (also record simultaneous changed sources) |
| 2 | One or more already-seeded stable values change, or a retained error recovers to stable OK | `event_status=RETAINED_CHANGE` |
| 3 | Mode is `every_tick_diagnostic` | `event_status=RETAINED_DIAGNOSTIC` |
| 4 | Otherwise | no journal event |

A retainable-error transition occurs when `value_status` changes into one
of `OCR_FAILURE`, `NO_NUMBER`, `AMBIGUOUS_MULTIPLE_NUMBERS`,
`MALFORMED_NUMBER`, `OUT_OF_RANGE`, `INPUT_TRUNCATED`,
`SOURCE_NOT_VISIBLE`, `TARGET_UNAVAILABLE`, or `CAPTURE_FAILURE` from a
different value status. Repeating the identical error retains nothing
outside diagnostic mode. `MISSING_SOURCE_VALUE` is not retainable because
hover-dependent fields may legitimately be empty; `UNSTABLE_READING` is
also diagnostic-only. Their appearance does not mutate the last retained
stable signature. No other non-OK outcome mutates it either. A transition from a retained error back to a stable OK
reading is retained once as `ERROR_RECOVERED`, even if the normalized value
equals its pre-error value.

Mode semantics are closed:

- `changed_and_errors` applies priorities 1 and 2 and writes required audit
  crops.
- `changed_only` suppresses error transitions. It applies priority 2 only when
  the stable signature actually changes; because it did not retain the error,
  a same-value recovery alone is not an event. Required change crops are
  written.
- `every_tick_diagnostic` applies priorities 1 and 2, then retains every other
  completed or frameless scheduled tick as diagnostic. A changed hash is
  persisted once; an unchanged diagnostic observation references the prior
  same-hash artifact if one exists, otherwise its crop reference is null. It
  never triggers a second capture.
- `values_only` uses the same event eligibility and precedence as
  `changed_and_errors`, but writes no crop PNGs. Evidence preserves bounded raw,
  parse, value, pixel-hash, and evidence-frame provenance with crop fields null;
  received crop bytes are discarded after the event decision.

On a successful framed event `worker_status=OK`. A frameless transport failure
stores the exact non-OK value both at event level and in `scheduler_context` so
the failure remains self-contained. No generic status field is introduced.

### 6b. Stabilized candidate evidence ownership

With confirmations=1, the current frame is both event and evidence frame.
With confirmations>=2, Python buffers exactly one candidate evidence
bundle per source: the first frame that introduced the candidate's
`{value_kind, normalized_value, value_status}` plus its raw/truncation,
parse, pixel-hash and, unless mode is `values_only`, changed-crop PNG bytes.
When later frames confirm the
candidate, that **first candidate frame** is retained as evidence and its
`evidence_frame_id` is explicit. A later same-value crop never silently
replaces it.

The §0 PNG-payload, canonical-metadata, and accounted-owned-byte caps are all
enforced before ownership transfers into the buffer. Metadata accounting uses
the canonical UTF-8 encoding of the bounded evidence fields; the 1-8 source
count also bounds interpreter-object overhead, which is measured separately in
the soak test and is never treated as part of the byte-exact protocol claim. A
new candidate for the same source replaces and releases the old owned bundle
without persisting it. A parse/capture/OCR failure, different candidate, confirmation
rejection, candidate timeout, Pause, Stop, or shutdown discards the pending
bundle. Confirmation writes the bundle according to the retention mode and
releases it only after the journal append succeeds. A crop-write failure
keeps the bounded bundle while the session is paused for an explicit retry;
Stop discards it after the best-effort error/recovery notice. The system
never evicts another source under memory pressure: exceeding any cap
rejects the new bundle, raises `EVIDENCE_BUFFER_LIMIT`, and pauses. No event
may claim crop evidence that was not written and hashed.

### 6c. Crash-safe write and recovery ordering

For every retained event:

1. Atomically write and flush each required crop to its final run-relative
   path (temporary file in the same directory, then replace).
2. Hash the final PNG file bytes into `crop_artifact_sha256`; keep
   `pixel_sha256` separate for pixel-change detection.
3. Append one complete JSON line referencing those final paths/hashes,
   flush it, and call the platform durability primitive (`fsync`/equivalent).
4. Only afterward, atomically replace a due checkpoint. A checkpoint must
   never lead the journal event it claims.

`events.jsonl` is canonical and wins over the checkpoint. Recovery ignores
only an unterminated partial final line and emits `PARTIAL_FINAL_LINE`; a
malformed complete line or sequence break fails closed and publishes no
exports. A missing or hash-mismatched referenced crop does not crash
recovery: the recovered view sets that crop reference to null and emits
`MISSING_CROP` or `CROP_HASH_MISMATCH`, leaving the canonical JSONL
unchanged. Checkpoint divergence emits `CHECKPOINT_DIVERGENCE` and the
journal state wins. Crops written before a crash but never referenced are
reported as `ORPHAN_CROP`, ignored, and not deleted. Final exports are
rebuilt only from the canonical valid journal events.

## 7. Artifact matrix (tiers × artifacts)

| Tier | UI | events.jsonl | crops | checkpoint |
|---|---|---|---|---|
| Provisional (every tick) | live grid + diagnostics | only in `every_tick_diagnostic` mode | changed-hash PNG once; unchanged diagnostic events reference the prior same-hash artifact without duplicate bytes | no |
| Stable state | current-state row highlight | no | no | every 15 s |
| Retained event | history row | 1 append | per retention mode | via next checkpoint |

## 8. Checkpoint (`state_checkpoint.json`, atomic replacement)

`{schema_version, session_id, written_utc, last_event_seq, last_frame_seq,
stable_signature, last_value_status_by_source,
counters{ticks, skipped, ocr_errors, events, disk_bytes}}`. It is written
to a same-directory temporary file, flushed, then atomically replaced; it
is never edited in place. Used by `recover` for cross-checking only; the
journal remains authoritative.

## 9. Exports (finalize or `recover`)

- **Wide CSV** `events_wide.csv`: `event_seq, event_id, event_status, capture_utc,
  monotonic_offset_ms, cursor_screen_x?, cursor_screen_y?,` then per
  enabled source `"<display_name> [value]", "<display_name> [value_status]"`;
  one row per retained event; formula-safe.
- **Long CSV** `observations_long.csv`: `event_seq, capture_utc, worker_status, source_id,
  display_name, value_kind, capture_status, ocr_status, parse_status,
  stability_status, value_status, raw_text_display, normalized_value,
  ocr_executed, confirmation, evidence_frame_id, crop_path`.
- **Summary** `run_summary.json`: counters, timings percentiles, backend,
  retention mode, XYZ eligibility outcome, and a
  `sanitized_environment_snapshot` containing scope type, client dimensions and
  DPI, ordinalized monitor geometry/DPI, virtual-screen geometry, backend, and
  capture time. It uses a bounded user label (default `Selected target`) and
  excludes HWND, PID, raw title, process name, and raw monitor device IDs.
- **XYZ** `points.xyz` (+ `points_xyz_metadata.json`): only under the
  M2-FR-066 filter gate; rows = `RETAINED_CHANGE` events whose X/Y/Z
  observations all have `value_status: "OK"` and a stable/confirmed number
  value (necessarily `value_kind: "number"` —
  roles are restricted to number sources); format `"<x> <y> <z>"`;
  metadata records axis order (`x y z` explicit source names), row count,
  **`excluded_event_count`** (change events dropped by the filter),
  `coordinate_reference: "UNSPECIFIED_LOCAL"` (always, in MVP), and the
  output classification line. `recover` applies the identical gate.
- **Manifest** `evidence_manifest_sha256.txt` over the run dir
  (`write_manifest` reuse).

Determinism: export ordering is strictly by `event_seq`. Given the same valid
journal, session configuration, and finalization mode, each export is
byte-deterministic. Direct finalization and `recover` produce byte-identical
wide CSV, long CSV, XYZ, and XYZ metadata payloads. `run_summary.json`
intentionally differs in `recovered` and may differ in explicitly
best-effort timing fields; its manifest therefore may differ too. No broader
cross-mode byte-equality claim is made.

## 10. Worker protocol messages

This document is normative; architecture §7 explains the lifecycle.
`protocol_version: "m2w.1"`. Commands are exactly the §0 set.
`REGION_SNAPSHOT` is an explicit-click, one-frame full-client response and
is legal only in `TARGET_SELECTED` or `REGIONS_CONFIGURED`.
`PREVIEW` is a distinct explicit-click, one-frame configured-region OCR
response and is legal only in `REGIONS_CONFIGURED`, before `ARM`. Neither
operation starts a loop or writes a run artifact. `CAPTURE` is legal only
in `RECORDING` and is the only periodic operation.

The Python `session_state` is authoritative. The worker does not infer local
source/region edits; it maintains the separate closed `worker_mode`. Every
post-INIT request carries `ui_session_state` and `configuration_revision`.
Target/source/region/backend edits increment the revision locally. A setup
request with a newer revision resets worker mode to `SETUP` and invalidates any
prior preview. `PREVIEW` carries the complete bounded source/region
configuration; success records that exact revision and enters `PREVIEWED`.
`ARM` is accepted only from `PREVIEWED` at the same revision. This request
envelope synchronizes `TARGET_SELECTED` to `REGIONS_CONFIGURED` without adding
an undeclared command, and a revision jump on `ARM` fails closed.

Exact command legality:

| Command | Legal condition / UI state | Effect |
|---|---|---|
| `INIT` | Exactly once in each fresh worker generation, before every other command | Negotiate protocol, capabilities, DPI context, and bounds; restore the same live UI session state under the rule below; set the mapped worker mode; no UI-state transition |
| `REGION_SNAPSHOT` | UI `TARGET_SELECTED` or `REGIONS_CONFIGURED`; worker `SETUP` after revision synchronization | One full-client frame; no persistence or state transition |
| `PREVIEW` | UI `REGIONS_CONFIGURED`; worker `SETUP` at the request revision | One configured-region frame/OCR result; on success worker enters `PREVIEWED`; no UI-state transition |
| `ARM` | UI `REGIONS_CONFIGURED` after explicit preview; worker `PREVIEWED` at the exact revision | Lock configuration/backend; UI and worker enter `ARMED` |
| `DISARM` | UI `ARMED`, or `PAUSED` when reconfiguration is required | Invalidate preview, increment/synchronize revision, enter UI `REGIONS_CONFIGURED` and worker `SETUP`; recording must pause first |
| `RECORD_START` | UI and worker `ARMED` | Enter `RECORDING`; also used after a disarm/re-preview/re-arm repair under the incremented configuration revision |
| `CAPTURE` | UI and worker `RECORDING` | Exactly one periodic frame/response; no state transition |
| `PAUSE` | UI and worker `RECORDING` | Enter `PAUSED` and stop scheduling captures |
| `RESUME` | UI and worker `PAUSED` only when no reconfiguration is required | Re-enter `RECORDING` without a setup capture |
| `HEALTH` | Any initialized mode, only between requests | Health reply; no state transition |
| `STOP` | UI and worker `RECORDING` or `PAUSED` | Enter UI `STOPPING` and worker `STOPPED`; Python finalizes |
| `SHUTDOWN` | Any initialized non-recording mode, or after `STOP`; normal recording/paused shutdown must send `STOP` first | Exit worker; emergency stop may instead terminate the process within the hard bound |

Every setup button press produces at most one frame. A near-uniform result may
offer **Compare fallback**; accepting it starts another visible countdown and
sends a separate one-frame `REGION_SNAPSHOT` or `PREVIEW` with the alternate
backend. No automatic dual capture or hidden retry is permitted.

`INIT` includes `session_id`, `configuration_revision`, and
`restore_session_state`, which is one of `TARGET_SELECTED`,
`REGIONS_CONFIGURED`, `ARMED`, `RECORDING`, or `PAUSED`. The first generation
uses the current pre-worker UI state. A replacement generation may restore
`RECORDING` or `PAUSED` only inside the same still-running UI process, for the
same session/revision, after that in-memory session previously completed
`ARM` and explicit `RECORD_START`. A newly launched/recovered UI can never
restore `RECORDING`; it starts non-recording and requires preview/ARM/Start.
The reply echoes the restored state. Any mismatch fails initialization. INIT
state restoration itself performs no capture. `TARGET_SELECTED` and
`REGIONS_CONFIGURED` restore to worker `SETUP`; `ARMED`, `RECORDING`, and
`PAUSED` map directly. A worker lost after preview but before ARM restores to
`SETUP`, so the user must preview again.

Every response echoes `request_id`, `worker_generation`,
`configuration_revision`, and `worker_mode`; a response
without a live matching four-field tuple is dropped and logged. Malformed or oversized
lines fail closed before unbounded allocation, terminate that worker
generation, and follow the restart policy. `INIT` capability reply:
`{protocol_version, max_image_dimension,
available_languages[], backends:{printwindow_clientonly: true,
copyfromscreen: true}, dpi_awareness: "per_monitor_v2", restore_session_state,
worker_mode,
limits:{max_crop_png_bytes,max_aggregate_crop_bytes,max_full_frame_png_bytes,
max_json_line_bytes}}` — a different DPI or limit contract is a startup
failure.

Response ownership:

- `REGION_SNAPSHOT` returns one bounded `frame_png_b64` for the picker and no
  configured-source crop payload.
- `PREVIEW` returns frame metadata plus bounded crop bytes and OCR for every
  configured source, but no full-client PNG.
- `CAPTURE` accepts prior `pixel_sha256` values. For every changed hash it
  automatically returns the crop PNG bytes from that same frame; unchanged
  hashes return metadata only. There is no `want_crops` field and no second
  evidence capture.
- The Python client decodes into the bounded candidate buffer and writes
  bytes only for retained change/error/diagnostic evidence. Unretained
  changed bytes are discarded. An unchanged diagnostic event references a
  previously persisted same-hash crop rather than duplicating bytes.

The worker rejects any response whose encoded JSON would exceed 96 MiB even
when each decoded-from-base64 PNG is individually within its own cap. Thus a
response never combines the 64 MiB setup full-frame payload with the 64 MiB
aggregate crop payload.

The worker supplies causal `capture_status`, `frame_content_status`,
`crop_content_status`, and `ocr_status`; Python adds `parse_status`,
`stability_status`, `value_status`, and `event_status`. No generic
`status` field crosses the protocol or journal.

## 11. Mismatch and duplication rules (summary)

Duplicate source name → reject at entry. Second x/y/z assignment →
move-or-cancel prompt. Incomplete X/Y/Z at finalize → XYZ skipped with
recorded reason (never an error). Window moved → transparent (per-tick
origin re-query). Client resized / DPI changed / topology changed → pause +
disarm + `REGIONS_CONFIGURED`; an explicit `PREVIEW` and new `ARM` are
required before `RECORD_START` resumes the same run under an incremented
configuration revision. Profile loaded on different topology → forced
preview with diff. Two windows same title → explicit user resolve (HWND
shown).
