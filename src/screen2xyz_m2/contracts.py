"""Authoritative M2 constants and closed enums.

Single executable mirror of `docs/requirements/M2_LIVE_DATA_CONTRACTS.md`
§0. Other modules import from here; nothing redefines these values.
"""

from __future__ import annotations

SCHEMA_VERSION = "m2.1"
PROTOCOL_VERSION = "m2w.1"
# The synthetic demo target's stdin/stdout handshake version (separate from
# the real capture worker's PROTOCOL_VERSION above) - shared here so
# demo.py never has to import the Tk/ctypes-heavy adapter module just to
# read a string constant (that import previously ran the adapter's
# module-level DPI-awareness call a second time, in the main process).
DEMO_PROTOCOL_VERSION = "m2demo.1"

WORKER_COMMANDS = (
    "INIT", "REGION_SNAPSHOT", "PREVIEW", "ARM", "DISARM", "RECORD_START",
    "CAPTURE", "PAUSE", "RESUME", "HEALTH", "STOP", "SHUTDOWN",
)

BACKEND_PRINTWINDOW = "printwindow_clientonly"
BACKEND_COPYFROMSCREEN = "copyfromscreen"
BACKEND_AUTO = "auto"
BACKENDS = (BACKEND_PRINTWINDOW, BACKEND_COPYFROMSCREEN)
REQUESTABLE_BACKENDS = (BACKEND_AUTO, BACKEND_PRINTWINDOW, BACKEND_COPYFROMSCREEN)

# A probed frame is usable evidence of real content; NEAR_UNIFORM_DARK/LIGHT
# are the exact classes the owner's real-target evidence showed PrintWindow
# returning on a window it could not actually render (M2-FR-INFRA-1).
USABLE_CONTENT_STATUSES = frozenset({"CONTENT_DETECTED", "NEAR_UNIFORM_OTHER"})

SOURCE_COUNT_MIN, SOURCE_COUNT_MAX = 1, 8
REGION_MIN_PX = 8
REGION_MAX_W, REGION_MAX_H = 2000, 800
CLIENT_MAX_PX = 8192
UPSCALE_MIN, UPSCALE_MAX = 1, 4

DISPLAY_NAME_MAX_BYTES = 80
NOTES_MAX_BYTES = 512
TITLE_MAX_BYTES = 512
RAW_OCR_MAX_BYTES = 4096

MIB = 1024 * 1024
CROP_PNG_MAX_BYTES = 8 * MIB
AGGREGATE_CROP_MAX_BYTES = 64 * MIB
FULL_FRAME_PNG_MAX_BYTES = 64 * MIB
JSON_LINE_MAX_BYTES = 96 * MIB
EVIDENCE_META_MAX_PER_SOURCE = 16 * 1024
EVIDENCE_META_MAX_TOTAL = 128 * 1024
PROFILE_FILE_MAX_BYTES = 256 * 1024

COUNTDOWN_DEFAULT_S = 3
COUNTDOWN_RANGE_S = (3, 5)
INTERVAL_DEFAULT_MS = 1000
INTERVAL_MIN_MS, INTERVAL_MAX_MS = 250, 10000
HEALTH_TIMEOUT_MS = 1000
GRACEFUL_SHUTDOWN_MS = 2000
EMERGENCY_STOP_MS = 2000
RESTART_BACKOFF_MS = (0, 1000, 5000)
FAILURE_STREAK_LIMIT = 3
# Generous client-side budget for an explicit Test capture/Retest: worst case
# is two backend attempts, each individually bounded by the worker's own
# PRINTWINDOW_TIMEOUT_MS (1.5s) plus normal capture/encode overhead.
BACKEND_PROBE_TIMEOUT_MS = 8000

PAUSE_MINIMIZED_TICKS = 5
PAUSE_BLANK_FRAME_TICKS = 5

LUMA_GRID = 40
LUMA_UNIFORM_RANGE = 3.0
LUMA_DARK_MEAN = 5.0
LUMA_LIGHT_MEAN = 250.0

STABILITY_CONFIRMATIONS_DEFAULT = 1
STABILITY_CONFIRMATIONS_RANGE = (1, 5)
DEBOUNCE_DEFAULT_MS = 0
DEBOUNCE_RANGE_MS = (0, 5000)

RETENTION_CHANGED_AND_ERRORS = "changed_and_errors"
RETENTION_CHANGED_ONLY = "changed_only"
RETENTION_EVERY_TICK = "every_tick_diagnostic"
RETENTION_VALUES_ONLY = "values_only"
RETENTION_MODES = (
    RETENTION_CHANGED_AND_ERRORS, RETENTION_CHANGED_ONLY,
    RETENTION_EVERY_TICK, RETENTION_VALUES_ONLY,
)
RETENTION_DEFAULT = RETENTION_CHANGED_AND_ERRORS

CHECKPOINT_INTERVAL_MS = 15000
DISK_WARN_BYTES = 200 * MIB
DISK_STOP_BYTES = 500 * MIB

RUN_ROOT_RELATIVE = ".lab_work/m2_runs"
PROFILE_ROOT_RELATIVE = ".lab_work/m2_profiles"
DIAGNOSTICS_ROOT_RELATIVE = ".lab_work/m2_diagnostics"
CROP_PATH_TEMPLATE = "crops/{event_seq}/{source_id}.png"

