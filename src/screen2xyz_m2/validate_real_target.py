"""Consolidated owner-run real-target validation (G-E-REAL) - §5 rebuild.

Replaces the old three-horizontal-band, PrintWindow-only, "COMPLETED means
success" stub. This is a guided Tk wizard built on the SAME production UI
components and controller path as the normal application
(`screen2xyz_m2.ui.app.M2App`) - target selection, Test capture, the real
region-selection picker, the real preview-confirmation gate, and the real
recording dashboard are all reused unmodified via subclassing, not
reimplemented. It never fabricates a PASS: every technical claim is
verified against real controller/journal state, and PASS additionally
requires four explicit owner confirmations. Result is exactly one of PASS,
FAIL, or BLOCKED. The written report is sanitized: no screenshots, no
window title, no raw target identity.
"""

from __future__ import annotations

import json
import tkinter as tk
from datetime import datetime, timezone
from tkinter import messagebox, ttk
from typing import Any

from .dpi import enable_pmv2
from .paths import run_root
from .ui.app import M2App

REQUIRED_TECHNICAL_CHECKS = (
    "captures_occurred",
    "ocr_meaningful",
    "every_enabled_source_meaningful",
    "change_detected",
    "journal_event_persisted",
    "live_csv_snapshot_updated",
    "final_csv_generated",
    "final_csv_row_count_matches_journal",
    "crop_artifacts_match_policy",
    "no_orphan_worker",
)

REQUIRED_OWNER_CONFIRMATIONS = (
    "crops_aligned",
    "values_corresponded_to_real_target",
    "recording_ui_understandable",
    "exported_row_meaningful",
)


def observation_is_meaningful(*, data_type: str, ocr_status: str,
                              value_status: str, normalized_value: object,
                              raw_text: str) -> bool:
    """§12: a MEANINGFUL observation is NOT merely non-empty OCR text.

    OCR must have actually succeeded (ocr_status == OK) AND the parsed value
    must be acceptable (value_status == OK). For a numeric source a valid
    normalized number is required; for text/auto a non-empty normalized (or
    raw) string. This rejects the noise a wrong/blank region produces - e.g.
    a border OCR'd to '|'/'::' parses to NO_NUMBER/MALFORMED (value_status !=
    OK) and is not meaningful - so garbage OCR can never satisfy
    ocr_meaningful. (A wrong-but-valid misread that still parses is caught by
    the mandatory owner confirmations, not this check.)"""

    if ocr_status != "OK" or value_status != "OK":
        return False
    if data_type == "number":
        return normalized_value is not None and str(normalized_value) != ""
    text = (str(normalized_value) if normalized_value is not None
            else (raw_text or ""))
    return bool(text.strip())


def compute_verdict(technical: dict[str, bool],
                    owner_confirmations: dict[str, bool],
                    blocked_reason: str | None = None) -> str:
    """PASS requires every named technical check AND every named owner
    confirmation to be True - no partial credit, no substitute status like
    the old "COMPLETED". BLOCKED is reserved for a declared environmental
    limitation and short-circuits before any check is inspected. Missing
    required keys raise rather than silently defaulting to a pass-friendly
    value, so a caller cannot accidentally omit a gate."""

    if blocked_reason:
        return "BLOCKED"
    missing_tech = [k for k in REQUIRED_TECHNICAL_CHECKS if k not in technical]
    if missing_tech:
        raise ValueError(f"missing technical checks: {missing_tech}")
    missing_conf = [k for k in REQUIRED_OWNER_CONFIRMATIONS
                    if k not in owner_confirmations]
    if missing_conf:
        raise ValueError(f"missing owner confirmations: {missing_conf}")
    if all(technical[k] for k in REQUIRED_TECHNICAL_CHECKS) and \
            all(owner_confirmations[k] for k in REQUIRED_OWNER_CONFIRMATIONS):
        return "PASS"
    return "FAIL"


