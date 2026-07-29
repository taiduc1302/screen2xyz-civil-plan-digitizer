"""Overnight QA end-to-end scenario matrix (sections 15-16): drives the
REAL LiveSessionController + REAL PowerShell worker + REAL Windows OCR
against image fixtures, a real Excel workbook, and the built-in synthetic
demo target, for 1/3/8-field complete workflows. Writes a JSON results
file; never asserts via unittest (this needs real subprocesses/timing and
is run manually during the overnight sprint, not as a CI gate)."""

from __future__ import annotations

import json
import sys
import tempfile
import time
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "tests_m2" / "fixtures"))

from image_fixtures import generate_all as generate_images  # noqa: E402
from excel_fixtures import generate_all as generate_excel  # noqa: E402
import excel_com  # noqa: E402
from scenario_runner import (close_window_wm_close, open_excel_fixture,  # noqa: E402
                             open_image_fixture, run_field_scenario)

from screen2xyz_m2 import demo as demo_mod  # noqa: E402
from screen2xyz_m2.controller import LiveSessionController  # noqa: E402
from screen2xyz_m2.models import SessionDefaults, new_source_id  # noqa: E402

IMAGE_SUBSET = ["01_top_left", "02_top_right", "03_center",
               "07_white_bg_dark_text", "08_dark_bg_light_text",
               "10_small_font", "11_large_font", "17_blank",
               "18_near_uniform_dark", "19_near_uniform_light",
               "20_malformed_number", "21_unicode_minus",
               "24_duplicate_values", "25_long_text"]

# Independent audit BLOCKER: "ok" previously meant only "the pipeline
# reached stop() without raising WorkerError" - it never compared the
# observed value to the fixture's declared truth, so a scenario whose
# region/content was miswired (or whose OCR simply misread the value)
# still reported ok=True. Every scenario is classified here as either
# NEGATIVE (the fixture's own name/expected text says no meaningful OCR
# value should come out - blank/near-uniform cases) or POSITIVE (a real
# value is expected), and matched accordingly - never just "didn't crash."
_NEGATIVE_MARKERS = ("blank field", "near-uniform", "ambiguous")


def _expected_value_token(expected: str) -> str:
    """Strip a fixture's trailing "(explanatory note)" annotation to get
    the bare value it actually expects OCR/parse to produce."""

    return expected.split(" (", 1)[0].strip()


def _matches_expected(expected: str, observed: dict | None) -> bool:
    if any(marker in expected for marker in _NEGATIVE_MARKERS):
        # A negative scenario: no meaningful value should have come out.
        return observed is None or observed.get("value_status") != "OK"
    if observed is None or observed.get("value_status") != "OK":
        return False
    token = _expected_value_token(expected)
    actual = str(observed.get("normalized_value") or "")
    if token == actual:
        return True
    try:
        return abs(float(token) - float(actual)) < 1e-6
    except (TypeError, ValueError):
        return False


def run_image_scenarios(results: dict) -> None:
    truth = generate_images(REPO_ROOT / ".lab_work/fixture_gallery/images")
    for name in IMAGE_SUBSET:
        info = truth[name]
        entry = {"expected": info["expected"]}
        try:
            fw = open_image_fixture(Path(info["path"]))
            scope = {"type": "window", "hwnd": fw.hwnd, "pid": fw.pid,
                     "title": "image fixture viewer"}
            with tempfile.TemporaryDirectory() as tmp:
                r = run_field_scenario(
                    scope=scope, regions=[tuple(info["region"])],
                    data_type=("text" if "long_text" in name else "number"),
                    ticks=1, run_parent=Path(tmp))
            fw.close()
            entry["pipeline_completed"] = r["ok"]
            entry["test_capture_status"] = r.get("test_capture_status")
            first_tick = (r.get("ticks") or [{}])[0]
            obs = list((first_tick.get("observations") or {}).values())
            entry["observed"] = obs[0] if obs else None
            entry["error"] = r.get("error")
            entry["ok"] = r["ok"] and _matches_expected(
                info["expected"], entry["observed"])
        except Exception as exc:  # noqa: BLE001 - record, never abort matrix
            entry["ok"] = False
            entry["pipeline_completed"] = False
            entry["error"] = f"{type(exc).__name__}: {exc}"
        results["images"][name] = entry
        print(f"[image] {name}: ok={entry.get('ok')} "
             f"expected={entry['expected']!r} "
             f"observed={(entry.get('observed') or {}).get('normalized_value')!r}")