SESSION_STATES = (
    "IDLE", "TARGET_SELECTED", "REGIONS_CONFIGURED", "ARMED",
    "RECORDING", "PAUSED", "STOPPING", "FINALIZED",
)
WORKER_MODES = ("SETUP", "PREVIEWED", "ARMED", "RECORDING", "PAUSED", "STOPPED")
WORKER_STATUSES = (
    "OK", "PROTOCOL_ERROR", "REQUEST_TIMEOUT", "PROCESS_EXITED",
    "RESTARTING", "UNAVAILABLE",
)
CAPTURE_STATUSES = (
    "OK", "TARGET_UNAVAILABLE", "TARGET_MINIMIZED", "REGION_OUT_OF_BOUNDS",
    "BACKEND_FAILURE", "PAYLOAD_TOO_LARGE", "DISPLAY_INVALIDATED",
)
CONTENT_STATUSES = (
    "CONTENT_DETECTED", "NEAR_UNIFORM_DARK", "NEAR_UNIFORM_LIGHT",
    "NEAR_UNIFORM_OTHER", "NOT_EVALUATED",
)
OCR_STATUSES = (
    "OK", "EMPTY_TEXT", "ENGINE_FAILURE", "NOT_RUN_UNCHANGED",
    "NOT_RUN_CAPTURE_FAILED",
)
PARSE_STATUSES = (
    "OK", "NOT_APPLICABLE", "NOT_RUN", "NO_NUMBER",
    "AMBIGUOUS_MULTIPLE_NUMBERS", "MALFORMED_NUMBER", "OUT_OF_RANGE",
    "INPUT_TRUNCATED", "SUSPECT_GLYPH_CONFUSION",
)
STABILITY_STATUSES = (
    "IMMEDIATE", "PENDING_CONFIRMATION", "CONFIRMED", "REJECTED",
    "NOT_EVALUATED",
)
VALUE_STATUSES = (
    "OK", "MISSING_SOURCE_VALUE", "OCR_FAILURE", "NO_NUMBER",
    "AMBIGUOUS_MULTIPLE_NUMBERS", "MALFORMED_NUMBER", "OUT_OF_RANGE",
    "INPUT_TRUNCATED", "UNSTABLE_READING", "SOURCE_NOT_VISIBLE",
    "TARGET_UNAVAILABLE", "CAPTURE_FAILURE", "SUSPECT_GLYPH_CONFUSION",
)
EVENT_STATUSES = ("RETAINED_CHANGE", "RETAINED_ERROR", "RETAINED_DIAGNOSTIC")
PAUSE_REASONS = (
    "USER_REQUEST", "TARGET_UNAVAILABLE", "TARGET_MINIMIZED_STREAK",
    "DISPLAY_INVALIDATED", "BACKEND_BLANK_STREAK", "WORKER_FAILURE_STREAK",
    "DISK_LIMIT", "CROP_WRITE_FAILURE", "EVIDENCE_BUFFER_LIMIT",
    "MANUAL_RECONFIGURATION",
)

RETAINABLE_ERROR_VALUE_STATUSES = frozenset({
    "OCR_FAILURE", "NO_NUMBER", "AMBIGUOUS_MULTIPLE_NUMBERS",
    "MALFORMED_NUMBER", "OUT_OF_RANGE", "INPUT_TRUNCATED",
    "SOURCE_NOT_VISIBLE", "TARGET_UNAVAILABLE", "CAPTURE_FAILURE",
    "SUSPECT_GLYPH_CONFUSION",
})

DATA_TYPES = ("number", "text", "auto", "coordinate")
SEMANTIC_ROLES = ("x", "y", "z", "metadata", "none")
COORDINATE_BASES = ("client_area", "monitor")
DECIMAL_SEPARATORS = ("point", "comma", "auto")

OUTPUT_CLASSIFICATION = "Conceptual and preliminary estimating data only."
COORDINATE_REFERENCE = "UNSPECIFIED_LOCAL"


def derive_value_status(
    capture_status: str,
    ocr_status: str,
    parse_status: str,
    stability_status: str,
    worker_status: str = "OK",
) -> str:
    """Causal mapping from data contracts §5 (order matters)."""

    if worker_status != "OK" or capture_status == "BACKEND_FAILURE":
        return "CAPTURE_FAILURE"
    if capture_status in ("TARGET_UNAVAILABLE", "TARGET_MINIMIZED"):
        return "TARGET_UNAVAILABLE"
    if capture_status == "REGION_OUT_OF_BOUNDS":
        return "SOURCE_NOT_VISIBLE"
    if capture_status in ("PAYLOAD_TOO_LARGE", "DISPLAY_INVALIDATED"):
        return "CAPTURE_FAILURE"
    if ocr_status == "ENGINE_FAILURE":
        return "OCR_FAILURE"
    if ocr_status == "EMPTY_TEXT":
        return "MISSING_SOURCE_VALUE"
    if ocr_status == "NOT_RUN_CAPTURE_FAILED":
        return "CAPTURE_FAILURE"
    if parse_status == "INPUT_TRUNCATED":
        return "INPUT_TRUNCATED"
    if parse_status in ("NO_NUMBER", "AMBIGUOUS_MULTIPLE_NUMBERS",
                        "MALFORMED_NUMBER", "OUT_OF_RANGE",
                        "SUSPECT_GLYPH_CONFUSION"):
        return parse_status
    if stability_status == "REJECTED":
        return "UNSTABLE_READING"
    return "OK"