def build_report(*, attempted_backends: list[str],
                 selected_backend: str | None,
                 target_w: int | None, target_h: int | None,
                 target_dpi: int | None, source_count: int,
                 per_source_status: dict[str, str],
                 capture_counts: dict[str, int],
                 ocr_counts: dict[str, int],
                 journal_event_count: int, live_csv_row_count: int,
                 final_csv_row_count: int,
                 owner_confirmations: dict[str, bool],
                 controls_exercised: list[str],
                 pause_resume_stop_results: dict[str, Any],
                 orphan_process_check: str,
                 limitations: list[str],
                 final_result: str) -> dict[str, Any]:
    """Assembles the sanitized JSON report. Structurally cannot include a
    screenshot or window title - no parameter accepts one."""

    return {
        "schema_version": "screen2xyz.m2real.2",
        "gate": "G-E-REAL",
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "target_identity_included": False,
        "attempted_backends": list(attempted_backends),
        "selected_backend": selected_backend,
        "target_dimensions": {"client_w": target_w, "client_h": target_h,
                              "dpi": target_dpi},
        "source_count": source_count,
        "per_source_status": per_source_status,
        "capture_counts": capture_counts,
        "ocr_counts": ocr_counts,
        "journal_event_count": journal_event_count,
        "live_csv_row_count": live_csv_row_count,
        "final_csv_row_count": final_csv_row_count,
        "owner_confirmations": owner_confirmations,
        "controls_exercised": list(controls_exercised),
        "pause_resume_stop_results": pause_resume_stop_results,
        "orphan_process_check": orphan_process_check,
        "limitations": list(limitations),
        "output_classification":
            "Conceptual and preliminary estimating data only.",
        "final_result": final_result,
    }