def run_excel_scenario(results: dict) -> None:
    """B/G combined: opens the real installed Excel on the "simple
    coordinates" workbook, drives the real controller through a complete
    setup -> record -> observe chain, then updates a cell via the real
    running Excel instance's COM API mid-recording (§12.G "a safe
    mechanism that visibly updates selected synthetic values") and checks
    for a retained change - a genuine live-Excel change-detection proof,
    not a static single-frame check."""

    truth = generate_excel(REPO_ROOT / ".lab_work/fixture_gallery/excel")
    path = Path(truth["A_simple_coordinates"]["path"])
    entry: dict = {"expected": truth["A_simple_coordinates"]["expected"]}
    fw = None
    try:
        fw = open_excel_fixture(path, timeout=25.0)
        if fw is None:
            entry["ok"] = False
            entry["error"] = "Excel window did not appear within timeout"
            results["excel_available"] = False
            results["excel"] = entry
            print(f"[excel] SKIPPED: {entry['error']}")
            return
        results["excel_available"] = True
        time.sleep(1.5)  # let Excel finish painting before first capture
        scope = {"type": "window", "hwnd": fw.hwnd, "pid": fw.pid,
                 "title": "Excel"}
        # Independent audit finding: the original guess (0, 140, 300, 90)
        # landed on ribbon chrome ("Clipboard"/"Font" group labels), not
        # the grid - confirmed by capturing a real screenshot of this
        # machine's Excel window and measuring where row 1 actually
        # starts. This value is empirically verified (re-read "123.456
        # -78.9" correctly), but is still approximate for OTHER machines/
        # DPI/ribbon states - real region calibration always needs the
        # product's own interactive picker, never a hardcoded guess.
        region = (0, 300, 220, 90)
        env_backend = "auto"
        from screen2xyz_m2.models import SourceConfig
        from screen2xyz_m2.targets import environment_snapshot
        with tempfile.TemporaryDirectory() as tmp:
            source = SourceConfig(
                source_id=new_source_id(), display_name="grid",
                semantic_role="none", data_type="text", rect=region)
            controller = LiveSessionController(
                scope=scope, backend=env_backend, sources=[source],
                defaults=SessionDefaults(interval_ms=200),
                environment_snapshot=environment_snapshot(scope,
                                                          env_backend),
                run_parent=Path(tmp))
            controller.machine.select_target()
            controller.machine.sources_configured()
            controller.ensure_worker()
            entry["test_capture_status"] = controller.test_capture() \
                .get("capture_status")
            controller.preview()
            controller.confirm_preview_and_arm()
            controller.start_recording()
            tr1 = controller.tick()
            obs1 = list(tr1.observations.values())
            entry["observed_before_change"] = (
                obs1[0].to_json() if obs1 else None)
            excel_com.set_cell("B2", "999.99")
            time.sleep(1.0)
            retained = 0
            for _ in range(5):
                tr = controller.tick()
                if tr.event is not None:
                    retained += 1
                time.sleep(0.3)
            summary = controller.stop()
            entry["retained_after_com_change"] = retained
            entry["final_csv_row_count"] = summary.get(
                "final_csv_row_count")
            # Independent audit BLOCKER: this used to be unconditional
            # (entry["ok"] = True right after stop(), regardless of
            # whether anything was actually detected) - the recorded run
            # that produced retained_after_com_change=0 and
            # final_csv_row_count=0 was still reported "ok": true. Real
            # success requires the pre-change read to have been a genuine
            # OK value AND the COM-driven edit to have produced at least
            # one retained change event.
            before_ok = (entry.get("observed_before_change") or {}).get(
                "value_status") == "OK"
            entry["ok"] = before_ok and retained >= 1
    except Exception as exc:  # noqa: BLE001
        entry["ok"] = False
        entry["error"] = f"{type(exc).__name__}: {exc}"
        results.setdefault("excel_available", None)
    finally:
        if fw is not None:
            fw.close()
    results["excel"] = entry
    print(f"[excel] ok={entry.get('ok')} "
         f"retained_after_com_change={entry.get('retained_after_com_change')} "
         f"error={entry.get('error')}")


