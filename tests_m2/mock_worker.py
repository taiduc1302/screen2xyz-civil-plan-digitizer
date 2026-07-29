"""Python mock worker speaking protocol m2w.1 for contract tests.

Behavior selected by argv[1]: normal | slow_capture | stale_then_ok |
malformed | bad_dpi | exit_after_init | init_error
"""

from __future__ import annotations

import json
import sys
import time

behavior = sys.argv[1] if len(sys.argv) > 1 else "normal"
generation = ""
revision = 0
mode = "SETUP"


def reply(base: dict, **extra) -> None:
    message = {"protocol_version": "m2w.1",
               "request_id": base.get("request_id"),
               "worker_generation": generation,
               "configuration_revision": revision,
               "worker_mode": mode,
               "worker_status": "OK", **extra}
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    request = json.loads(line)
    command = request.get("command")
    if command == "INIT":
        generation = request.get("worker_generation", "")
        revision = int(request.get("configuration_revision", 0))
        restore = request.get("restore_session_state", "REGIONS_CONFIGURED")
        mode = {"ARMED": "ARMED", "RECORDING": "RECORDING",
                "PAUSED": "PAUSED"}.get(restore, "SETUP")
        if behavior == "init_error":
            reply(request, worker_status="PROTOCOL_ERROR",
                  error="mock init failure")
            continue
        dpi = "unaware" if behavior == "bad_dpi" else "per_monitor_v2"
        reply(request, max_image_dimension=10000,
              available_languages=["en-US"],
              backends={"printwindow_clientonly": True,
                        "copyfromscreen": True},
              dpi_awareness=dpi,
              restore_session_state=restore,
              limits={"max_crop_png_bytes": 8388608,
                      "max_aggregate_crop_bytes": 67108864,
                      "max_full_frame_png_bytes": 67108864,
                      "max_json_line_bytes": 100663296})
        if behavior == "exit_after_init":
            sys.exit(0)
        continue
    if command == "CAPTURE" and behavior == "slow_capture":
        time.sleep(30)
    if behavior == "malformed" and command == "CAPTURE":
        sys.stdout.write("this is not json\n")
        sys.stdout.flush()
        continue
    if behavior == "stale_then_ok" and command == "CAPTURE":
        stale = {"protocol_version": "m2w.1", "request_id": "req-stale",
                 "worker_generation": generation,
                 "configuration_revision": revision,
                 "worker_mode": mode, "worker_status": "OK"}
        sys.stdout.write(json.dumps(stale) + "\n")
        sys.stdout.flush()
    if command in ("ARM",):
        mode = "ARMED"
    elif command == "RECORD_START":
        mode = "RECORDING"
    elif command == "PAUSE":
        mode = "PAUSED"
    elif command == "RESUME":
        mode = "RECORDING"
    elif command in ("STOP",):
        mode = "STOPPED"
    elif command == "PREVIEW":
        mode = "PREVIEWED"
    if command == "CAPTURE":
        frame_seq = request.get("frame_seq", 0)
        # capture_calls proves exactly one capture happened for this request
        # (M2-FR-042); the mock captures once per CAPTURE by construction.
        observations = []
        for region in request.get("regions", []):
            observations.append({
                "source_id": region["source_id"],
                "capture_status": "OK",
                "crop_content_status": "CONTENT_DETECTED",
                "ocr_status": "OK",
                "pixel_sha256": f"hash-{frame_seq}",
                "crop_w": region["rect"]["w"], "crop_h": region["rect"]["h"],
                "ocr_executed": True, "confirmation": "new_ocr",
                "raw_text": f"{frame_seq}.0", "raw_truncated": False,
                "raw_original_utf8_bytes": 3, "warning_codes": [],
                "ocr_ms": 1, "crop_png_b64": "UE5H"})
        reply(request, frame_seq=frame_seq,
              capture_utc="2026-07-18T00:00:00Z",
              window={"exists": True, "iconic": False, "client_w": 900,
                      "client_h": 300, "origin_x": 0, "origin_y": 0,
                      "dpi": 96},
              capture_status="OK",
              frame_content_status="CONTENT_DETECTED",
              cursor=None,
              capture_calls=1,
              timings={"capture_ms": 1, "ocr_ms_total": 1},
              observations=observations)
        continue
    if command == "SHUTDOWN":
        reply(request, worker_mode="STOPPED")
        sys.exit(0)
    reply(request)