class ValidationApp(M2App):
    """A thin, real wizard around the production UI: adds a validation
    banner, a consent gate, a small always-on-top prompt during recording
    ("I changed a target value"), and a post-Stop verdict computation -
    every setup/picker/preview/recording screen in between is exactly the
    real M2App, unmodified."""

    _welcome_shown_this_process = True  # keep the validator flow uncluttered

    def __init__(self) -> None:
        self._val: dict[str, Any] = {
            "capture_count": 0, "ok_capture_count": 0,
            "retained_change_count": 0, "owner_marked_change": False,
            "controls_exercised": [], "blocked_reason": None,
            "pause_resume_stop": {},
            # source_id -> {"data_type","meaningful","observations",
            #               "capture","ocr","parse","value"} counts
            "per_source": {},
        }
        self.final_verdict: str | None = None
        super().__init__()
        self.root.title(
            "Screen2XYZ M2-Live — Real-target validation (G-E-REAL)")

    # -- setup screen: banner + consent + manual BLOCKED escape ------------

    def _build_setup(self) -> None:
        super()._build_setup()
        children = self.root.winfo_children()
        outer = children[0] if children else None
        banner = tk.Frame(self.root, bg="#7a1f1f")
        if outer is not None:
            banner.pack(fill="x", side="top", before=outer)
        else:
            banner.pack(fill="x", side="top")
        tk.Label(banner, text="REAL-TARGET VALIDATION (G-E-REAL) — select "
                             "only authorized, non-confidential content",
                bg="#7a1f1f", fg="white", font=("Segoe UI", 11, "bold"),
                pady=4).pack()
        ttk.Button(banner, text="Mark as BLOCKED (capture unsupported for "
                                "this target)",
                  command=self._mark_blocked_manually).pack(pady=(0, 4))
        if not self._val.get("consent_given"):
            self.root.after(50, self._show_consent_gate)

    def _show_consent_gate(self) -> None:
        ok = messagebox.askyesno(
            "Authorization required",
            "You are about to select and briefly record from a REAL "
            "application window.\n\nDoes the target you are about to "
            "select contain ONLY authorized, non-confidential content "
            "that you are permitted to capture and process locally?",
            parent=self.root)
        self._val["consent_given"] = ok
        if not ok:
            self._val["blocked_reason"] = (
                "owner did not confirm authorized/non-confidential content")
            self._finish_blocked()

    def _mark_blocked_manually(self) -> None:
        if messagebox.askyesno(
                "Confirm BLOCKED",
                "Mark this validation as BLOCKED because capture is not "
                "supported for this target (e.g. protected content, no "
                "usable backend, or OCR unavailable)?", parent=self.root):
            self._val["blocked_reason"] = (
                "owner marked capture/backend/OCR unsupported for this "
                "target")
            self._finish_blocked()

    # -- recording screen: a small satellite prompt (mini-controller-like) -

    def _build_recording(self) -> None:
        super()._build_recording()
        self._open_validator_overlay()

    def _open_validator_overlay(self) -> None:
        overlay = tk.Toplevel(self.root)
        overlay.title("Validation controls")
        overlay.attributes("-topmost", True)
        overlay.geometry("+20+20")
        frame = tk.Frame(overlay, bg="#222222", padx=8, pady=8)
        frame.pack()
        tk.Label(frame, text="Now change a value in the real target,\n"
                            "then click below.", bg="#222222", fg="white",
                font=("Segoe UI", 9)).pack()
        tk.Button(frame, text="I changed a target value just now",
                 command=lambda: self._mark_owner_change(overlay)).pack(
            pady=4)
        row = tk.Frame(frame, bg="#222222")
        row.pack()
        tk.Button(row, text="Pause", command=self._val_pause).pack(
            side="left", padx=2)
        tk.Button(row, text="Resume", command=self._val_resume).pack(
            side="left", padx=2)
        self._val_overlay = overlay

    def _mark_owner_change(self, overlay: tk.Toplevel) -> None:
        self._val["owner_marked_change"] = True
        self._val["controls_exercised"].append("owner_marked_value_change")
        for widget in overlay.winfo_children():
            for child in widget.winfo_children():
                if isinstance(child, tk.Button) and \
                        "I changed" in child.cget("text"):
                    child.configure(text="✓ change marked", state="disabled")

    def _val_pause(self) -> None:
        self._val["controls_exercised"].append("pause")
        self._pause()

    def _val_resume(self) -> None:
        self._val["controls_exercised"].append("resume")
        self._resume()

    def _render_tick(self, result) -> None:
        super()._render_tick(result)
        self._val["capture_count"] = self._feed_counters["captures"]
        # §11/§12: count only frames that actually captured OK, and only
        # observations that are genuinely meaningful (real parse + OK value
        # status) per source - not every rendered tick or any non-empty OCR.
        frame = result.frame or {}
        if frame.get("capture_status") == "OK":
            self._val["ok_capture_count"] += 1
        if result.event is not None and \
                result.event.get("event_status") == "RETAINED_CHANGE":
            self._val["retained_change_count"] += 1
        types = {s.source_id: s.data_type for s in self.sources}
        for sid, obs in result.observations.items():
            ps = self._val["per_source"].setdefault(sid, {
                "data_type": types.get(sid, "number"), "meaningful": 0,
                "observations": 0, "ok_value": 0})
            ps["observations"] += 1
            if obs.value_status == "OK":
                ps["ok_value"] += 1
            if observation_is_meaningful(
                    data_type=types.get(sid, "number"),
                    ocr_status=obs.ocr_status, value_status=obs.value_status,
                    normalized_value=obs.normalized_value,
                    raw_text=obs.raw_text or ""):
                ps["meaningful"] += 1

    # -- stop: compute the real verdict, ask for owner confirmations -------

    def _stop(self) -> None:
        if self.scheduler:
            self.scheduler.stop()
        summary = self.controller.stop()
        self._close_mini()
        if getattr(self, "_val_overlay", None) is not None:
            self._val_overlay.destroy()
            self._val_overlay = None
        self._val["controls_exercised"].append("stop")
        self._build_finalized(summary)
        self._finish_validation(summary)

    def _ask_owner_confirmations(self) -> dict[str, bool]:
        questions = {
            "crops_aligned": "Did every field's crop/region look correctly "
                            "aligned with its intended value?",
            "values_corresponded_to_real_target":
                "Did the displayed/recorded values correspond to what the "
                "real target actually showed?",
            "recording_ui_understandable":
                "Was the recording screen (field cards, live feed, "
                "persistence states) understandable?",
            "exported_row_meaningful":
                "Was at least one exported row meaningful and usable?",
        }
        return {key: messagebox.askyesno("Owner confirmation", text,
                                        parent=self.root)
                for key, text in questions.items()}

    def _finish_validation(self, summary: dict[str, Any]) -> None:
        journal_event_count = summary.get("event_count", 0)
        final_csv_row_count = summary.get("final_csv_row_count", 0)
        live_csv_row_count = summary.get("live_csv_snapshot_row_count", 0)
        warnings = summary.get("warnings") or []
        crop_ok = not any(
            w.startswith("MISSING_CROP") or w.startswith("CROP_HASH_MISMATCH")
            for w in warnings)
        no_orphan = self.controller.worker is None
        enabled = [s for s in self.sources if s.enabled]
        # §12: every enabled source must have produced at least one genuinely
        # meaningful observation (real parse + OK value status), not merely
        # non-empty OCR text somewhere in the session.
        every_source_ok = bool(enabled) and all(
            self._val["per_source"].get(s.source_id, {}).get("meaningful", 0)
            > 0 for s in enabled)
        any_source_meaningful = any(
            ps.get("meaningful", 0) > 0
            for ps in self._val["per_source"].values())
        technical = {
            "captures_occurred": self._val["ok_capture_count"] > 0,
            "ocr_meaningful": any_source_meaningful,
            "every_enabled_source_meaningful": every_source_ok,
            "change_detected": (self._val["retained_change_count"] > 0
                                and self._val["owner_marked_change"]),
            "journal_event_persisted": journal_event_count > 0,
            "live_csv_snapshot_updated": live_csv_row_count > 0,
            "final_csv_generated": final_csv_row_count > 0,
            "final_csv_row_count_matches_journal":
                final_csv_row_count == journal_event_count,
            "crop_artifacts_match_policy": crop_ok,
            "no_orphan_worker": no_orphan,
        }
        owner_confirmations = self._ask_owner_confirmations()
        verdict = compute_verdict(technical, owner_confirmations,
                                  self._val.get("blocked_reason"))
        window = self.controller.environment_snapshot.get("window") or {}
        report = build_report(
            attempted_backends=[p.get("name") for p in
                                (self.controller.last_backend_probe or [])],
            selected_backend=self.controller.effective_backend,
            target_w=window.get("client_w"), target_h=window.get("client_h"),
            target_dpi=window.get("dpi"), source_count=len(self.sources),
            per_source_status={
                s.source_id: {
                    "region": ("region_confirmed" if s.rect[2] > 0
                              and s.rect[3] > 0 else "no_region"),
                    "meaningful_observations":
                        self._val["per_source"].get(
                            s.source_id, {}).get("meaningful", 0),
                    "ok_value_observations":
                        self._val["per_source"].get(
                            s.source_id, {}).get("ok_value", 0),
                    "total_observations":
                        self._val["per_source"].get(
                            s.source_id, {}).get("observations", 0),
                }
                for s in self.sources},
            capture_counts={"total": self._val["capture_count"],
                           "ok": self._val["ok_capture_count"]},
            ocr_counts={"retained_changes":
                       self._val["retained_change_count"],
                       "meaningful_sources": sum(
                           1 for ps in self._val["per_source"].values()
                           if ps.get("meaningful", 0) > 0)},
            journal_event_count=journal_event_count,
            live_csv_row_count=live_csv_row_count,
            final_csv_row_count=final_csv_row_count,
            owner_confirmations=owner_confirmations,
            controls_exercised=self._val["controls_exercised"],
            pause_resume_stop_results={
                "pause_used": "pause" in self._val["controls_exercised"],
                "resume_used": "resume" in self._val["controls_exercised"],
                "stop_used": "stop" in self._val["controls_exercised"]},
            orphan_process_check=("none_found" if no_orphan
                                 else "ORPHAN_SUSPECTED"),
            limitations=[
                "This report reflects only the target and session just "
                "recorded, not general real-target support.",
                "OCR/backend behavior is verified only against this "
                "specific target this run."],
            final_result=verdict)
        self._write_report(report)
        self.final_verdict = verdict
        self._show_result(report)

    def _finish_blocked(self) -> None:
        verdict = compute_verdict({}, {}, self._val["blocked_reason"])
        report = build_report(
            attempted_backends=[], selected_backend=None, target_w=None,
            target_h=None, target_dpi=None, source_count=0,
            per_source_status={}, capture_counts={}, ocr_counts={},
            journal_event_count=0, live_csv_row_count=0,
            final_csv_row_count=0, owner_confirmations={},
            controls_exercised=self._val["controls_exercised"],
            pause_resume_stop_results={}, orphan_process_check="not_applicable",
            limitations=[self._val["blocked_reason"]], final_result=verdict)
        self._write_report(report)
        self.final_verdict = verdict
        messagebox.showinfo(
            "Validation blocked",
            f"{self._val['blocked_reason']}\n\nG-E-REAL remains pending.",
            parent=self.root)
        self.root.after(200, self.root.destroy)

    def _write_report(self, report: dict[str, Any]) -> None:
        out_dir = run_root() / "real_target_validation"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_path = out_dir / f"g_e_real_{stamp}.json"
        out_path.write_text(json.dumps(report, indent=2, sort_keys=True),
                            encoding="utf-8")
        self._val["report_path"] = str(out_path)

    def _show_result(self, report: dict[str, Any]) -> None:
        messagebox.showinfo(
            f"Validation result: {report['final_result']}",
            f"Result: {report['final_result']}\n\n"
            f"Report written to:\n{self._val['report_path']}\n\n"
            "Share only this JSON file - never a screenshot.",
            parent=self.root)


def run_validation() -> int:
    """Launches the guided Tk wizard and returns 0 (PASS), 1 (FAIL), or 2
    (BLOCKED). Never prints or returns a screenshot or window title."""

    enable_pmv2()
    app = ValidationApp()
    app.run()
    return {"PASS": 0, "BLOCKED": 2}.get(app.final_verdict or "FAIL", 1)