def run_demo_field_count_workflow(field_count: int, results: dict) -> None:
    """A COMPLETE workflow (select -> test capture -> N fields -> preview ->
    arm -> start -> change value -> observe -> pause -> resume -> stop ->
    finalize -> verify final CSV) against the real demo target, for
    1/3/8 fields."""

    entry: dict = {}
    session = demo_mod.DemoSession()
    try:
        session.set_case("changing")
        names = ["X", "Y", "Z"] + [f"F{i}" for i in range(4, field_count + 1)]
        names = names[:field_count]
        rects = []
        ready_fields = session.ready["fields"]
        base_names = list(ready_fields.keys())
        for i in range(field_count):
            src_name = base_names[i % len(base_names)]
            rects.append(tuple(ready_fields[src_name]))
        scope = {"type": "window", "hwnd": session.ready["hwnd"],
                 "pid": session.ready["pid"], "title": "demo target"}
        env_backend = "auto"
        with tempfile.TemporaryDirectory() as tmp:
            from screen2xyz_m2.targets import environment_snapshot
            sources = [
                __import__("screen2xyz_m2.models",
                           fromlist=["SourceConfig"]).SourceConfig(
                    source_id=new_source_id(), display_name=names[i],
                    semantic_role="none", data_type="number",
                    rect=rects[i])
                for i in range(field_count)]
            controller = LiveSessionController(
                scope=scope, backend=env_backend, sources=sources,
                defaults=SessionDefaults(interval_ms=150),
                environment_snapshot=environment_snapshot(scope,
                                                          env_backend),
                run_parent=Path(tmp))
            controller.machine.select_target()
            controller.machine.sources_configured()
            controller.ensure_worker()
            entry["test_capture_status"] = controller.test_capture() \
                .get("capture_status")
            controller.preview()
            controller.confirm_preview_and_arm()
            controller.start_recording()
            session.auto_change(True)
            retained = 0
            for _ in range(20):
                tr = controller.tick()
                if tr.event is not None:
                    retained += 1
                time.sleep(0.12)
            controller.user_pause()
            controller.user_resume()
            for _ in range(5):
                controller.tick()
                time.sleep(0.12)
            summary = controller.stop()
            entry["retained_events_during_run"] = retained
            entry["final_csv_row_count"] = summary.get(
                "final_csv_row_count")
            entry["final_csv_row_count_verified"] = summary.get(
                "final_csv_row_count_verified")
            # Independent audit finding: this was unconditional. Real
            # success requires at least one genuine retained change AND
            # the final CSV row count verified against the journal - not
            # merely "stop() didn't raise."
            entry["ok"] = (retained > 0
                           and entry["final_csv_row_count_verified"] is True)
    except Exception as exc:  # noqa: BLE001
        entry["ok"] = False
        entry["error"] = f"{type(exc).__name__}: {exc}"
        entry["traceback"] = traceback.format_exc()[-1500:]
    finally:
        session.quit()
    results["demo_workflows"][f"{field_count}_field"] = entry
    print(f"[demo {field_count}-field] ok={entry.get('ok')} "
         f"retained={entry.get('retained_events_during_run')} "
         f"final_csv_rows={entry.get('final_csv_row_count')} "
         f"verified={entry.get('final_csv_row_count_verified')} "
         f"error={entry.get('error')}")


def main() -> None:
    results: dict = {"images": {}, "demo_workflows": {}}
    run_image_scenarios(results)
    run_excel_scenario(results)
    for count in (1, 3, 8):
        run_demo_field_count_workflow(count, results)
    out = REPO_ROOT / ".lab_work/overnight_qa/scenario_matrix_results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, default=str),
                   encoding="utf-8")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
